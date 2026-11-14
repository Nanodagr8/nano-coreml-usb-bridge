from pathlib import Path
import copy,hashlib,itertools,json,random,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'client'))
import r3_native_concurrent_analyze as audit
class CorrectedNativeEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=json.loads((ROOT/'results/r3_native_concurrent_corrected_20261113.json').read_text(encoding='utf-8'))
 def mutate(self,fn):
  d=copy.deepcopy(self.data);fn(d)
  with self.assertRaises((ValueError,KeyError)):audit.analyze(d)
 def test_complete_corrected_outcome_recomputes_without_prior_pooling(self):
  d=self.data
  self.assertTrue(d['complete']);self.assertEqual(audit.analyze(d),d['analysis'])
  self.assertEqual(d['analysis']['native_artifact_checks_passed'],50)
  self.assertFalse(d['pooled_with_prior_studies'] or d['outliers_excluded'])
  for stage in ('registered','followup'):
   prior=json.loads((ROOT/f'results/r3_native_concurrent_{stage}_20261113.json').read_text(encoding='utf-8'))
   self.assertFalse(prior['complete']);self.assertFalse(prior['analysis']['primary_outcome_reported'])
 def test_corrected_protocol_and_measured_sources_keep_exact_bytes(self):
  d=self.data;raw=(ROOT/d['protocol_file']).read_bytes();p=json.loads(raw)
  self.assertEqual(hashlib.sha256(raw).hexdigest(),d['protocol_sha256'])
  self.assertEqual(p['controller_sha256'],hashlib.sha256((ROOT/'client/r3_native_concurrent_v2.py').read_bytes()).hexdigest())
  self.assertEqual(p['worker_sha256'],hashlib.sha256((ROOT/'client/r3_native_job.py').read_bytes()).hexdigest())
  self.assertEqual(p['native_job_deadline_s'],45);self.assertEqual(p['observer_deadline_s'],45)
  self.assertEqual(p['conservative_overlap_margin_s'],.25);self.assertEqual(p['label_prefix'],'native_corrected')
  orders=list(itertools.permutations(('windows_cpu','windows_gpu_candidate','iphone_usb_coreml')))
  random.Random(p['public_order_seed']).shuffle(orders)
  self.assertEqual(orders,[tuple(x) for x in p['condition_orders']])
 def test_reject_stale_objects_changed_inputs_and_signature(self):
  for change in ({'fresh_application_objects':9},{'dependency_inputs_unchanged':False},{'new_application_objects_linked':False}):
   self.mutate(lambda d,c=change:d['samples'][0]['compiler_job'].update(c))
  self.mutate(lambda d:d['samples'][0]['compiler_job']['macho'].update(code_signature_present=True))
 def test_reject_quality_placement_and_unregistered_timing(self):
  self.mutate(lambda d:d['ai_warmups'][0].update(passed_exact_answer=False))
  self.mutate(lambda d:d.update(registration_created_utc=d['completed_utc']))
  def wrong(d):next(r for r in d['samples'] if r['target']=='windows_gpu_candidate')['placement_after']['size_vram_bytes']=0
  self.mutate(wrong)
 def test_reject_ai_after_pipeline_finish(self):
  def late(d):
   r=next(r for r in d['samples'] if r['ai_requests'])
   r['ai_requests'][-1]['finish_offset_from_launch_s']=r['compiler_job']['elapsed_s']
  self.mutate(late)
 def test_reject_extra_job_fields_and_budget_overrun(self):
  self.mutate(lambda d:d['samples'][0]['compiler_job'].update(unexpected='value'))
  from datetime import datetime,timedelta
  self.mutate(lambda d:d.update(completed_utc=(datetime.fromisoformat(d['started_utc'])+timedelta(seconds=1201)).isoformat()))
if __name__=='__main__':unittest.main()
