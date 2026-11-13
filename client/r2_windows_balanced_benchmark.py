"""NANO R2: bounded, alternating Windows CPU/GPU study. No phone activity.

Dry-run by default. Explicit --execute and --pilot or --full required.
No prompts or generated text written to log or data; only aggregate metadata.
The iPhone and Core ML inference paths are NOT compared by this experiment.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time
from urllib.request import ProxyHandler, Request, build_opener

from r1_benchmark import run_windows_once, SYNTHETIC_PROMPTS

MODEL = "qwen3.5:0.8b"
PROMPT_LABEL = "logic"
PROMPTS = dict(SYNTHETIC_PROMPTS)
EXPECTED_DIGEST = "de63045f29755d4721c09d54c9b45c2dadb644f4fd7d604d4cac90d96049971c"
ROOT = Path(os.environ.get("NANO_R2_PRIVATE_DIR",
           str(Path.home() / "nano-r2-private-results"))).expanduser().resolve()
MODES = {"pilot": (1, 3), "full": (6, 5)}
MAX_RUNTIME_S = 420

def plan(mode: str):
    if mode not in MODES:
        raise ValueError("Unknown study mode")
    n_pairs, measured_per_block = MODES[mode]
    blocks = []
    for pair in range(n_pairs):
        order = ("windows_cpu", "windows_gpu_candidate") if pair % 2 == 0 else (
            "windows_gpu_candidate", "windows_cpu")
        for position, backend in enumerate(order):
            blocks.append({"pair": pair, "position": position, "backend": backend,
                           "warmups": 1, "measurements": measured_per_block})
    return blocks

def parse_processor(output: str) -> str:
    lines = [line for line in output.splitlines() if "qwen3.5:0.8b" in line]
    if len(lines) != 1:
        return "unavailable"
    matches = re.findall(r"\b100%\s*(CPU|GPU)\b", lines[0], flags=re.I)
    if len(matches) != 1:
        return "unavailable"
    return matches[0].upper()

def processor_status() -> str:
    r = subprocess.run(["ollama", "ps"], text=True, capture_output=True,
                       timeout=8, check=False)
    return parse_processor(r.stdout) if r.returncode == 0 else "unavailable"

def model_installed() -> dict:
    url="http://127.0.0.1:11434/api/tags"
    request=Request(url, method="GET")
    with build_opener(ProxyHandler({})).open(request, timeout=10) as resp:
        if resp.status != 200:
            raise ValueError("Local model registry unavailable")
        data=json.loads(resp.read(262144))
    matching=[m for m in data.get("models",[]) if m.get("name")==MODEL]
    if len(matching)!=1:
        raise ValueError("Approved model missing or ambiguous")
    m=matching[0]
    if m.get("digest")!=EXPECTED_DIGEST:
        raise ValueError("Model digest differs from verified 0.8B install")
    return {"model": MODEL, "digest": EXPECTED_DIGEST,
            "size_bytes": m.get("size")}

def summarize(rows):
    measured=[x for x in rows if x["phase"]=="measurement"]
    result=[]
    for backend in ("windows_cpu","windows_gpu_candidate"):
        observed=[x for x in measured if x["backend"]==backend]
        good=[x for x in observed if x.get("success") and
              type(x.get("elapsed_wall_s")) in (int,float) and
              math.isfinite(x["elapsed_wall_s"]) and x["elapsed_wall_s"]>0]
        lat=[x["elapsed_wall_s"] for x in good]
        token_counts=[x["completion_tokens_reported"] for x in good
                      if type(x.get("completion_tokens_reported")) is int]
        rates=[x["completion_tokens_reported"]/x["decode_duration_s_reported"] for x in good
               if type(x.get("completion_tokens_reported")) is int
               and type(x.get("decode_duration_s_reported")) in (float,int)
               and x["decode_duration_s_reported"]>0]
        result.append({"backend":backend,"attempts":len(observed),"successes":len(good),
                       "median_wall_s":round(statistics.median(lat),5) if lat else None,
                       "mean_wall_s":round(statistics.mean(lat),5) if lat else None,
                       "median_decode_tok_per_s":round(statistics.median(rates),3) if rates else None,
                       "min_output_tokens":min(token_counts) if token_counts else None,
                       "max_output_tokens":max(token_counts) if token_counts else None})
    return result

def save_report(path, report):
    # Only write experiment metadata inside existing private study directory.
    path=path.resolve()
    if path.parent != ROOT.resolve() or path.suffix.lower()!=".json":
        raise ValueError("Report must be JSON in the private benchmark directory")
    if path.exists():
        raise FileExistsError("Study report already exists: no overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--execute",action="store_true",help="opt into local inference")
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument("--pilot",action="store_true")
    modes.add_argument("--full",action="store_true")
    parser.add_argument("--report",type=Path)
    args=parser.parse_args(argv)
    mode="full" if args.full else "pilot"
    blocks=plan(mode)
    if not args.execute:
        print(json.dumps({"mode":"DRY_RUN","local_only":True,"model":MODEL,
                          "blocks":blocks,"measurements_per_backend":
                          sum(b["measurements"] for b in blocks if b["backend"]=="windows_cpu"),
                          "phone_inference":False,"gpu_kernel_trace":False},indent=2))
        return 0
    if not (args.pilot or args.full):
        parser.error("--execute requires explicit --pilot or --full")
    if args.report is None:
        parser.error("--execute requires --report (private directory)")
    report_path=args.report.resolve()
    if report_path.parent!=ROOT.resolve() or report_path.exists():
        raise ValueError("Private JSON report path required and must not exist")
    model=model_installed()
    began=time.monotonic()
    rows=[]
    block_checks=[]
    stopped_reason=None
    print("R2_EXPERIMENT_STARTED="+mode,flush=True)
    for block_index, block in enumerate(blocks):
        if time.monotonic()-began>MAX_RUNTIME_S:
            stopped_reason="wall_time_cap"
            break
        backend=block["backend"]
        cpu=backend=="windows_cpu"
        for phase,count in (("warmup",block["warmups"]),
                            ("measurement",block["measurements"])):
            for i in range(count):
                try:
                    item=run_windows_once(PROMPTS[PROMPT_LABEL],PROMPT_LABEL,
                                          cpu_only=cpu,model=MODEL)
                    if item["completion_tokens_reported"] is None or not 1<=item["completion_tokens_reported"]<=32:
                        raise ValueError("Reported token count outside bounded study range")
                    assert item["model"]==MODEL
                    record={"backend":backend,"block":block_index,
                            "pair":block["pair"],"position":block["position"],
                            "phase":phase,"iteration":i,"success":True,
                            "elapsed_wall_s":item["elapsed_wall_s"],
                            "completion_tokens_reported":item["completion_tokens_reported"],
                            "decode_duration_s_reported":item["decode_duration_s_reported"],
                            "prefill_duration_s_reported":item["prefill_duration_s_reported"],
                            "hardware_execution_traced":False}
                except (ValueError,RuntimeError,OSError,TimeoutError) as exc:
                    record={"backend":backend,"block":block_index,
                            "pair":block["pair"],"position":block["position"],
                            "phase":phase,"iteration":i,"success":False,
                            "error_class":type(exc).__name__}
                rows.append(record)
                if not record["success"]:
                    stopped_reason="inference_or_validation_error"
                    break
            if stopped_reason:
                break
        processor=processor_status()
        block_checks.append({"block":block_index,"backend":backend,
                             "ollama_ps_reported_processor":processor,
                             "expected_processor":"CPU" if cpu else "GPU",
                             "matches_expected":processor==("CPU" if cpu else "GPU")})
        print(f"R2_BLOCK_{block_index+1}_OF_{len(blocks)}="+
              ("PASS" if not stopped_reason and block_checks[-1]["matches_expected"] else "CHECK"),
              flush=True)
        if not block_checks[-1]["matches_expected"]:
            stopped_reason=stopped_reason or "processor_status_unverified"
        if stopped_reason:
            break
    completed=(len(block_checks)==len(blocks) and not stopped_reason)
    report={"schema":"nano-r2-windows-balanced-v1",
            "timestamp_utc":datetime.now(timezone.utc).isoformat(),
            "mode":mode,
            "model":model,"transport":"windows_localhost_ollama",
            "host_cpu_gpu":"Ryzen 7 5825U / integrated Radeon",
            "temperature":0,"seed":42,"think":False,"token_cap":32,
            "fixed_prompt_label":PROMPT_LABEL,
            "fixed_prompt_sha256":hashlib.sha256(PROMPTS[PROMPT_LABEL].encode()).hexdigest(),
            "interleaved_execution_blocks":True,
            "warmup_after_each_processor_switch":True,
            "runtime_cap_s":MAX_RUNTIME_S,
            "no_model_output_or_prompt_text_logged":True,
            "independent_gpu_kernel_trace":False,
            "independent_power_energy_measurement":False,
            "iPhone_benchmarked":False,
            "full_execution_completed":completed,
            "stopped_reason":stopped_reason,
            "block_checks":block_checks,
            "samples":rows,"summary":summarize(rows),
            "comparative_iphone_speedup_claim":False}
    save_report(report_path,report)
    print("R2_SANITIZED_REPORT_CREATED=YES",flush=True)
    print("R2_BLOCKS_COMPLETED="+str(len(block_checks)),flush=True)
    print("R2_MEASURED_SAMPLES="+str(sum(x["phase"]=="measurement" for x in rows)),flush=True)
    print("R2_FULL_COMPLETION="+str(completed),flush=True)
    return 0 if completed else 2

if __name__=="__main__":
    raise SystemExit(main())
