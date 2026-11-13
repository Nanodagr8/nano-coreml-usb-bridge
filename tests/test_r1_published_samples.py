"""Audit sanitized R1 Windows observations without running any inference."""
import json
from pathlib import Path
import statistics
import unittest

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/"results/r1_qwen35_08b_windows_exploratory.json"

class PublishedR1ResultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=PUBLIC.read_text(encoding="utf-8")
        cls.doc=json.loads(cls.text)

    def test_model_identification_and_hardware_caveats(self):
        doc=self.doc
        self.assertEqual(doc["schema"],"nano-r1-sanitized-windows-v1")
        self.assertEqual(doc["model"]["ollama_tag"],"qwen3.5:0.8b")
        self.assertEqual(doc["model"]["quantization"],"Q8_0")
        self.assertEqual(len(doc["model"]["ollama_digest"]),64)
        self.assertFalse(doc["protocol"]["matched_iphone_quantization"])
        self.assertFalse(doc["protocol"]["iphone_coreml_benchmark_performed"])
        self.assertFalse(doc["protocol"]["novelty_or_speedup_claim"])
        self.assertFalse(doc["protocol"]["power_energy_measured"])

    def test_all_samples_present_and_bounded(self):
        rows=self.doc["samples"]
        self.assertEqual(len(rows),24)
        for target in ("windows_cpu","windows_gpu_candidate"):
            matched=[r for r in rows if r["requested_backend"]==target]
            self.assertEqual(len(matched),12)
            self.assertEqual(sum(r["phase"]=="measurement" for r in matched),9)
            self.assertEqual(sum(r["phase"]=="warmup" for r in matched),3)
            for row in matched:
                self.assertTrue(row["success"])
                self.assertGreater(row["end_to_end_wall_seconds"],0)
                self.assertLessEqual(row["completion_tokens_reported"],32)

    def test_summary_matches_samples(self):
        for summary in self.doc["summary"]:
            values=[row["end_to_end_wall_seconds"] for row in self.doc["samples"]
                    if row["phase"]=="measurement"
                    and row["prompt_label"]==summary["prompt_label"]
                    and row["requested_backend"]==summary["requested_backend"]]
            self.assertEqual(summary["n"],3)
            self.assertEqual(summary["median_wall_seconds"],
                             round(statistics.median(values),5))

    def test_no_sensitive_user_material(self):
        text=self.text.lower()
        for value in ["bearer ", "authorization", "private key", "kevin inthavong",
                      "kevininthavong", "begin private", "private_output",
                      "nano-v8-local-tls", "c:\\users", "password"]:
            self.assertNotIn(value,text)

if __name__=="__main__":
    unittest.main()
