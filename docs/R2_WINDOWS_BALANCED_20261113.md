# NANO R2: 30-trial balanced CPU/GPU benchmark on Windows

**Measured:** November 13, 2026. **Scope:** Windows-local inference using the *same* installed Ollama Qwen3.5 0.8B Q8_0 model. **Not** a Windows-to-iPhone speedup experiment.

## Result

| Condition | Successful measured requests | Median wall latency | Median Ollama decode speed |
| --- | ---: | ---: | ---: |
| Ryzen 7 5825U, CPU-requested (\`num_gpu=0\`) | 30/30 | **1.41350 s** | **17.052 tok/s** |
| Integrated Radeon, GPU-requested (\`num_gpu=99\`) | 30/30 | **1.02211 s** | **24.486 tok/s** |

Every measured request returned **22 completion tokens** and a nonempty response. One warmup request preceded each of the twelve processor blocks (12/12 successful). \`ollama ps\` reported **100% CPU** or **100% GPU**, respectively, at the end of all 12 corresponding blocks. This is Ollama runtime-reported residency, not a separate hardware-kernel trace.

**Paired block analysis:** 6 CPU/GPU pairs, each with 5 measured requests per backend. A geometric mean of pairwise median CPU/GPU wall-time ratios yielded **1.3903×**; a descriptive 95% percentile bootstrap CI (5,000 deterministic paired-block resamples) was **1.3280–1.4471×**.

This is a **Windows GPU-vs-CPU performance observation** under one workload, not a claim of energy efficiency, hardware novelty, or an iPhone accelerator speedup. Because there are only 6 block pairs, thermal behavior, process cache and operational conditions may still influence uncertainty; the simple bootstrap does not resolve all dependence or device changes.

## Controls and methods

- Host: AMD Ryzen 7 5825U, integrated AMD Radeon, ~27.9 GB RAM.
- Model: \`qwen3.5:0.8b\`, **Q8_0**, 752.39M params, installed model digest \`de63045f29755d4721c09d54c9b45c2dadb644f4fd7d604d4cac90d96049971c\`.
- Same synthetic **logic** prompt (see source code) for both backends; \`think:false\`, temperature 0, seed 42, maximum 32 generated tokens.
- Six paired blocks in alternating \`CPU→GPU\`, \`GPU→CPU\` order; one warmup and five measured requests per block.
- Captured end-to-end wall time, Ollama \`eval_count\`, \`eval_duration\`, \`prompt_eval_duration\`, and \`ollama ps\` CPU/GPU status per block.
- All 60 measurements and 12 warmups completed successfully; no TCP connections beyond the host loopback Ollama API; iPhone inference not invoked.
- No generated output text, private user prompts, credentials, signing material or personal device identifiers logged.
- No power, battery or independent thermal sensors sampled; no output-content quality scoring performed.

## Evidence

- [Full sanitized dataset (72 observations)](../results/r2_windows_08b_balanced_20261113.json).
- [Paired block analysis (including all six pairs and interval)](../results/r2_windows_08b_paired_analysis_20261113.json).
- [Reproducible bounded benchmark source](../client/r2_windows_balanced_benchmark.py).
- [Data analysis and validation source](../client/r2_analyze.py).
- [Research issue R1](https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/1).

Private full report SHA-256: \`8cde1c1654c49592fbee12c7003225e2ab80912f9219ee90cfabea6cd32702c\`. **Do not publish any private logs.**

## Reproduce safely

Python 3.10+, \`cryptography\` in \`client/requirements.txt\`, existing Ollama with \`qwen3.5:0.8b\` installed. The harness **never pulls or installs models automatically**.

Start with a dry run:

    python client/r2_windows_balanced_benchmark.py
    python -m unittest discover -s tests -v

Run an optional 6-measurement pilot (plus 2 warmups):

    python client/r2_windows_balanced_benchmark.py --execute --pilot --report ~/nano-r2-private-results/pilot.json

Then the full 60-measurement study (plus 12 warmups):

    python client/r2_windows_balanced_benchmark.py --execute --full --report ~/nano-r2-private-results/full.json

On Windows PowerShell, expand \`~\` to your local user profile path before passing it to the Python script if necessary. Alternatively, set the \`NANO_R2_PRIVATE_DIR\` environment variable to a dedicated private report directory, and place \`--report\` inside it.

Analysis of a complete dataset:

    python client/r2_analyze.py --input ~/nano-r2-private-results/full.json --output ~/nano-r2-private-results/analysis.json

The scripts refuse to overwrite existing reports, use host loopback only, and run bounded workloads. The analysis rejects missing samples, mismatched model digest and missing processor confirmation rather than manufacturing results.

## What remains open

Our iPhone uses a Qwen3.5 0.8B Core ML model with four INT8-palettized chunks and FP16 embedding, **not verified numerically equivalent** to Ollama's Q8_0 model. We have already verified v11 token telemetry through pinned HTTPS over USB, but these Windows-only results cannot establish an offloading benefit. A legitimate cross-device test needs workload-quality comparison, controlled power/thermal measurement, and independent ANE execution tracing.
