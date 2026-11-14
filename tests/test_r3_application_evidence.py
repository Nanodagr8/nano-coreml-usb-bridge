"""Recompute published sessions and reject corrupted quality, identity and overlap evidence."""
import copy,hashlib,itertools,json,random,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'client'))
from r3_application_analyze import analyze,bootstrap
from r3_swift_prepare import canonical_sha,load_spec
class ApplicationEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.sessions=[json.loads((ROOT/f'results/r3_application_session{i}_20261113.json').read_text()) for i in (1,2)]
 def test_recompute_complete_sessions(self):
  for d in self.sessions:
   with self.subTest(session=d['session_id']):
    self.assertTrue(d['complete'])
    self.assertEqual(analyze(d),d['analysis'])
    self.assertEqual(d['logical_spec_sha256'],canonical_sha(load_spec()))
    self.assertFalse(d['energy_measured'] or d['ane_profiled'] or d['independent_external_review'])
    self.assertFalse(d['pooled_with_prior_studies'] or d['outliers_excluded'])
 def test_frozen_protocol_hash_order_and_preregistration(self):
  for i,d in enumerate(self.sessions,1):
   raw=(ROOT/f'results/r3_application_protocol_session{i}_20261113.json').read_bytes()
   p=json.loads(raw)
   self.assertEqual(hashlib.sha256(raw).hexdigest(),d['protocol_sha256'])
   self.assertEqual(p['sequence'],d['registered_sequence'])
   self.assertEqual(p['job_manifest_sha256'],d['job_manifest_sha256'])
   permutations=list(itertools.permutations(('windows_cpu','windows_gpu_candidate','iphone_usb_coreml')))
   random.Random(p['public_order_seed']).shuffle(permutations)
   self.assertEqual(permutations,[tuple(v) for v in p['condition_orders']])
  self.assertNotEqual(self.sessions[0]['public_order_seed'],self.sessions[1]['public_order_seed'])
  self.assertFalse(self.sessions[0]['uncertainty_preregistered'])
  self.assertTrue(self.sessions[1]['uncertainty_preregistered'])
 def mutate(self,change):
  d=copy.deepcopy(self.sessions[1]);change(d)
  with self.assertRaises((ValueError,KeyError)): analyze(d)
 def test_reject_late_ai(self):
  def change(d):
   r=next(r for r in d['samples'] if r['ai_requests'])
   r['ai_requests'][-1]['finish_offset_from_launch_s']=r['compiler_job']['elapsed_s']
  self.mutate(change)
 def test_reject_changed_source_and_manifest(self):
  self.mutate(lambda d:d['samples'][0]['compiler_job'].update(source_unchanged=False))
  self.mutate(lambda d:d['samples'][0]['compiler_job'].update(job_manifest_sha256='bad'))
 def test_reject_failed_quality_and_placement(self):
  self.mutate(lambda d:d['ai_warmups'][0].update(passed_exact_answer=False))
  def change(d):
   next(r for r in d['samples'] if r['target']=='windows_cpu')['placement_after']['size_vram_bytes']=1
  self.mutate(change)
 def test_reject_reordered_or_timed_out_jobs(self):
  self.mutate(lambda d:d['samples'].reverse())
  self.mutate(lambda d:d['compiler_warmups'][0]['compiler_job'].update(timed_out=True))
 def test_reject_extra_fields_and_nonfinite_ai(self):
  def extra(d): next(r for r in d['samples'] if r['ai_requests'])['ai_requests'][0]['unexpected']='x'
  def nonfinite(d): next(r for r in d['samples'] if r['ai_requests'])['ai_requests'][0]['wall_s']=float('nan')
  self.mutate(extra);self.mutate(nonfinite)
 def test_reject_logical_mismatch_or_late_registration(self):
  self.mutate(lambda d:d['samples'][0]['compiler_job'].update(logical_spec_sha256='bad'))
  self.mutate(lambda d:d.update(registration_created_utc=d['completed_utc']))
 def test_bootstrap_is_deterministic_and_degenerate_case(self):
  self.assertEqual(bootstrap([1,2,3,4,5,6]),bootstrap([1,2,3,4,5,6]))
  self.assertEqual(bootstrap([7]*6),[7,7])
if __name__=='__main__': unittest.main()
