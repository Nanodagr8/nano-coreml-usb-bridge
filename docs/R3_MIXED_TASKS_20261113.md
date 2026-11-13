# R3 synchronized mixed-task replication

November 13, 2026. Research draft. This extends the [arithmetic-only synchronized study](R3_SYNCHRONIZED_20261113.md) with an exact-format task. Datasets are separate and are not pooled.

## Protocol and quality gate

Each AI window measures the same sequence: **arithmetic, format, arithmetic, format**. The arithmetic task requires an exact numeric answer; the format task requires an exact uppercase word. Both fixed tasks are defined in the existing R3 task map. Answers are checked in memory and never saved.

Both tasks receive a warmup before each AI window, outside measured host work. A wrong warmup stops the run before that measured AI window. Wrong measured answers, late requests, worker failures, placement mismatches, or incomplete worker overlap also stop the run and produce an incomplete report.

Four Windows workers announce readiness, wait on a shared event, and target one scheduled start 200 milliseconds ahead. Each hashes a fixed 256 KiB buffer for five seconds and records its actual compute interval. Requests begin at scheduled start plus 300 milliseconds and must complete inside all four workers' common compute interval.

All six CPU/GPU/iPhone permutations occur once. Each condition occupies each position twice. Seven baseline windows bracket the rounds. Order is deterministic, not randomized. Resident models are not forcibly unloaded and unrelated services remain running.

Windows model digest and Ollama-reported placement are checked before and after each Windows AI window. The iPhone requires foreground-ready, authenticated pinned HTTPS over the existing trusted USB loopback forward.

## Results

All **25/25 windows**, **72/72 measured answers**, and **36/36 warmups** passed. Measured task totals were **36 arithmetic and 36 format**, all correct. All **100 worker intervals** and **24 placement snapshots** validated. A preceding five-window mixed-task pilot passed 12 measured requests and six warmups; it is not pooled here.

| Condition | Windows | Requests | Median host MiB/s | Median request seconds | Median burst seconds | Median nearby-baseline change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No inference | 7 | 0 | 6361.591 | - | - | - |
| Windows CPU | 6 | 24 | 5725.467 | 0.30202 | 1.12051 | -9.52% |
| Windows GPU | 6 | 24 | 5926.006 | 0.37530 | 1.48359 | -6.37% |
| iPhone Core ML | 6 | 24 | 6288.117 | 0.71161 | 2.92165 | -1.03% |

For each round, reference throughput is the mean of its preceding and following baseline. A condition's change is `100 * (condition_rate / reference_rate - 1)`. The table reports the median of six changes, not the ratio of overall medians. Adjacent rounds share baseline observations.

Within rounds, iPhone versus CPU host throughput had a median difference of **+10.51%**, ranging from **+7.21% to +12.03%**. All six rounds favored iPhone for host hashing throughput. iPhone responses were slower for both tasks. Baseline throughput ranged from 6200.323 to 6399.604 MiB/s, a 3.13% spread relative to its median. No outlier was excluded.

| Condition | Task | Correct requests | Median request seconds | Observed completion tokens |
| --- | --- | ---: | ---: | ---: |
| Windows CPU | Arithmetic | 12/12 | 0.31693 | 3 |
| Windows CPU | Format | 12/12 | 0.24140 | 2 |
| Windows GPU | Arithmetic | 12/12 | 0.42672 | 3 |
| Windows GPU | Format | 12/12 | 0.31566 | 2 |
| iPhone Core ML | Arithmetic | 12/12 | 0.83738 | 2 |
| iPhone Core ML | Format | 12/12 | 0.62642 | 1 |

Maximum within-window worker-start spread was **0.532 ms**; the latest worker start relative to schedule was **0.654 ms**. Every measured request completed inside the recorded common worker interval. These observations are not real-time scheduling guarantees.

Median summed request wall time occupied 22.4% of the five-second window for CPU, 29.7% for GPU, and 58.4% for iPhone. Wall time includes transport and runtime overhead; it is not a hardware-utilization measurement.

## Reproduce or audit

- [Mixed-task runner](../client/r3_mixed_burst_workload.py)
- [Numeric evidence](../results/r3_mixed_tasks_20261113.json): all measured request metrics, 36 warmups, 100 worker intervals, 24 placement snapshots, hashes, and recomputable summaries
- [Task checks](../tests/test_r3_mixed_suite.py), [barrier checks](../tests/test_r3_mixed_barrier.py), [output/failure checks](../tests/test_r3_mixed_reports.py), [published-evidence checks](../tests/test_r3_mixed_published.py)

With the existing dependencies, from repository root:

    python client/r3_mixed_burst_workload.py
    python -m unittest discover -s tests -v

The default is a dry plan with no phone access. The suite includes short local CPU-only worker checks with mocked inference; it does not require an inference service or iPhone.

For an optional Windows pilot in PowerShell:

    $env:NANO_R3_PRIVATE_DIR = Join-Path $env:USERPROFILE 'nano-r3-private'
    python client/r3_mixed_burst_workload.py --execute --targets baseline,windows_cpu,windows_gpu_candidate --runs 1 --requests 4 --report "$env:NANO_R3_PRIVATE_DIR/mixed-windows.json"

For a full physical-iPhone replication, privately load `NANO_USB_TLS_PIN` and `NANO_USB_BEARER` using your existing protected credential method. Keep the installed service foregrounded and the trusted USB forward active, then run:

    python client/r3_mixed_burst_workload.py --execute --targets baseline,windows_cpu,windows_gpu_candidate,iphone_usb_coreml --runs 6 --requests 4 --report "$env:NANO_R3_PRIVATE_DIR/mixed-iphone.json"

The mixed suite requires four requests per AI window. Use one round for a pilot or all permutations of selected AI targets. Reports must be new and outside the repository. Never place credentials in command arguments, Git, or shared logs. The runner does not install software or configure the phone, keys, certificates, or USB forward.

The public runner adapts the measured private runner only for portable import/repository paths and its module description. The dataset preserves hashes of the measured runner, its R3 dependency, and the source report. The adapted public file is not claimed to have the measured runner's hash.

## Limits

These remain two fixed, repeated, very short tasks, not a broad reasoning or natural-language quality benchmark. Exact-answer agreement and equal request counts do not imply matched quantization, generated tokens, numerical work, or task diversity. Caching remains possible.

There are six host-throughput observations per AI condition, not 24 independent throughput observations. Serial conditions, shared baselines, deterministic ordering, thermals, resident models, and background load remain possible influences.

Placement snapshots describe Ollama's reported allocation before/after Windows windows, not continuous independent hardware utilization. No sustained saturation, ANE operator trace, or total-system energy measurement was collected. The late-start guard does not impose a hard cancellation deadline on in-flight requests; inherited network timeouts apply.

The task-specific throughput/response-latency trade-off persisted across both tasks. No general application-productivity, offloading, or energy advantage is established. Tracking: [issue #4](https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4) and [draft PR #5](https://github.com/Nanodagr8/nano-coreml-usb-bridge/pull/5).
