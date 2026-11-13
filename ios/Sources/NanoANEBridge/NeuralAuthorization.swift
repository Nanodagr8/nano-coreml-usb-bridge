import Foundation

/// Authorization gate for the experimental USB-loopback Core ML HTTPS server.
/// This does not create a server, store credentials, or permit anonymous calls.
enum NeuralAuthorizationDecision: Equatable {
    case accepted
    case rejected
    case misconfigured
}

enum NeuralAuthorization {
    static let minimumSecretBytes = 32
    static let maximumSecretBytes = 128

    static func validSecret(_ candidate: String) -> Bool {
        let bytes = Array(candidate.utf8)
        guard (minimumSecretBytes...maximumSecretBytes).contains(bytes.count) else {
            return false
        }
        // Bearer credentials are unstructured, printable ASCII with no
        // whitespace to avoid ambiguity across HTTP parsers/proxies.
        return bytes.allSatisfy { $0 >= 33 && $0 <= 126 }
    }

    static func validate(header: String?, secret: String) -> NeuralAuthorizationDecision {
        guard validSecret(secret) else { return .misconfigured }
        guard let header, header.hasPrefix("Bearer ") else { return .rejected }
        let token = Array(header.dropFirst(7).utf8)
        guard token.count <= maximumSecretBytes else { return .rejected }
        let expected = Array(secret.utf8)
        var difference = token.count ^ expected.count
        // Fixed-length loop avoids exposing the location of a mismatch.
        // Network-level rate limiting and TLS remain required.
        for index in 0..<maximumSecretBytes {
            let actualByte: UInt8 = index < token.count ? token[index] : 0
            let expectedByte: UInt8 = index < expected.count ? expected[index] : 0
            difference |= Int(actualByte ^ expectedByte)
        }
        return difference == 0 ? .accepted : .rejected
    }
}
