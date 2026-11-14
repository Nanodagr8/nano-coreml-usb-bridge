"""Offline tests for NANO R3 workload isolation and quality gates."""
from pathlib import Path
import io
import contextlib
import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"client"))
import r3_system_workload as r3

class R3Tests(unittest.TestCase):
    def test_dry_run_and_schedule(self):
        with patch.object(r3,"_bounded_request",side_effect=AssertionError("NO_NETWORK")):
            with contextlib.redirect_stdout(io.StringIO()) as s:
                rc=r3.main([])
        self.assertEqual(rc,0)
        obj=json.loads(s.getvalue())
        self.assertEqual(obj["mode"],"DRY_RUN_NO_INFERENCE")
        self.assertEqual(obj["order"],["baseline","windows_cpu","windows_gpu_candidate",
                                        "baseline","windows_gpu_candidate","windows_cpu",
                                        "baseline"])
        self.assertNotIn("iphone_usb_coreml",obj["order"])

    def test_guards(self):
        with self.assertRaises(ValueError):
            r3.plan(["baseline","baseline"],2,5,2)
        with self.assertRaises(ValueError):
            r3.plan(["not_a_target"],2,5,2)
        with self.assertRaises(ValueError):
            r3.plan(["windows_cpu"],11,5,2)
        with self.assertRaises(ValueError):
            r3.plan(["windows_cpu"],2,9,2)
        with self.assertRaises(ValueError):
            r3.plan(["windows_cpu"],2,5,5)

    def test_successful_cpu_and_gpu_quality(self):
        def f(url,request,timeout=40):
            self.assertEqual(url,r3.OLLAMA_URL)
            self.assertEqual(request["model"],r3.MODEL)
            self.assertIs(request["think"],False)
            self.assertEqual(request["options"]["num_predict"],32)
            return {"model":r3.MODEL, "response":"42","eval_count":22,
                    "eval_duration":1000000000,"prompt_eval_duration":100000000}
        for kind in ("windows_cpu","windows_gpu_candidate"):
            with patch.object(r3,"_bounded_request",f):
                observed=r3.infer(kind,"arithmetic")
            self.assertTrue(observed["passed_exact_answer"])
            self.assertEqual(observed["completion_tokens"],22)
            self.assertNotIn("response",json.dumps(observed))

    def test_invalid_quality_is_recorded_not_output(self):
        with patch.object(r3,"_bounded_request",
                          return_value={"model":r3.MODEL,"response":"forty two",
                                        "eval_count":12}):
            observed=r3.infer("windows_cpu","arithmetic")
        self.assertIs(observed["passed_exact_answer"],False)
        self.assertNotIn("forty two",json.dumps(observed))

    def test_iphone_uses_bounded_pinned_client(self):
        class FakePhone:
            def generate(self,prompt,max_tokens):
                self_args=[max_tokens]
                return {"text":"42","completion_tokens":3,
                        "metrics_source":"on_device_coreml_generator",
                        "model_elapsed_ms":1300.0}
        observed=r3.infer("iphone_usb_coreml","arithmetic",client=FakePhone())
        self.assertTrue(observed["passed_exact_answer"])
        self.assertEqual(observed["completion_tokens"],3)

    def test_missing_iphone_metrics_fail(self):
        class FakePhone:
            def generate(self,prompt,max_tokens):
                return {"text":"42","completion_tokens":None,"metrics_source":None}
        with self.assertRaises(ValueError):
            r3.infer("iphone_usb_coreml","arithmetic",client=FakePhone())

    def test_summary(self):
        rows=[{"target":"baseline","success":True,"host_hash_mib_s":200,"ai":None},
              {"target":"windows_cpu","success":True,"host_hash_mib_s":180,
               "ai":{"wall_s":1.3,"passed_exact_answer":True}}]
        stats=r3.summarize(rows)
        self.assertEqual(stats[0]["target"],"baseline")
        self.assertEqual(stats[1]["checked_answers"],1)

if __name__=="__main__":
    unittest.main()
