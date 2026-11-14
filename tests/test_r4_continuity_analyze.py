from pathlib import Path
import copy,json,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import r4_continuity_analyze as audit
def fixture():
 d={'schema':'nano-r4-continuity-evidence-v1','stage':'soak','target':'iphone_usb_coreml','model_id':'qwen3.5-0.8b','complete':True,'stop':None,
  'runtime_build_attested':False,'wakelock_runtime_verified':False,'foreground_state_instrumented':False,
  'energy_measured':False,'ane_profiled':False,'automatic_retries':False,'externally_registered':True,
  'protected_configuration_unchanged':True,'registration_created_utc':'2026-11-14T00:00:00Z',
  'started_utc':'2026-11-14T00:00:01+00:00','status_attempts':13,'generation_attempts':12,
  'observed_elapsed_s':722,'statuses':[],'samples':[],'idle_intervals':[]}
 for r in range(1,7):
  for phase in ('before_round','after_round'):
   d['statuses'].append({'round':r,'phase':phase,'wall_s':.1,'elapsed_s':120*(r-1),'pinned_authenticated_ready':True})
  for task in ('arithmetic','format'):
   d['samples'].append({'round':r,'task':task,'elapsed_s':120*(r-1),'passed_exact_answer':True,'completion_tokens':2,
    'wall_s':.5,'model_elapsed_ms':400.,'generator_tokens_per_second':5.,'on_device_metrics_verified':True})
  d['idle_intervals'].append({'round':r,'requested_s':120,'observed_s':120.})
 d['statuses'].append({'round':6,'phase':'final_status','wall_s':.1,'elapsed_s':722.,'pinned_authenticated_ready':True})
 return d
class ContinuityAuditTests(unittest.TestCase):
 def test_complete_counts_and_limits(self):
  a=audit.analyze(fixture());self.assertTrue(a['observation_complete'])
  self.assertEqual((a['ready_checks_passed'],a['correct_answers'],a['idle_seconds_observed']),(13,12,720))
 def mutate(self,change):
  d=fixture();change(d)
  with self.assertRaises(ValueError):audit.analyze(d)
 def test_reject_missing_checks_short_idle_and_bad_quality(self):
  self.mutate(lambda d:d['statuses'].pop())
  self.mutate(lambda d:d['idle_intervals'][0].update(observed_s=119))
  self.mutate(lambda d:d['idle_intervals'][0].update(observed_s=1000))
  self.mutate(lambda d:d.update(target='windows_cpu'))
  self.mutate(lambda d:d['samples'][0].update(passed_exact_answer=False))
 def test_reject_unsupported_claims_and_credential_changes(self):
  for field in ('runtime_build_attested','wakelock_runtime_verified','energy_measured','automatic_retries'):
   self.mutate(lambda d,f=field:d.update({f:True}))
  self.mutate(lambda d:d.update(protected_configuration_unchanged=False))
 def test_reject_extra_response_fields_and_late_registration(self):
  self.mutate(lambda d:d['samples'][0].update(secret='must not serialize'))
  self.mutate(lambda d:d.update(registration_created_utc=d['started_utc']))
 def test_failed_observation_is_not_promoted(self):
  d=fixture();d['complete']=False;d['stop']={'code':'transport_timeout','phase':'before_round','round':6,'task':None}
  d['samples']=d['samples'][:10];d['statuses']=d['statuses'][:10];d['idle_intervals']=d['idle_intervals'][:5]
  self.assertFalse(audit.analyze(d)['observation_complete'])
  d['stop']['code']='sensitive arbitrary exception text'
  with self.assertRaises(ValueError):audit.analyze(d)
 def test_supervisor_timing_has_separate_provenance(self):
  r={'started_utc':'2026-11-14T00:00:00+00:00','finished_utc':'2026-11-14T00:15:00+00:00','stop':{'phase':'supervisor'}}
  self.assertEqual(audit.normalized_elapsed(r),(900,'supervisor_utc'))
  self.assertEqual(audit.normalized_elapsed({'observed_elapsed_s':720}),(720,'worker_monotonic'))
if __name__=='__main__':unittest.main()
