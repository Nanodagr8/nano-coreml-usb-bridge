import Foundation

/// Native Swift-only wire encoding fixture. It does not start any service.
@main
struct NanoV11WireFixture {
    static func object<T: Encodable>(_ value: T) throws -> [String: Any] {
        let bytes = try JSONEncoder().encode(value)
        guard let result = try JSONSerialization.jsonObject(with: bytes) as? [String: Any] else {
            fatalError("Wire response must be a JSON object")
        }
        return result
    }

    static func main() throws {
        let v11 = try object(NeuralProtocol.makeGenerationResponse(
            text: "test response",
            completionTokens: 22,
            modelElapsedMs: 1072.5,
            generatorTokensPerSecond: 41.6,
            prefillMs: 50.4))
        guard v11["model_id"] as? String == "qwen3.5-0.8b",
              v11["text"] as? String == "test response",
              v11["completion_tokens"] as? Int == 22,
              v11["model_elapsed_ms"] as? Double == 1072.5,
              v11["generator_tokens_per_second"] as? Double == 41.6,
              v11["prefill_ms"] as? Double == 50.4,
              v11["metrics_source"] as? String == "on_device_coreml_generator",
              v11["hardware_verified"] as? Bool == false,
              v11["hardware_unit"] as? String == "unverified" else {
            fatalError("Telemetry wire schema failed")
        }

        let legacy = try object(NeuralProtocol.makeGenerationResponse(text: "legacy"))
        guard legacy["model_id"] as? String == "qwen3.5-0.8b",
              legacy["text"] as? String == "legacy",
              legacy["completion_tokens"] == nil,
              legacy["model_elapsed_ms"] == nil,
              legacy["generator_tokens_per_second"] == nil,
              legacy["prefill_ms"] == nil,
              legacy["metrics_source"] == nil,
              legacy["hardware_verified"] as? Bool == false else {
            fatalError("Legacy response compatibility failed")
        }
        print("NANO_SWIFT_V11_WIRE_FIXTURE=PASS")
    }
}
