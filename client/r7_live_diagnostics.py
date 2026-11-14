"""Run the frozen coding tasks with the isolated diagnostic grader."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from statistics import median
import sys
import time
from uuid import uuid4

import r4_foreground_reliability as continuity
import r5_coding_quality as coding
import r6_diagnostic_grading as grading


ROOT = Path(__file__).resolve().parents[1]
BUDGET = {"pilot": 120, "study": 360}
UNASSESSED = {"resource_limit", "wrapper_rejected"}
MISMATCH = {"empty_output", "invalid_json", "invalid_syntax",
            "json_value_mismatch", "python_noncanonical"}
OUTCOMES = MISMATCH | UNASSESSED | {"exact_match", "code_fence_normalized"}
SAMPLE_FIELDS = {
    "case_id", "target", "classification", "strict_pass", "normalized_pass",
    "completion_tokens", "wall_s", "model_elapsed_s", "metrics_source",
}


def protocol_bytes():
    if list(grading.CASES.values()) != list(coding.CASES):
        raise ValueError("The task bank and diagnostic reference differ")
    sources = coding.identities()
    for source in (Path(grading.__file__), Path(__file__)):
        sources[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    plan = {
        "schema": "nano-live-coding-diagnostic-plan-v1",
        "reference_tasks_sha256": grading.REFERENCE_SHA256,
        "source_sha256": sources,
        "cases": [case["id"] for case in coding.CASES],
        "sequence": {stage: coding.sequence(stage) for stage in BUDGET},
        "budget_seconds": BUDGET,
        "max_output_tokens": coding.MAX_TOKENS,
        "model_ids": {"windows": coding.WINDOWS_MODEL, "iphone": continuity.MODEL},
        "primary": "Counts by diagnostic classification for each target on the fixed suite.",
        "secondary": "Strict true, false and unassessed counts, fence-normalized counts, "
                     "token-cap hits and median generation wall time per target.",
        "pilot_gate": "Six completed responses and both readiness checks. Exclude pilot "
                      "observations from study results. Pilot correctness is not a gate.",
        "stopping": "Stop at the first service, metrics, grader infrastructure or budget failure. "
                    "Keep the prefix. No automatic retries or unrecorded generation warmups.",
        "unassessed_strict": sorted(UNASSESSED),
        "privacy": "Grade transient answers in the isolated worker. Persist labels and numeric "
                   "metadata only. Never execute candidate code.",
        "limits": "One observation per case and target, repeated pilot tasks, unmatched model "
                  "implementations and load state. No semantic correctness, hardware placement, "
                  "energy or productivity estimate.",
    }
    return (json.dumps(plan, indent=2, sort_keys=True) + "\n").encode("utf-8")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def new_report(stage, digest, nonce, started_utc):
    return {
        "schema": "nano-live-coding-diagnostics-v1", "stage": stage,
        "protocol_sha256": digest, "owner_nonce": nonce, "started_utc": started_utc,
        "complete": False, "stop": None, "status_checks_passed": 0,
        "generation_attempts": 0, "samples": [],
    }


def run_session(adapter, report, path, diagnose=grading.diagnose):
    stage = report["stage"]
    start = time.monotonic()
    phase, case_id, target = "initial_readiness", None, None

    def check_budget():
        if time.monotonic() - start >= BUDGET[stage]:
            raise continuity.CheckFailure("study_budget_expired")

    try:
        adapter.status()
        report["status_checks_passed"] = 1
        continuity.checkpoint(path, report)
        for case_id, target in coding.sequence(stage):
            phase = "generation"
            check_budget()
            report["generation_attempts"] += 1
            continuity.checkpoint(path, report)
            row = adapter.generate(target, grading.CASES[case_id]["prompt"])
            metrics = coding.validate_metrics(row, target)
            phase = "diagnostic"
            verdict = diagnose(case_id, row.pop("text"))
            if verdict["classification"] not in OUTCOMES:
                raise ValueError("Diagnostic worker could not classify the response")
            report["samples"].append({
                "case_id": case_id, "target": target,
                "classification": verdict["classification"],
                "strict_pass": verdict["strict_pass"],
                "normalized_pass": verdict["normalized_pass"], **metrics,
            })
            continuity.checkpoint(path, report)
        phase, case_id, target = "final_readiness", None, None
        check_budget()
        adapter.status()
        report["status_checks_passed"] = 2
        check_budget()
        report["complete"] = True
    except Exception as exc:
        if isinstance(exc, coding.InvalidMetrics):
            code = "metrics_invalid"
        elif phase == "diagnostic":
            code = "diagnostic_failed"
        else:
            code = continuity.classify(exc)
        report["stop"] = {"code": code, "phase": phase, "case_id": case_id, "target": target}
    finally:
        report["elapsed_s"] = round(time.monotonic() - start, 6)
        report["finished_utc"] = utc_now()
        continuity.checkpoint(path, report)
    return report["complete"]


def summarize(report, digest):
    def require(condition):
        if not condition:
            raise ValueError("Invalid live diagnostic evidence")

    require(report["schema"] == "nano-live-coding-diagnostics-v1")
    require(report["protocol_sha256"] == digest and report["stage"] in BUDGET)
    order = coding.sequence(report["stage"])
    rows = report["samples"]
    require([(r["case_id"], r["target"]) for r in rows] == order[:len(rows)])
    require(type(report["generation_attempts"]) is int)
    require(len(rows) <= report["generation_attempts"] <= min(len(order), len(rows) + 1))
    require(type(report["complete"]) is bool and type(report["status_checks_passed"]) is int)
    require(0 <= report["status_checks_passed"] <= 2)
    if report["complete"]:
        require(report["stop"] is None and len(rows) == len(order) and report["status_checks_passed"] == 2)
        require(isinstance(report["elapsed_s"], (float, int)) and math.isfinite(report["elapsed_s"])
                and 0 <= report["elapsed_s"] <= BUDGET[report["stage"]])
    else:
        require(isinstance(report["stop"], dict))
    for row in rows:
        require(set(row) == SAMPLE_FIELDS)
        label = row["classification"]
        require(label in OUTCOMES)
        expected_strict = None if label in UNASSESSED else label == "exact_match"
        require(row["strict_pass"] is expected_strict)
        require(row["normalized_pass"] is (label in {"exact_match", "code_fence_normalized"}))
        coding.validate_metrics({"text": "", "tokens": row["completion_tokens"],
                                 "wall_s": row["wall_s"], "model_elapsed_s": row["model_elapsed_s"],
                                 "source": row["metrics_source"]}, row["target"])
    by_target = {}
    for target in coding.TARGETS:
        group = [row for row in rows if row["target"] == target]
        counts = Counter(row["classification"] for row in group)
        by_target[target] = {
            "responses": len(group), "classification_counts": dict(sorted(counts.items())),
            "strict_passed": counts["exact_match"],
            "strict_failed": sum(row["strict_pass"] is False for row in group),
            "strict_unassessed": sum(row["strict_pass"] is None for row in group),
            "normalized_passed": sum(row["normalized_pass"] for row in group),
            "token_cap_hits": sum(row["completion_tokens"] == coding.MAX_TOKENS for row in group),
            "median_wall_s": round(median(row["wall_s"] for row in group), 6) if group else None,
        }
    return by_target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--stage", choices=BUDGET)
    parser.add_argument("--plan-sha256")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--pilot-report", type=Path)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    plan = protocol_bytes()
    if not args.execute and not args.worker:
        sys.stdout.buffer.write(plan)
        return 0
    digest = hashlib.sha256(plan).hexdigest()
    if args.plan_sha256 != digest or not args.stage or not args.report:
        parser.error("Live execution requires the frozen plan digest, stage and new private report")
    path = args.report.resolve()
    if path == ROOT or ROOT in path.parents or not path.parent.is_dir():
        parser.error("Use a private report outside the checkout")
    if args.stage == "study":
        if not args.pilot_report:
            parser.error("Study requires a completed pilot report")
        pilot = json.loads(args.pilot_report.read_bytes())
        summarize(pilot, digest)
        if pilot["stage"] != "pilot" or not pilot["complete"]:
            parser.error("Study requires a completed pilot under this protocol")
    if args.worker:
        report = json.loads(path.read_bytes())
        if report != new_report(args.stage, digest, args.worker, report.get("started_utc")):
            parser.error("Worker requires its own fresh checkpoint")
        try:
            adapter = coding.LiveAdapter()
        except Exception:
            report["stop"] = {"code": "configuration_invalid", "phase": "configuration",
                              "case_id": None, "target": None}
            report["finished_utc"] = utc_now()
            continuity.checkpoint(path, report)
            return 2
        return 0 if run_session(adapter, report, path) else 2
    nonce = uuid4().hex
    with path.open("x", encoding="utf-8") as output:
        json.dump(new_report(args.stage, digest, nonce, utc_now()), output)
    child = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", nonce,
             "--stage", args.stage, "--plan-sha256", digest, "--report", str(path)]
    if args.pilot_report:
        child.extend(["--pilot-report", str(args.pilot_report.resolve())])
    try:
        rc = continuity.supervise(child, path, nonce, BUDGET[args.stage])
    except OSError:
        rc = 2
    result = json.loads(path.read_bytes())
    if rc and result["stop"] is None:
        result = continuity.owned_failure(path, nonce, "worker_process_failed")
    summary = summarize(result, digest)
    print(json.dumps({"complete": result["complete"], "stop": result["stop"], "targets": summary}))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
