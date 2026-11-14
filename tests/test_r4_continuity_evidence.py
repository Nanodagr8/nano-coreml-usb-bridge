from pathlib import Path
import copy,hashlib,json,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'client'))
from r4_continuity_analyze import analyze
class ContinuityEvidenceTests(unittest.TestCase):
 def test_pilot_and_sampled_session_recompute(self):
  for stage in ('pilot','soak'):
   d=json.loads((ROOT/f'results/r4_foreground_{stage}_20261113.json').read_text(encoding='utf-8'))
   self.assertTrue(d['complete']);self.assertEqual(analyze(d),d['analysis'])
   p=(ROOT/f'results/r4_foreground_{stage}_protocol_20261113.json').read_bytes();plan=json.loads(p)
   self.assertEqual(hashlib.sha256(p).hexdigest(),d['protocol_sha256'])
   self.assertEqual(plan['runner_sha256'],hashlib.sha256((ROOT/'client/r4_foreground_reliability.py').read_bytes()).hexdigest())
   self.assertEqual(plan['supporting_client_sha256'],hashlib.sha256((ROOT/'client/nano_usb_client.py').read_bytes()).hexdigest())
   self.assertFalse(d['runtime_build_attested'] or d['wakelock_runtime_verified'] or d['foreground_state_instrumented'])
   self.assertNotIn('owner_nonce',d)
 def test_idle_observations_cannot_be_shortened_or_promoted(self):
  d=json.loads((ROOT/'results/r4_foreground_soak_20261113.json').read_text(encoding='utf-8'))
  self.assertEqual((len(d['samples']),len(d['statuses']),len(d['idle_intervals'])),(12,13,6))
  changed=copy.deepcopy(d);changed['idle_intervals'][0]['observed_s']=0
  with self.assertRaises(ValueError):analyze(changed)
  changed=copy.deepcopy(d);changed['wakelock_runtime_verified']=True
  with self.assertRaises(ValueError):analyze(changed)
if __name__=='__main__':unittest.main()
