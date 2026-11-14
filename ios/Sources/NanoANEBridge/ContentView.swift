import SwiftUI
import UIKit
import CoreMLLLM
import UniformTypeIdentifiers

/// The ANE-oriented Core ML model is separate from the user's abliterated
/// GGUF model, which remains available through the existing AI Chat server.
@MainActor
final class NanoModelSession: ObservableObject {
    @Published var isWorking = false
    @Published var isLoaded = false
    @Published var status = "No Core ML model loaded"
    @Published var output = ""
    @Published var benchmarkStatus = "Not benchmarked"
    @Published var threeRunStatus = "Three-run benchmark not started"
    @Published var computePlanStatus = "Compute plan not inspected"
    @Published var allPlanStatus = "All four compute plans not inspected"
    @Published var backendPolicy = ""
    private var generateAnswer: ((String, Int) async throws -> String)?
    private var measureAnswer: ((String, Int) async throws -> (String, Qwen35InferenceMetrics))?

    func load() {
        guard !isWorking, !isLoaded else { return }
        isWorking = true
        status = "Loading Qwen3.5 0.8B Core ML. Initial load may download ~1.2 GB."
        Task {
            defer { isWorking = false }
            do {
                // This ONLY runs when the user taps Load. No startup download.
                let llm = try await Qwen35ModelAdapter.load()
                generateAnswer = { input, count in try await llm.generate(input, maxTokens: count) }
                measureAnswer = { input, count in try await llm.generateMeasured(input, maxTokens: count) }
                isLoaded = true
                backendPolicy = llm.backendDescription
                status = "Core ML model loaded (\(llm.backendDescription)); actual ANE placement: unverified."
            } catch {
                generateAnswer = nil
                measureAnswer = nil
                backendPolicy = ""
                isLoaded = false
                status = "Load failed: \(error.localizedDescription)"
            }
        }
    }

    enum ServiceError: Error {
        case modelNotLoaded
        case unauthorized
        case invalidServerCredential
    }

    /// A FUTURE server must pass only the header from an already-verified
    /// TLS session. Secrets stay in memory and are never logged or persisted.
    /// This method does NOT create or start an iPhone LAN listener.
    func handleAuthenticatedGenerationBody(
        _ body: Data,
        authorizationHeader: String?,
        serverCredential: String
    ) async throws -> Data {
        switch NeuralAuthorization.validate(header: authorizationHeader, secret: serverCredential) {
        case .accepted: break
        case .rejected: throw ServiceError.unauthorized
        case .misconfigured: throw ServiceError.invalidServerCredential
        }
        let request = try NeuralProtocol.parseGeneration(body)
        guard isLoaded, let measureAnswer else {
            throw ServiceError.modelNotLoaded
        }
        // The same Core ML generator already measures generated token IDs.
        // Only bounded, in-memory numerical telemetry is returned; no logs.
        let (text, metrics) = try await measureAnswer(request.prompt, request.maxTokens)
        guard metrics.outputTokens >= 0,
              metrics.outputTokens <= request.maxTokens,
              metrics.elapsedMs.isFinite, metrics.elapsedMs >= 0,
              metrics.prefillMs.isFinite, metrics.prefillMs >= 0,
              metrics.generatorTokensPerSecond.isFinite,
              metrics.generatorTokensPerSecond >= 0 else {
            throw NSError(domain: "NanoANEBridge", code: 16,
                          userInfo: [NSLocalizedDescriptionKey:
                            "Invalid local generation telemetry."])
        }
        return try JSONEncoder().encode(NeuralProtocol.makeGenerationResponse(
            text: text,
            completionTokens: metrics.outputTokens,
            modelElapsedMs: metrics.elapsedMs,
            generatorTokensPerSecond: metrics.generatorTokensPerSecond,
            prefillMs: metrics.prefillMs))
    }

    func run(_ input: String) {
        guard !isWorking, let generateAnswer else {
            status = "Load the Core ML model before generating."
            return
        }
        let safe: String
        do {
            safe = try RequestGuard.validate(InferenceRequest(prompt: input, maxTokens: nil)).prompt
        } catch {
            status = "Enter a prompt under 8 KiB."
            return
        }
        isWorking = true
        status = "Generating locallyâ€¦"
        Task {
            defer { isWorking = false }
            do {
                output = try await generateAnswer(safe, RequestGuard.defaultTokens)
                status = "Generated on-device. ANE operation placement not independently measured."
            } catch {
                status = "Inference failed: \(error.localizedDescription)"
            }
        }
    }

    /// One explicit 32-token run; no model reload, no repeated background tasks.
    func runBenchmark() {
        guard isLoaded, !isWorking, let measureAnswer else { return }
        isWorking = true
        benchmarkStatus = "Running bounded 32-token benchmark..."
        Task {
            defer { isWorking = false }
            do {
                let (text, metrics) = try await measureAnswer(
                    "Reply with one sentence about on-device AI.", 32)
                output = text
                benchmarkStatus = String(
                    format: "Prefill %.0f ms | End-to-end %.0f ms | Generator decode speed %.2f tok/s | Output %d tokens | Backend policy: %@. ANE operation placement remains unverified.",
                    metrics.prefillMs, metrics.elapsedMs,
                    metrics.generatorTokensPerSecond, metrics.outputTokens,
                    metrics.backendDescription)
                status = "Benchmark completed locally. ANE operation placement remains unverified."
            } catch {
                benchmarkStatus = "Benchmark failed: \(error.localizedDescription)"
            }
        }
    }
    /// Three opt-in, bounded runs with identical prompt and model; no reload.
    private func median(_ values: [Double]) -> Double {
        values.sorted()[values.count / 2]
    }

    func runThreeBenchmarks() {
        guard isLoaded, !isWorking, let measureAnswer else { return }
        isWorking = true
        threeRunStatus = "Running 3 Ã— 32-token benchmarks..."
        Task {
            defer { isWorking = false }
            var samples: [Qwen35InferenceMetrics] = []
            do {
                for index in 0..<3 {
                    let thermal = ProcessInfo.processInfo.thermalState
                    guard thermal != .serious && thermal != .critical else {
                        throw NSError(domain: "NANOBenchmark", code: 5,
                            userInfo: [NSLocalizedDescriptionKey:
                                "Stopped because device thermal state is elevated."])
                    }
                    let (text, metrics) = try await measureAnswer("Reply with one sentence about on-device AI.", 32)
                    output = text
                    samples.append(metrics)
                    threeRunStatus = "Completed \(index + 1) of 3 runs..."
                    if index < 2 { try await Task.sleep(nanoseconds: 350_000_000) }
                }
                let speeds = samples.map { $0.generatorTokensPerSecond }
                let prefills = samples.map { $0.prefillMs }
                let totals = samples.map { $0.elapsedMs }
                threeRunStatus = String(
                    format: "3 runs decode [%.2f, %.2f, %.2f] tok/s; median %.2f tok/s. Median prefill %.0f ms, median end-to-end %.0f ms. Output tokens [%d, %d, %d]. Compute policy: %@. ANE actual execution not measured.",
                    speeds[0], speeds[1], speeds[2], median(speeds),
                    median(prefills), median(totals),
                    samples[0].outputTokens, samples[1].outputTokens, samples[2].outputTokens,
                    samples[0].backendDescription)
            } catch {
                threeRunStatus = "Stopped after \(samples.count) of 3: \(error.localizedDescription)"
            }
        }
    }

    func inspectComputePlan() {
        guard isLoaded, !isWorking else { return }
        isWorking = true
        computePlanStatus = "Reading cached Core ML compute plan..."
        Task {
            defer { isWorking = false }
            do {
                computePlanStatus = try await Qwen35ComputePlanInspector.inspect(policy: backendPolicy)
                status = "Compute plan inspected; this is not a measured ANE execution trace."
            } catch {
                computePlanStatus = "Compute plan unavailable: \(error.localizedDescription)"
            }
        }
    }

    /// Read-only model-cache inspection; per-chunk relative cost, not execution tracing.
    func inspectAllComputePlans() {
        guard isLoaded, !isWorking else { return }
        isWorking = true
        allPlanStatus = "Inspecting four cached Core ML plans..."
        Task {
            defer { isWorking = false }
            do {
                allPlanStatus = try await Qwen35ComputePlanInspector.inspectAllChunks(
                    policy: backendPolicy)
                status = "Four compute plans inspected; not a measured ANE execution trace."
            } catch {
                allPlanStatus = "All-chunk inspection unavailable: \(error.localizedDescription)"
            }
        }
    }
}

struct ContentView: View {
    @StateObject private var model = NanoModelSession()
    @State private var prompt = "Reply with one sentence about local AI."
    @Environment(\.scenePhase) private var scenePhase
    @State private var showTLSImporter = false
    @State private var tlsPassword = ""
    @State private var usbBearerToken = ""
    @State private var tlsStatus = "Secure USB service is off."
    @State private var tlsServer: NeuralForegroundTLSServer?
    @State private var tlsActive = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("NANO Â· Neural Compute")
                        .font(.title).bold()
                    Text("Core ML proof-of-concept â€” Qwen3.5 0.8B")
                        .font(.headline)
                    Text("This is NOT your existing Qwen Abliterated GGUF. That model stays in the AI Chat app. No LAN service is enabled in this prototype.")
                        .font(.footnote).foregroundStyle(.secondary)

                    Button(model.isLoaded ? "Core ML Model Loaded" : "Load Core ML Model") {
                        model.load()
                    }
                    .disabled(model.isWorking || model.isLoaded)
                    .buttonStyle(.borderedProminent)

                    ProgressView().opacity(model.isWorking ? 1 : 0)
                    Text(model.status)
                        .font(.footnote)
                        .accessibilityIdentifier("nano-model-status")

                    Text("Prompt").font(.headline)
                    TextEditor(text: $prompt)
                        .frame(minHeight: 120, maxHeight: 160)
                        .overlay(RoundedRectangle(cornerRadius: 8)
                            .stroke(.secondary.opacity(0.3)))

                    Button("Generate on iPhone") {
                        model.run(prompt)
                    }
                    .buttonStyle(.bordered)
                    .disabled(model.isWorking || !model.isLoaded)

                    Button("Benchmark 32 Tokens") {
                        model.runBenchmark()
                    }
                    .buttonStyle(.bordered)
                    .disabled(model.isWorking || !model.isLoaded)
                    Text(model.benchmarkStatus)
                        .font(.footnote)
                        .accessibilityIdentifier("nano-benchmark-status")

                    Button("Benchmark 3 Runs") {
                        model.runThreeBenchmarks()
                    }
                    .buttonStyle(.bordered)
                    .disabled(model.isWorking || !model.isLoaded)
                    Text(model.threeRunStatus)
                        .font(.footnote)
                        .accessibilityIdentifier("nano-three-run-results")

                    Button("Inspect Core ML Plan") {
                        model.inspectComputePlan()
                    }
                    .buttonStyle(.bordered)
                    .disabled(model.isWorking || !model.isLoaded)
                    Text(model.computePlanStatus)
                        .font(.footnote)
                        .accessibilityIdentifier("nano-compute-plan-results")


                    Button("Inspect All 4 Core ML Plans") {
                        model.inspectAllComputePlans()
                    }
                    .buttonStyle(.bordered)
                    .disabled(model.isWorking || !model.isLoaded)
                    Text(model.allPlanStatus)
                        .font(.footnote)
                        .textSelection(.enabled)
                        .accessibilityIdentifier("nano-four-chunk-cost-plan-results")

                    Divider()
                    Text("Secure USB Inference (experimental)")
                        .font(.headline)
                    Text("Foreground and USB loopback only. An encrypted TLS identity must be imported to this app's Keychain. No listener starts automatically.")
                        .font(.caption).foregroundStyle(.secondary)

                    SecureField("PKCS#12 file password", text: $tlsPassword)
                        .textContentType(.password)
                    Button("Import TLS Identity") {
                        showTLSImporter = true
                    }
                    .disabled(tlsActive)

                    Button("Import USB-Staged TLS Identity") {
                        defer { tlsPassword = "" }
                        do {
                            usbBearerToken = try NeuralIdentityProvisioner.importStagedPKCS12(password: tlsPassword)
                            tlsStatus = "USB-staged TLS identity imported; credentials prepared. Tap Start after loading the model."
                        } catch {
                            tlsStatus = "USB import failed; check protected staged identity and password."
                        }
                    }
                    .buttonStyle(.bordered)
                    .disabled(tlsActive)

                    SecureField("Shared 32–128 character bearer secret", text: $usbBearerToken)
                        .textContentType(.password)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)

                    Button("Check TLS Identity") {
                        let available = NeuralForegroundTLSServer.hasExpectedIdentity()
                        tlsStatus = available
                            ? "Matching TLS identity found in Keychain. Enter bearer token, then Start."
                            : "Matching TLS identity missing from Keychain. Re-stage encrypted identity only if needed."
                    }
                    .buttonStyle(.bordered)

                    Button("Start Secure USB Service") {
                        startTLS()
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!model.isLoaded || model.isWorking || tlsActive)
                    Button("Stop Secure USB Service") {
                        stopTLS()
                    }
                    .buttonStyle(.bordered)
                    .disabled(!tlsActive)
                    Text(tlsStatus).font(.footnote)
                        .accessibilityIdentifier("nano-usb-tls-status")

                    Text("Output").font(.headline)
                    Text(model.output.isEmpty ? "(No result yet)" : model.output)
                        .textSelection(.enabled)

                    Divider()
                    Text("GPU/ANE tracing: not performed. Compute-unit preferences are not proof of actual execution.")
                        .font(.caption).foregroundStyle(.secondary)
                    Text("USB-only TLS server is opt-in and foreground-only. Verify certificate pinning on the host.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                .padding()
            }
            .navigationTitle("NANO AI")
            .fileImporter(isPresented: $showTLSImporter,
                          allowedContentTypes: [UTType(filenameExtension: "p12") ?? .data]) { result in
                defer { tlsPassword = "" }
                do {
                    let fileURL = try result.get()
                    let accessing = fileURL.startAccessingSecurityScopedResource()
                    defer { if accessing { fileURL.stopAccessingSecurityScopedResource() } }
                    try NeuralIdentityProvisioner.importPKCS12(
                        from: fileURL, password: tlsPassword)
                    usbBearerToken = NeuralIdentityProvisioner.deriveBearer(password: tlsPassword)
                    tlsStatus = "TLS identity imported into app Keychain; service remains off."
                } catch {
                    tlsStatus = "TLS import failed; verify the password and encrypted .p12 file."
                }
            }
            .onChange(of: scenePhase) { _, phase in
                if phase != .active { stopTLS() }
            }
        }
    }
    private func startTLS() {
        guard model.isLoaded, !model.isWorking else {
            tlsStatus = "Load the Core ML model before starting the service."
            return
        }
        guard !tlsActive else { return }
        do {
            let server = NeuralForegroundTLSServer(model: model)
            server.onStatus = { message in
                tlsStatus = message
                if message.hasPrefix("TLS listener failed") {
                    tlsActive = false
                    UIApplication.shared.isIdleTimerDisabled = false
                    tlsServer = nil
                }
            }
            try server.startExplicitly(secret: usbBearerToken,
                identityLabel: NeuralIdentityProvisioner.identityLabel)
            tlsServer = server
            tlsActive = true
            UIApplication.shared.isIdleTimerDisabled = true
            tlsStatus = "Opening secure USB loopback listener; waiting for iOS ready state."
        } catch let reason as NeuralForegroundTLSServer.ActivationError {
            switch reason {
            case .identityMissing:
                tlsStatus = "Matching TLS identity missing in app Keychain."
            case .invalidSecret:
                tlsStatus = "Bearer token invalid: use the 64-character hex token shown on PC."
            case .notForeground:
                tlsStatus = "NANO AI must be active in foreground to start secure USB."
            case .alreadyRunning:
                tlsStatus = "Secure USB listener is already active."
            }
        } catch {
            let code = (error as NSError).code
            tlsStatus = "TLS listener unavailable (error code \(code)); investigate loopback binding."
        }
    }

    private func stopTLS() {
        tlsServer?.stop()
        tlsServer = nil
        tlsActive = false
        UIApplication.shared.isIdleTimerDisabled = false
        usbBearerToken = ""
        tlsStatus = "Secure USB service is off."
    }

}
