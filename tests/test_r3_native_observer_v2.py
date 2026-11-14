import json,sys,unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import r3_native_concurrent_v2 as app
class NativeObserverTests(unittest.TestCase):
 def setUp(self):app.PROTOCOL={'native_job_deadline_s':45}
 def test_accepts_live_compiler_after_old_ten_second_cutoff(self):
  now=[0.]
  phase=Mock();phase.exists.side_effect=lambda:now[0]>=10.5
  phase.read_text.return_value=json.dumps({'phase':'compiler_started','job_manifest_sha256':'fixed','live_native_frontend_observed':True})
  child=Mock();child.poll.return_value=None
  app.wait_for_native_frontend(phase,child,'fixed',clock=lambda:now[0],sleep=lambda _:now.__setitem__(0,now[0]+.5))
  self.assertGreaterEqual(now[0],10.5);self.assertLess(now[0],45)
 def test_still_stops_at_original_native_job_limit(self):
  now=[0.];phase=Mock();phase.exists.return_value=False
  child=Mock();child.poll.return_value=None
  with self.assertRaises(RuntimeError):
   app.wait_for_native_frontend(phase,child,'fixed',clock=lambda:now[0],sleep=lambda _:now.__setitem__(0,now[0]+1))
  self.assertLessEqual(now[0],46)
 def test_rejects_exited_job_and_wrong_manifest(self):
  phase=Mock();phase.exists.return_value=False;child=Mock();child.poll.return_value=0
  with self.assertRaises(RuntimeError):app.wait_for_native_frontend(phase,child,'fixed')
  phase.exists.return_value=True;phase.read_text.return_value=json.dumps({'phase':'compiler_started','job_manifest_sha256':'wrong','live_native_frontend_observed':True})
  with self.assertRaises(ValueError):app.wait_for_native_frontend(phase,child,'fixed')
if __name__=='__main__':unittest.main()
