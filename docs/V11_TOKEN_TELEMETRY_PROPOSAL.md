# v11 token telemetry — signed field candidate, physical verification pending

**Engineering status (November 13, 2026):** The v11 Swift/Python protocol extension has passed unit tests, a native Swift JSON wire fixture, full ARM64 iOS compilation and app linking. With user approval, the rebuilt candidate was signed and installed on the paired iPhone by the existing free signing workflow (installer exit 0, install verification complete). **Authenticated v11 token-metrics responses have NOT yet been verified on the physical phone.**

The known-good v10 unsigned rollback IPA remains intact and hash-verified. The current public branch is a review candidate; do not merge it as production-verified until the physical-device regression suite passes.

## Wire contract

Endpoint: `POST /v1/neural/generate`, existing pinned HTTPS over manually foregrounded, USB-only loopback.

Existing keys remain: `model_id`, `text`, `hardware_verified:false`, `hardware_unit:"unverified"`. New optional keys:

- `completion_tokens`: count of Core ML generator non-EOS emitted token IDs, bounded 0..requested maximum
- `model_elapsed_ms`: existing `Qwen35InferenceMetrics.elapsedMs` for on-device generation, not Windows request wall time
- `prefill_ms`: Core ML generator's reported prefill time
- `generator_tokens_per_second`: generator-specific decoding throughput; **not a Windows offload speedup**
- `metrics_source:"on_device_coreml_generator"`: provenance for actual reported token count, not inferred count

No field asserts Apple Neural Engine hardware placement. No new network listener, background service, credential storage or model download was introduced.

## Gates completed

- Python regression tests: **30/30 passing**, including legacy v10 response and malformed metric tests
- Native Swift JSON wire fixture: passed
- Isolated ARM64 iOS target: **351 compile steps passed**, app product successfully linked
- Source and artifact scan: Gitleaks clean
- USB install dry run: signing inventory and physical USB preflight passed
- Existing signed deployment workflow: v11 candidate installed, installer and installation verification exit 0
- Original v10 rollback IPA hash unchanged

The Linux-based iOS cross-linker emits an unsupported-platform compatibility warning even when the link succeeds. A successful linker result does not establish runtime correctness.

## Remaining physical-device gates

1. Open NANO AI on the iPhone, explicitly load the model and start **Secure USB Service** in the foreground
2. Check TLS pinning, wrong-certificate rejection before HTTP, invalid bearer HTTP 401 and authenticated status
3. Request three bounded synthetic prompts; independently validate actual `completion_tokens`, `model_elapsed_ms`, `prefill_ms`, `generator_tokens_per_second` and `metrics_source`
4. Check no private keys, bearer tokens, prompt texts or responses are logged
5. Confirm existing model cache, app behavior and background-shutdown semantics remain intact
6. Preserve a rollback path if the candidate fails any gate

A recorded installation success is **not** evidence that the hardware actually executed ANE operators, nor proof of improved inference speed. Controlled benchmarking and Core ML Instruments traces remain future work.

## Security and reproducibility

The public source intentionally omits the device-specific TLS certificate fingerprint and signing material. The deployed private build uses the pre-existing identity configuration; only the two v11 Swift telemetry hunks were introduced. No private signed IPA, model weights, Apple pairing records, or bearer credentials are published.

[Research issue R1](https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/1) tracks the remaining physical measurements and model parity limitations.
