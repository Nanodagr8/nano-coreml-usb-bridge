from datetime import datetime
from pathlib import Path
import hashlib
import json
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'client'))
import r5_coding_quality as r5

def load(name):
    return json.loads((ROOT/'results'/name).read_text(encoding='utf-8'))

class CompletedCodingEvidenceTests(unittest.TestCase):
    def test_followup_pilot_and_study_are_complete_and_recompute(self):
        for stage,name,count in [('pilot','r5_coding_followup_pilot_20261114.json',6),
                                 ('study','r5_coding_study_20261114.json',36)]:
            d=load(name)
            self.assertTrue(d['complete'])
            self.assertEqual(d['generation_attempts'],count)
            self.assertEqual(d['analysis'],r5.summarize(d))
            self.assertEqual(d['analysis']['completed_requests'],count)
            protocol=(ROOT/f'results/r5_coding_{stage}_protocol_20261114.json').read_bytes()
            self.assertEqual(d['protocol_sha256'],hashlib.sha256(protocol).hexdigest())
            self.assertEqual(d['source_sha256'],r5.identities())
            self.assertLess(datetime.fromisoformat(d['registration_created_utc'].replace('Z','+00:00')),datetime.fromisoformat(d['started_utc']))

    def test_stopped_attempt_pilot_and_study_are_separate(self):
        stopped=load('r5_coding_pilot_20261114.json')
        pilot=load('r5_coding_followup_pilot_20261114.json')
        study=load('r5_coding_study_20261114.json')
        self.assertFalse(stopped['complete']);self.assertEqual(stopped['samples'],[])
        self.assertNotEqual(stopped['registration_url'],pilot['registration_url'])
        self.assertEqual(pilot['registration_url'],study['registration_url'])
        self.assertLess(datetime.fromisoformat(pilot['finished_utc']),datetime.fromisoformat(study['started_utc']))
        for target in r5.TARGETS:
            self.assertEqual([x['case_id'] for x in study['samples'] if x['target']==target],[c['id'] for c in r5.CASES])
        self.assertEqual(len(study['samples']),36)

    def test_public_evidence_does_not_claim_hardware_or_retain_raw_answers(self):
        for name in ('r5_coding_followup_pilot_20261114.json','r5_coding_study_20261114.json'):
            d=load(name)
            for flag in ('hardware_placement_verified','model_parity_verified','runtime_build_attested','energy_measured',
                         'generated_code_executed','raw_response_saved','automatic_retries'):
                self.assertIs(d[flag],False)
            self.assertIs(d['protected_configuration_unchanged'],True)
            for forbidden in ('owner_nonce','bearer','text','prompt','response'):
                self.assertNotIn(forbidden,d)
                self.assertTrue(all(forbidden not in row for row in d['samples']))

if __name__=='__main__':unittest.main()
