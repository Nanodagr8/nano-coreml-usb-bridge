# R5 coding-task qualification: prepared, live comparison pending

The fixed-suite runner and scoring package are validated. The registered pilot stopped at initial readiness with a transport timeout, **before any generation request**. The three-backend coding comparison has not run; there is no coding-quality or timing result to rank.

A separate, subsequent readiness diagnostic found the pinned/authenticated iPhone service ready. Windows Ollama accepted TCP connections on its existing loopback endpoint, but `/api/tags` timed out after 25 seconds; `/api/version` and `/api/ps` also timed out under separate four-second checks. A listening socket does not prove API readiness. No restart, alternate backend, install, listener change or credential/certificate change was attempted in this qualification.

The failed pilot is retained. A follow-up requires a fresh registration, new private output paths and a separate dataset. No failed prefix or later diagnostic is pooled into the planned study.

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

## Current project limits

R3's native-build benefit remains inconclusive; R4's sampled continuity result remains separate. This pending qualification adds neither a coding advantage nor a productivity, ANE, energy, wake-lock, unattended-reliability or release claim. Separate app-identity work in draft PR #7 is not modified or certified here. Independent review/reproduction, broader sustained tasks and quality, controlled thermals/background load, model equivalence, independent operator/energy instruments, physical recovery and app release gates remain open.
