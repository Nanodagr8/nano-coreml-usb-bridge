# Architecture and trust boundaries

    Windows Python client
      -> HTTPS: verify TLS certificate SPKI SHA-256 BEFORE any HTTP bytes
      -> Bearer authorization and bounded JSON
      -> Windows loopback 127.0.0.1:49443
      -> trusted Apple USB pairing and forwarding
      -> iPhone loopback 127.0.0.1:49443
      -> Network.framework TLS using Keychain SecIdentity
      -> strict HTTP/1.1 framing and bearer authorization
      -> Core ML Qwen3.5-0.8B multi-chunk MLKV
      -> bounded JSON text response

The host learns the public TLS SPKI SHA-256 pin through an independent trusted channel. The iOS app selects the appropriate server Keychain identity by comparing its DER certificate SHA-256 against a value configured by each builder in Info.plist (NanoTLSCertificateSHA256). These two public fingerprints are different and serve different purposes.

Never publish secrets or forward to a Wi-Fi or LAN address. In this reference, service activation is explicit and foreground-only. Port-forward readiness does not imply the phone's TLS listener is active.

The compute-unit policy cpuAndNeuralEngine expresses a preference. Real Apple Neural Engine operator placement has NOT yet been measured.
