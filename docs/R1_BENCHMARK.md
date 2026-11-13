# R1 benchmark protocol — exploratory Windows ↔ iPhone offloading

**Status: initial harness, not evidence of acceleration.** Research issue: https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/1

## Safety and measurement scope

The script client/r1_benchmark.py defaults to DRY RUN with zero network requests. A measurement requires explicit --execute, uses fixed synthetic prompts, caps generation at 32 new tokens, and saves metadata only: latency, server-provided token counts/durations and success/failure. It never saves the text of prompts, generated responses, bearer tokens or certificate keys.

Targets:

- windows_cpu: loopback-only Ollama at http://127.0.0.1:11434/api/generate, requesting num_gpu=0. This is a requested CPU setting, not a hardware utilization trace.
- windows_gpu_candidate: the same local Ollama endpoint with num_gpu=99. Actual GPU placement is UNVERIFIED; a candidate might fall back to CPU. An independent GPU monitor is required.
- iphone_usb_coreml: paired USB loopback https://127.0.0.1:49443, with TLS SPKI pin and bearer supplied privately through the local host process environment; the iPhone service must be manually foregrounded.

## Critical model parity caveat

The existing Windows Ollama installation has Qwen3.5 4B and the tested iPhone Core ML path is Qwen3.5 0.8B. Their measurements cannot support a cross-device performance ranking or claimed speedup.

For a controlled speedup claim both devices need verified identical model weights, tokenizer, quantization, sampling/decoding settings and task quality criteria. Record exact fingerprints and measurements. A model name alone is not adequate proof of equivalence. The current harness intentionally marks parity as unmatched.

## Run safely

Python 3.10+ and dependencies in client/requirements.txt:

    python client/r1_benchmark.py
    python -m unittest discover -s tests -v

These commands make no inference calls. With the preexisting local Ollama model a single bounded Windows CPU exploratory run is:

    python client/r1_benchmark.py --execute --target windows_cpu --repeats 1 --warmups 0

This runs three fixed synthetic prompts at maximum 32 output tokens each.

For a foregrounded iPhone service, configure NANO_USB_TLS_PIN (base64 SPKI SHA-256) and NANO_USB_BEARER (private high-entropy token) ONLY inside your host process environment. Then:

    python client/r1_benchmark.py --execute --target iphone_usb_coreml --repeats 1

Never paste credentials into logs, shell command arguments, screenshots or GitHub. Never forward port 49443 to LAN.

## Next statistical experiment

Once identical model configurations and instrumentation are available, use at least 5 warmups and 30 measured repetitions per condition, randomized/paired prompt order, controlled thermals, and predeclared metrics. Report prefill time, decode time, wall latency, error rates and both-device total energy where independently measurable. Report uncertainty and negative results. A CPU/GPU/ANE operation trace is required before assigning actual execution hardware.

Total wall latency includes HTTP/TLS, USB transfer, scheduling and model processing. The wall-clock stopwatch alone cannot isolate USB/TLS overhead; a dedicated authenticated status-round-trip control will be needed.

This is an engineering research reference and makes no claim of being a world-first implementation.

## Approved 0.8B model on Windows (November 13 checkpoint)

The Windows-only measurements now support an explicit allowlisted model selector:

    python client/r1_benchmark.py --windows-model qwen3.5:0.8b
    python client/r1_benchmark.py --windows-model qwen3.5:0.8b --execute --target windows_cpu --warmups 1 --repeats 3
    python client/r1_benchmark.py --windows-model qwen3.5:0.8b --execute --target windows_gpu_candidate --warmups 1 --repeats 3

The options never download a model automatically; `qwen3.5:0.8b` must be installed in the existing Ollama runtime first. The downloadable Windows model is Q8_0; **we have not established that the iPhone Core ML model uses the same quantization/weights**. A shared parameter size does not establish an apples-to-apples comparison.

See the [sanitized Windows 0.8B results](R1_08B_WINDOWS_RESULTS_20261113.md) and [machine-readable observations](../results/r1_qwen35_08b_windows_exploratory.json). These are small exploratory samples, not a measured Windows/iPhone acceleration claim.
