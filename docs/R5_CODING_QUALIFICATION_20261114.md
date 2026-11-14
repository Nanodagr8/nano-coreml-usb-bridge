# R5 coding-task qualification: complete, bounded descriptive results

The freshly registered study completed **36/36 generation requests** across twelve fixed cases and three existing local targets in **89.291 seconds**, within the 600-second host budget. Both initial and final readiness checks passed. Every request passed its model/telemetry/token gate; wrong rubric answers were counted and retained. No request was retried and no task/scorer changed after the pilot.

The separate fresh pilot completed six requests in 23.445 seconds. Its scores were CPU 2/2, GPU candidate 1/2 and iPhone 1/2, and are excluded from the study. The first registered pilot stopped before any generation and remains retained without a quality estimate.

## Main study result

| Target | Passed / 12 | Expression repairs / 6 | Code reading / 6 | Responses at 64-token cap | Median wall seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| windows_cpu | 4/12 | 2/6 | 2/6 | 0 | 3.211083 |
| windows_gpu_candidate | 3/12 | 1/6 | 2/6 | 0 | 3.870920 |
| iphone_usb_coreml | 4/12 | 1/6 | 3/6 | 0 | 1.563534 |

Counts describe only these fixed tasks under the conservative declared rubric. A failure can reflect formatting or a different valid expression as well as an incorrect answer; the unretained output cannot be independently reclassified. The counts do not establish general coding quality or a statistically reliable backend ranking. Being at the token cap does not by itself prove truncation. Generation wall times include model/backend loading and differing warm/carryover conditions; they are diagnostics, not hardware speed or productivity estimates.

| Case | CPU | GPU candidate | iPhone |
| --- | --- | --- | --- |
| py_inclusive_range | pass | pass | fail |
| py_bool_token_guard | pass | fail | pass |
| py_owned_cancel | fail | fail | fail |
| py_safe_lookup | fail | fail | fail |
| py_cap_tokens | fail | fail | fail |
| py_fresh_list | fail | fail | fail |
| py_slice_trace | pass | pass | pass |
| py_bool_trace | fail | fail | fail |
| py_finally_trace | pass | pass | pass |
| py_dedupe_trace | fail | fail | fail |
| ts_filter_trace | fail | fail | fail |
| swift_clamp_trace | fail | fail | pass |

## Preserved failure and authorized recovery

The first pilot stopped at initial readiness with a timeout, before any generation. A separate subsequent diagnostic passed pinned/authenticated iPhone readiness, while Windows Ollama accepted TCP connections but timed out on model-list, version and running-model APIs. After the user authorized recovery, only the existing Ollama server and its paused launcher wrapper were stopped. The existing executable was restarted hidden with the unchanged launcher's settings, loopback endpoint and existing model store. Launcher, executable and model manifest hashes remained unchanged; both APIs then passed readiness.

The fresh attempt was registered before inference and used new private reports and separate public datasets. The frozen cases, scorer, order, token cap and budget were unchanged. No failed prefix, diagnostic or pilot observations were pooled into the 36-request study. No installation, model download, signing, reboot, key/certificate change, forward restart or other listener change occurred. Protected configuration remained unchanged. Parallel iOS/app-identity work was not modified or attested here.

## Frozen task and scoring contract

- Six constrained Python-expression repairs: inclusive range, boolean-excluding token validation, owned cancellation, safe dictionary lookup, token clamping and fresh-list initialization.
- Six code-reading tasks: Python slicing, bool/int behavior, finally cleanup and insertion-order deduplication; TypeScript filter/map; Swift clamping.
- The pilot contains the first two cases on each target (six planned requests). It is excluded from the main study.
- The main study contains all twelve cases on explicit Windows CPU, Windows GPU candidate and pinned/authenticated `iphone_usb_coreml` (36 planned requests). Two cycles of all six backend permutations balance serial position. No hidden generation warmups or automatic retries are used.
- Existing model labels: `qwen3.5:0.8b` on Windows and `qwen3.5-0.8b` on iPhone. These labels do not establish weight, quantization or tokenizer equivalence.
- Each request is capped at 64 output tokens. Each session has a 600-second host budget, plus at most ten seconds of owned-child termination/reaping. Terminating the host does not guarantee cancellation of computation already dispatched remotely.
- Python repairs require AST identity with the declared expression. Code-reading answers require canonical JSON identity, distinguishing booleans/integers and integers/floats. Outer whitespace is tolerated; markdown and additional prose are not. Semantically valid alternative repair algorithms can fail this deliberately conservative rubric.
- Wrong answers score false and continue. Transport, model or metric failures stop and preserve the prefix. Correctness is the primary outcome; timing is only descriptive and includes differing cold-load conditions.
- Generated code is never executed. Raw generated text is not saved; only its hash, scorer verdict, task identity and allowlisted numeric metadata are retained. Reviewers can reproduce the scorer and tasks but cannot independently rescore unretained model text.

These are small, hand-authored, openly specified exercises. Some repair prompts strongly constrain the requested syntax. They measure compliance with these instructions, not autonomous debugging, broad coding ability or real-world build productivity. There is one planned observation per case/target, no blind holdout and no independent replication. Repeated pilot exposure is explicitly disclosed and not treated as novel holdout testing.

## Evidence

- [Complete 36-request study](../results/r5_coding_study_20261114.json).
- [Separate fresh pilot](../results/r5_coding_followup_pilot_20261114.json).
- [Sanitized recovery audit](../results/r5_recovery_audit_20261114.json).
- [Fresh follow-up registration](https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4#issuecomment-6879060537).
- [Frozen pilot protocol](../results/r5_coding_pilot_protocol_20261114.json).
- [Frozen study protocol](../results/r5_coding_study_protocol_20261114.json).
- [Stopped pilot evidence](../results/r5_coding_pilot_20261114.json): zero generation attempts, zero scored answers, incomplete, `transport_timeout` during `initial_readiness`.
- [Separate readiness diagnostic](../results/r5_readiness_diagnostic_20261114.json): Windows API timed out; the iPhone subsequently passed pinned/authenticated readiness. This is not inference-study data.
- [Public pre-registration](https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4#issuecomment-6878729872).
- [As-run runner and scorer](../client/r5_coding_quality.py), [behavior tests](../tests/test_r5_coding_quality.py), [source/protocol/stopped-evidence tests](../tests/test_r5_coding_evidence.py).

The frozen protocols record the as-run source/client/supervisor hashes and full synthetic cases and order. They are preserved byte-for-byte through Git export. Private raw reports, local diagnostic/process metadata and protected configuration are excluded from publication.

## Reproduction

With the existing dependencies installed:

```text
python -m unittest discover -s tests -v
python client/r5_coding_quality.py
python client/r5_coding_quality.py --analyze results/r5_coding_pilot_20261114.json
```

Dry mode creates no inference worker and sends no requests. A live attempt requires the existing intended model and both APIs ready, protected `NANO_USB_TLS_PIN` and `NANO_USB_BEARER` loaded locally without printing, and a new registration/output path:

```text
python client/r5_coding_quality.py --execute --plan PLAN --plan-sha256 SHA --report NEW_PRIVATE_REPORT
```

Reports must be outside the checkout and are never overwritten. Match the frozen source/client/supervisor and protocol bytes. Foreground operation is required by the existing iPhone service; screen state and installed build identity are not attested by this runner. The Windows GPU setting is a candidate configuration, not an independent hardware placement trace.

## Current project limits and conclusion

R3's native-build benefit remains inconclusive; R4's sampled continuity result remains separate. This completes the scoped fixed-suite qualification and provides descriptive per-case correctness evidence. It establishes no general coding advantage, productivity improvement, ANE or energy benefit, wake-lock certification, unattended reliability or release approval. Separate app-identity work in draft PR #7 is not modified or certified here. Independent review/reproduction, broader sustained tasks and quality, controlled thermals/background load, model equivalence, independent operator/energy instruments, physical recovery and app release gates remain open.
