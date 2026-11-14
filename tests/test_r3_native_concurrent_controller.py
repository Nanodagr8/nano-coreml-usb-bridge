import contextlib,io,hashlib,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'client'))
import r3_native_concurrent_study as app
import test_r3_native_job as native_tests
class NativeConcurrentControllerTests(unittest.TestCase):
 def test_dry_plan_does_not_start_phone_or_process(self):
  with patch.object(app.subprocess,'Popen') as child,patch.object(app,'NanoUSBClient') as phone,contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(app.main([]),0)
  child.assert_not_called();phone.assert_not_called()
 def test_locked_plan_tamper_rejected(self):
  with self.assertRaises(ValueError):app.load_plan(ROOT/'results/r3_native_concurrent_pilot_protocol_20261113.json','0'*64)
 def test_locked_pilot_plan_is_full_explicit_target_set(self):
  f=ROOT/'results/r3_native_concurrent_pilot_protocol_20261113.json'
  app.load_plan(f,hashlib.sha256(f.read_bytes()).hexdigest())
  self.assertEqual(app.ORDER[0],app.ORDER[-1])
  self.assertEqual(set(app.ORDER),{'baseline','windows_cpu','windows_gpu_candidate','iphone_usb_coreml'})
 def test_native_artifact_failure_is_never_hidden_by_answer_quality(self):
  r=native_tests.NativeJobTests().valid();r['fresh_application_objects']=0
  self.assertEqual(app.assess(r,[],False),'stale_artifact')
 def test_native_overlap_quality_and_identity(self):
  f=ROOT/'results/r3_native_concurrent_pilot_protocol_20261113.json'
  app.load_plan(f,hashlib.sha256(f.read_bytes()).hexdigest());app.MANIFEST='fixed'
  r=native_tests.NativeJobTests().valid()
  r.update(passed=True,elapsed_s=6,source_count=10,logical_spec_sha256=app.PROTOCOL['logical_spec_sha256'],
   native_spec_sha256=app.PROTOCOL['native_spec_sha256'],job_manifest_sha256='fixed')
  answers=[{'task_label':t,'passed_exact_answer':True,'finish_offset_from_launch_s':4} for t in app.TASKS]
  self.assertIsNone(app.assess(r,answers,True))
  answers[-1]['finish_offset_from_launch_s']=5.9
  self.assertEqual(app.assess(r,answers,True),'conservative_overlap_gate_failed')
if __name__=='__main__':unittest.main()
