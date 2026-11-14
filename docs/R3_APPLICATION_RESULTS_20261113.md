# R3 real NANO coding-validation results

The scoped coding-validation research milestone is complete: two separately registered sessions, a public runner and private-path materializer, numeric evidence, uncertainty analysis and offline audit tests. Broader performance, release and hardware-profiling gates remain open.

The fixed job typechecks ten frozen NANO v11 Swift sources under the existing Windows-controlled WSL Swift 6.4.2 compiler and iPhoneOS27.1 SDK. This is source validation, not a signed app build or deployment. It does not evaluate AI-written code quality.

Each session uses all six permutations of CPU/GPU/iPhone inference once, with baseline jobs bracketing rounds. Each condition gets one immediately preceding unmeasured compiler warmup. Two short exact-answer tasks run during each AI-condition job. No measured attempts, failures or outliers were dropped. The five session-2 cache-calibration jobs (including the cold cache) are excluded as registered. The earlier pilot and synthetic hashing studies are separate.

| Session | Paired compiler-time reduction, iPhone vs CPU | Rounds favoring iPhone | Conditional 95% bootstrap interval | Baseline spread | Receipt to end |
| --- | ---: | ---: | ---: | ---: | ---: |
| session1 | +13.65% | 6/6 | [+7.76%, +25.68%] | 17.18% | 414.11 s |
| session2 | +16.00% | 6/6 | [+11.71%, +31.19%] | 32.42% | 373.10 s |

The primary statistic is the median of six per-round values 100*(CPU seconds - iPhone seconds)/CPU seconds. It differs from a ratio of the overall medians. The 10,000-resample percentile intervals resample whole paired-round reductions with seed 20261113. Session 1 uncertainty analysis is retrospective; session 2 specified the method before measurement. Rounds may have serial/carryover effects. These conditional intervals do not cover between-session, thermal, environment or cross-machine uncertainty; no pooled estimate is reported.

| Session | Condition | Compiler median (s) | AI request median (s) |
| --- | --- | ---: | ---: |
| session1 | baseline | 3.836938 | none |
| session1 | windows_cpu | 5.100647 | 1.094400 |
| session1 | windows_gpu_candidate | 4.140370 | 0.741600 |
| session1 | iphone_usb_coreml | 4.115830 | 0.806605 |
| session2 | baseline | 3.671464 | none |
| session2 | windows_cpu | 4.719223 | 1.129195 |
| session2 | windows_gpu_candidate | 3.971261 | 0.716070 |
| session2 | iphone_usb_coreml | 3.839728 | 0.822975 |

Both sessions passed 25 measured compiler jobs, 25 compiler warmups, 36 measured exact-answer requests, 36 AI warmups and 24 Ollama CPU/GPU placement snapshots: totals are 50 measured jobs, 50 compiler warmups, 72 measured answers, 72 AI warmups and 48 placement snapshots. Every source hash and conservative process-overlap gate passed. The registered full runs remained within their 600-second budgets.

Session 2's baseline spread was 32.42% of its median, which limits the precision of the observed effect. The -2.82% median iPhone change relative to adjacent baseline averages is consistent with timing variation and does not establish acceleration beyond baseline. These data do not establish an advantage over GPU inference. The measurements use short arithmetic and formatting tasks and different Core ML/Ollama model implementations; equivalence of all weights, quantization and tokenization has not been established. The iPhone is foreground supervised. Actual ANE placement, system energy, thermals, background reliability, broader coding workloads and independent external reproduction remain unmeasured. The parallel foreground-awake fix was neither modified nor deployed.

This is a repeat on the same Windows/physical-iPhone setup with a new source/cache workspace and a new registered order, not external independent replication. Session 2 uses the public worker/controller. Session 1 used its retained private predecessor; the public logical argument template reconstructs that workload. Existing SDK/compiler/dependency binary contents were not fully hashed; version, source and dependency-lock checks have that limit.

## Audit trail

- [Reproduction guide](R3_APPLICATION_REPRODUCE_20261113.md)
- [Public source/argument specification](../results/r3_application_source_spec_20261113.json)
- [Session 1 protocol](../results/r3_application_protocol_session1_20261113.json) and [numeric evidence](../results/r3_application_session1_20261113.json)
- [Session 2 protocol](../results/r3_application_protocol_session2_20261113.json) and [numeric evidence](../results/r3_application_session2_20261113.json)
- [Public runner](../client/r3_application_study.py), [worker](../client/r3_swift_job.py), [materializer](../client/r3_swift_prepare.py) and [analyzer](../client/r3_application_analyze.py)
- session1 preregistration: https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4#issuecomment-6870119453
  - Protocol SHA-256: b0117793152ec5a66dce89568127213a7fa3809da854bf51c0ca671879c5a430; retained private source-report SHA-256: dc8a46bbd08916120ee4a34b8363c7a0b8cfd172fe1d1eca87f328cdd43a0f91.
- session2 preregistration: https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4#issuecomment-6870536776
  - Protocol SHA-256: a1dc930543ab351244a0ddf845e2296f11723f6a2bdd46911e2ad2a60df993e6; retained private source-report SHA-256: 13c5545e55e94d4147ccc17fe8c0405b8b53a56f186966051cb9b683ff834e83.
