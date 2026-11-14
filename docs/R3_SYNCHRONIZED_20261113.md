> Arithmetic-only checkpoint. The [mixed-task follow-up](R3_MIXED_TASKS_20261113.md) adds exact-format requests and records both-task warmups. Datasets remain separate.

# R3 synchronized, position-balanced replication

November 13, 2026. Research draft; fixed-task observations, not a general offloading or efficiency claim.

This replication addresses two limitations of the [earlier burst study](R3_IPHONE_BURSTS_20261113.md): staggered worker startup and a GPU condition fixed in the middle. The earlier observations are retained separately and are not pooled into this dataset.

## Protocol

Four spawned Windows workers first announce readiness. A shared event releases them to target a common start scheduled 200 milliseconds ahead. Each worker hashes a fixed 256 KiB buffer for five seconds and records its actual start/end offsets relative to the scheduled time.

At scheduled start plus 300 milliseconds, the parent begins four sequential fixed arithmetic requests. It records per-request timing and checks the answer in memory. Every request must fall inside the intersection of all four recorded worker intervals. A latest worker start more than 50 milliseconds late fails the window. This is measured OS scheduling, not a real-time guarantee.

All six permutations of CPU, GPU, and iPhone inference occur once, with a no-inference baseline before and after each round (seven baselines in total). Each condition occupies each position twice. The order is deterministic, not randomized. One warmup precedes each AI window outside measured work. Resident models are not forcibly unloaded; unrelated services are not stopped.

Both Ollama's processor column and loaded-model API are checked before and after every Windows AI window. CPU must report 100% CPU and zero model VRAM; GPU must report 100% GPU and positive model VRAM; the expected model digest must match. These are runtime-reported placement snapshots, not continuous hardware utilization traces. The iPhone uses authenticated, pinned HTTPS through the trusted USB loopback forward.

## Results

All **25/25 windows**, **72/72 measured exact answers**, and **24/24 placement checks** passed. All **100 worker intervals** validated, and every measured AI request completed inside the four workers' common compute interval. Eighteen single-request warmups passed. A preceding five-window synchronized pilot passed 12 measured requests and is not pooled here.

| Condition | Windows | Requests | Median host MiB/s | Median request seconds | Median burst seconds | Median nearby-baseline change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No inference | 7 | 0 | 6370.254 | - | - | - |
| Windows CPU | 6 | 24 | 5666.553 | 0.31267 | 1.25117 | -10.88% |
| Windows GPU | 6 | 24 | 5869.573 | 0.37465 | 1.53269 | -7.49% |
| iPhone Core ML | 6 | 24 | 6312.791 | 0.79331 | 3.22004 | -0.70% |

For each round, reference throughput is the mean of its preceding and following baseline. A condition's change is `100 * (condition_rate / reference_rate - 1)`; the table reports the median of six per-round changes, not the ratio of overall medians. Adjacent rounds share baseline observations.

Within rounds, iPhone versus CPU host throughput had a median difference of **+11.02%**, ranging from **+6.51% to +17.10%**; all six rounds favored iPhone for host hashing throughput. The iPhone responded more slowly. Baseline throughput ranged from 6302.630 to 6413.527 MiB/s, a 1.74% spread relative to its median. No outlier was excluded.

Maximum within-window worker-start spread was **0.543 ms**. The latest worker start relative to the shared schedule was **0.630 ms**. These describe this replication's recorded starts; they are not guarantees for another machine or run.

Windows emitted three tokens per request; iPhone emitted two. Median summed request wall time occupied 25.0% of the five-second window for CPU, 30.7% for GPU, and 64.4% for iPhone. Those fractions include transport/runtime overhead, not hardware utilization.

## Reproducibility

- [Synchronized runner](../client/r3_sync_burst_workload.py)
- [25 numeric observation windows](../results/r3_synchronized_permutations_20261113.json), including all 72 request timings, 100 worker intervals, and 24 placement snapshots
- [Synchronization checks](../tests/test_r3_sync_workload.py), [published-evidence checks](../tests/test_r3_sync_published.py), and [private-output checks](../tests/test_r3_sync_reports.py)

With the existing dependencies, from repository root:

    python client/r3_sync_burst_workload.py
    python -m unittest discover -s tests -v

The runner defaults to a dry plan, excludes the phone unless explicitly selected, and requires a new report outside the repository. The suite includes a short local CPU-only spawn/barrier check; it does not require inference services or an iPhone.

For an optional short Windows pilot in PowerShell:

    $env:NANO_R3_PRIVATE_DIR = Join-Path $env:USERPROFILE 'nano-r3-private'
    python client/r3_sync_burst_workload.py --execute --targets baseline,windows_cpu,windows_gpu_candidate --runs 1 --requests 4 --report "$env:NANO_R3_PRIVATE_DIR/sync-windows.json"

For the full replication, first load `NANO_USB_TLS_PIN` and `NANO_USB_BEARER` privately using your existing protected credential method. Keep the secure iPhone service foregrounded and the trusted USB forward active, then run:

    python client/r3_sync_burst_workload.py --execute --targets baseline,windows_cpu,windows_gpu_candidate,iphone_usb_coreml --runs 6 --requests 4 --report "$env:NANO_R3_PRIVATE_DIR/sync-iphone.json"

Use one round for a pilot or all permutations of the selected AI targets. With three AI targets, the complete design uses six rounds and 25 windows. Never put credentials in command arguments, shared logs, or Git. The runner does not install or configure the phone, certificates, or USB forward.

The public file is adapted from the measured private runner only for portable import/repository paths and its module description. The dataset preserves hashes of the measured runner, its R3 dependency, and its source report. The adapted public file is not claimed to have the measured runner's hash.

## Interpretation limits

The fixed-task throughput/latency trade-off persisted after synchronization and position balancing. There are still only six host-throughput observations per AI condition, serial conditions, shared baselines, and deterministic ordering. The 24 requests per condition are not 24 independent host-throughput observations. Identical prompts can benefit from caching; thermals, background load, and resident model state remain possible influences.

Equal request count and exact-answer correctness do not imply equal generated tokens, equal model quantization, or equal numerical work. No general application-productivity gain, sustained saturation, independent ANE trace, or total-system energy benefit was established.

The late-start guard stops issuing requests when less than 1.25 seconds remains. It does not cancel an in-flight request at a hard deadline; inherited network timeouts apply. Barrier failures and overruns stop the run and produce an incomplete report.

Tracking: [issue #4](https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4), [draft PR #5](https://github.com/Nanodagr8/nano-coreml-usb-bridge/pull/5).
