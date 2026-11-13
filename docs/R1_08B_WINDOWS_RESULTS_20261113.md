# R1 checkpoint: Windows Qwen3.5 0.8B CPU/GPU-requested benchmarks

**Experimental date:** November 13, 2026

**Status:** Valid Windows-only exploratory measurements. This report is NOT proof of Windows-to-iPhone acceleration, matched Core ML quantization, or ANE hardware execution.

## Installation verified

The user explicitly approved installing the free Ollama model `qwen3.5:0.8b` in their existing Windows Ollama installation. Ollama v0.40.16 independently listed the model after download:

- Architecture: `qwen35`
- Parameter count: **752.39 million**
- Quantization: **Q8_0**
- Ollama manifest digest: `de63045f29755d4721c09d54c9b45c2dadb644f4fd7d604d4cac90d96049971c`
- Model size from local Ollama inventory: **1,322,069,277 bytes**
- Preexisting `qwen3.5:4b` remains installed.
- Host: AMD Ryzen 7 5825U (8C/16T), integrated Radeon graphics, about 27.9 GB RAM.

## Experiment design

The R1 harness used **exactly the same installed Ollama 0.8B model** for both Windows conditions. Fixed temperature 0, seed 42, `think:false`, and up to 32 new tokens. Each condition ran one warmup and **three measured requests per synthetic prompt** (logic, structure, short); the prompts within each condition were shuffled deterministically.

These are wall-clock end-to-end API timings, not decode-only token rates. No user prompts or generated text were logged.

| Prompt | CPU-requested median (s) | GPU-requested median (s) | Measured runs/condition |
| --- | ---: | ---: | ---: |
| Logic | 1.74349 | 1.34116 | 3 |
| Structured | 1.97396 | 1.47608 | 3 |
| Short | 2.26692 | 1.56598 | 3 |

**Reliability:** CPU-requested 9/9 measured successes and 3/3 warmups; GPU-requested 9/9 measured successes and 3/3 warmups. A separate CPU-requested processor check succeeded 3/3.

The host used `num_gpu=0` for the CPU condition and `num_gpu=99` for the GPU candidate. Immediately after the GPU candidate, `ollama ps` reported `qwen3.5:0.8b` using **100% GPU**. Immediately after a separate CPU-requested verification run, `ollama ps` reported **100% CPU**. These are Ollama runtime reports, **not independent per-kernel hardware traces**.

## Reproducibility and raw data

The [sanitized JSON dataset](../results/r1_qwen35_08b_windows_exploratory.json) includes all **24** observations, including warmups, with reported token counts, elapsed times, and API-reported prefill/decode durations where available. It contains no model outputs, prompt strings, passwords, bearer tokens or private files.

Its SHA-256 digest at publication is `722534a2532ceeb0c8630e303756453bf501d5d4d46e05fbc6836f417fccd088`.

The [R1 harness](../client/r1_benchmark.py) is dry-run by default. To remeasure on a host with this exact installed model:

    python client/r1_benchmark.py --windows-model qwen3.5:0.8b
    python client/r1_benchmark.py --windows-model qwen3.5:0.8b --execute --target windows_cpu --warmups 1 --repeats 3
    python client/r1_benchmark.py --windows-model qwen3.5:0.8b --execute --target windows_gpu_candidate --warmups 1 --repeats 3

No new model is downloaded by these commands; the existing host model must already be present. Run tests with `python -m unittest discover -s tests -v`.

## Critical limitations

- **Sample size is small:** three measured trials per condition/prompt. No confidence interval, statistical significance, or production performance certification is claimed.
- **Order was not counterbalanced between CPU and GPU execution blocks.** Warm caches, frequency scaling, temperatures, first-load effects, and runner context differences may influence measurements.
- **GPU attribution is Ollama-reported PROCESSOR telemetry**, not a standalone GPU kernel profiler or power/energy sensor.
- **Output correctness and semantic equivalence were not compared.** Token counts for specific prompts are server-reported.
- **The Windows 0.8B model is Q8_0**, but the phone's Core ML weights and quantization equivalence have not been established. The Windows/iPhone paths cannot yet support controlled speedup claims.
- **No iPhone R1 benchmark was run during this checkpoint.** The previously verified USB HTTPS connection is preserved, but requires iPhone foreground activation for future timed trials.
- **No ANE per-operation trace or full-system energy measurement exists yet.**

## Next experiment

1. Inspect phone Core ML model metadata and tokenizer/quantization to assess comparable conditions, rather than inferring parity from the shared 0.8B size.
2. Preserve the TLS-only iPhone service and conduct a foreground, pinned-HTTPS, bounded 0.8B iPhone run using the same synthetic prompts.
3. Establish a reproducible, interleaved repeated-run protocol with thermal, energy and operation-placement instrumentation; target at least 30 measured trials per condition before research-grade comparison.

More work: [research milestone R1](https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/1).
