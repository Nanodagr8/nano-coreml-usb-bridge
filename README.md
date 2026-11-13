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

## R2 research: balanced Windows CPU/GPU measurements

The [R2 30-trial study](docs/R2_WINDOWS_BALANCED_20261113.md) now includes 60 controlled Windows-only measurements on the **same Ollama Qwen3.5 0.8B Q8_0 model**, collected in six alternating CPU/GPU block pairs. The median observed wall time was **1.414 s CPU** vs **1.022 s integrated GPU**; the paired-block geometric-mean speed ratio was **1.390×** (descriptive bootstrap interval 1.328–1.447×). You can inspect [all 72 observations](results/r2_windows_08b_balanced_20261113.json), [the analysis](results/r2_windows_08b_paired_analysis_20261113.json), and the [bench source](client/r2_windows_balanced_benchmark.py). This is **not** a demonstrated Windows-to-iPhone offloading benefit or energy/ANE measurement.

## Built on existing work

NANO Studios integrates [CoreML-LLM](https://github.com/john-rocky/CoreML-LLM) (MIT) and [Swift Transformers](https://github.com/huggingface/swift-transformers) (Apache-2.0). The USB interface uses concepts implemented by [pymobiledevice3](https://github.com/doronz88/pymobiledevice3); it is not included or modified here. Model weights and upstream dependencies retain their own respective licenses.

Please contribute reproducibility reports, security reviews, and measured CPU/GPU/ANE comparisons. See [CONTRIBUTING.md](CONTRIBUTING.md).
