import Foundation
import Security
import CryptoKit

/// Imports a user-selected encrypted PKCS#12 identity into this app's Keychain.
/// Does not create certificates, save passwords, or enable a network listener.
enum NeuralIdentityProvisioner {
    static let identityLabel = "NanoANEBridge USB TLS v8"

    enum ImportError: Error {
        case invalidFile, invalidPassword, invalidIdentity, duplicate, keychain(OSStatus)
    }

    static func importPKCS12(from fileURL: URL, password: String) throws {
        guard fileURL.pathExtension.lowercased() == "p12" else {
            throw ImportError.invalidFile
        }
        guard !password.isEmpty else { throw ImportError.invalidPassword }
        let data = try Data(contentsOf: fileURL)
        guard !data.isEmpty && data.count <= 1_048_576 else {
            throw ImportError.invalidFile
        }
        let options: [String: Any] = [kSecImportExportPassphrase as String: password]
        var rawItems: CFArray?
        let result = SecPKCS12Import(data as CFData, options as CFDictionary, &rawItems)
        guard result == errSecSuccess,
              let entries = rawItems as? [[String: Any]],
              entries.count == 1,
              let item = entries[0][kSecImportItemIdentity as String] else {
            throw ImportError.invalidIdentity
        }
        // SecPKCS12Import returns a Security identity reference for this key.
        let identity = item as! SecIdentity

        // Keychain enforces encryption; no private key or password is written
        // into app documents or user defaults. Existing identity is never replaced.
        let addition: [String: Any] = [
            kSecValueRef as String: identity,
            kSecAttrLabel as String: identityLabel,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]
        let status = SecItemAdd(addition as CFDictionary, nil)
        if status == errSecDuplicateItem { throw ImportError.duplicate }
        guard status == errSecSuccess else { throw ImportError.keychain(status) }
    }

    /// Same 192-bit random import password yields a domain-separated 64-char
    /// bearer digest on the phone and Windows; password itself is never kept.
    static func deriveBearer(password: String) -> String {
        let bytes = Data(("NANO-v8-USB-BEARER:" + password).utf8)
        let token = SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
        return token
    }

    /// Imported only after a physical USB-paired host staged this encrypted
    /// PKCS#12 inside our private sandbox. Never expose Files sharing.
    static func importStagedPKCS12(password: String) throws -> String {
        guard !password.isEmpty else { throw ImportError.invalidPassword }
        guard let docs = FileManager.default.urls(for: .documentDirectory,
                                                  in: .userDomainMask).first else {
            throw ImportError.invalidFile
        }
        let stagedFile = docs.appendingPathComponent(".nano-provision/server.p12")
        guard FileManager.default.fileExists(atPath: stagedFile.path) else {
            throw ImportError.invalidFile
        }
        try importPKCS12(from: stagedFile, password: password)
        let derived = deriveBearer(password: password)
        guard NeuralAuthorization.validSecret(derived) else {
            throw ImportError.invalidPassword
        }
        // Do not leave the encrypted identity in Documents after import.
        try FileManager.default.removeItem(at: stagedFile)
        return derived
    }

}
