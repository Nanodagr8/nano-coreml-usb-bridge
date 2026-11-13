# End-to-end physical-device evidence — November 13, 2026

The local experiment used Windows with USB forwarding, a physical iPhone 16 Pro Max on iOS 27.2, and Qwen3.5-0.8B through Core ML. The test requested at most 32 output tokens.

Sanitized verification output:

    V10_WATCHER_STARTED=YES
    V10_WAITING_FOR_IPHONE=TLS_NOT_CONNECTED
    V10_REAL_TLS_STATUS=READY
    V10_TLS_STATUS_ATTEMPTS=28
    V8_PINNED_HTTPS_STATUS=READY
    V8_REPORTED_POLICY=cpuAndNeuralEngine
    V8_INVALID_PIN_REJECTED_BEFORE_HTTP=YES
    V8_INVALID_BEARER_HTTP401=YES
    V8_PINNED_HTTPS_GENERATION=SUCCESS
    V8_OUTPUT_CHARACTERS=172
    V8_HARDWARE_EXECUTION_VERIFIED=NO
    V8_ALL_TESTS=PASS
    V10_END_TO_END_USB_VERIFY=SUCCESS

The entire test watcher took 60.49 seconds including user foreground activation, retrying the connection and deliberate negative security checks. **That is not the model's generation latency.**

The private development suite had 331/331 passing Python tests at the v10 checkpoint. This public repo contains a separate, portable host-client test suite; the private suite, certificate, identities and private hardware logs are not included.

This proves authenticated, pinned HTTPS USB inference from Windows into on-device Core ML generation under these test conditions. It does not prove ANE hardware placement, sustained throughput, production security, an always-on service, or world-first novelty.
