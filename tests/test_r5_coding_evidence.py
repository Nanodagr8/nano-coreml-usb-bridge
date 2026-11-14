from pathlib import Path
import hashlib
import json
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'client'))
import r5_coding_quality as r5

class CodingEvidenceTests(unittest.TestCase):
    def test_registered_cases_and_source_identities_are_preserved(self):
        for stage in ('pilot','study'):
            plan=json.loads((ROOT/f'results/r5_coding_{stage}_protocol_20261114.json').read_text(encoding='utf-8'))
            self.assertEqual(plan['cases'],list(r5.CASES))
            self.assertEqual(plan['sequence'],[list(x) for x in r5.sequence(stage)])
            self.assertEqual(plan['source_sha256'],r5.identities())
            self.assertEqual((plan['max_tokens'],plan['budget_s']),(64,600))

    def test_stopped_pilot_is_not_promoted_or_given_a_quality_score(self):
        evidence=json.loads((ROOT/'results/r5_coding_pilot_20261114.json').read_text(encoding='utf-8'))
        plan=(ROOT/'results/r5_coding_pilot_protocol_20261114.json').read_bytes()
        self.assertEqual(evidence['protocol_sha256'],hashlib.sha256(plan).hexdigest())
        self.assertFalse(evidence['complete'])
        self.assertEqual(evidence['generation_attempts'],0)
        self.assertEqual(evidence['samples'],[])
        self.assertEqual(evidence['stop']['code'],'transport_timeout')
        self.assertEqual(evidence['analysis'],r5.summarize(evidence))
        self.assertTrue(all(v['attempted_and_scored']==0 for v in evidence['analysis']['by_target'].values()))

if __name__=='__main__':unittest.main()
