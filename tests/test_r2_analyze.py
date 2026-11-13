"""Deterministic data-only tests for R2 paired analysis."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"client"))
import r2_analyze as analysis

def fixture():
    rows=[]
    blocks=[]
    for pair in range(6):
        sequence=("windows_cpu","windows_gpu_candidate") if pair%2==0 else (
            "windows_gpu_candidate","windows_cpu")
        for pos,backend in enumerate(sequence):
            block=pair*2+pos
            expected="CPU" if backend=="windows_cpu" else "GPU"
            blocks.append({"block":block,"backend":backend,
                           "ollama_ps_reported_processor":expected,
                           "matches_expected":True})
            for phase,count in (("warmup",1),("measurement",5)):
                for i in range(count):
                    rows.append({
                        "backend":backend,"pair":pair,"position":pos,
                        "block":block,"phase":phase,"iteration":i,"success":True,
                        "elapsed_wall_s":2.0+(pair/100)+(i/100) if expected=="CPU" else
                                         1.0+(pair/100)+(i/100),
                        "completion_tokens_reported":22,
                        "decode_duration_s_reported":1.3 if expected=="CPU" else .7,
                    })
    return {"schema":"nano-r2-windows-balanced-v1","mode":"full",
            "full_execution_completed":True,
            "model":{"digest":analysis.EXPECTED_DIGEST},
            "block_checks":blocks,"samples":rows}

class R2AnalysisTests(unittest.TestCase):
    def test_matched_block_structure_and_ci(self):
        result=analysis.evaluate(fixture(),bootstrap=400,seed=42)
        self.assertEqual(result["paired_blocks"],6)
        self.assertEqual(result["measured_samples_total"],60)
        self.assertEqual(result["conditions"]["windows_cpu"]["measured_n"],30)
        self.assertEqual(result["conditions"]["windows_gpu_candidate"]["measured_n"],30)
        self.assertGreater(result["gpu_vs_cpu_geometric_mean_wall_speed_ratio"],1.0)
        low,high=result["paired_block_bootstrap_95pct_CI"]
        self.assertLessEqual(low,high)
        self.assertFalse(result["cross_device_offloading_speedup_proved"])
        self.assertFalse(result["iPhone_benchmarked"])

    def test_determinism(self):
        self.assertEqual(
            json.dumps(analysis.evaluate(fixture(),bootstrap=200,seed=33),sort_keys=True),
            json.dumps(analysis.evaluate(fixture(),bootstrap=200,seed=33),sort_keys=True))

    def test_reject_partial(self):
        r=fixture()
        r["full_execution_completed"]=False
        with self.assertRaises(ValueError):
            analysis.evaluate(r)
        r=fixture()
        r["samples"].pop()
        with self.assertRaises(ValueError):
            analysis.evaluate(r)

    def test_reject_wrong_model_and_processor(self):
        r=fixture()
        r["model"]["digest"]="unknown"
        with self.assertRaises(ValueError):
            analysis.evaluate(r)
        r=fixture()
        r["block_checks"][0]["matches_expected"]=False
        with self.assertRaises(ValueError):
            analysis.evaluate(r)

    def test_reject_invalid_response(self):
        r=fixture()
        r["samples"][5]["completion_tokens_reported"]=None
        with self.assertRaises(ValueError):
            analysis.evaluate(r)

if __name__=="__main__":
    unittest.main()
