"""NANO R3: measure host productivity while concurrent AI inference runs.

Dry-run by default. Pilot workload capped at six 5-second windows and two
fixed local CPU workers. Uses fixed public prompts but logs NO model answer.
The 'iphone_usb_coreml' target is optional and requires the existing secure
pinned HTTPS service foregrounded. No new network exposure or installation.
This is system-level workload research, not matched-weight model throughput.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

from r1_benchmark import _bounded_request
from nano_usb_client import NanoUSBClient

MODEL = "qwen3.5:0.8b"
MODEL_DIGEST = "de63045f29755d4721c09d54c9b45c2dadb644f4fd7d604d4cac90d96049971c"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
TASKS = {
    "arithmetic": ("What is 17 + 25? Reply with exactly the integer, digits only.", "42"),
    "format": ("Reply with exactly the word BLUE in capitals. No other characters.", "BLUE"),
}
TOKENS = 32
WORK_UNIT_BYTES = 256 * 1024
PRIVATE = Path(os.environ.get("NANO_R3_PRIVATE_DIR",
                      str(Path.home() / "nano-r3-private"))).expanduser().resolve()

def worker(seconds: float) -> None:
    """Runs in an isolated local subprocess; no network, no output until done."""
    if not (0.5 <= seconds <= 8):
        raise ValueError("Worker duration outside guardrails")
    payload = b"NANO-R3-fixed-host-workload-" * (WORK_UNIT_BYTES // 28 + 1)
    payload = payload[:WORK_UNIT_BYTES]
    start = time.perf_counter()
    count = 0
    while time.perf_counter() - start < seconds:
        hashlib.sha256(payload).digest()
        count += 1
    elapsed = time.perf_counter() - start
    print(json.dumps({"units":count, "seconds":round(elapsed,6),
                      "bytes_per_unit":len(payload)},separators=(",",":")),
          flush=True)

def plan(targets: list[str], runs: int, seconds: float, workers: int) -> list[str]:
    allowed = {"baseline","windows_cpu","windows_gpu_candidate","iphone_usb_coreml"}
    if not targets or len(targets)!=len(set(targets)) or set(targets)-allowed:
        raise ValueError("Unexpected or duplicated target")
    if type(runs) is not int or not 1 <= runs <= 10:
        raise ValueError("Runs must be 1..10")
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("At most four CPU workers")
    if not 2 <= seconds <= 8:
        raise ValueError("Window must be 2..8 seconds")
    other = [x for x in targets if x != "baseline"]
    # Alternate non-baseline ordering between cycles to avoid fixed sequencing.
    sequence=[]
    for i in range(runs):
        if "baseline" in targets and i == 0:
            sequence.append("baseline")
        sequence.extend(other if i % 2 == 0 else reversed(other))
        if "baseline" in targets:
            sequence.append("baseline")
    if len(sequence)>30:
        raise ValueError("Too many measured windows")
    return sequence

def model_integrity():
    from urllib.request import Request,ProxyHandler,build_opener
    url="http://127.0.0.1:11434/api/tags"
    with build_opener(ProxyHandler({})).open(Request(url,method="GET"),timeout=5) as r:
        reply=json.loads(r.read(262144))
    found=[x for x in reply.get("models",[]) if x.get("name")==MODEL]
    if len(found)!=1 or found[0].get("digest")!=MODEL_DIGEST:
        raise ValueError("Expected local Ollama model not installed or digest changed")
    return True

def infer(target: str, label: str, client=None) -> dict:
    prompt, expected=TASKS[label]
    started=time.perf_counter()
    if target in ("windows_cpu","windows_gpu_candidate"):
        response=_bounded_request(OLLAMA_URL,{
            "model":MODEL, "prompt":prompt, "stream":False,
            "think":False,"keep_alive":"1m",
            "options":{"temperature":0,"seed":42,"num_predict":TOKENS,
                       "num_gpu":0 if target=="windows_cpu" else 99},
        },timeout=40)
        if response.get("model") not in (None,MODEL):
            raise ValueError("Wrong Ollama model")
        answer=response.get("response")
        tokens=response.get("eval_count")
        model_ms=(response["eval_duration"]+response["prompt_eval_duration"])/1e6 if (
             type(response.get("eval_duration")) is int and
             type(response.get("prompt_eval_duration")) is int) else None
    elif target=="iphone_usb_coreml":
        if client is None:
            client=NanoUSBClient(
                os.getenv("NANO_USB_URL","https://127.0.0.1:49443"),
                os.getenv("NANO_USB_TLS_PIN",""),
                os.getenv("NANO_USB_BEARER",""))
        response=client.generate(prompt,TOKENS)
        answer=response.get("text")
        tokens=response.get("completion_tokens")
        model_ms=response.get("model_elapsed_ms")
        if response.get("metrics_source")!="on_device_coreml_generator":
            raise ValueError("No verified v11 token metrics source")
    else:
        raise ValueError("Unexpected target")
    latency=time.perf_counter()-started
    if not isinstance(answer,str):
        raise ValueError("Missing model output")
    if type(tokens) is not int or not (1<=tokens<=TOKENS):
        raise ValueError("Invalid emitted token count")
    if model_ms is not None and (type(model_ms) not in (int,float) or
       not math.isfinite(model_ms) or model_ms<0):
        raise ValueError("Invalid model duration")
    # Exact-match task quality checked in memory; text is never logged.
    correctness = answer.strip() == expected
    return {"wall_s":round(latency,5),"completion_tokens":tokens,
            "model_elapsed_ms":round(model_ms,3) if model_ms is not None else None,
            "passed_exact_answer":correctness}

def run_window(target: str, label: str, seconds: float, n_workers: int, client=None):
    workers=[]
    start=time.perf_counter()
    try:
        for _ in range(n_workers):
            worker_cmd=[sys.executable,str(Path(__file__).resolve()),
                        "--worker",str(seconds)]
            workers.append(subprocess.Popen(worker_cmd,stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL,text=True))
        time.sleep(0.3) # Background load already running before AI.
        request_start=time.perf_counter()-start
        generation = infer(target,label,client) if target!="baseline" else None
        request_finish=time.perf_counter()-start
        per_worker=[]
        for child in workers:
            output,_=child.communicate(timeout=seconds+12)
            if child.returncode!=0:
                raise RuntimeError("Host background worker exited with an error")
            m=json.loads(output)
            if m["units"]<=0 or m["bytes_per_unit"]!=WORK_UNIT_BYTES:
                raise ValueError("Host background worker invalid output")
            per_worker.append(m)
        elapsed=time.perf_counter()-start
    finally:
        for child in workers:
            if child.poll() is None:
                child.kill()
                child.communicate()
    # Workers deliberately have a fixed-duration compute window independent of
    # how fast AI finishes. Extra wall time is measured separately.
    total_units=sum(w["units"] for w in per_worker)
    avg_worker_seconds=statistics.mean(w["seconds"] for w in per_worker)
    complete_in_window=(generation is None or request_finish<=seconds)
    return {"target":target,"task":label,"success":True,
            "worker_count":n_workers,"configured_window_seconds":seconds,
            "host_bytes_hashed":total_units*WORK_UNIT_BYTES,
            "host_hash_mib_s":round(total_units*WORK_UNIT_BYTES/1048576/avg_worker_seconds,3),
            "overall_window_wall_s":round(elapsed,5),
            "ai_start_offset_s":round(request_start,5) if generation else None,
            "ai_finish_offset_s":round(request_finish,5) if generation else None,
            "ai_completed_during_host_work":complete_in_window,
            "ai":generation}

def summarize(rows):
    result=[]
    for target in sorted({r["target"] for r in rows}):
        selected=[r for r in rows if r["target"]==target]
        rates=[r["host_hash_mib_s"] for r in selected if r["success"]]
        latencies=[r["ai"]["wall_s"] for r in selected if r.get("ai")]
        correct=[r["ai"]["passed_exact_answer"] for r in selected if r.get("ai")]
        result.append({"target":target,"runs":len(selected),
                       "median_host_hash_mib_s":round(statistics.median(rates),3) if rates else None,
                       "median_ai_wall_s":round(statistics.median(latencies),5) if latencies else None,
                       "correct_answers":sum(correct),
                       "checked_answers":len(correct)})
    return result

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--targets",default="baseline,windows_cpu,windows_gpu_candidate")
    parser.add_argument("--runs",type=int,default=2)
    parser.add_argument("--seconds",type=float,default=5)
    parser.add_argument("--workers",type=int,default=2)
    parser.add_argument("--task",choices=tuple(TASKS),default="arithmetic")
    parser.add_argument("--report",type=Path)
    args=parser.parse_args(argv)
    targets=args.targets.split(",")
    order=plan(targets,args.runs,args.seconds,args.workers)
    if not args.execute:
        print(json.dumps({"mode":"DRY_RUN_NO_INFERENCE","order":order,
                          "task":args.task,"host_workload":"sha256_256kib",
                          "window_s":args.seconds,"workers":args.workers,
                          "no_phone_without_explicit_target":True},indent=2))
        return 0
    if args.report is None or args.report.resolve().parent!=PRIVATE or args.report.exists():
        parser.error("Use a new report path in the private R3 directory")
    if any(t.startswith("windows_") for t in targets):
        model_integrity()
    if "iphone_usb_coreml" in targets:
        client=NanoUSBClient(os.getenv("NANO_USB_URL","https://127.0.0.1:49443"),
                             os.getenv("NANO_USB_TLS_PIN",""),os.getenv("NANO_USB_BEARER",""))
        if client.status().get("status")!="ready":
            raise RuntimeError("iPhone not foreground-ready")
    else:
        client=None
    rows=[]
    stop=None
    for idx,target in enumerate(order):
        if target!="baseline":
            try:
                warmed=infer(target,args.task,client)
                if not warmed["passed_exact_answer"]:
                    stop="warmup_quality_failure"
                    break
            except Exception as exc:
                stop="warmup_"+type(exc).__name__
                break
        try:
            row=run_window(target,args.task,args.seconds,args.workers,client)
            row["sequence"]=idx
            if row.get("ai") and not row["ai"]["passed_exact_answer"]:
                stop="task_quality_failure"
            rows.append(row)
            print("R3_WINDOW_"+str(idx+1)+"="+("PASS" if not stop else "CHECK"),flush=True)
            if stop:
                break
        except Exception as exc:
            stop=type(exc).__name__
            break
    report={"schema":"nano-r3-system-workload-v1",
            "timestamp_utc":datetime.now(timezone.utc).isoformat(),
            "model_family":"qwen3.5-0.8b",
            "windows_model_digest":MODEL_DIGEST,
            "iPhone_coreml_quantization_equivalence":False,
            "task_label":args.task,
            "fixed_task_response_quality":"exact_answer_checked_in_memory",
            "host_workload":"sha256_256kib_fixed_background",
            "baseline_and_ai_conditions":order,
            "complete":len(rows)==len(order) and not stop,
            "stop_reason":stop,"samples":rows,"summary":summarize(rows),
            "no_prompts_or_generated_text_logged":True,
            "energy_measured":False,"ane_execution_verified":False,
            "cross_device_speedup_proved":False}
    PRIVATE.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf8")
    print("R3_SANITIZED_LOCAL_REPORT_CREATED=YES",flush=True)
    print("R3_COMPLETED="+str(report["complete"]),flush=True)
    print("R3_WINDOWS_COMPLETED="+str(len(rows)),flush=True)
    return 0 if report["complete"] else 2

if __name__=="__main__":
    if len(sys.argv)>=3 and sys.argv[1]=="--worker":
        worker(float(sys.argv[2]))
    else:
        raise SystemExit(main())
