"""Verify only sanitized, non-secret public iPhone experiment observations."""
import json
from pathlib import Path
import statistics
import unittest

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/"results/r1_qwen35_08b_iphone_usb_exploratory.json"

class R1IPhonePublicEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=RESULT.read_text(encoding="utf-8")
        cls.data=json.loads(cls.text)
    def test_12_valid_observations(self):
        d=self.data
        self.assertEqual(d["schema"],"nano-r1-sanitized-iphone-usb-v1")
        self.assertEqual(d["model"],"qwen3.5-0.8b")
        self.assertEqual(d["max_new_tokens_requested"],32)
        self.assertEqual(len(d["samples"]),12)
        self.assertEqual(sum(x["phase"]=="warmup" for x in d["samples"]),3)
        self.assertEqual(sum(x["phase"]=="measurement" for x in d["samples"]),9)
        self.assertTrue(all(x["success"] and x["output_nonempty"] for x in d["samples"]))
        self.assertTrue(all(x["completion_tokens_reported"] is None for x in d["samples"]))
        self.assertTrue(all(x["end_to_end_wall_seconds"]>0 for x in d["samples"]))
    def test_no_unverified_hardware_or_parity_claims(self):
        d=self.data
        self.assertTrue(d["host_spki_pin_validated"])
        self.assertFalse(d["comparison_speedup_claim_allowed"])
        self.assertEqual(d["model_weight_quantization_parity_with_ollama_q8_0"],"unverified")
        self.assertEqual(d["ane_hardware_execution"],"unverified")
        self.assertEqual(d["power_energy_measurements"],"not measured")
        self.assertTrue(all(not x["hardware_placement_verified"] for x in d["samples"]))
    def test_summary_recomputed(self):
        for s in self.data["summary"]:
            vals=[r["end_to_end_wall_seconds"] for r in self.data["samples"]
                if r["phase"]=="measurement" and r["prompt_label"]==s["prompt_label"]]
            self.assertEqual(len(vals),3)
            self.assertEqual(s["median_wall_seconds"],round(statistics.median(vals),5))
    def test_no_secret_or_private_material(self):
        t=self.text.lower()
        for forbidden in ("authorization","bearer ","begin private", "private key",
                          "kevininthavong","kevin inthavong","c:\\users",
                          "nano-v8-local-tls","api_key","password"):
            self.assertNotIn(forbidden,t)

if __name__=="__main__":
    unittest.main()
