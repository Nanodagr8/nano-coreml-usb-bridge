# R4 sampled foreground-service continuity and safe failure reporting

The scoped operational-readiness milestone is complete. The existing pinned USB service passed **13 authenticated ready checks and 12 exact-answer requests** over 729.905 seconds, including six idle intervals totaling 720.002 seconds without intervening requests. No failure was recorded. Protected configuration remained unchanged.

This qualifies the sampled observations in this session. It does **not** certify continuous uptime, unattended/background persistence, a reliability probability, the installed app build, or the wake-lock implementation in PR #6. Foreground/screen state was not instrumented; the operator was required to keep the existing app awake and foregrounded.

## Locked procedure and result

Each of six rounds performs pinned/authenticated ready -> arithmetic -> formatting -> pinned/authenticated ready -> 120 seconds with no requests. One final ready check follows the sixth idle interval. The two fixed tasks require exact answers, no more than 32 output tokens, the expected model identity and positive finite on-device Core ML metrics. Raw prompts, responses, device identifiers, credentials and exception messages are not serialized.

The short pilot separately passed three ready checks and two exact-answer requests. Its observations are not pooled into the sampled session.

| Field | Recorded outcome |
| --- | ---: |
| Authenticated ready checks | 13/13 |
| Exact-answer generation requests | 12/12 |
| Completed idle intervals | 6/6 |
| Total observed idle seconds | 720.002049 |
| Total observation seconds | 729.904771 |
| Median generation wall seconds | 0.796032 |
| Retry/recovery actions inside observation | 0 |
| Protected credential configuration changed | no |

The median wall time is an operational diagnostic, not a comparative speed benchmark. The two repeated short tasks do not evaluate broader coding quality or match numerical work across backends.

## Host safeguards

- The existing client verifies certificate SPKI before sending any HTTP credentials or prompt.
- Pin, authorization, TLS, timeout, reset, model, answer and metric failures stop the observation immediately. No alternative inference backend, automatic retry, pin replacement or forward restart is attempted.
- Error reports contain fixed diagnostic codes and phase/task labels; arbitrary exception text and response fields are discarded.
- Exclusive report creation and atomic checkpoints preserve completed observations after interruption.
- A separate supervisor enforces the 900-second host execution budget, followed by at most ten seconds of owned-child termination/reaping cleanup. This does not guarantee cancellation of computation already dispatched on the phone.
- Forced supervisor-stop duration can be derived from recorded UTC endpoints and is labelled separately from normal worker-monotonic timing.
- Tests simulate pin/auth/transport failures and host budget expiry. They prove host failure handling; no physical disconnect or bad-credential injection was performed during this live observation.

## Failure triage

| Fixed diagnostic family | Meaning and next step |
| --- | --- |
| pin_rejected | Stop; verify the intended existing service and private identity locally. Do not bypass pinning. |
| authorization_rejected | Stop; check the existing protected configuration locally. No secret should be pasted into a report. |
| connection_refused/reset, transport_timeout, tls_failed | Preserve the checkpoint; inspect cable, existing loopback forward and foreground service. A listening port alone is not authenticated readiness. |
| model_not_ready / model_identity_invalid | Keep the intended existing model/service state explicit; do not silently route to another backend. |
| answer/telemetry/tokens/metrics invalid | Do not count the request as a pass; inspect the fixed task and protocol. |
| study_budget_expired / worker_process_failed | Host sampling stopped; retain the checkpoint and private worker log. A new attempt needs a new output path and declared plan. |

## Evidence and reproduction

- [Locked observation plan](../results/r4_foreground_soak_protocol_20261113.json), SHA-256 3d3231586bcb3740c55baf0443a1472fcce1a69f6d4350e9c7e218defd1fa2b5.
- [Sampled-session evidence](../results/r4_foreground_soak_20261113.json).
- [Separate pilot plan](../results/r4_foreground_pilot_protocol_20261113.json) and [pilot evidence](../results/r4_foreground_pilot_20261113.json).
- [Runner and host supervisor](../client/r4_foreground_reliability.py), [analyzer](../client/r4_continuity_analyze.py).
- Public registration: https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4#issuecomment-6872570454.
- Private raw report SHA-256: 4a66f92a06bbbaf867d2c83ad3eed91c7956f00c45580330fe422188937e3b87.

With the already installed test dependencies:

    python -m unittest discover -s tests -v
    python client/r4_foreground_reliability.py
    python client/r4_continuity_analyze.py results/r4_foreground_soak_20261113.json

Dry mode creates no worker and sends no requests. A separate live reproduction requires the intended existing foreground service and protected NANO_USB_TLS_PIN/NANO_USB_BEARER, loaded locally without printing them. Register the plan first. Use --execute --plan PLAN --plan-sha256 SHA --report NEW_PRIVATE_REPORT. The report must be outside this checkout; existing reports are never overwritten. The recorded plan and as-run runner bytes are preserved through Git export.

No app installation, signing, reboot, deployment, model download, certificate/key change, listener-policy change or recovery action was part of R4. The parallel wake-lock work was not modified or attributed to these observations.

## What remains

| Open gate | Why it remains open |
| --- | --- |
| Independent reproduction and review | This is the same operator/Windows/iPhone setup, not an external replication. |
| Broader native/Windows workloads, sustained AI and coding quality | Earlier native-build benefit remained inconclusive; these two short tasks and idle observations do not resolve it. |
| Controlled thermals and background load | No host/phone thermal or physical screen-state instrumentation was used. |
| Matched model weights/quantization/tokenization | Application-level answer agreement does not establish numerical equivalence. |
| Actual Core ML CPU/GPU/ANE placement | No independent operator trace was captured. |
| Combined host+iPhone energy | No power instruments or total-system energy measurement were used. |
| Wake-lock PR #6 runtime, disconnect/recovery and unattended reliability | Installed build and screen/foreground state were not attested; the earlier R3 connection failure remains relevant. |
| Bundle/resources, provisioning/signing, installation and device release validation | These are separate gates outside the current no-signing/no-install scope. |

The [R3 native-build result](R3_NATIVE_CONCURRENT_20261113.md) remains separate: +4.24% observed paired reduction with a conditional interval spanning zero. R4 adds sampled continuity evidence and bounded host diagnostics, not a new offloading, ANE, energy or release claim.
