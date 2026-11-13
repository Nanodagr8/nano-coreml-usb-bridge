# R1 model and decoding parity audit — November 13, 2026

## Finding: same model family, **different formats and decoding contracts**

The Windows and iPhone installations both use the **Qwen3.5 0.8B model family**, but our engineering audit confirms that we **cannot label their existing runtimes numerically equivalent**. This audit is of source code, pinned dependencies, model metadata and earlier test evidence. It is not an independent numerical comparison of on-device tensors, output quality, or hardware execution.

| Property | Windows Ollama R1 | iPhone Core ML R1 | Assessment |
| --- | --- | --- | --- |
| Family | Qwen3.5 0.8B | Qwen3.5 0.8B | Same family |
| Local model identifier | `qwen3.5:0.8b` | `qwen3.5-0.8b` | Different runtime IDs |
| Runtime | Ollama v0.40.16, llama.cpp runner | CoreML-LLM v1.9.0, Qwen35MLKVGenerator | Different |
| Runtime model encoding | **GGUF Q8_0** reported by `ollama show` | Upstream downloader documents **four INT8-palettized Core ML chunks plus raw FP16 embedding sidecar** | **Not weight/quantization-equivalent** |
| Runtime model provenance | Local manifest digest `de63045f29755d4721c09d54c9b45c2dadb644f4fd7d604d4cac90d96049971c` | Upstream download `mlboydaisuke/qwen3.5-0.8B-CoreML`; on-device snapshot SHA of every compiled weight not recorded | Full provenance remains incomplete |
| Tokenizer | Ollama Qwen3.5 renderer/template metadata | Swift Transformers `AutoTokenizer.from(pretrained:"Qwen/Qwen3.5-0.8B")` | Token-ID/template equality not tested |
| Chat template | Ollama renderer `qwen3.5`, modelfile `TEMPLATE {{ .Prompt }}` | Swift `applyChatTemplate(messages:)` or ChatML fallback | Effective prompt-token parity unverified |
| Decoding | `think:false`, temperature 0, seed 42, `num_predict=32`, model defaults include presence penalty **1.5**, top-k **20**, top-p **0.95** | temperature **0**, top-p **1.0**, repetition penalty **1.1**, 32-token cap, EOS set | **Not equivalent** |
| Output-token counts | Ollama reports `eval_count` | v10 HTTPS response does not report counts, although `Qwen35ModelAdapter.generateMeasured` computes `outputTokens` internally | Comparable per-token rate unavailable |
| Hardware attribution | `ollama ps` reported 100% CPU / 100% GPU for respective Windows runs | `cpuAndNeuralEngine` compute policy; no actual operator trace | ANE unverified |
| Energy | Not measured | Not measured | No energy conclusion |

The original public benchmark datasets use the same three synthetic **prompt strings** and a 32-new-token upper bound, but that does not equalize actual generated token counts or task quality.

## Source evidence

- Locally pinned `Package.resolved` `CoreML-LLM` **v1.9.0**, commit `c69a4e9bb8f9574f7b332babd93bb745c1022c11`; `swift-transformers` **v1.4.0**, commit `402a8a1105f52038b0949d9596981fc9e32bed17` (read from the authorized Windows/WSL build environment).
- [Qwen35ModelAdapter.swift](../ios/Sources/NanoANEBridge/Qwen35ModelAdapter.swift): selects `ModelDownloader.ModelInfo.qwen35_08b`, downloads `Qwen/Qwen3.5-0.8B` tokenizer and sets `temperature=0,topP=1.0,repetitionPenalty=1.1`; also already obtains `Qwen35InferenceMetrics.outputTokens` internally.
- [Upstream CoreML-LLM v1.8.0 release notes](https://github.com/john-rocky/CoreML-LLM/releases/tag/v1.8.0): describes four INT8-palettized chunks + FP16 embedding sidecar and full-vocabulary decoding; the device package pins later v1.9.0, whose local ModelDownloader confirms the same bundle family.
- [Core ML model repository](https://huggingface.co/mlboydaisuke/qwen3.5-0.8B-CoreML): upstream architecture/format context. Repository documentation can change independently of the cached physical device bytes.
- `ollama show qwen3.5:0.8b` on host: 752.39M params, Q8_0; `ollama show --modelfile qwen3.5:0.8b`: renderer and defaults.
- [R1 Windows results](R1_08B_WINDOWS_RESULTS_20261113.md) and [R1 iPhone results](R1_IPHONE_USB_RESULTS_20261113.md), each with three trials per prompt.

## Engineering decision

**Treat the 2026-11-13 cross-device chart as descriptive only**. Do not calculate or advertise a speedup percentage from it. The data already supports proof of secure, successful multi-request USB inference, not comparative model throughput or energy superiority.

Next measurement upgrade: iPhone HTTPS v11 should add **optional generated-token counts and model timing** using the metrics that the Swift generator already computes, without including prompt strings, output text in logs, credentials or hardware-placement claims. The current signed v10 app must remain unchanged until a new build is tested and deployment separately authorized.

Following that, a defensible system-level offloading experiment can compare *equivalent task quality / workload completion* under an explicitly stated heterogeneity model, even if absolute weight-by-weight equivalence is impossible. A strictly controlled **same-quantization model speed test** requires a new carefully matched conversion workflow and independent verification.
