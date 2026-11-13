# Safe reproduction prerequisites

This is reference source, **not a one-command iOS installer**. You need a physical iPhone, an authorized USB-paired host, an appropriate iOS developer toolchain, your own Apple signing setup, a self-generated TLS identity and a Qwen3.5-0.8B model download. None of those private assets are bundled.

1. Review ios/Package.swift and upstream project licenses. Build your own SwiftUI iOS application target using the ios/Sources/NanoANEBridge reference files with your own bundle identifier; the source package is a library, not a turnkey signed app.
2. Generate a short-lived server TLS certificate with SAN IP:127.0.0.1 and serverAuth extension. Import the encrypted PKCS#12 certificate and private key into the app Keychain. Never commit it.
3. Compute SHA-256 of the DER certificate and place its 64-character lowercase hex digest under the Info.plist key NanoTLSCertificateSHA256 before building your app.
4. Separately calculate the SHA-256 of the certificate's DER SubjectPublicKeyInfo, base64-encode it and configure the Windows client NANO_USB_TLS_PIN variable. Do not confuse this SPKI pin with the DER certificate digest.
5. Pair and trust the iPhone over normal Apple USB pairing. Use a loopback-only usbmux forward from host 127.0.0.1:49443 to iPhone 127.0.0.1:49443. Never expose port 49443 publicly.
6. On the iPhone, explicitly load the model, enter the high-entropy 32–128 printable ASCII bearer, verify the Keychain identity, and start the TLS service while the app stays foregrounded. Wait for a real listener-ready status.
7. Install the Python cryptography dependency, privately configure NANO_USB_BEARER and NANO_USB_TLS_PIN, and run the host client status and a bounded generation request.
8. Test bad pin rejection before HTTP, bad bearer HTTP 401, and service shutdown when the app backgrounds.

No real TLS identities, signing keys, bearer tokens, personal UDIDs, model weights or pairing records are published. The existing iPhone implementation is foreground-only, and CPU/GPU/ANE placement requires independent profiling.
