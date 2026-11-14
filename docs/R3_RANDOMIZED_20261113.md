# R3 preregistered randomized-order replication

November 13, 2026. Custom research study, not an MLPerf result or a general offloading/efficiency claim.

The preceding [mixed-task study](R3_MIXED_TASKS_20261113.md) used deterministic condition ordering. This replication shuffles the six condition permutations with one public seed while preserving balanced positions, synchronized workers, task sequence, and quality checks. Earlier data are not pooled.

## Registration and protocol

The [public preregistration](https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4#issuecomment-6854803471) preceded the full run. The protocol was locked locally before a separate five-window pilot. That pilot passed 12 measured requests and six warmups and is not pooled here.

- Public order seed: **3875528134**
- [Exact registered protocol](../results/r3_randomized_protocol_20261113.json)
- Protocol SHA-256: `2212fcadb78d8e2631026ff40bd75a1354fb95d30f75b9054fa7192398b19b3a`
- Primary outcome: six per-round iPhone/CPU host-throughput ratios, expressed as percent differences, and their median.
- Secondary outcomes: throughput relative to surrounding baselines, per-task latency, correctness, worker overlap, and reported placement.
- No pooling, outlier removal, or automatic repeat after a failed full run. The measured full run completed on its first attempt.

Each AI window issues arithmetic, format, arithmetic, format. Both fixed tasks receive a warmup outside the measured window. Four spawned workers announce readiness and target one shared start 200 milliseconds ahead, then hash a fixed 256 KiB buffer for five seconds. AI requests begin at scheduled start plus 300 milliseconds and must complete inside all four actual worker intervals.

All six condition orders occur once, each condition occupying each position twice. The permutation-to-round assignment is randomized with the registered seed; it is not six independent unconstrained random orders. Seven no-inference baselines bracket the rounds. Resident models and unrelated services are not forcibly unloaded/stopped.

The registered order is CPU/iPhone/GPU; iPhone/GPU/CPU; GPU/CPU/iPhone; CPU/GPU/iPhone; GPU/iPhone/CPU; iPhone/CPU/GPU.

## Results

All **25/25 windows**, **72/72 measured answers**, **36/36 warmups**, **100 worker intervals**, and **24 placement snapshots** passed. Arithmetic and format each had 36 correct measured answers.

| Condition | Median host MiB/s | Median request seconds | Median burst seconds | Median nearby-baseline change |
| --- | ---: | ---: | ---: | ---: |
| No inference (7 windows) | 6262.467 | - | - | - |
| Windows CPU (6 windows) | 5682.665 | 0.30502 | 1.12538 | -8.51% |
| Windows GPU (6 windows) | 5906.692 | 0.37611 | 1.46145 | -5.20% |
| iPhone Core ML (6 windows) | 6264.038 | 0.71023 | 2.89370 | +0.41% |

The registered primary result was **+9.77%** median iPhone-versus-CPU host throughput. All six differences were positive: +8.3145%, +9.7174%, +13.5626%, +10.6396%, +9.7702%, +9.7747%. This is a within-study descriptive result, not a population effect estimate.

Nearby-baseline change is `100 * (condition_rate / mean(preceding_baseline, following_baseline) - 1)`, summarized by the median of six changes. It is not a ratio of overall medians; adjacent rounds share controls. Baselines ranged from 6080.738 to 6322.407 MiB/s (3.86% of baseline median).

| Condition | Task | Correct requests | Median request seconds | Completion tokens |
| --- | --- | ---: | ---: | ---: |
| Windows CPU | Arithmetic | 12/12 | 0.32554 | 3 |
| Windows CPU | Format | 12/12 | 0.24707 | 2 |
| Windows GPU | Arithmetic | 12/12 | 0.41872 | 3 |
| Windows GPU | Format | 12/12 | 0.31742 | 2 |
| iPhone Core ML | Arithmetic | 12/12 | 0.82872 | 2 |
| iPhone Core ML | Format | 12/12 | 0.61888 | 1 |

Maximum within-window worker-start spread was **0.549 ms**; latest worker start relative to schedule was **0.646 ms**. Every measured AI request completed in the common worker interval.

The iPhone preserved more host hashing throughput while responding more slowly for both tasks. This repeats the fixed-task trade-off under registered randomized round ordering. No outlier was excluded.

## Reproduce and verify

- [Runner](../client/r3_randomized_mixed_workload.py)
- [Allowlisted numeric evidence](../results/r3_randomized_mixed_20261113.json): all measured requests, warmups, worker intervals, placement snapshots, timing/provenance, registration link, and recomputable primary/secondary summaries
- [Protocol checks](../tests/test_r3_randomized_protocol.py), [worker checks](../tests/test_r3_randomized_barrier.py), [report guards](../tests/test_r3_randomized_reports.py), [evidence checks](../tests/test_r3_randomized_published.py)

With the existing dependencies, from repository root:

    python client/r3_randomized_mixed_workload.py
    python -m unittest discover -s tests -v

Default behavior is a dry plan excluding the phone. Live execution requires the explicit registered target list. The suite uses short CPU-only worker checks with mocked inference, without a live iPhone or inference service.

For a new live reproduction, privately load your existing TLS pin and bearer into `NANO_USB_TLS_PIN` and `NANO_USB_BEARER`. Keep the secure phone service foregrounded and the trusted USB loopback forward active. In PowerShell:

    $env:NANO_R3_PRIVATE_DIR = Join-Path $env:USERPROFILE 'nano-r3-private'
    python client/r3_randomized_mixed_workload.py --execute --targets baseline,windows_cpu,windows_gpu_candidate,iphone_usb_coreml --runs 1 --requests 4 --report "$env:NANO_R3_PRIVATE_DIR/registered-pilot.json"

After a successful pilot, six rounds reproduce the full registered design:

    python client/r3_randomized_mixed_workload.py --execute --targets baseline,windows_cpu,windows_gpu_candidate,iphone_usb_coreml --runs 6 --requests 4 --report "$env:NANO_R3_PRIVATE_DIR/registered-full.json"

Reports must be new and outside the repository. Never put credentials into command arguments or shared logs. No installation, certificate/key modification, or USB-forward setup is performed.

The protocol file is byte-for-byte identical to the locked manifest. Its Git attributes disable line-ending conversion. The runner refuses a changed protocol. A new experimental design needs a separate protocol and registration; editing this manifest does not reproduce this study.

The public runner adapts the measured private runner only for portable imports, repository/protocol paths, and module description. The dataset records separate measured-runner and source-report hashes. It does not equate the adapted public file's hash with the measured runner.

## Remaining limits and guidance

There are six host-throughput windows per AI condition, serial measurements, shared baselines, and two repeated short prompts. The 24 requests per condition are not 24 independent host-throughput observations. Caching, thermals, background load, and resident model state remain possible influences. Equal request count does not imply equal generated tokens, weight quantization, or numerical work.

Ollama snapshots are runtime-reported placement before/after Windows windows, not continuous independent utilization. There is no ANE operator trace, total-system energy measurement, sustained saturation, or broad task-quality coverage. Request wall time is not hardware utilization. The late-start guard does not cancel in-flight requests at a hard deadline; inherited network timeouts apply.

Blocking and randomization are informed by [NIST experimental-design guidance](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm). Quality/reproducibility principles are informed by [MLPerf rules](https://github.com/mlcommons/inference_policies/blob/master/inference_rules.adoc). This custom protocol is not MLPerf-compliant benchmarking and carries no MLPerf result claim.

Tracking: [issue #4](https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4), [draft PR #5](https://github.com/Nanodagr8/nano-coreml-usb-bridge/pull/5).
