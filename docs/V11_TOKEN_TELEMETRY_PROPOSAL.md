# Proposed v11 on-device numeric telemetry — draft, not installed

The v10 iPhone service is **already verified and should not be replaced prematurely**. This isolated research branch adds optional response telemetry to a future v11 build.

## Wire contract

Endpoint: `POST /v1/neural/generate`, existing pinned HTTPS over manually foregrounded USB loopback.

Existing keys remain: `model_id`, `text`, `hardware_verified:false`, `hardware_unit:"unverified"`. New optional keys:

- `completion_tokens`: integer count of the Core ML generator's non-EOS emitted token IDs, in the range 0..requested max tokens
- `model_elapsed_ms`: locally measured tokenizer+generation wall time, from `Qwen35InferenceMetrics.elapsedMs`
- `prefill_ms`: Core ML generator prefill measurement
- `generator_tokens_per_second`: the existing generator-specific decoding throughput metric; **not a total system speedup**
- `metrics_source:"on_device_coreml_generator"`: distinguishes actual on-device counts from guessed/estimated host-side tokens

No field asserts actual ANE hardware placement. No new networking, credentials, background service, logging or model download is introduced.

## Compatibility and validation

- Existing v10 JSON without optional fields remains accepted by the Windows client; token rate stays unknown.
- Optional telemetry is checked for finite, nonnegative numerical values; token count must be an integer 0..requested cap and must carry the recognized source.
- The iPhone implementation collects metrics from `Qwen35ModelAdapter.generateMeasured`, already present in v10. A source-only change cannot establish physical runtime success.
- The host logs structured timing/count data but does **not** log the prompt or generated text.
- The new wire format does not change the TLS identity, pinning, bearer validation or authenticated route.

## Release gates (pending)

1. Native Swift wire fixture and Python regression tests pass.
2. iOS app cross-compiles and links using the existing authorized free toolchain.
3. The user explicitly approves installation of a separately signed v11 candidate after reviewing the risks.
4. On physical iPhone, separately verify pinned HTTPS, wrong pin, wrong bearer, numeric token counts, validity under a 32-token cap, background shutdown, and no change to the original AI Chat app.
5. Only then publish a measured v11 dataset. No claim of CPU/GPU/ANE operation placement without a separate Instruments trace.

Current branch state is **experimental source proposal only** and must not be described as deployed.
