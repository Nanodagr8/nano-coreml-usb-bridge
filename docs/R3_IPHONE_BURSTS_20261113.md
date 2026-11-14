> Earlier burst study. See the [synchronized, position-balanced follow-up](R3_SYNCHRONIZED_20261113.md) for the later replication. Datasets are separate.

# R3 physical iPhone burst comparison

November 13, 2026. Research draft, not a general speedup or efficiency claim.

The physical iPhone served authenticated, pinned-HTTPS Core ML inference over USB while Windows performed a fixed SHA-256 workload. The placement-checked replication completed **25/25 windows and 72/72 correct measured requests**, with **24/24 matching Windows placement snapshots**.

## Protocol and measurements

- Four Windows background worker processes each hash a fixed 256 KiB buffer for five seconds.
- Each AI window contains four sequential requests for the same fixed arithmetic task. Correctness is checked in memory; prompts and answer text are not saved.
- Six rounds alternate CPU/GPU/iPhone and iPhone/GPU/CPU. Seven no-inference baselines bracket the rounds. This balances CPU/iPhone early and late positions but always leaves GPU in the middle.
- One warmup request per AI window runs outside measured host work: 18 warmups in the replication.
- Windows conditions use the same installed model digest. Before and after each Windows window, both the loaded-model API and Ollama's processor column must match the requested condition. CPU reports zero model VRAM; GPU reports positive model VRAM and 100% GPU.
- iPhone status must be ready through the pinned, authenticated loopback service. Per-request metrics must identify the on-device Core ML generator.
- Baseline means no new inference request in that window. It does not unload resident models or stop unrelated services.
- A separate five-window pilot completed 12 correct requests before the replication. Its observations are not pooled into the published replication dataset.

| Condition | Workload windows | AI requests | Median host MiB/s | Median request seconds | Median burst seconds | Median nearby-baseline change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No inference | 7 | 0 | 6341.601 | - | - | - |
| Windows CPU | 6 | 24 | 5535.132 | 0.33446 | 1.33834 | -12.02% |
| Windows GPU | 6 | 24 | 5875.641 | 0.39141 | 1.57787 | -7.63% |
| iPhone Core ML | 6 | 24 | 6363.171 | 0.79272 | 3.22145 | +0.05% |

For each round, reference throughput is the mean of its preceding and following baseline. Each condition's change is `100 * (condition_rate / reference_rate - 1)`; the table reports the median of six changes. This is not the ratio of overall medians. Adjacent rounds share baseline observations.

iPhone/CPU host-throughput ratios within rounds had a median difference of **+15.69%**, ranging from **+11.96% to +28.91%**. Every round favored iPhone for host hashing throughput, while iPhone request latency was slower. CPU's changes against nearby baselines ranged from -27.93% to -11.65%; GPU's ranged from -13.42% to -5.28%; iPhone's ranged from -7.09% to +3.18%. No outlier was removed.

Baseline throughput ranged from 6237.811 to 6427.691 MiB/s, a 2.99% spread relative to its median.

## What the result supports

In this fixed task on this setup, delegating inference to the phone preserved more Windows hashing throughput at the cost of slower responses. The result is exploratory and task-specific. It does not establish a general advantage for games, rendering, development workloads, or total-system energy.

Windows emitted three tokens per request and iPhone emitted two. This is equal application request count and exact-answer correctness, not equal token count, matched weight quantization, or equivalent numerical work.

Request wall time occupied median fractions of 26.8% (CPU), 31.6% (GPU), and 64.4% (iPhone) of the five-second window. These fractions include runtime and transport overhead; they are **not hardware utilization measurements**.

## Reproduce or inspect without hardware

- [Portable burst runner](../client/r3_burst_workload.py)
- [25 allowlisted numeric observation windows](../results/r3_iphone_placement_bursts_20261113.json)
- [Burst controls](../tests/test_r3_burst_workload.py), [placement checks](../tests/test_r3_burst_placement.py), [published-evidence checks](../tests/test_r3_burst_published.py)

From repository root, with the existing dependencies available:

    python client/r3_burst_workload.py
    python -m unittest discover -s tests -v

The default is a dry run and excludes the phone. The public runner adapts the measured private runner only for portable imports, private report paths outside the repository, and exclusive report creation. The dataset records hashes of the measured runner, its R3 dependency, and its source report. It does not imply the adapted public file has the measured runner's hash.

For an optional short Windows pilot in PowerShell:

    $env:NANO_R3_PRIVATE_DIR = Join-Path $env:USERPROFILE 'nano-r3-private'
    python client/r3_burst_workload.py --execute --targets baseline,windows_cpu,windows_gpu_candidate --runs 1 --requests 4 --report "$env:NANO_R3_PRIVATE_DIR/windows-burst.json"

To reproduce the physical-iPhone replication, first load `NANO_USB_TLS_PIN` and `NANO_USB_BEARER` privately using your existing protected credential method. Keep the installed service foregrounded and the trusted USB forward active. Then use:

    python client/r3_burst_workload.py --execute --targets baseline,windows_cpu,windows_gpu_candidate,iphone_usb_coreml --runs 6 --requests 4 --report "$env:NANO_R3_PRIVATE_DIR/iphone-burst.json"

Report files must be new and outside the repository. No credentials belong in command arguments, Git, or shared logs. The runner does not install, sign, change certificates, or configure a USB forward.

## Remaining limits

There are six host-throughput observations per AI condition, not 24 independent throughput observations. Repeated identical prompts may benefit from caching. Conditions are serial; GPU is always in the middle. Workers are not synchronized by a startup barrier. Resident model state, thermals, background services, and drift remain possible influences.

The runner refuses to start another request with less than 1.25 seconds left and stops on wrong answers or an overrun. This is not a hard deadline for an in-flight call: inherited network timeouts still apply. It logs incomplete reports as incomplete and does not silently discard them.

Ollama snapshots attest its reported placement before/after Windows windows, not continuous independent hardware utilization. No ANE operator trace, sustained saturation, paired power measurement, or cross-device quantization equivalence was collected.

Earlier [Windows-only pilots](R3_SYSTEM_WORKLOAD_PILOT_20261113.md) and issue comments remain historical evidence and are not concurrent controls for this dataset. Tracking: [issue #4](https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4).
