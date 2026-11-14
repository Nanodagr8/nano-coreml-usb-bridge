> Historical Windows-only checkpoint. For completed physical-iPhone measurements, see the [placement-checked burst follow-up](R3_IPHONE_BURSTS_20261113.md).

# NANO R3 — system-level host productivity pilot (Windows only)

**Experimental date:** November 13, 2026. **Status:** preliminary host-only pilot, **not** offloading proof.

## Research question

Can the Windows PC complete more unrelated work while inference executes on an authenticated USB iPhone, rather than running inference on its own CPU or integrated GPU?

The R3 harness measures **host background compute throughput concurrent with AI**, plus end-to-end AI request latency and a narrow exact-response correctness check. The current results include **only Windows CPU and Windows integrated GPU inference**; the iPhone condition has not yet been measured.

## Windows exploratory pilot results

The host's background workload is a fixed SHA-256 hash of a 256 KiB buffer executed in separate bounded Python processes. The workload ran for 5 seconds per condition. The same installed Qwen3.5 0.8B GGUF Q8_0 model produced the exact required synthetic answer in every Windows AI trial. No response text was saved.

| Background workers | Condition | Runs | Median background throughput (MiB/s) | Median AI wall time (s) | Exact answers |
| ---: | --- | ---: | ---: | ---: | ---: |
| 2 | No AI | 2 | 3,487.166 | — | — |
| 2 | Windows CPU inference | 1 | 3,447.194 | 0.28989 | 1/1 |
| 2 | Windows integrated GPU inference | 1 | 3,524.519 | 0.39592 | 1/1 |
| 4 | No AI | 3 | 6,339.326 | — | — |
| 4 | Windows CPU inference | 2 | 6,116.608 | 0.31044 | 2/2 |
| 4 | Windows integrated GPU inference | 2 | 6,068.285 | 0.42076 | 2/2 |

All **11 measurement windows completed** (6 Windows AI request completions; 5 baselines). Each background worker completed within its configured five-second compute window, and all AI requests finished while background work was running.

### Interpretation

- There is **no demonstrated host-productivity gain** from CPU versus GPU inference in these exploratory samples. Differences are small relative to expected trial variability.
- The short exact-answer workload generated only a few tokens. Its latency cannot be compared directly with earlier R2 trials producing 22 tokens or R1 iPhone v11 smoke tests producing 32 tokens.
- We have **not yet measured the iPhone condition** under concurrent Windows background work, so the central R3 offloading question remains open.
- 1–2 AI trials per condition and 2–3 background-only controls are **insufficient** for confidence intervals or statistically strong claims.
- Hashing MiB/s is an artificial host-work proxy, not a validated representation of games, rendering, development tools, or other real applications.
- There are no host+iPhone power measurements, no battery or thermal profiling, no Core ML ANE operator trace, and no cross-device output-quality equivalence claim.
- The Windows Ollama model uses Q8_0 while the iPhone Core ML model uses different weight packaging/quantization. Equal parameter counts do not mean equal numerical work.

## Engineering work and reproducibility

- [R3 source](../client/r3_system_workload.py): defaults to dry run; opt-in bounded Windows CPU/GPU or, when foreground-ready with local credentials, USB iPhone target.
- [11 sanitized observations](../results/r3_windows_host_workload_pilots_20261113.json): a strict public field allowlist. No user prompts, generated output, bearer tokens, key material or device identifiers.
- [R3 regression tests](../tests/test_r3_system_workload.py) and [public-dataset tests](../tests/test_r3_published.py).

From repository root:

    python client/r3_system_workload.py
    python -m unittest discover -s tests -v

For an optional Windows-only pilot, using an existing local Ollama model and a private output directory:

    python client/r3_system_workload.py --execute --targets baseline,windows_cpu,windows_gpu_candidate --runs 1 --seconds 5 --workers 2 --task arithmetic --report <private-r3-directory>/pilot.json

The environment variable \`NANO_R3_PRIVATE_DIR\` should point to the same private directory as the new report file, which must not exist. Use your operating system's normal path syntax. No network beyond local Ollama is required, and the iPhone is untouched unless the target is explicitly selected. Never place credentials in command arguments.

## Next gates

1. With NANO AI **foreground-ready** and its secure USB service running, verify pinned HTTPS and authenticate without printing secrets. Run the iPhone target under the same five-second host-work window.
2. Use repeated and alternating condition orders, temperature/CPU-load checks, response correctness and equivalent application tasks. Do not rank model-token throughput across unlike weight formats.
3. Report host-work distribution, AI end-to-end latency, invalid or delayed results and failure cases. Add calibrated **total-system energy** measurement before claiming efficiency gains.
4. Independently determine real ANE/CPU/GPU operator execution; a Core ML preferred compute policy is not evidence of hardware placement.

Study tracking: [GitHub R3 issue #4](https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4).
