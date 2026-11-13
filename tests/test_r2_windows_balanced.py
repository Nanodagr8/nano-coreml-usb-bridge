"""No-network unit tests for the bounded R2 Windows research harness."""
from pathlib import Path
import io
import json
import contextlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"client"))
import r2_windows_balanced_benchmark as r2

class R2WindowsTests(unittest.TestCase):
    def test_full_design_balanced(self):
        blocks=r2.plan("full")
        self.assertEqual(len(blocks),12)
        cpu=[b for b in blocks if b["backend"]=="windows_cpu"]
        gpu=[b for b in blocks if b["backend"]=="windows_gpu_candidate"]
        self.assertEqual(len(cpu),6)
        self.assertEqual(len(gpu),6)
        self.assertEqual(sum(b["measurements"] for b in cpu),30)
        self.assertEqual(sum(b["measurements"] for b in gpu),30)
        self.assertTrue(all(b["warmups"]==1 for b in blocks))
        for pair in range(6):
            p=[b for b in blocks if b["pair"]==pair]
            self.assertEqual({b["backend"] for b in p},
                             {"windows_cpu","windows_gpu_candidate"})
            self.assertEqual(p[0]["backend"]=="windows_cpu",pair%2==0)

    def test_pilot_is_bounded(self):
        p=r2.plan("pilot")
        self.assertEqual(len(p),2)
        self.assertEqual(sum(b["measurements"] for b in p),6)
        with self.assertRaises(ValueError):
            r2.plan("unbounded")

    def test_processor_reading(self):
        output="NAME  ID SIZE PROCESSOR CONTEXT\nqwen3.5:0.8b abcd 1.3GB 100% GPU 4096\n"
        self.assertEqual(r2.parse_processor(output),"GPU")
        self.assertEqual(r2.parse_processor(output.replace("GPU","CPU")),"CPU")
        self.assertEqual(r2.parse_processor("empty"),"unavailable")
        self.assertEqual(r2.parse_processor(output.replace("100% GPU","80% GPU / 20% CPU")),"unavailable")

    def test_dry_run_does_not_request_inference(self):
        with patch.object(r2,"run_windows_once",side_effect=AssertionError("NETWORK")):
            with contextlib.redirect_stdout(io.StringIO()) as capture:
                rc=r2.main([])
        self.assertEqual(rc,0)
        data=json.loads(capture.getvalue())
        self.assertEqual(data["mode"],"DRY_RUN")
        self.assertEqual(data["measurements_per_backend"],3)
        self.assertIs(data["phone_inference"],False)

    def test_execution_requires_explicit_mode(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as e:
                r2.main(["--execute"])
        self.assertEqual(e.exception.code,2)

    def test_summary_synthetic_only(self):
        rows=[]
        for b in ("windows_cpu","windows_gpu_candidate"):
            for i in range(3):
                rows.append({"phase":"measurement","backend":b,"success":True,
                             "elapsed_wall_s":1+i/10,
                             "completion_tokens_reported":32,
                             "decode_duration_s_reported":0.5,
                             "prefill_duration_s_reported":0.1})
        stats=r2.summarize(rows)
        self.assertEqual(len(stats),2)
        self.assertEqual(stats[0]["median_wall_s"],1.1)
        self.assertEqual(stats[1]["median_decode_tok_per_s"],64.0)

    def test_private_only_report_path(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"report.json"
            with self.assertRaises(ValueError):
                r2.save_report(path,{"sample":"x"})

    def test_no_text_or_secrets_in_published_source(self):
        source=Path(r2.__file__).read_text(encoding="utf8").lower()
        self.assertIn("no prompts or generated text",source)
        self.assertIn("independent_gpu_kernel_trace",source)
        self.assertIn("iphone_benchmarked",source)

if __name__=="__main__":
    unittest.main()
