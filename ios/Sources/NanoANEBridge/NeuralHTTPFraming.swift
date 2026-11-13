import Foundation

/// Framing for exactly ONE authenticated HTTP/1.1 request over an already
/// established TLS connection. Never accepts plaintext, pipelining, chunked
/// encoding, duplicate authority/length/authentication, or ambiguous lengths.
enum NeuralHTTPFrameError: Error {
    case malformed
    case headerTooLarge
    case bodyTooLarge
    case unsupported
}

struct NeuralHTTPRequest {
    let method: String
    let path: String
    let authorizationHeader: String
    let body: Data
}

enum NeuralHTTPParseResult {
    case incomplete
    case ready(NeuralHTTPRequest)
}

enum NeuralHTTPFraming {
    static let maximumHeaderBytes = 4096
    static let maximumBodyBytes = 16384
    static let maximumRequestBytes = maximumHeaderBytes + maximumBodyBytes

    static func parse(_ bytes: Data) throws -> NeuralHTTPParseResult {
        guard bytes.count <= maximumRequestBytes else { throw NeuralHTTPFrameError.bodyTooLarge }
        // Reject bare LF and CR in request framing, including incomplete headers.
        let octets = Array(bytes)
        for (idx, c) in octets.enumerated() {
            if c == 10 && (idx == 0 || octets[idx - 1] != 13) {
                throw NeuralHTTPFrameError.malformed
            }
            if c == 13 && idx + 1 < octets.count && octets[idx + 1] != 10 {
                throw NeuralHTTPFrameError.malformed
            }
            if c == 0 { throw NeuralHTTPFrameError.malformed }
        }
        let delimiter = Data([13, 10, 13, 10])
        guard let boundary = bytes.range(of: delimiter) else {
            if bytes.count > maximumHeaderBytes { throw NeuralHTTPFrameError.headerTooLarge }
            return .incomplete
        }
        guard boundary.lowerBound <= maximumHeaderBytes else { throw NeuralHTTPFrameError.headerTooLarge }
        let headersData = bytes.prefix(upTo: boundary.lowerBound)
        guard let text = String(data: headersData, encoding: .utf8) else {
            throw NeuralHTTPFrameError.malformed
        }
        let lines = text.components(separatedBy: "\r\n")
        guard !lines.isEmpty else { throw NeuralHTTPFrameError.malformed }
        let start = lines[0].split(separator: " ", omittingEmptySubsequences: false)
        guard start.count == 3,
              start[2] == "HTTP/1.1" else { throw NeuralHTTPFrameError.malformed }
        let method = String(start[0])
        let path = String(start[1])
        guard (method == "POST" && path == "/v1/neural/generate")
                || (method == "GET" && path == "/v1/neural/status") else {
            throw NeuralHTTPFrameError.unsupported
        }
        var fields: [String:String] = [:]
        for line in lines.dropFirst() {
            guard !line.isEmpty,
                  !line.hasPrefix(" "), !line.hasPrefix("\t"),
                  let colon = line.firstIndex(of: ":") else {
                throw NeuralHTTPFrameError.malformed
            }
            let name = String(line[..<colon]).lowercased()
            let value = String(line[line.index(after: colon)...]).trimmingCharacters(in: .whitespaces)
            guard !name.isEmpty, name.utf8.allSatisfy({
                (65...90).contains(Int($0)) || (97...122).contains(Int($0))
                || (48...57).contains(Int($0)) || $0 == 45
            }), value.unicodeScalars.allSatisfy({ $0.value >= 32 && $0.value <= 126 }),
                  fields[name] == nil else {
                throw NeuralHTTPFrameError.malformed
            }
            fields[name] = value
        }
        guard fields["transfer-encoding"] == nil,
              let host = fields["host"], !host.isEmpty,
              let authorization = fields["authorization"], !authorization.isEmpty else {
            throw NeuralHTTPFrameError.malformed
        }
        let expected: Int
        if method == "POST" {
            guard fields["content-type"]?.lowercased() == "application/json",
                  let literal = fields["content-length"],
                  !literal.isEmpty,
                  literal.utf8.allSatisfy({ $0 >= 48 && $0 <= 57 }),
                  let length = Int(literal) else {
                throw NeuralHTTPFrameError.malformed
            }
            expected = length
        } else {
            guard fields["content-length"] == nil || fields["content-length"] == "0" else {
                throw NeuralHTTPFrameError.malformed
            }
            expected = 0
        }
        guard expected <= maximumBodyBytes else { throw NeuralHTTPFrameError.bodyTooLarge }
        let payloadStart = boundary.upperBound
        let available = bytes.distance(from: payloadStart, to: bytes.endIndex)
        guard available <= expected else { throw NeuralHTTPFrameError.malformed }
        if available < expected { return .incomplete }
        return .ready(NeuralHTTPRequest(method: method, path: path,
                                        authorizationHeader: authorization,
                                        body: Data(bytes[payloadStart...])))
    }
}
