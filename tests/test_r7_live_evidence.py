"""Recompute the published live summaries from every retained row."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client"))
import r7_live_diagnostics as live


class RegisteredEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = ROOT / "results"
        cls.plan = (cls.results / "r7_live_protocol_20261114.json").read_bytes()
        cls.evidence = json.loads((cls.results / "r7_live_diagnostics_20261114.json").read_bytes())

    def test_protocol_identity_and_chronology(self):
        self.assertEqual(self.plan, live.protocol_bytes())
        self.assertEqual(self.evidence["protocol_sha256"], hashlib.sha256(self.plan).hexdigest())
        self.assertEqual(self.evidence["reference_tasks_sha256"], live.grading.REFERENCE_SHA256)
        previous = datetime.fromisoformat(self.evidence["registered_utc"])
        for stage in ("pilot", "study"):
            report = self.evidence["stages"][stage]
            start = datetime.fromisoformat(report["started_utc"])
            end = datetime.fromisoformat(report["finished_utc"])
            self.assertLessEqual(previous, start)
            self.assertLessEqual(start, end)
            self.assertTrue(report["complete"])
            self.assertIs(report["protected_credentials_matched_before_after"], True)
            self.assertLess(end.timestamp() - start.timestamp(), live.BUDGET[stage])
            previous = end

    def test_all_rows_reproduce_published_separate_stage_summaries(self):
        for stage, planned in (("pilot", 6), ("study", 36)):
            report = self.evidence["stages"][stage]
            self.assertEqual(report["stage"], stage)
            self.assertEqual((len(report["samples"]), report["generation_attempts"]), (planned, planned))
            self.assertEqual(report["status_checks_passed"], 2)
            self.assertIsNone(report["stop"])
            self.assertEqual(report["by_target"], live.summarize(report, self.evidence["protocol_sha256"]))
            for target in live.coding.TARGETS:
                rows = [r for r in report["samples"] if r["target"] == target]
                self.assertEqual(len({r["case_id"] for r in rows}), planned // 3)
                labels = Counter(r["classification"] for r in rows)
                totals = report["by_target"][target]
                self.assertEqual(labels, totals["classification_counts"])
                self.assertEqual(totals["normalized_passed"],
                                 labels["exact_match"] + labels["code_fence_normalized"])
