import Foundation
import CoreML
import CoreMLLLM

/// Reads Core ML's *anticipated* preferred-device map from an already compiled
/// model chunk. This is not an execution trace or utilization measurement.
enum Qwen35ComputePlanInspector {
    @available(iOS 17.4, *)
    static func inspect(policy: String) async throws -> String {
        guard let cached = ModelDownloader.shared.localModelURL(
            for: ModelDownloader.ModelInfo.qwen35_08b) else {
            throw NSError(domain: "NANOComputePlan", code: 1,
                userInfo: [NSLocalizedDescriptionKey:
                    "Qwen model is not cached. Load it before inspecting the plan."])
        }
        let dir = cached.deletingLastPathComponent()
        let modelPath = dir.appendingPathComponent(
            "qwen3_5_0_8b_decode_chunks_mlkv/chunk_d.mlpackage")
        guard FileManager.default.fileExists(atPath: modelPath.path) else {
            throw NSError(domain: "NANOComputePlan", code: 2,
                userInfo: [NSLocalizedDescriptionKey: "Cached Qwen chunk_d missing."])
        }
        // The generator's load() compiles .mlpackage files into tmp/*.mlmodelc.
        // Inspect the already-compiled cache; never recompile or redownload here.
        let temp = FileManager.default.temporaryDirectory
        let files = try FileManager.default.contentsOfDirectory(
            at: temp, includingPropertiesForKeys: nil)
        let exact = files.first { $0.lastPathComponent == "chunk_d.mlmodelc" }
        let alternate = files.first {
            $0.lastPathComponent.hasPrefix("chunk_d_") &&
            $0.lastPathComponent.hasSuffix(".mlmodelc")
        }
        guard let compiledModel = exact ?? alternate else {
            throw NSError(domain: "NANOComputePlan", code: 3,
                userInfo: [NSLocalizedDescriptionKey:
                    "No compiled chunk_d cache found. Run Load Core ML Model first."])
        }

        let cfg = MLModelConfiguration()
        cfg.computeUnits = policy.contains("GPU fallback") ? .cpuAndGPU : .cpuAndNeuralEngine
        let plan = try await MLComputePlan.load(
            contentsOf: compiledModel, configuration: cfg)
        guard case let .program(program) = plan.modelStructure,
              let main = program.functions["main"] else {
            throw NSError(domain: "NANOComputePlan", code: 4,
                userInfo: [NSLocalizedDescriptionKey:
                    "Core ML did not return an ML Program main block."])
        }
        var cpu = 0, gpu = 0, ane = 0, unknown = 0
        let operations = main.block.operations
        for operation in operations {
            guard let preferred = plan.deviceUsage(for: operation)?.preferred else {
                unknown += 1
                continue
            }
            switch preferred {
            case .cpu: cpu += 1
            case .gpu: gpu += 1
            case .neuralEngine: ane += 1
            @unknown default: unknown += 1
            }
        }
        return "Core ML chunk_d main block: \(operations.count) operations. " +
            "Anticipated preferred: ANE \(ane), GPU \(gpu), CPU \(cpu), " +
            "unknown \(unknown). Config: \(policy). " +
            "This is not a measured ANE execution trace."
    }


    /// Inspect each Qwen MLKV chunk independently: weights are relative to each
    /// chunk, NOT additive as a whole-model ANE-time or energy percentage.
    @available(iOS 17.4, *)
    static func inspectAllChunks(policy: String) async throws -> String {
        guard let cached = ModelDownloader.shared.localModelURL(
            for: ModelDownloader.ModelInfo.qwen35_08b) else {
            throw NSError(domain: "NANOComputePlan", code: 10,
                userInfo: [NSLocalizedDescriptionKey: "Load the cached Qwen model first."])
        }
        let directory = cached.deletingLastPathComponent()
            .appendingPathComponent("qwen3_5_0_8b_decode_chunks_mlkv")
        let temporary = FileManager.default.temporaryDirectory
        let entries = try FileManager.default.contentsOfDirectory(
            at: temporary, includingPropertiesForKeys: nil)
        let cfg = MLModelConfiguration()
        cfg.computeUnits = policy.contains("GPU fallback") ? .cpuAndGPU : .cpuAndNeuralEngine
        var lines = ["Qwen3.5 per-chunk plan | compute policy: \(policy)"]
        for letter in ["a", "b", "c", "d"] {
            let source = directory.appendingPathComponent("chunk_\(letter).mlpackage")
            guard FileManager.default.fileExists(atPath: source.path) else {
                throw NSError(domain: "NANOComputePlan", code: 11,
                    userInfo: [NSLocalizedDescriptionKey: "Cached chunk \(letter) is missing."])
            }
            let exactName = "chunk_\(letter).mlmodelc"
            let exact = entries.first { $0.lastPathComponent == exactName }
            let alternatives = entries.filter {
                $0.lastPathComponent.hasPrefix("chunk_\(letter)_") &&
                $0.lastPathComponent.hasSuffix(".mlmodelc")
            }
            // Never arbitrarily choose among multiple stale alternative builds.
            if exact == nil && alternatives.count > 1 {
                throw NSError(domain: "NANOComputePlan", code: 12,
                    userInfo: [NSLocalizedDescriptionKey:
                        "Ambiguous compiled cache for chunk \(letter); reload the model first."])
            }
            guard let compiled = exact ?? alternatives.first else {
                throw NSError(domain: "NANOComputePlan", code: 13,
                    userInfo: [NSLocalizedDescriptionKey:
                        "No compiled chunk \(letter) available. Load the model first."])
            }
            let plan = try await MLComputePlan.load(
                contentsOf: compiled, configuration: cfg)
            guard case let .program(program) = plan.modelStructure,
                  let main = program.functions["main"] else {
                throw NSError(domain: "NANOComputePlan", code: 14,
                    userInfo: [NSLocalizedDescriptionKey:
                        "Chunk \(letter) has no ML Program main block."])
            }
            var ane = 0, gpu = 0, cpu = 0, unclassified = 0
            var aneCost = 0.0, gpuCost = 0.0, cpuCost = 0.0, unknownCost = 0.0
            var estimatedCostUnavailable = 0
            let operations = main.block.operations
            for operation in operations {
                let estimatedWeight = plan.estimatedCost(of: operation)?.weight
                let weight: Double?
                if let estimatedWeight, estimatedWeight.isFinite,
                   estimatedWeight >= 0 {
                    weight = estimatedWeight
                } else {
                    weight = nil
                    estimatedCostUnavailable += 1
                }
                switch plan.deviceUsage(for: operation)?.preferred {
                case .some(.neuralEngine):
                    ane += 1
                    if let weight { aneCost += weight }
                case .some(.gpu):
                    gpu += 1
                    if let weight { gpuCost += weight }
                case .some(.cpu):
                    cpu += 1
                    if let weight { cpuCost += weight }
                case .none, .some(_):
                    unclassified += 1
                    if let weight { unknownCost += weight }
                }
            }
            let countText = "chunk_\(letter): \(operations.count) main-block ops | preferred ANE \(ane), GPU \(gpu), CPU \(cpu), unclassified \(unclassified)."
            let costs = String(format:
                "ANE relative cost %.4f, GPU %.4f, CPU %.4f, unclassified %.4f; cost unavailable for %d ops.",
                aneCost, gpuCost, cpuCost, unknownCost, estimatedCostUnavailable)
            lines.append(countText + " " + costs)
        }
        lines.append("Per-chunk cost weights cannot be summed into a whole-model share.")
        lines.append("Preferred device and relative cost are anticipated, not a measured ANE execution trace.")
        return lines.joined(separator: "\n")
    }
}
