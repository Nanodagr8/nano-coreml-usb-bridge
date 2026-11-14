"""Verify published R3 Windows pilot values from allowlisted raw observations."""
import json
from pathlib import Path
import statistics
import unittest

DOC=Path(__file__).resolve().parents[1]/"results/r3_windows_host_workload_pilots_20261113.json"

class R3PublicDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=DOC.read_text(encoding="utf8")
        cls.data=json.loads(cls.text)

    def test_two_host_experiments_complete(self):
        d=self.data
        self.assertEqual(d["schema"],"nano-r3-windows-concurrency-exploratory-v1")
        self.assertEqual(len(d["runs"]),2)
        self.assertEqual(sum(len(x["observations"]) for x in d["runs"]),11)
        self.assertEqual([x["background_workers"] for x in d["runs"]],[2,4])
        self.assertEqual([len(x["observations"]) for x in d["runs"]],[4,7])
        self.assertEqual(d["iphone_measurements"],0)
        self.assertIs(d["cross_device_offloading_advantage_proved"],False)
        self.assertIs(d["energy_measured"],False)

    def test_host_compute_and_quality_all_valid(self):
        for group in self.data["runs"]:
            self.assertTrue(group["all_conditions_completed"])
            for row in group["observations"]:
                self.assertGreater(row["host_hash_mib_s"],0)
                self.assertTrue(row["ai_completed_during_host_work"])
                if row["condition"]=="baseline":
                    self.assertIsNone(row["ai_wall_s"])
                    self.assertIsNone(row["exact_answer_correct"])
                else:
                    self.assertIs(row["exact_answer_correct"],True)
                    self.assertGreater(row["ai_wall_s"],0)
                    self.assertTrue(1<=row["ai_completion_tokens"]<=32)

    def test_recompute_all_medians(self):
        for group in self.data["runs"]:
            rows=group["observations"]
            for s in group["summary"]:
                subset=[r for r in rows if r["condition"]==s["condition"]]
                self.assertEqual(s["trials"],len(subset))
                self.assertEqual(s["median_host_hash_mib_s"],
                   round(statistics.median(r["host_hash_mib_s"] for r in subset),3))
                if s["condition"]!="baseline":
                    self.assertEqual(s["median_ai_wall_s"],
                        round(statistics.median(r["ai_wall_s"] for r in subset),5))
                    self.assertEqual(s["correct_answers"],len(subset))

    def test_no_private_information(self):
        lower=self.text.lower()
        for s in ("kevin inthavong","kevininthavong","authorization","bearer ",
                  "nano-v8-local-tls","private key","c:\\users","password",
                  "prompt_text","response_text","spki.pin"):
            self.assertNotIn(s,lower)

if __name__=="__main__":
    unittest.main()
