# Research roadmap

This is a verified integration of existing approaches, not a claimed first discovery.

Next useful experiments:
1. Capture authoritative operation placement and execution traces with Apple Instruments / Core ML profiling.
2. Measure prefill, decode throughput, end-to-end latency, power per token and thermal state over controlled repeated runs.
3. Compare matching weights and tokenization on desktop CPU/GPU, Core ML CPU/GPU and ANE-preferred policies; report differences in quantization.
4. Test USB disconnect/reconnect, certificate expiry, app background suspension and user-mediated recovery.
5. Publish reproducible iOS build guidance that does not require exposing signing material.
6. Seek security review and reproducibility reports from external contributors.

Do not equate ANE-preferred compute policy with measured ANE hardware utilization.
