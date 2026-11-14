import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "client"))
import r7_live_diagnostics as live


class FakeAdapter:
    def __init__(self, answers=None, fail_on=None):
        self.answers = answers or {}
        self.fail_on = fail_on
        self.calls = 0

    def status(self):
        pass

    def generate(self, target, prompt):
        self.calls += 1
        if self.calls == self.fail_on:
            raise ConnectionResetError()
        case = next(case for case in live.coding.CASES if case["prompt"] == prompt)
        return {
            "text": self.answers.get(self.calls, case["expected"]),
            "tokens": 5, "wall_s": 1, "model_elapsed_s": 0.5,
            "source": "on_device_coreml_generator" if target == "iphone_usb_coreml" else "ollama_reported",
        }


class LiveDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "private.json"
        self.digest = hashlib.sha256(live.protocol_bytes()).hexdigest()
        self.report = live.new_report("pilot", self.digest, "test-owner", live.utc_now())

    def test_frozen_schedule_and_source_digests(self):
        plan = json.loads(live.protocol_bytes())
        self.assertEqual(len(plan["sequence"]["pilot"]), 6)
        self.assertEqual(len(plan["sequence"]["study"]), 36)
        for name, digest in plan["source_sha256"].items():
            self.assertEqual(digest, hashlib.sha256((live.ROOT / "client" / name).read_bytes()).hexdigest())

    def test_real_grader_integration_counts_and_redaction(self):
        fence = "\x60\x60\x60"
        wrapped = f"{fence}python\nrange(1,n+1)\n{fence}"
        adapter = FakeAdapter({1: wrapped, 2: "Extra prose\n" + wrapped, 3: "PRIVATE_RESPONSE_MARKER"})
        self.assertTrue(live.run_session(adapter, self.report, self.path))
        saved = self.path.read_text(encoding="utf-8")
        for marker in ("PRIVATE_RESPONSE_MARKER", "Extra prose", "range(", "input_sha256"):
            self.assertNotIn(marker, saved)
        summary = live.summarize(json.loads(saved), self.digest)
        cpu = summary["windows_cpu"]
        self.assertEqual((cpu["strict_passed"], cpu["strict_failed"], cpu["normalized_passed"]), (1, 1, 2))
        self.assertEqual(summary["windows_gpu_candidate"]["strict_unassessed"], 1)
        self.assertEqual(self.report["status_checks_passed"], 2)
        self.assertEqual(adapter.calls, 6)

    def test_partial_failure_preserves_prefix_without_retry(self):
        adapter = FakeAdapter(fail_on=2)
        self.assertFalse(live.run_session(adapter, self.report, self.path))
        self.assertEqual(self.report["stop"]["code"], "connection_reset")
        self.assertEqual((len(self.report["samples"]), adapter.calls), (1, 2))
        live.summarize(self.report, self.digest)

    def test_diagnostic_worker_failure_is_not_a_scored_answer(self):
        adapter = FakeAdapter()
        self.assertFalse(live.run_session(adapter, self.report, self.path,
                                          diagnose=lambda *_: {"classification": "worker_timeout"}))
        self.assertEqual(self.report["stop"]["code"], "diagnostic_failed")
        self.assertEqual((self.report["generation_attempts"], self.report["samples"]), (1, []))

    def test_evidence_rejects_inconsistent_verdict_and_extra_fields(self):
        self.assertTrue(live.run_session(FakeAdapter(), self.report, self.path))
        row = self.report["samples"][0]
        for field, value in (("strict_pass", None), ("normalized_pass", False), ("text", "private")):
            with patch.dict(row, {field: value}), self.assertRaises(ValueError):
                live.summarize(self.report, self.digest)
        with self.assertRaises(ValueError):
            live.summarize(self.report, "incorrect-digest")

    def test_incomplete_pilot_blocks_study_before_launch(self):
        live.run_session(FakeAdapter(fail_on=1), self.report, self.path)
        dest = Path(self.tmp.name) / "study.json"
        with patch.object(live.continuity, "supervise") as supervisor, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                live.main(["--execute", "--stage", "study", "--plan-sha256", self.digest,
                           "--pilot-report", str(self.path), "--report", str(dest)])
        supervisor.assert_not_called()
        self.assertFalse(dest.exists())

    def test_existing_report_and_wrong_plan_cannot_start(self):
        self.path.write_text("preserve", encoding="utf-8")
        args = ["--execute", "--stage", "pilot", "--report", str(self.path), "--plan-sha256"]
        with patch.object(live.continuity, "supervise") as supervisor, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                live.main(args + ["wrong-digest"])
            with self.assertRaises(FileExistsError):
                live.main(args + [self.digest])
        supervisor.assert_not_called()
        self.assertEqual(self.path.read_text(encoding="utf-8"), "preserve")
