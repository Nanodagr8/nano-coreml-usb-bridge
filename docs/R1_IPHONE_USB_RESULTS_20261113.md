# R1 iPhone USB benchmark — first repeated physical-device results

**Measured November 13, 2026; exploratory checkpoint (n=3 per prompt)**

## Verified outcome

Windows successfully performed **12 consecutive authenticated, pinned-HTTPS requests** to the iPhone-hosted Qwen3.5 0.8B Core ML service over the existing USB-only loopback forward: **3 warmup and 9 measured generations, all successful**. The source watcher independently logged `R1_IPHONE_PINNED_HTTPS_READY=YES` and `R1_IPHONE_BENCHMARK_EXIT=0`.

The model was manually loaded and the TLS listener activated in the foreground. A Windows localhost forward by itself does not prove that the iPhone service is active.

| Fixed synthetic prompt | iPhone USB + Core ML median wall latency | Measured successes |
| --- | ---: | ---: |
| Logic | **1.33925 s** | 3/3 |
| Structured | **1.29259 s** | 3/3 |
| Short | **1.30739 s** | 3/3 |

These are **end-to-end wall times** covering network/TLS/USB and generation. The iPhone endpoint did **not** supply completion token counts; no decode token/s should be inferred from these times.

## Exploratory context — not a speedup result

Earlier Windows-only R1 tests used the installed Qwen3.5 0.8B **Ollama Q8_0** model. Those separate experiments measured the following medians:

| Prompt | Windows CPU-requested | Windows GPU-requested | iPhone USB Core ML |
| --- | ---: | ---: | ---: |
| Logic | 1.74349 s | 1.34116 s | 1.33925 s |
| Structured | 1.97396 s | 1.47608 s | 1.29259 s |
| Short | 2.26692 s | 1.56598 s | 1.30739 s |

**Do not interpret this table as device superiority.** Core ML weight/quantization equivalence to Ollama Q8_0 is unverified; Windows and iPhone measurements came from separate sessions, not a randomized matched design. Output quality was not scored and actual iPhone output-token counts were unavailable. No power/thermal control or hardware ANE placement trace was collected. Even if the timings appear faster for some tasks, no acceleration claim is justified.

## Sanitized evidence and provenance

- [All 12 iPhone observations](../results/r1_qwen35_08b_iphone_usb_exploratory.json), including warmups and per-sample times, with a strict public field allowlist
- [Prior Windows CPU/GPU observations](../results/r1_qwen35_08b_windows_exploratory.json), 24 observations total
- [Benchmark source](../client/r1_benchmark.py) and [R1 study protocol](R1_BENCHMARK.md)
- Original **private** R1 iPhone raw file SHA-256: `e3bb118aff1a5c83ff72829db1bc51002f44a6a4e8f3923fd552e99a8810af86`
- Sanitized public iPhone JSON SHA-256: `82fd2b430d24b4fe7018873eef8a4ab1b4f59cdc1e0890b0895a7633fbe65bfc`

Neither public dataset includes TLS credentials, signing material, private paths, user prompts or model responses.

## Research status

The **repeated secure USB inference functional milestone is verified**. Cross-device performance superiority, inference-energy improvement, and true ANE operator placement remain **unverified**.

Next research task: verify iPhone Core ML model weights and quantization; obtain a defensible equivalent Windows model configuration; add response correctness metrics, token counts, thermal/power instruments and interleaved 30+ trial benchmark sessions. Publish negative results as carefully as positive results.
