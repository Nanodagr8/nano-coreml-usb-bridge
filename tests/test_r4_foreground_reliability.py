from pathlib import Path
import contextlib,io,json,ssl,subprocess,sys,tempfile,unittest
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'client'))
import r4_foreground_reliability as r4
class Clock:
 def __init__(self):self.now=0
 def clock(self):return self.now
 def sleep(self,value):self.now+=value
class Phone:
 def __init__(self,error=None):self.error=error;self.calls=0
 def status(self):
  if self.error:raise self.error
  return {'model_id':r4.MODEL,'status':'ready','private_extra':'never publish this'}
 def generate(self,prompt,max_tokens):
  self.calls+=1
  return {'model_id':r4.MODEL,'text':'42' if '17 + 25' in prompt else 'BLUE',
   'completion_tokens':2,'model_elapsed_ms':200.,'generator_tokens_per_second':10.,
   'metrics_source':'on_device_coreml_generator','private_extra':'never publish this'}
def plan():return {'stage':'soak','rounds':6,'idle_seconds':120,'budget_s':900}
class ForegroundContinuityTests(unittest.TestCase):
 def test_six_idle_intervals_and_exact_request_counts(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'r.json';clock=Clock();phone=Phone()
   r=r4.run_session(lambda:phone,path,plan(),'hash','owned',clock.clock,clock.sleep)
   self.assertTrue(r['complete']);self.assertEqual(len(r['samples']),12);self.assertEqual(len(r['statuses']),13)
   self.assertEqual(len(r['idle_intervals']),6);self.assertEqual(r['observed_elapsed_s'],720)
   text=path.read_text();self.assertNotIn('never publish',text);self.assertNotIn('What is',text);self.assertNotIn('BLUE',text)
 def test_pin_auth_and_transport_faults_stop_before_generation(self):
  for error,code in ((r4.PinMismatch('LEAK_ME'),'pin_rejected'),(r4.AuthenticationError('LEAK_ME'),'authorization_rejected'),
   (ConnectionResetError('LEAK_ME'),'connection_reset'),(TimeoutError('LEAK_ME'),'transport_timeout'),(ssl.SSLError('LEAK_ME'),'tls_failed')):
   with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'r.json';phone=Phone(error);clock=Clock()
    r=r4.run_session(lambda:phone,path,plan(),'hash','owned',clock.clock,clock.sleep)
    self.assertFalse(r['complete']);self.assertEqual(r['stop']['code'],code);self.assertEqual(phone.calls,0)
    self.assertNotIn('LEAK_ME',path.read_text())
 def test_unknown_error_messages_and_codes_are_not_serialized(self):
  self.assertEqual(r4.classify(RuntimeError('sensitive secret')),'unexpected_error')
  self.assertEqual(r4.classify(r4.CheckFailure('sensitive secret')),'unexpected_error')
 def test_model_not_ready_never_generates(self):
  phone=Phone();phone.status=lambda:{'model_id':r4.MODEL,'status':'unloaded'}
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'r.json';clock=Clock()
   r=r4.run_session(lambda:phone,path,plan(),'hash','owned',clock.clock,clock.sleep)
   self.assertEqual(r['stop']['code'],'model_not_ready');self.assertEqual(phone.calls,0)
 def test_quality_and_telemetry_are_required(self):
  value=Phone().generate('17 + 25',32)
  self.assertTrue(r4.check_response(value,'42',.2)['on_device_metrics_verified'])
  for field,bad in (('text','43'),('completion_tokens',0),('metrics_source','unknown'),('model_elapsed_ms',float('nan'))):
   changed=dict(value);changed[field]=bad
   with self.assertRaises(r4.CheckFailure):r4.check_response(changed,'42',.2)
 def test_existing_evidence_and_foreign_checkpoints_are_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'r.json';path.write_text('{"owner_nonce":"other"}')
   with self.assertRaises(FileExistsError):r4.run_session(lambda:Phone(),path,plan(),'hash','mine')
   with self.assertRaises(ValueError):r4.owned_failure(path,'mine','study_budget_expired')
   self.assertEqual(json.loads(path.read_text())['owner_nonce'],'other')
 def test_supervisor_terminates_only_its_child_and_preserves_checkpoint(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'r.json';path.write_text(json.dumps({'owner_nonce':'mine','complete':False,'samples':[{'safe':True}]}))
   child=Mock();child.wait.side_effect=[subprocess.TimeoutExpired('worker',1),0]
   with patch.object(r4.subprocess,'Popen',return_value=child):
    self.assertEqual(r4.supervise(['owned-worker'],path,'mine',1),2)
   child.terminate.assert_called_once();saved=json.loads(path.read_text())
   self.assertEqual(saved['stop']['code'],'study_budget_expired');self.assertEqual(saved['samples'],[{'safe':True}])
 def test_dry_plan_never_starts_a_worker(self):
  with patch.object(r4.subprocess,'Popen') as child,contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(r4.main([]),0)
  child.assert_not_called()
if __name__=='__main__':unittest.main()
