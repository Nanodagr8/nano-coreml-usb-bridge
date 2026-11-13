import Foundation

/// Wire format for the experimental USB-loopback Core ML HTTPS server.
/// This source handles bounded messages; authentication and listening are separate.
enum NeuralRoute: Equatable {
    case status
    case generate
}

enum NeuralProtocolError: Error, Equatable {
    case invalidJSON
    case tooLarge
    case wrongModel
    case streamingUnsupported
}

private struct NeuralGenerationInput: Decodable {
    let model: String
    let prompt: String
    let maxTokens: Int?
    let stream: Bool?

    enum CodingKeys: String, CodingKey {
        case model
        case prompt
        case maxTokens = "max_tokens"
        case stream
    }
}

struct NeuralGenerationResult: Encodable {
    let modelID: String
    let text: String
    let hardwareVerified: Bool
    let hardwareUnit: String

    enum CodingKeys: String, CodingKey {
        case modelID = "model_id"
        case text
        case hardwareVerified = "hardware_verified"
        case hardwareUnit = "hardware_unit"
    }
}

struct NeuralStatusResult: Encodable {
    let status: String
    let modelID: String
    let computeUnitPreference: String
    let hardwareVerified: Bool
    let hardwareUnit: String

    enum CodingKeys: String, CodingKey {
        case status
        case modelID = "model_id"
        case computeUnitPreference = "compute_unit_preference"
        case hardwareVerified = "hardware_verified"
        case hardwareUnit = "hardware_unit"
    }
}

enum NeuralProtocol {
    static let modelID = "qwen3.5-0.8b"
    static let maximumBodyBytes = 16384

    static func route(method: String, path: String) -> NeuralRoute? {
        switch (method, path) {
        case ("GET", "/v1/neural/status"): return .status
        case ("POST", "/v1/neural/generate"): return .generate
        default: return nil
        }
    }

    static func parseGeneration(_ body: Data) throws -> (prompt: String, maxTokens: Int) {
        guard body.count <= maximumBodyBytes else { throw NeuralProtocolError.tooLarge }
        let input: NeuralGenerationInput
        do {
            input = try JSONDecoder().decode(NeuralGenerationInput.self, from: body)
        } catch {
            throw NeuralProtocolError.invalidJSON
        }
        guard input.model == modelID else { throw NeuralProtocolError.wrongModel }
        guard input.stream != true else { throw NeuralProtocolError.streamingUnsupported }
        return try RequestGuard.validate(InferenceRequest(prompt: input.prompt, maxTokens: input.maxTokens))
    }

    static func makeGenerationResponse(text: String) -> NeuralGenerationResult {
        NeuralGenerationResult(modelID: modelID, text: text,
                               hardwareVerified: false, hardwareUnit: "unverified")
    }

    static func makeStatusResponse(
        modelLoaded: Bool, computeUnitPreference: String = "unknown"
    ) -> NeuralStatusResult {
        NeuralStatusResult(status: modelLoaded ? "ready" : "unloaded",
                           modelID: modelID,
                           computeUnitPreference: modelLoaded ? computeUnitPreference : "unknown",
                           hardwareVerified: false, hardwareUnit: "unverified")
    }
}
