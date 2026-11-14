import copy,hashlib,itertools,json,random,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'client'))
import r3_native_concurrent_analyze as audit
class NativeConcurrentEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=[json.loads((ROOT/f'results/r3_native_concurrent_{s}_20261113.json').read_text(encoding='utf-8')) for s in ('pilot','registered')]
 def test_recompute_separate_native_evidence(self):
  for d in self.data:
   self.assertEqual(audit.analyze(d),d['analysis'])
   self.assertFalse(d['energy_measured'] or d['ane_profiled'] or d['independent_external_review'])
   self.assertFalse(d['pooled_with_prior_studies'] or d['outliers_excluded'])
  self.assertTrue(self.data[0]['complete']);self.assertFalse(self.data[1]['complete'])
  self.assertFalse(self.data[1]['analysis']['primary_outcome_reported'])
  self.assertEqual(self.data[1]['analysis']['fully_valid_windows'],21)
  self.assertEqual(self.data[1]['analysis']['passed_native_jobs'],22)
 def test_locked_bytes_orders_and_measured_code(self):
  for d in self.data:
   raw=(ROOT/f"results/r3_native_concurrent_{d['stage']}_protocol_20261113.json").read_bytes();plan=json.loads(raw)
   self.assertEqual(hashlib.sha256(raw).hexdigest(),d['protocol_sha256'])
   self.assertEqual(plan['sequence'],d['registered_sequence'])
   self.assertEqual(plan['worker_sha256'],hashlib.sha256((ROOT/'client/r3_native_job.py').read_bytes()).hexdigest())
   self.assertEqual(plan['controller_sha256'],hashlib.sha256((ROOT/'client/r3_native_concurrent_study.py').read_bytes()).hexdigest())
  d=self.data[1];p=json.loads((ROOT/'results/r3_native_concurrent_registered_protocol_20261113.json').read_bytes())
  orders=list(itertools.permutations(('windows_cpu','windows_gpu_candidate','iphone_usb_coreml')))
  random.Random(p['public_order_seed']).shuffle(orders)
  self.assertEqual(orders,[tuple(o) for o in p['condition_orders']])
  for pos in range(3):self.assertTrue(all(sum(o[pos]==t for o in orders)==2 for t in orders[0]))
 def mutate(self,fn):
  d=copy.deepcopy(self.data[1]);fn(d)
  with self.assertRaises((ValueError,KeyError)):audit.analyze(d)
 def test_reject_unsigned_artifact_identity_and_freshness_failures(self):
  for change in ({'fresh_application_objects':0},{'new_application_objects_linked':False},{'dependency_inputs_sha256':'bad'}):
   self.mutate(lambda d,c=change:d['samples'][0]['compiler_job'].update(c))
  self.mutate(lambda d:d['samples'][0]['compiler_job']['macho'].update(code_signature_present=True))
 def test_reject_inference_before_frontend_or_after_native_finish(self):
  def before(d):
   row=next(r for r in d['samples'] if r['ai_requests'])
   row['ai_requests'][0]['start_offset_from_launch_s']=0
  def after(d):
   row=next(r for r in d['samples'] if r['ai_requests'])
   row['ai_requests'][-1]['finish_offset_from_launch_s']=row['compiler_job']['elapsed_s']
  for change in (before,after):
   d=copy.deepcopy(self.data[0]);change(d)
   with self.assertRaises(ValueError):audit.analyze(d)
 def test_reject_late_registration_and_over_budget(self):
  self.mutate(lambda d:d.update(registration_created_utc=d['completed_utc']))
  from datetime import datetime,timedelta
  d=copy.deepcopy(self.data[0]);d['completed_utc']=(datetime.fromisoformat(d['started_utc'])+timedelta(seconds=241)).isoformat()
  with self.assertRaises(ValueError):audit.analyze(d)
 def test_reject_incorrect_answers_placement_or_extra_job_fields(self):
  self.mutate(lambda d:d['ai_warmups'][0].update(passed_exact_answer=False))
  def placement(d):
   next(r for r in d['samples'] if r['target']=='windows_cpu')['placement_after']['size_vram_bytes']=1
  self.mutate(placement)
  self.mutate(lambda d:d['samples'][0]['compiler_job'].update(unexpected='value'))
if __name__=='__main__':unittest.main()
