"""Analyze NANO R2 Windows-only alternating CPU/GPU blocks.

No inference; reading metadata-only private JSON. Paired-block resampling
respects the benchmark's 6 pairs rather than treating 60 measurements as IID.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

CPU="windows_cpu"
GPU="windows_gpu_candidate"
EXPECTED_DIGEST="de63045f29755d4721c09d54c9b45c2dadb644f4fd7d604d4cac90d96049971c"

def percentile(sorted_values, fraction):
    assert sorted_values
    index=(len(sorted_values)-1)*fraction
    lo=int(math.floor(index))
    hi=int(math.ceil(index))
    return sorted_values[lo]*(hi-index)+sorted_values[hi]*(index-lo) if lo!=hi else sorted_values[lo]

def evaluate(report, bootstrap=5000, seed=20261113):
    if report.get("schema")!="nano-r2-windows-balanced-v1":
        raise ValueError("Unexpected benchmark report")
    if report.get("mode")!="full" or report.get("full_execution_completed") is not True:
        raise ValueError("No complete 30-trial dataset")
    if report.get("model",{}).get("digest")!=EXPECTED_DIGEST:
        raise ValueError("Model digest mismatch")
    checks=report.get("block_checks",[])
    samples=report.get("samples",[])
    if len(checks)!=12 or any(not b.get("matches_expected") for b in checks):
        raise ValueError("Incomplete processor attribution blocks")
    measured=[row for row in samples if row.get("phase")=="measurement"]
    warmups=[row for row in samples if row.get("phase")=="warmup"]
    if len(measured)!=60 or len(warmups)!=12:
        raise ValueError("Unexpected measured sample count")
    if any(not row.get("success") or row.get("completion_tokens_reported") is None
           or not 1<=row["completion_tokens_reported"]<=32 for row in samples):
        raise ValueError("Unsuccessful or unbounded test record")
    by_pair=defaultdict(lambda:defaultdict(list))
    for r in measured:
        if r.get("backend") not in (CPU,GPU) or not isinstance(r.get("pair"),int):
            raise ValueError("Unexpected CPU/GPU record")
        by_pair[r["pair"]][r["backend"]].append(r)
    if set(by_pair)!=set(range(6)):
        raise ValueError("Expected six pairs")
    pairs=[]
    for pair in range(6):
        a,b=by_pair[pair][CPU],by_pair[pair][GPU]
        if len(a)!=5 or len(b)!=5:
            raise ValueError("Each pair requires five samples on each backend")
        a_median=statistics.median(x["elapsed_wall_s"] for x in a)
        b_median=statistics.median(x["elapsed_wall_s"] for x in b)
        if a_median<=0 or b_median<=0:
            raise ValueError("Invalid latency")
        pairs.append({
            "pair":pair,"cpu_median_wall_s":round(a_median,5),
            "gpu_median_wall_s":round(b_median,5),
            "gpu_vs_cpu_wall_speed_ratio":round(a_median/b_median,5),
            "gpu_wall_latency_reduction_pct":round(100*(a_median-b_median)/a_median,3),
        })
    def aggregate_ratio(groups):
        return math.exp(statistics.mean(math.log(g["cpu_median_wall_s"]/g["gpu_median_wall_s"]) for g in groups))
    ratio=aggregate_ratio(pairs)
    rng=random.Random(seed)
    boot=[]
    for _ in range(bootstrap):
        sample=[pairs[rng.randrange(6)] for __ in range(6)]
        boot.append(aggregate_ratio(sample))
    boot.sort()
    per_backend={}
    for target in (CPU,GPU):
        sample=[r for r in measured if r["backend"]==target]
        latencies=[r["elapsed_wall_s"] for r in sample]
        tok_s=[r["completion_tokens_reported"]/r["decode_duration_s_reported"]
               for r in sample if r.get("decode_duration_s_reported",0)>0]
        per_backend[target]={
            "measured_n":len(sample),
            "median_wall_seconds":round(statistics.median(latencies),5),
            "mean_wall_seconds":round(statistics.mean(latencies),5),
            "median_reported_decode_tps":round(statistics.median(tok_s),3) if tok_s else None,
            "min_output_tokens":min(r["completion_tokens_reported"] for r in sample),
            "max_output_tokens":max(r["completion_tokens_reported"] for r in sample)
        }
    return {
        "schema":"nano-r2-windows-balanced-analysis-v1",
        "paired_blocks":6,
        "measured_samples_total":60,
        "conditions":per_backend,
        "per_pair":pairs,
        "gpu_vs_cpu_geometric_mean_wall_speed_ratio":round(ratio,4),
        "paired_block_bootstrap_95pct_CI":[round(percentile(boot,.025),4),round(percentile(boot,.975),4)],
        "confidence_method":"percentile bootstrap resampling six paired block medians; descriptive only",
        "statistical_caveats":["Six pairs are not guaranteed independent; warm-cache and thermal order remain potential confounds",
                               "Reported CPU/GPU processor residency from Ollama ps, no independent kernel trace",
                               "No sample text or output quality adjudication, no power/energy measurement",
                               "No iPhone or Core ML comparison; cross-device weight quantization does not match"],
        "iPhone_benchmarked":False,
        "cross_device_offloading_speedup_proved":False
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.input.resolve()==args.output.resolve() or args.output.exists():
        parser.error("Refusing to overwrite an existing report")
    source=json.loads(args.input.read_text(encoding="utf8"))
    result=evaluate(source)
    result["source_sha256"]=hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf8")
    print("R2_PAIRED_BLOCK_ANALYSIS_COMPLETE=YES")
    print("R2_MEASUREMENTS="+str(result["measured_samples_total"]))
    print("R2_CPU_MEDIAN_WALL_S="+str(result["conditions"][CPU]["median_wall_seconds"]))
    print("R2_GPU_MEDIAN_WALL_S="+str(result["conditions"][GPU]["median_wall_seconds"]))
    print("R2_GPU_VS_CPU_RATIO="+str(result["gpu_vs_cpu_geometric_mean_wall_speed_ratio"]))
    print("R2_BOOTSTRAP_95_CI="+str(result["paired_block_bootstrap_95pct_CI"]))

if __name__=="__main__":
    main()
