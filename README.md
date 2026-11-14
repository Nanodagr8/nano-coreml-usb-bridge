# NANO CoreML USB Bridge

**Secure, USB-only Windows ↔ iPhone Core ML language-model inference — verified on physical hardware.**

NANO CoreML USB Bridge lets a Windows PC request AI-generated text from an iPhone running Qwen3.5-0.8B through Apple's Core ML. The host uses a trusted USB port forward and **pinned HTTPS**, checking the server's public key *before* sending its bearer token or prompt.

On **November 13, 2026**, the physical-device test succeeded: pinned HTTPS status, bad-certificate-pin rejection, bad-bearer rejection (HTTP 401), and bounded text generation (172 output characters). Read the [sanitized test transcript](docs/RESULTS.md).

## Verified versus outstanding

| Capability | Status |
| --- | --- |
| Local Qwen3.5-0.8B inference using Core ML | Verified |
| Windows ↔ iPhone HTTPS over paired USB | Verified |
| Certificate SPKI pin checked before HTTP credentials | Verified |
| Invalid pin and bearer rejected | Verified |
| Authenticated remote generation | Verified |
| Core ML cpuAndNeuralEngine *preference* | Reported |
| Actual Neural Engine operator placement | **Not measured** |
| Background service or unattended persistence | **Not implemented** |
| Public one-click iOS installer | **Not provided** |

This is a **research prototype**, not a commercial security audit or claim of being the first iPhone AI server.

## Repository

- [ios](ios) — Swift reference sources. Developers need their own iOS signing, TLS identity and certificate configuration; no signed IPA or model weights are included.
- [client](client) — Standalone Python host client that checks TLS certificate SPKI before sending credentials.
- [tests](tests) — Portable host-side security and protocol tests.
- [Architecture](docs/ARCHITECTURE.md), [Reproduction](docs/REPRODUCE.md), [Evidence](docs/RESULTS.md), [Security](SECURITY.md), [Research roadmap](docs/ROADMAP.md).

## Quick host-side tests

Requires Python 3.10+ and the free Python cryptography library.

    python -m pip install -r client/requirements.txt
    python -m unittest discover -s tests -v

To connect to your *own* running, foregrounded iPhone service, privately configure these environment variables:

- NANO_USB_TLS_PIN — base64-encoded SHA-256 of your server certificate SubjectPublicKeyInfo.
- NANO_USB_BEARER — your high-entropy 32–128-character ASCII bearer secret.
- NANO_USB_URL — optional; must be https://127.0.0.1:49443.

Then:

    python client/nano_usb_client.py status

Do not put credentials or certificates into Git. Follow [reproduction steps](docs/REPRODUCE.md).

## R1 research: Windows 0.8B benchmark checkpoint

We have added a guarded [R1 benchmark harness](client/r1_benchmark.py) and published a [sanitized Windows CPU/GPU exploratory dataset](results/r1_qwen35_08b_windows_exploratory.json), with a [results report](docs/R1_08B_WINDOWS_RESULTS_20261113.md). Both Windows conditions use Ollama Qwen3.5 0.8B Q8_0; the tests are **not** an iPhone comparison or a proven offloading speedup. GPU/CPU attribution comes from Ollama's reported PROCESSOR status; the iPhone's Core ML weight equivalence and ANE execution still require independent verification.

## R3 research: Windows host productivity during AI inference

The [preregistered randomized-order replication](docs/R3_RANDOMIZED_20261113.md) completed 25 windows, 72 correct measured answers, 36 correct warmups, 100 validated worker intervals, and 24 matching Ollama placement snapshots. Its public seed, condition order, primary outcome, and stop rules were registered before the full run.

The registered primary result was +9.77% median Windows host hashing throughput with iPhone inference versus CPU inference, with all six round differences positive. Median request latency was slower on iPhone (0.71023 s) than CPU (0.30502 s). These are fixed-task observations, not a general offloading or energy advantage.

The [registered runner](client/r3_randomized_mixed_workload.py) defaults to a dry plan and verifies the exact [protocol bytes](results/r3_randomized_protocol_20261113.json). [Numeric evidence](results/r3_randomized_mixed_20261113.json) includes task results, warmups, worker intervals, registration timing, and recomputable outcomes.

Earlier [deterministic mixed-task](docs/R3_MIXED_TASKS_20261113.md), [arithmetic-only synchronized](docs/R3_SYNCHRONIZED_20261113.md), [placement burst](docs/R3_IPHONE_BURSTS_20261113.md), and [Windows-only pilot](docs/R3_SYSTEM_WORKLOAD_PILOT_20261113.md) studies remain separate.

## R3 coding-validation milestone

Two separately registered sessions completed the frozen ten-source NANO Swift typecheck workload alongside bounded CPU/GPU/iPhone inference. The [application results and limitations](docs/R3_APPLICATION_RESULTS_20261113.md), [numeric evidence](results/r3_application_session2_20261113.json), and [reproduction guide](docs/R3_APPLICATION_REPRODUCE_20261113.md) keep each session separate. This completes the scoped coding-validation research gate; full app builds, independent replication, energy and actual ANE profiling remain open.

## Offline native build qualification

Two isolated offline workspaces compiled all ten frozen NANO v11 sources and linked new unsigned ARM64 iOS executables. See the [native build qualification](docs/R3_NATIVE_BUILD_QUALIFICATION_20261113.md) and [numeric evidence](results/r3_native_build_qualification_20261113.json). This uses cached dependencies and does not package, deploy or run the app on a device.

## Registered native build workload

The observer-corrected, publicly preregistered randomized study completed native recompilation/linking alongside explicit Windows CPU, GPU and iPhone inference. Two earlier stopped attempts remain separate. See the [native workload results, uncertainty and limitations](docs/R3_NATIVE_CONCURRENT_20261113.md) and [numeric evidence](results/r3_native_concurrent_corrected_20261113.json). This is separate from the earlier typecheck study and standalone native qualification.

## R4 sampled foreground continuity

The existing pinned service passed a bounded sampled-continuity session across six two-minute idle intervals. The [operational report and remaining gates](docs/R4_FOREGROUND_CONTINUITY_20261113.md) and [numeric evidence](results/r4_foreground_soak_20261113.json) distinguish these observations from continuous uptime, unattended operation and wake-lock runtime certification. The host runner stops safely on security/transport/quality errors and preserves partial checkpoints.

## Built on existing work

NANO Studios integrates [CoreML-LLM](https://github.com/john-rocky/CoreML-LLM) (MIT) and [Swift Transformers](https://github.com/huggingface/swift-transformers) (Apache-2.0). The USB interface uses concepts implemented by [pymobiledevice3](https://github.com/doronz88/pymobiledevice3); it is not included or modified here. Model weights and upstream dependencies retain their own respective licenses.

Please contribute reproducibility reports, security reviews, and measured CPU/GPU/ANE comparisons. See [CONTRIBUTING.md](CONTRIBUTING.md).
