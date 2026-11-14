# Live coding diagnostics on Windows and iPhone

The registered study completed **36 of 36 requests** in **101.826 seconds**. Each target answered the same twelve coding cases. **Eleven answers matched the strict reference.** Removing one complete Markdown code fence yielded zero additional matches. The six-request pilot completed separately in 28.344 seconds. Both stages passed their initial and final readiness checks. [Registration on issue #4](https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4#issuecomment-6880361989)

| Main study target | Answers | Strict passes | Strict failures | Strict unassessed | Passes after fence handling | Median generation wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Windows CPU | 12 | 4 | 8 | 0 | 4 | 3.463 s |
| Windows GPU candidate | 12 | 3 | 9 | 0 | 3 | 4.314 s |
| iPhone USB Core ML | 12 | 4 | 7 | 1 | 4 | 1.617 s |

## What accounted for the other 25 answers

| Diagnostic label | Windows CPU | Windows GPU candidate | iPhone | Total |
| --- | ---: | ---: | ---: | ---: |
| Invalid Python expression syntax | 3 | 3 | 2 | 8 |
| Malformed JSON | 1 | 1 | 1 | 3 |
| Valid JSON with a different value or type | 3 | 3 | 2 | 8 |
| Parseable Python expression with a different syntax tree | 1 | 2 | 2 | 5 |
| Rejected wrapping, strict result unassessed | 0 | 0 | 1 | 1 |

The iPhone response to the inclusive-range task had wrapping that the registered rules reject. Its contents remain unassessed. The five parseable Python alternatives could include equivalent expressions or errors. This study did not test their behavior. None of the 36 responses reached the 64-token output cap. [Per-response measurements and summaries for both stages](../results/r7_live_diagnostics_20261114.json)

## How the study ran

The Windows host used Python 3.14.0 and the existing Ollama installation. The iPhone used its physical USB connection, a verified TLS public-key pin and local bearer authorization. Each status check confirmed the expected iPhone model was ready and the Windows model was listed. The existing Windows settings requested CPU or GPU execution. Windows GPU placement was not independently observed.

The pilot exercised the first two cases on all three targets before the main study. The main study used the original twelve-case task bank and two cycles of all six target orders. It included the two pilot cases again. The frozen rules capped output at 64 tokens per request and set host budgets of 120 seconds for the pilot and 360 seconds for the study. Every attempted response is represented. There were zero generation retries and zero hidden warmup requests. [Frozen protocol](../results/r7_live_protocol_20261114.json)

The runner passed answer text directly to the existing isolated grader and retained only the case, target, diagnostic labels and numeric measurements. Generated code was never executed. Before-and-after checks confirmed that the protected pin and bearer were unchanged in each stage. Public evidence excludes their values and all response text. The raw answers therefore cannot be independently rescored. [Runner](../client/r7_live_diagnostics.py) · [Diagnostic rules](R6_DIAGNOSTIC_GRADING_20261114.md)

The pilot produced two strict matches on Windows CPU, one on the Windows GPU candidate and one on iPhone. Its six answers are excluded from the table. R7 collected fresh responses. R5's historical counts and evidence are preserved. [Earlier coding qualification](R5_CODING_QUALIFICATION_20261114.md)

## Interpreting timing

The iPhone had the lowest observed median generation wall time. Each case ran once per target in a single session. Model implementations, quantization, tokenization and load state could differ. This run measured no concurrent Windows build, system energy or independent operator placement. A Windows build-time or general coding-productivity advantage remains unestablished. [Concurrent native-build results](R3_NATIVE_CONCURRENT_20261113.md)

## Reproduce the evidence checks

Run these commands from the checkout with the existing Python dependencies. The first command emits the frozen plan. The second validates the retained evidence and reruns the automated tests.

~~~text
python -B client/r7_live_diagnostics.py
python -B -m unittest discover -s tests
~~~

For a new physical reproduction, record the plan digest and attempt identity before inference. Load the existing credentials locally, use a new private report path for each stage, and pass the completed pilot to the study. The registered source commit is [3bec5fb](https://github.com/Nanodagr8/nano-coreml-usb-bridge/commit/3bec5fb10c4fe041261897136730968a7a832468).

~~~text
python -B client/r7_live_diagnostics.py --execute --stage pilot --plan-sha256 DIGEST --report NEW_PRIVATE_PILOT
python -B client/r7_live_diagnostics.py --execute --stage study --plan-sha256 DIGEST --pilot-report NEW_PRIVATE_PILOT --report NEW_PRIVATE_STUDY
~~~
