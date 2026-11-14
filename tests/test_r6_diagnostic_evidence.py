import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'client'))
import r6_diagnostic_grading as r6

class DiagnosticEvidenceTests(unittest.TestCase):
    def test_qualification_recomputes_and_binds_exact_source_bytes(self):
        stored=json.loads((ROOT/'results/r6_diagnostic_fixtures_20261114.json').read_text(encoding='utf-8'))
        self.assertEqual(stored,r6.qualify())
        self.assertEqual((stored['fixture_count'],stored['passed']),(20,20))
        self.assertEqual(stored['scope'],'offline_synthetic_fixtures_only')
        for name,digest in stored['source_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/'client'/name).read_bytes()).hexdigest(),digest)
        self.assertEqual(hashlib.sha256((ROOT/'results/r5_coding_study_protocol_20261114.json').read_bytes()).hexdigest(),stored['reference_protocol_sha256'])
        self.assertFalse(stored['r5_rescored']);self.assertFalse(stored['live_inference'])

    def test_five_distinct_plugins_are_recorded_without_certification(self):
        report=json.loads((ROOT/'results/r6_tool_checks_20261114.json').read_text(encoding='utf-8'))
        self.assertEqual(report['successful_plugin_count'],5)
        self.assertEqual(len({x['plugin'] for x in report['checks']}),5)
        self.assertTrue(all(x['succeeded'] for x in report['checks']))
        self.assertEqual(report['new_plugin_installations'],0)
        self.assertFalse(report['automatic_pipeline_configured'])
        self.assertFalse(next(x for x in report['checks'] if x['plugin']=='Code Tytor: Python')['certification'])

if __name__=='__main__':unittest.main()
