import Foundation
import CoreMLLLM
import Tokenizers

/// Qwen3.5 uses hybrid SSM/attention MLState chunks, NOT the Gemma-style
/// model_config.json runtime behind CoreMLLLM.load(repo:).
/// No network activity occurs until the user explicitly taps Load.
@MainActor
final class Qwen35ModelAdapter {
    private let generator: Qwen35MLKVGenerator
    private let tokenizer: any Tokenizer
    let backendDescription: String

    private init(generator: Qwen35MLKVGenerator, tokenizer: any Tokenizer,
                 backendDescription: String) {
        self.generator = generator
        self.tokenizer = tokenizer
        self.backendDescription = backendDescription
    }

    static func load() async throws -> Qwen35ModelAdapter {
        let info = ModelDownloader.ModelInfo.qwen35_08b
        let downloader = ModelDownloader.shared
        // Reuse the existing phone cache when the earlier generic loader
        // already downloaded Qwen; otherwise download ONLY on button tap.
        let chunksURL: URL
        if let cached = downloader.localModelURL(for: info) {
            chunksURL = cached
        } else {
            chunksURL = try await downloader.download(info)
        }
        let folder = chunksURL.deletingLastPathComponent()
        let expected = folder.appendingPathComponent(
            "qwen3_5_0_8b_decode_chunks_mlkv/embed_weight.bin")
        guard FileManager.default.fileExists(atPath: expected.path) else {
            throw NSError(domain: "NanoANEBridge", code: 1,
                userInfo: [NSLocalizedDescriptionKey:
                    "Qwen MLKV chunk bundle incomplete; check download and retry."])
        }

        let tokenizer = try await AutoTokenizer.from(pretrained: "Qwen/Qwen3.5-0.8B")
        let generator = Qwen35MLKVGenerator(cfg: .default0_8B)
        generator.setModelFolder(folder)
        do {
            try await generator.load()
            return Qwen35ModelAdapter(generator: generator, tokenizer: tokenizer,
                                      backendDescription: "ANE-preferred compute units")
        } catch {
            let primary = error as NSError
            // Core ML -14 can indicate an execution-plan compiler failure.
            // Retry already-cached weights on CPU/GPU; do not redownload.
            guard primary.code == -14
                    || primary.localizedDescription.contains("error code: -14") else {
                throw error
            }
            generator.setComputeUnits(.cpuAndGPU)
            do {
                try await generator.load()
                return Qwen35ModelAdapter(generator: generator, tokenizer: tokenizer,
                                          backendDescription: "CPU/GPU fallback")
            } catch {
                throw NSError(domain: "NanoANEBridge", code: 14,
                    userInfo: [NSLocalizedDescriptionKey:
                        "ANE plan error -14; CPU/GPU fallback also failed: \(error.localizedDescription)"])
            }
        }
    }

    func generate(_ prompt: String, maxTokens: Int) async throws -> String {
        let (text, _) = try await generateMeasured(prompt, maxTokens: maxTokens)
        return text
    }

    func generateMeasured(_ prompt: String, maxTokens: Int) async throws -> (String, Qwen35InferenceMetrics) {
        let started = DispatchTime.now().uptimeNanoseconds
        let messages: [[String: Any]] = [["role": "user", "content": prompt]]
        let inputTokens = (try? tokenizer.applyChatTemplate(messages: messages))
            ?? tokenizer.encode(text:
                "<|im_start|>user\n\(prompt)<|im_end|>\n<|im_start|>assistant\n")
        let bounded = min(max(maxTokens, 1), 512)
        guard !inputTokens.isEmpty, inputTokens.count + bounded < 2048 else {
            throw NSError(domain: "NanoANEBridge", code: 2,
                userInfo: [NSLocalizedDescriptionKey:
                    "Prompt exceeds the 2048-token Qwen MLKV context."])
        }
        var eos: Set<Int32> = [248044, 248045, 248046]
        if let tokenId = tokenizer.eosTokenId { eos.insert(Int32(tokenId)) }
        let outputIds = try await generator.generate(
            inputIds: inputTokens.map(Int32.init),
            maxNewTokens: bounded,
            temperature: 0,
            topP: 1.0,
            repetitionPenalty: 1.1,
            eosTokenIds: eos)
        let cleanIds = outputIds.filter { !eos.contains($0) }
        let elapsedNs = DispatchTime.now().uptimeNanoseconds - started
        let report = Qwen35InferenceMetrics(
            prefillMs: generator.prefillMs,
            averageDecodeMs: generator.decodeMsAvg,
            generatorTokensPerSecond: generator.tokensPerSecond,
            elapsedMs: Double(elapsedNs) / 1_000_000.0,
            outputTokens: cleanIds.count,
            backendDescription: backendDescription)
        return (tokenizer.decode(tokens: cleanIds.map(Int.init)), report)
    }
}

struct Qwen35InferenceMetrics: Sendable {
    let prefillMs: Double
    let averageDecodeMs: Double
    let generatorTokensPerSecond: Double
    let elapsedMs: Double
    let outputTokens: Int
    let backendDescription: String
}
