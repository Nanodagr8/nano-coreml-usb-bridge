"""NANO R1 protocol and benchmark guard tests, with synthetic responses."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "client"))
import r1_benchmark as r1

class R1Tests(unittest.TestCase):
    def test_plan_dry_run_and_model_mismatch(self):
        plan = r1.plan()
        self.assertEqual(plan["default_run"], "DRY_RUN_NO_INFERENCE")
        self.assertFalse(plan["parity"]["matched"])
        self.assertNotEqual(plan["windows"]["model"], plan["iphone"]["model"])
        self.assertFalse(plan["windows"]["gpu_execution_verified"])
        self.assertFalse(plan["iphone"]["ane_execution_verified"])

    def test_parity_fails_closed(self):
        self.assertFalse(r1.model_parity("a","a")["matched"])
        self.assertFalse(r1.model_parity("a","b", "hash","hash","Q4","Q4","tok","tok")["matched"])
        self.assertFalse(r1.model_parity("a","a", "hash","hash","Q4","Q8","tok","tok")["matched"])
        self.assertFalse(r1.model_parity("a","a", "hash","hash","Q4","Q4","tok",None)["matched"])
        self.assertTrue(r1.model_parity("a","a", "hash","hash","Q4","Q4","tok","tok")["matched"])

    def test_reject_unbounded_schedule(self):
        for rep,warm in [(0,0),(31,0),(1,-1),(1,6),(True,0),(1,True)]:
            with self.subTest(rep=rep,warm=warm), self.assertRaises(ValueError):
                r1.make_schedule(rep,warm,("short",))
        self.assertEqual(len(r1.make_schedule(3,2,("short","logic"))), 10)

    def test_schedule_reproducible(self):
        a=r1.make_schedule(5,2,("short","logic","structure"))
        b=r1.make_schedule(5,2,("short","logic","structure"))
        self.assertEqual(a,b)

    def test_windows_forces_cpu_and_sanitizes_output(self):
        payloads=[]
        def fake(url,payload):
            payloads.append(payload)
            return {"model":r1.WINDOWS_MODEL,
                    "response":"PRIVATE_OUTPUT_DO_NOT_RECORD",
                    "eval_count":12,
                    "eval_duration":2000000000,
                    "prompt_eval_duration":100000000}
        row=r1.run_windows_once("private prompt","short",request_fn=fake)
        self.assertEqual(payloads[0]["options"]["num_gpu"],0)
        self.assertEqual(payloads[0]["options"]["temperature"],0)
        self.assertEqual(payloads[0]["options"]["num_predict"],32)
        self.assertIs(payloads[0]["think"], False)
        self.assertFalse(row["hardware_placement_verified"])
        self.assertNotIn("PRIVATE_OUTPUT",json.dumps(row))
        self.assertNotIn("private prompt",json.dumps(row))
        self.assertEqual(row["completion_tokens_reported"],12)

    def test_windows_gpu_candidate_never_claims_gpu(self):
        def fake(url,payload):
            self.assertEqual(payload["options"]["num_gpu"],99)
            return {"response":"done","eval_count":1}
        row=r1.run_windows_once("x","structure",cpu_only=False,request_fn=fake)
        self.assertEqual(row["target"],"windows_gpu_candidate")
        self.assertFalse(row["hardware_placement_verified"])

    def test_iphone_result_no_prompt_or_generated_text(self):
        class FakeClient:
            def generate(self,prompt,max_tokens):
                self_args=(prompt,max_tokens)
                return {"model_id":r1.IPHONE_MODEL,
                        "text":"PRIVATE_IPHONE_RESPONSE"}
        row=r1.run_iphone_once("PRIVATE_IPHONE_PROMPT","logic",client=FakeClient())
        self.assertTrue(row["success"])
        self.assertNotIn("PRIVATE_IPHONE",json.dumps(row))
        self.assertIsNone(row["completion_tokens_reported"])
        self.assertFalse(row["hardware_placement_verified"])

    def test_iphone_empty_text_is_rejected(self):
        class FakeEmpty:
            def generate(self,prompt,max_tokens):
                return {"model_id":r1.IPHONE_MODEL, "text":" "}
        with self.assertRaises(ValueError):
            r1.run_iphone_once("public synthetic prompt","short",client=FakeEmpty())

    def test_summary_no_cross_model_speedup(self):
        rows=[{"target":"windows_cpu","label":"short","phase":"measurement",
               "success":True,"elapsed_wall_s":2.5},
              {"target":"iphone_usb_coreml","label":"short","phase":"measurement",
               "success":True,"elapsed_wall_s":1.0}]
        data=r1.summarize(rows)
        self.assertFalse(data["matched_model_comparison"])
        self.assertTrue(all(not g["comparative_speedup_claim_allowed"] for g in data["groups"]))

    def test_dry_run_has_no_side_effects(self):
        with patch.object(r1,"_bounded_request",side_effect=AssertionError("NETWORK")):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc=r1.main([])
        self.assertEqual(rc,0)
        self.assertIn("DRY_RUN_NO_INFERENCE",out.getvalue())

    def test_08b_model_selection_uses_explicit_identifier(self):
        seen = []
        def fake(url, payload):
            seen.append(payload)
            return {"model":"qwen3.5:0.8b", "response":"PRIVATE_DO_NOT_LOG",
                    "eval_count":8, "eval_duration":1000000000}
        row = r1.run_windows_once("sensitive input", "short",
                                   model="qwen3.5:0.8b", request_fn=fake)
        self.assertEqual(row["model"], "qwen3.5:0.8b")
        self.assertEqual(seen[0]["model"], "qwen3.5:0.8b")
        self.assertIs(seen[0]["think"], False)
        self.assertNotIn("PRIVATE_DO_NOT_LOG",json.dumps(row))
        self.assertNotIn("sensitive input",json.dumps(row))
        self.assertFalse(r1.plan("qwen3.5:0.8b")["parity"]["matched"])

    def test_reject_unapproved_model_and_response_mismatch(self):
        with self.assertRaises(ValueError):
            r1.plan("my-private-model:latest")
        with self.assertRaises(ValueError):
            r1.run_windows_once("prompt", "short", model="my-private-model:latest",
                                request_fn=lambda url, body: {})
        with self.assertRaises(ValueError):
            r1.run_windows_once("prompt", "short", model="qwen3.5:0.8b",
                                request_fn=lambda url, body: {"model":"qwen3.5:4b", "response":"wrong model"})

    def test_08b_cli_is_dry_run_unless_opted_in(self):
        with patch.object(r1, "_bounded_request",side_effect=AssertionError("UNEXPECTED_NETWORK")):
            with contextlib.redirect_stdout(io.StringIO()) as captured:
                rc = r1.main(["--windows-model", "qwen3.5:0.8b"])
        self.assertEqual(rc,0)
        self.assertIn("qwen3.5:0.8b", captured.getvalue())
        self.assertIn("DRY_RUN_NO_INFERENCE",captured.getvalue())

    def test_immutable_windows_endpoint(self):
        with self.assertRaises(ValueError):
            r1._bounded_request("http://0.0.0.0:11434/api/generate",{})
        with self.assertRaises(ValueError):
            r1._bounded_request("https://example.com/api/generate",{})

if __name__=="__main__": unittest.main()
