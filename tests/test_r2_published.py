"""Verify public R2 benchmark evidence against R2 analysis source."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"client"))
import r2_analyze

DATA=ROOT/"results/r2_windows_08b_balanced_20261113.json"
STATS=ROOT/"results/r2_windows_08b_paired_analysis_20261113.json"

class PublishedR2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=DATA.read_text(encoding="utf-8")
        cls.report=json.loads(cls.text)
        cls.analysis=json.loads(STATS.read_text(encoding="utf-8"))

    def test_60_successful_measurements(self):
        report=self.report
        self.assertEqual(report["schema"],"nano-r2-windows-balanced-v1")
        self.assertEqual(report["model"]["digest"],r2_analyze.EXPECTED_DIGEST)
        self.assertIs(report["full_execution_completed"],True)
        self.assertEqual(len(report["samples"]),72)
        self.assertEqual(len(report["block_checks"]),12)
        self.assertTrue(all(c["matches_expected"] for c in report["block_checks"]))
        measured=[r for r in report["samples"] if r["phase"]=="measurement"]
        self.assertEqual(len(measured),60)
        self.assertTrue(all(r["success"] and r["completion_tokens_reported"]==22 for r in measured))
        self.assertIs(report["iPhone_benchmarked"],False)
        self.assertIs(report["independent_power_energy_measurement"],False)

    def test_analysis_reproduces(self):
        recomputed=r2_analyze.evaluate(self.report,bootstrap=5000,seed=20261113)
        for key in ("conditions","per_pair","paired_blocks","measured_samples_total",
                    "gpu_vs_cpu_geometric_mean_wall_speed_ratio","paired_block_bootstrap_95pct_CI"):
            self.assertEqual(recomputed[key],self.analysis[key],key)
        self.assertFalse(self.analysis["cross_device_offloading_speedup_proved"])

    def test_no_unapproved_private_material(self):
        text=self.text.lower()
        for sensitive in ("kevininthavong","kevin inthavong",
                          "bearer.secret","authorization","begin private",
                          "spki.pin","c:\\users","nano-v8-local-tls","password"):
            self.assertNotIn(sensitive,text)

if __name__=="__main__":
    unittest.main()
