"""NANO R1 benchmark harness — no secrets/prompts/generated text written to disk.

Designed for deliberately **unmatched** Windows Qwen3.5 4B vs iPhone 0.8B
exploration. Never infer CPU/GPU/ANE usage or comparative speedup from APIs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from nano_usb_client import NanoUSBClient

WINDOWS_MODEL = "qwen3.5:4b"
IPHONE_MODEL = "qwen3.5-0.8b"
WINDOWS_API = "http://127.0.0.1:11434/api/generate"
SYNTHETIC_PROMPTS = (
    ("short", "List two advantages of computing locally. Use short sentences."),
    ("logic", "In one sentence, explain why a USB transfer may add latency."),
    ("structure", "Provide exactly three numbered steps for testing an API."),
)
MAX_TOKENS = 32

def model_parity(model_a: str, model_b: str, weights_sha_a=None, weights_sha_b=None,
                 quantization_a=None, quantization_b=None, tokenizer_sha_a=None,
                 tokenizer_sha_b=None) -> dict:
    """Fail CLOSED: equivalent names alone never establish model parity."""
    fields = ((weights_sha_a, weights_sha_b), (quantization_a, quantization_b),
              (tokenizer_sha_a, tokenizer_sha_b))
    exact = (model_a == model_b and all(a and b and a == b for a, b in fields))
    return {"matched": bool(exact),
            "reason": ("weights_quantization_tokenizer_verified"
                       if exact else "unmatched_model_configuration_no_speedup_claim")}


def plan(windows_model: str = WINDOWS_MODEL) -> dict:
    if windows_model not in ("qwen3.5:4b", "qwen3.5:0.8b"):
        raise ValueError("Only approved local Ollama models are permitted")
    return {
        "research_id": "NANO-R1",
        "phase": "exploratory_unmatched_models",
        "windows": {"model": windows_model, "transport": "localhost_ollama",
                    "cpu_forced": True, "gpu_execution_verified": False},
        "iphone": {"model": IPHONE_MODEL, "transport": "usb_loopback_pinned_https",
                   "foreground_required": True, "ane_execution_verified": False},
        "parity": model_parity(windows_model, IPHONE_MODEL),
        "max_new_tokens": MAX_TOKENS,
        "default_run": "DRY_RUN_NO_INFERENCE",
        "privacy": "metadata_only_no_prompt_response_or_credential_logs",
        "limitations": ["No hardware operation trace", "No measured energy",
                        "Windows/iPhone currently use different model sizes",
                        "USB offload superiority cannot be inferred"],
    }


def _bounded_request(url: str, payload: dict, timeout: int = 95) -> dict:
    if url != WINDOWS_API:
        raise ValueError("No non-loopback or dynamic Windows endpoints permitted")
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if len(raw) > 8_192:
        raise ValueError("Request too large")
    request = Request(url, data=raw, method="POST",
                      headers={"Content-Type": "application/json"})
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError("Non-200 Ollama response")
            data = response.read(1_048_577)
    except (URLError, HTTPError, TimeoutError) as exc:
        raise RuntimeError("Windows model API unavailable") from exc
    if len(data) > 1_048_576:
        raise ValueError("Response exceeds 1 MiB")
    parsed = json.loads(data)
    if not isinstance(parsed, dict):
        raise ValueError("Expected Ollama JSON object")
    return parsed


def run_windows_once(prompt: str, label: str, *, cpu_only: bool = True,
                     model: str = WINDOWS_MODEL, request_fn=_bounded_request) -> dict:
    if model not in ("qwen3.5:4b", "qwen3.5:0.8b"):
        raise ValueError("Only approved local Ollama models are permitted")
    opts = {"temperature": 0, "seed": 42, "num_predict": MAX_TOKENS,
            "num_gpu": 0 if cpu_only else 99}
    payload = {"model": model, "prompt": prompt, "stream": False,
               "think": False, "options": opts, "keep_alive": "1m"}
    start = time.perf_counter()
    response = request_fn(WINDOWS_API, payload)
    elapsed = time.perf_counter() - start
    if response.get("model") not in (None, model):
        raise ValueError("Ollama reported another model")
    if not isinstance(response.get("response"), str) or not response["response"].strip():
        raise ValueError("Empty Ollama generation")
    eval_count = response.get("eval_count")
    duration_ns = response.get("eval_duration")
    prompt_ns = response.get("prompt_eval_duration")
    return {
        "target": "windows_cpu" if cpu_only else "windows_gpu_candidate",
        "model": model, "label": label, "success": True,
        "elapsed_wall_s": round(elapsed, 5),
        "completion_tokens_reported": eval_count if type(eval_count) is int and eval_count >= 0 else None,
        "decode_duration_s_reported": (round(duration_ns / 1e9, 5)
                                        if type(duration_ns) is int and duration_ns > 0 else None),
        "prefill_duration_s_reported": (round(prompt_ns / 1e9, 5)
                                        if type(prompt_ns) is int and prompt_ns >= 0 else None),
        "hardware_placement_verified": False,
        "hardware_evidence": "ollama_options_only_not_hardware_profiler",
        "output_nonempty": True,
    }


def run_iphone_once(prompt: str, label: str, *, client=None) -> dict:
    if client is None:
        client = NanoUSBClient(
            os.environ.get("NANO_USB_URL", "https://127.0.0.1:49443"),
            os.environ.get("NANO_USB_TLS_PIN", ""),
            os.environ.get("NANO_USB_BEARER", ""))
    start = time.perf_counter()
    response = client.generate(prompt, MAX_TOKENS)
    elapsed = time.perf_counter() - start
    return {
        "target": "iphone_usb_coreml", "model": IPHONE_MODEL, "label": label,
        "success": True, "elapsed_wall_s": round(elapsed, 5),
        "completion_tokens_reported": None,
        "decode_duration_s_reported": None,
        "prefill_duration_s_reported": None,
        "hardware_placement_verified": False,
        "hardware_evidence": "compute_preference_not_ane_operation_trace",
        "output_nonempty": bool(response.get("text", "").strip()),
    }


def make_schedule(repeats: int, warmups: int, labels: tuple[str, ...], seed=20261113):
    if type(repeats) is not int or not (1 <= repeats <= 30):
        raise ValueError("Measured repeats must be between 1 and 30")
    if type(warmups) is not int or not (0 <= warmups <= 5):
        raise ValueError("Warmups must be between 0 and 5")
    if not labels:
        raise ValueError("At least one prompt label required")
    rand = random.Random(seed)
    tasks = []
    for phase, count in (("warmup", warmups), ("measurement", repeats)):
        for i in range(count):
            shuffled = list(labels)
            rand.shuffle(shuffled)
            tasks.extend((phase, i, k) for k in shuffled)
    return tasks


def summarize(rows: list[dict]) -> dict:
    grouped = {}
    for r in rows:
        if r.get("phase") != "measurement":
            continue
        key = (r["target"], r["label"])
        grouped.setdefault(key, []).append(r)
    out = []
    for (target, label), data in sorted(grouped.items()):
        good = [r for r in data if r.get("success") and
                isinstance(r.get("elapsed_wall_s"), (int, float)) and
                math.isfinite(r["elapsed_wall_s"]) and r["elapsed_wall_s"] > 0]
        measured = [r["elapsed_wall_s"] for r in good]
        out.append({
            "target": target, "label": label, "attempts": len(data),
            "successes": len(good),
            "median_wall_s": round(statistics.median(measured), 5) if measured else None,
            "mean_wall_s": round(statistics.mean(measured), 5) if measured else None,
            "comparative_speedup_claim_allowed": False,
        })
    return {"groups": out, "matched_model_comparison": False,
            "interpretation": "exploratory_unmatched_models_not_relative_speedup"}


def main(argv=None):
    p = argparse.ArgumentParser(description="NANO R1 no-secret cross-device benchmark scaffold")
    p.add_argument("--execute", action="store_true",
                   help="Opt-in: run bounded inference on the selected local target")
    p.add_argument("--windows-model", choices=("qwen3.5:4b", "qwen3.5:0.8b"),
                   default=WINDOWS_MODEL)
    p.add_argument("--target", choices=("windows_cpu", "windows_gpu_candidate", "iphone_usb_coreml"),
                   default="windows_cpu")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--warmups", type=int, default=0)
    p.add_argument("--report", type=Path, help="Optional sanitized JSON report path")
    args = p.parse_args(argv)
    info = plan(args.windows_model)
    if not args.execute:
        print(json.dumps(info, indent=2))
        return 0
    tasks = make_schedule(args.repeats, args.warmups,
                          tuple(x[0] for x in SYNTHETIC_PROMPTS))
    prompts = dict(SYNTHETIC_PROMPTS)
    rows = []
    for phase, index, label in tasks:
        try:
            if args.target == "iphone_usb_coreml":
                row = run_iphone_once(prompts[label], label)
            else:
                row = run_windows_once(prompts[label], label,
                                       cpu_only=args.target == "windows_cpu",
                                       model=args.windows_model)
        except (ValueError, RuntimeError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            row = {"target": args.target, "model": (
                    IPHONE_MODEL if args.target == "iphone_usb_coreml" else args.windows_model),
                   "label": label, "success": False,
                   "error_class": type(exc).__name__}
        row["phase"] = phase
        row["index"] = index
        rows.append(row)
        print(f"{args.target} {phase} {label}: {'PASS' if row['success'] else 'UNAVAILABLE'}",
              flush=True)
    report = {
        "schema": "nano-r1-v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "plan": info, "target": args.target,
        "run_count": len(rows), "samples": rows,
        "summary": summarize(rows),
        "no_text_or_credentials_recorded": True,
    }
    if args.report:
        if args.report.exists():
            raise FileExistsError("Refusing to overwrite existing measurement report")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("SANITIZED_REPORT_SAVED=YES")
    else:
        print(json.dumps(report["summary"], indent=2))
    return 0 if all(r["success"] for r in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
