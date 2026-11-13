import Foundation

struct InferenceRequest: Codable {
    let prompt: String
    let maxTokens: Int?

    enum CodingKeys: String, CodingKey {
        case prompt
        case maxTokens = "max_tokens"
    }
}

enum RequestGuardError: Error, Equatable {
    case emptyPrompt
    case promptTooLong
    case invalidTokens
}

enum RequestGuard {
    static let maximumPromptBytes = 8192
    static let maximumTokens = 512
    static let defaultTokens = 128

    static func validate(_ request: InferenceRequest) throws -> (prompt: String, maxTokens: Int) {
        let cleaned = request.prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty else { throw RequestGuardError.emptyPrompt }
        guard cleaned.utf8.count <= maximumPromptBytes else { throw RequestGuardError.promptTooLong }
        let tokens = request.maxTokens ?? defaultTokens
        guard tokens >= 1 && tokens <= maximumTokens else { throw RequestGuardError.invalidTokens }
        return (cleaned, tokens)
    }
}
