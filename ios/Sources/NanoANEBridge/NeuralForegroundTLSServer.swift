import Foundation
import Network
import Security
import CryptoKit
import UIKit

/// Experimental on-device TLS endpoint. This type has no automatic startup.
/// It refuses to listen without a provisioned Keychain SecIdentity and a
/// user-entered 32..128 byte bearer secret. USB loopback only (not LAN).
@MainActor
final class NeuralForegroundTLSServer {
    enum ActivationError: Error {
        case identityMissing, invalidSecret, notForeground, alreadyRunning
    }

    var onStatus: ((String) -> Void)?
    private weak var model: NanoModelSession?
    private var listener: NWListener?
    private var activeConnection: NWConnection?
    private var bearerSecret: String?
    private var backgroundObserver: NSObjectProtocol?
    private let networkQueue = DispatchQueue(label: "com.nanostudios.neural.securetls")
    private let port = NWEndpoint.Port(rawValue: 49443)!
    // Public SHA-256 of the precise DER X509 certificate provisioned on
    // NanoStudios; no secret or private key is bundled.
    private static var expectedCertificateFingerprint: String {
        // Public DER certificate SHA-256; configure per signer in Info.plist.
        // An absent or malformed value fails closed: no Keychain identity matches.
        (Bundle.main.object(forInfoDictionaryKey: "NanoTLSCertificateSHA256") as? String ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    /// A certificate may not keep its imported Keychain label. Match its exact
    /// public fingerprint instead; do not choose the first arbitrary identity.
    private static func resolveTLSIdentity() throws -> SecIdentity {
        let query: [String: Any] = [
            kSecClass as String: kSecClassIdentity,
            kSecMatchLimit as String: kSecMatchLimitAll,
            kSecReturnRef as String: true
        ]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let result else {
            throw ActivationError.identityMissing
        }
        let candidates: [Any] = (result as? [Any]) ?? [result]
        for candidate in candidates {
            let item = candidate as CFTypeRef
            guard CFGetTypeID(item) == SecIdentityGetTypeID() else { continue }
            let candidateIdentity = candidate as! SecIdentity
            var certificate: SecCertificate?
            guard SecIdentityCopyCertificate(candidateIdentity, &certificate) == errSecSuccess,
                  let certificate else { continue }
            let certificateBytes = SecCertificateCopyData(certificate) as Data
            let actual = SHA256.hash(data: certificateBytes).map {
                String(format: "%02x", $0)
            }.joined()
            if actual == expectedCertificateFingerprint {
                return candidateIdentity
            }
        }
        throw ActivationError.identityMissing
    }

    static func hasExpectedIdentity() -> Bool {
        (try? resolveTLSIdentity()) != nil
    }

    init(model: NanoModelSession) {
        self.model = model
    }

    /// Only call from an explicit foreground user action after an identity has
    /// been securely imported into the app Keychain. No fallback to plaintext.
    func startExplicitly(secret: String, identityLabel: String) throws {
        guard listener == nil else { throw ActivationError.alreadyRunning }
        guard UIApplication.shared.applicationState == .active else {
            throw ActivationError.notForeground
        }
        guard NeuralAuthorization.validSecret(secret) else {
            throw ActivationError.invalidSecret
        }
        guard !identityLabel.isEmpty else { throw ActivationError.identityMissing }

        let secIdentity = try Self.resolveTLSIdentity()
        guard let identity = sec_identity_create(secIdentity) else {
            throw ActivationError.identityMissing
        }
        let tls = NWProtocolTLS.Options()
        sec_protocol_options_set_min_tls_protocol_version(
            tls.securityProtocolOptions, .TLSv12)
        sec_protocol_options_set_local_identity(
            tls.securityProtocolOptions, identity)

        let parameters = NWParameters(tls: tls, tcp: NWProtocolTCP.Options())
        parameters.requiredLocalEndpoint = .hostPort(
            host: NWEndpoint.Host("127.0.0.1"), port: port)
        // requiredLocalEndpoint already contains BOTH numeric loopback and port.
        // Passing on: port AGAIN yields nw_listener_create_with_port,
        // and iOS rejects the combination with POSIX EINVAL (22).
        // Use the .any default so Network.framework binds the required endpoint.
        let server = try NWListener(using: parameters)
        server.newConnectionHandler = { [weak self] connection in
            Task { @MainActor in
                self?.accept(connection)
            }
        }
        server.stateUpdateHandler = { [weak self] state in
            switch state {
            case .ready:
                Task { @MainActor in
                    guard let self, self.listener != nil else { return }
                    self.onStatus?("TLS loopback listener ready on port 49443. Keep NANO AI in foreground.")
                }
            case .failed(let failure):
                let code = (failure as NSError).code
                Task { @MainActor in
                    self?.onStatus?("TLS listener failed (network error code \(code)).")
                    self?.stop()
                }
            default: break
            }
        }
        // Activation is foreground-only; releasing all sockets on background
        // avoids the iOS suspended-listener trap.
        backgroundObserver = NotificationCenter.default.addObserver(
            forName: UIApplication.didEnterBackgroundNotification,
            object: nil, queue: .main) { [weak self] _ in
                Task { @MainActor in self?.stop() }
            }
        bearerSecret = secret
        listener = server
        server.start(queue: networkQueue)
    }

    func stop() {
        activeConnection?.cancel()
        activeConnection = nil
        listener?.cancel()
        listener = nil
        bearerSecret = nil
        if let backgroundObserver {
            NotificationCenter.default.removeObserver(backgroundObserver)
            self.backgroundObserver = nil
        }
    }

    private func accept(_ connection: NWConnection) {
        guard UIApplication.shared.applicationState == .active,
              listener != nil, bearerSecret != nil,
              activeConnection == nil else {
            connection.cancel()
            return
        }
        activeConnection = connection
        connection.stateUpdateHandler = { [weak self, weak connection] state in
            switch state {
            case .cancelled, .failed:
                Task { @MainActor in
                    guard let self, let connection else { return }
                    if self.activeConnection === connection {
                        self.activeConnection = nil
                    }
                }
            default: break
            }
        }
        connection.start(queue: networkQueue)
        // Limit TLS handshakes and inactive connections; no indefinite holds.
        networkQueue.asyncAfter(deadline: .now() + 25) { [weak connection] in
            connection?.cancel()
        }
        receive(connection, accumulating: Data())
    }

    private func receive(_ connection: NWConnection, accumulating original: Data) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 4096) {
            [weak self] incoming, _, complete, error in
            Task { @MainActor in
                guard let self, self.activeConnection === connection else {
                    connection.cancel()
                    return
                }
                var bytes = original
                if let incoming { bytes.append(incoming) }
                guard error == nil,
                      bytes.count <= NeuralHTTPFraming.maximumRequestBytes else {
                    self.respond(connection, code: 413, data: self.jsonError())
                    return
                }
                do {
                    switch try NeuralHTTPFraming.parse(bytes) {
                    case .incomplete:
                        if complete {
                            self.respond(connection, code: 400, data: self.jsonError())
                        } else {
                            self.receive(connection, accumulating: bytes)
                        }
                    case .ready(let request):
                        await self.handle(connection, request: request)
                    }
                } catch {
                    self.respond(connection, code: 400, data: self.jsonError())
                }
            }
        }
    }

    private func handle(_ connection: NWConnection,
                        request: NeuralHTTPRequest) async {
        guard UIApplication.shared.applicationState == .active,
              let bearerSecret else {
            respond(connection, code: 503, data: jsonError())
            return
        }
        guard NeuralAuthorization.validate(
            header: request.authorizationHeader, secret: bearerSecret) == .accepted else {
            respond(connection, code: 401, data: jsonError())
            return
        }
        guard let model else {
            respond(connection, code: 503, data: jsonError())
            return
        }
        if request.method == "GET" {
            do {
                // Report the selected compute POLICY, never observed ANE
                // operation placement. Unknown if model has not loaded.
                let selected: String
                if model.backendPolicy.contains("GPU fallback") {
                    selected = "cpuAndGPU"
                } else if model.backendPolicy.contains("ANE-preferred") {
                    selected = "cpuAndNeuralEngine"
                } else {
                    selected = "unknown"
                }
                let result = NeuralProtocol.makeStatusResponse(
                    modelLoaded: model.isLoaded, computeUnitPreference: selected)
                respond(connection, code: 200, data: try JSONEncoder().encode(result))
            } catch {
                respond(connection, code: 500, data: jsonError())
            }
        } else {
            guard model.isLoaded else {
                respond(connection, code: 503, data: jsonError())
                return
            }
            do {
                let result = try await model.handleAuthenticatedGenerationBody(
                    request.body,
                    authorizationHeader: request.authorizationHeader,
                    serverCredential: bearerSecret)
                respond(connection, code: 200, data: result)
            } catch {
                // No exceptions, request bodies, prompts, or secrets sent back.
                respond(connection, code: 400, data: jsonError())
            }
        }
    }

    private func jsonError() -> Data {
        Data(#"{"error":"request rejected"}"#.utf8)
    }

    private func respond(_ connection: NWConnection, code: Int, data: Data) {
        let reason: String
        switch code {
        case 200: reason = "OK"
        case 400: reason = "Bad Request"
        case 401: reason = "Unauthorized"
        case 413: reason = "Payload Too Large"
        default: reason = "Service Unavailable"
        }
        let headers = "HTTP/1.1 \(code) \(reason)\r\n" +
            "Content-Type: application/json\r\n" +
            "Cache-Control: no-store\r\n" +
            "Connection: close\r\n" +
            "Content-Length: \(data.count)\r\n\r\n"
        var response = Data(headers.utf8)
        response.append(data)
        connection.send(content: response, completion: .contentProcessed {
            [weak self] _ in
            connection.cancel()
            Task { @MainActor in
                if self?.activeConnection === connection {
                    self?.activeConnection = nil
                }
            }
        })
    }
}
