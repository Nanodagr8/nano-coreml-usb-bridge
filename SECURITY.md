# Security policy and limitations

**Experimental reference only. Not independently security-audited.**

The intended connection is Windows localhost to a physically paired iPhone using USB forwarding, with TLS 1.2+ and a separately provisioned certificate. The host checks the SHA-256 SPKI pin of the presented certificate before transmitting any authorization header or prompt. The iPhone requires a 32–128-character printable ASCII bearer, rejects incorrect tokens with HTTP 401, and only listens on 127.0.0.1 in the foreground.

The app imports a PKCS#12 server identity into its Keychain. Each builder provides the SHA-256 fingerprint of the DER *certificate* through the Info.plist key NanoTLSCertificateSHA256 to select an exact identity. That fingerprint differs from the host's **SPKI pin**.

Not yet implemented or certified: automatic certificate rotation, unattended/background operation, high-volume request handling, third-party penetration testing, cross-device deployment automation, real ANE operator-level measurement.

Never bind the USB forward to 0.0.0.0 or an exposed network interface. Do not commit secrets or signed app packages. The source intentionally contains **no valid private TLS identity, signing certificate, token or device-specific fingerprint**.

Please open a public issue with a nonsensitive summary, and ask to coordinate private disclosure before submitting sensitive exploit details.
