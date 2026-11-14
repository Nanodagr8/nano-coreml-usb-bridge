# Registered native rebuild + inference results

The native-build comparison milestone is complete after a short pilot and three separately registered attempts. The first two stopped at their declared gates and are retained without primary estimates. Only the complete observer-corrected attempt supplies the registered comparison. This measures Windows-controlled WSL application compilation/linking during bounded inference, extending the earlier typecheck study.

The primary median paired native-build time reduction with iPhone versus Windows CPU inference was **+4.24%**, with 5/6 paired rounds favoring iPhone. The registered conditional 95% percentile-bootstrap interval is **[-3.95%, +12.57%]**. The descriptive conditional interval spans zero, so this session does not establish a native-build advantage.

| Condition | Native jobs | Median native build (s) | Median AI request (s) |
| --- | ---: | ---: | ---: |
| baseline | 7 | 12.515286 | none |
| windows_cpu | 6 | 12.560846 | 0.327895 |
| windows_gpu_candidate | 6 | 11.781965 | 0.451640 |
| iphone_usb_coreml | 6 | 12.106583 | 0.804555 |

All 25 measured native jobs and 25 native warmups passed: ten fresh app objects, a new unsigned ARM64 iOS executable, correct link inputs, iOS 18.0 minimum/SDK 27.1 metadata, source integrity, unchanged 402 dependency inputs, live native-frontend witnesses and namespace isolation. All 36 measured answers and 36 AI warmups passed. All 24 reported CPU/GPU placement snapshots passed. The full run took 734.79 seconds within the fixed 1,200-second budget.

Baseline spread was 13.24% of its median. The six per-round reductions were +11.0921%, +14.0540%, -8.3015%, +7.6484%, +0.3955%, +0.8396%.

## Design and interpretation

All six CPU/GPU/iPhone condition permutations occur once in a seeded shuffled order; each condition occupies each position twice. Baselines bracket rounds. Every measured job gets an immediately preceding unmeasured native rebuild. The primary value is the median of six 100*(CPU seconds - iPhone seconds)/CPU seconds values, not a ratio of overall medians.

The 10,000-resample percentile interval (seed 20261113) resamples paired-round reductions. It assumes exchangeable rounds and is descriptive within this one session. Serial/carryover effects, thermal state, background load and between-session/system uncertainty are not covered. No outliers were excluded from the complete corrected run. The two stopped registrations, pilot and calibrations are retained separately and are not pooled with its outcome. No failed registration was resumed or overwritten. This is not independent external replication.

The job forces all ten frozen NANO v11 Swift app objects and linking to run, using cached third-party dependencies, Swift 6.4.2, four build workers and debug-info-format none. Source commit is 8e2087e4ff838970e2346e6520be87af8b9aed7c. Compiler bookkeeping and module cache are retained between jobs. The original cache project, SDK and toolchain are read-only inside isolated build namespaces; measured dependency object/module inputs are hashed before and after each job.

A live swift-frontend process containing the frozen source path is witnessed before inference starts. Both requests must finish at least 0.25 seconds before the conservative earliest build finish, using Windows launch-relative offsets and Linux native-build duration without equating clock epochs. This proves pipeline/process overlap, not continuous CPU/GPU/ANE operator placement.

Two short repeated exact-answer tasks (arithmetic and formatting), a 32-token output cap and warmed model contexts limit the scope. Matching answers and request counts do not mean identical model weights, numerical work, output tokens, quantization or tokenization. Ollama reports placement; the iPhone uses its existing pinned, authenticated foreground USB service. There is no ANE trace, power/energy or broader coding-assistant-quality measurement. Native timings must not be pooled with or substituted for the earlier typecheck results.

This is a warm-cache forced application rebuild and link. It is not a clean build of all dependencies, installable bundle/resource/signing verification, deployment or device runtime test. The separate dirty foreground-awake edits are excluded. No installs, reboot, signing, deployment or key/certificate changes occurred. After the first connection failure, only the existing USB forward was refreshed with identical loopback bind/address/port arguments; listener policy was unchanged. The user then fully closed/reopened the existing NANO app and restored its secure foreground service. Pinned authenticated status passed from both Windows and Linux, followed by two correct recovery-smoke answers.

## Stopped attempts and implementation repair

The original registration stopped at window 22 with ConnectionResetError during the iPhone formatting request: 22 native jobs and 22 native warmups passed, but only 21 windows were fully valid, with 31 correct recorded measured answers and 32 correct AI warmups. No six-round primary estimate or confidence interval is reported for this prefix.

Following user-confirmed foreground-service recovery, a fresh build workspace and registration were used. That follow-up stopped at window 6 with a local observer RuntimeError before measured inference in that window. All six native jobs and six native warmups passed. The native frontend appeared at 10.357 seconds, beyond the controller observation cutoff of 10 seconds; the native build passed in 14.726 seconds. No primary estimate is reported.

The corrected controller uses the existing 45-second native-job deadline for its live-frontend observer. A regression test accepts a marker arriving at 10.5 seconds while preserving the 45-second cap. Artifact, source/dependency, exact-answer and 0.25-second conservative overlap requirements remain unchanged. A new registration, unique job labels and private report/status directory preserve all earlier records. The isolated follow-up build workspace is reused as a warm cache; this is not a new machine or independent external replication.

- [Original stopped protocol](../results/r3_native_concurrent_registered_protocol_20261113.json) and [stopped evidence](../results/r3_native_concurrent_registered_20261113.json)
- [Observer-stopped follow-up protocol](../results/r3_native_concurrent_followup_protocol_20261113.json) and [evidence](../results/r3_native_concurrent_followup_20261113.json)

## Calibration, reproduction and audit

The cold preparation, two preliminary warm engineering jobs (one failed reset), three corrected warm calibrations, and the five-job/ten-build feasibility pilot are retained separately. The reset was corrected before the pilot to retain output-file-map bookkeeping while forcing all app object files and the binary to be recreated. No unchanged failed full experiment was silently retried.

- [Complete corrected protocol](../results/r3_native_concurrent_corrected_protocol_20261113.json)
- [Complete corrected evidence](../results/r3_native_concurrent_corrected_20261113.json)
- [Pilot protocol](../results/r3_native_concurrent_pilot_protocol_20261113.json) and [pilot evidence](../results/r3_native_concurrent_pilot_20261113.json)
- [All calibration outcomes](../results/r3_native_concurrent_calibrations_20261113.json)
- [Native logical job specification](../results/r3_native_concurrent_source_spec_20261113.json)
- [Corrected controller](../client/r3_native_concurrent_v2.py) and [retained original controller](../client/r3_native_concurrent_study.py), [bounded native worker](../client/r3_native_job.py), [private manifest preparer](../client/r3_native_prepare.py), [analyzer](../client/r3_native_concurrent_analyze.py)
- Public preregistration: https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4#issuecomment-6871956200
- Protocol SHA-256: f0e67dd8ff07b32ecb2d00f20e358ab2058d2c3df2ca9cf60adc874e9690f52a
- Retained private full report SHA-256: 3da074c161eb2f0a0ea3f98c7bc3837c4d02e58cfafe4ade36b51cfa56c49e46

Offline review uses the existing Python test dependencies and standard-library analysis:

    python -m unittest discover -s tests -v
    python client/r3_native_concurrent_v2.py
    python client/r3_native_concurrent_analyze.py results/r3_native_concurrent_corrected_20261113.json

To perform a separate reproduction, first create a new qualified offline workspace with the existing native-build runner and your authorized preexisting SDK/cache (see [native qualification](R3_NATIVE_BUILD_QUALIFICATION_20261113.md)). Then create its external private manifest:

    python3 client/r3_native_prepare.py --workspace /private/qualified-workspace

This outputs only hashes/counts; study-job.json contains private paths and stays local. Configure the same five private controller fields described in the [application reproduction guide](R3_APPLICATION_REPRODUCE_20261113.md): job_manifest_linux, job_manifest_sha256, linux_runner (the new native worker), linux_phase_root, wsl_distribution. Set NANO_R3_PRIVATE_DIR and NANO_SWIFT_STUDY_CONFIG externally; load the protected TLS credentials locally without printing them.

Default controller mode is dry. Live execution requires --execute, --plan, --plan-sha256 and a new private --report path. Different physical workspace paths require --reproduce and disclosure as a new reproduction. Register the environment/order/analysis before measuring. The published 45-second per-build watchdog and 1,200-second budget checked between conditions remain explicit; a started request/build remains governed by its own timeouts. Never overwrite failed reports or silently retry a failed registered run.

    python client/r3_native_concurrent_v2.py --execute --reproduce --plan YOUR_REGISTERED_PLAN --plan-sha256 YOUR_PLAN_SHA256 --report PRIVATE_OUTPUT/report.json

No SDK, model weights, compiled executable, private machine config, credentials or signing assets are distributed. The public preparer reconstructs the private manifest format; measured controller/worker bytes and exact registered protocol bytes are preserved through Git export.
