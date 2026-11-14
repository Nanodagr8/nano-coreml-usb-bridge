"""Recompute public conclusions from numeric observations; no live services."""
import json
import math
from pathlib import Path
import statistics
import unittest

ROOT=Path(__file__).resolve().parents[1]
TARGETS=['windows_cpu','windows_gpu_candidate','iphone_usb_coreml']

class BurstEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=(ROOT/'results/r3_iphone_placement_bursts_20261113.json').read_text()
        cls.data=json.loads(cls.text)
        cls.rows=cls.data['observations']

    def test_counts_order_and_privacy_shape(self):
        self.assertEqual(self.data['schema'],'nano-r3-placement-burst-published-v1')
        order=['baseline']
        for i in range(6):
            order.extend(TARGETS if i%2==0 else TARGETS[::-1])
            order.append('baseline')
        self.assertEqual([x['target'] for x in self.rows],order)
        self.assertEqual(sum(len(x['ai_requests']) for x in self.rows),72)
        keys={'sequence','target','host_hash_mib_s','workers','seconds','requested_ai_count',
              'ai_requests','stop_reason','wall_s','placement_before','placement_after'}
        for i,row in enumerate(self.rows):
            self.assertEqual(set(row),keys)
            self.assertEqual(row['sequence'],i)
            self.assertEqual(row['workers'],4)
            self.assertEqual(row['seconds'],5)
            self.assertIsNone(row['stop_reason'])
            self.assertTrue(math.isfinite(row['host_hash_mib_s']) and row['host_hash_mib_s']>0)
            self.assertEqual(len(row['ai_requests']),0 if row['target']=='baseline' else 4)
            last=0
            for a in row['ai_requests']:
                self.assertEqual(set(a),{'wall_s','completion_tokens','model_elapsed_ms',
                     'passed_exact_answer','start_offset_s','finish_offset_s'})
                self.assertIs(a['passed_exact_answer'],True)
                self.assertTrue(1<=a['completion_tokens']<=32)
                self.assertTrue(last<=a['start_offset_s']<a['finish_offset_s']<=5)
                self.assertTrue(0<a['wall_s']<5)
                self.assertTrue(math.isfinite(a['model_elapsed_ms']) and a['model_elapsed_ms']>=0)
                last=a['finish_offset_s']
        for marker in ('authorization','bearer ','private key','c:\\users','password',
                       'spki.pin','prompt_text','response_text','kevin inthavong'):
            self.assertNotIn(marker,self.text.lower())

    def test_all_placement_snapshots(self):
        count=0
        for row in self.rows:
            for key in ('placement_before','placement_after'):
                c=row[key]
                if row['target'] not in TARGETS[:2]:
                    self.assertIsNone(c)
                    continue
                count+=1
                self.assertEqual(set(c),{'expected_condition','ollama_processor','size_bytes',
                   'size_vram_bytes','digest_matches','placement_check_passed'})
                self.assertEqual(c['expected_condition'],row['target'])
                self.assertIs(c['digest_matches'],True)
                self.assertIs(c['placement_check_passed'],True)
                self.assertGreater(c['size_bytes'],0)
                if row['target']=='windows_cpu':
                    self.assertEqual(c['size_vram_bytes'],0)
                    self.assertEqual(c['ollama_processor'],'100% CPU')
                else:
                    self.assertGreater(c['size_vram_bytes'],0)
                    self.assertEqual(c['ollama_processor'],'100% GPU')
        self.assertEqual(count,24)

    def test_recompute_conclusions(self):
        paired={t:[] for t in TARGETS}
        phone_cpu=[]
        for i in range(6):
            block=self.rows[i*4:i*4+5]
            reference=(block[0]['host_hash_mib_s']+block[-1]['host_hash_mib_s'])/2
            rates={x['target']:x['host_hash_mib_s'] for x in block[1:-1]}
            for t in TARGETS:
                paired[t].append(round((rates[t]/reference-1)*100,4))
            phone_cpu.append(round((rates['iphone_usb_coreml']/rates['windows_cpu']-1)*100,4))
        self.assertEqual(paired,self.data['bracket_changes_percent'])
        self.assertEqual(phone_cpu,self.data['phone_vs_cpu_percent'])
        doc=(ROOT/'docs/R3_IPHONE_BURSTS_20261113.md').read_text()
        for s in self.data['summary']:
            rows=[x for x in self.rows if x['target']==s['target']]
            ai=[a for x in rows for a in x['ai_requests']]
            self.assertEqual(s['windows'],len(rows))
            self.assertEqual(s['requests'],len(ai))
            self.assertEqual(s['median_host_mib_s'],round(statistics.median(x['host_hash_mib_s'] for x in rows),3))
            self.assertIn('%.3f'%s['median_host_mib_s'],doc)
            if ai:
                self.assertEqual(s['median_request_s'],round(statistics.median(a['wall_s'] for a in ai),5))
                self.assertEqual(s['median_burst_s'],round(statistics.median(sum(a['wall_s'] for a in x['ai_requests']) for x in rows),5))
                self.assertEqual(s['median_bracket_change_percent'],round(statistics.median(paired[s['target']]),2))
                self.assertIn('%+.2f%%'%s['median_bracket_change_percent'],doc)

    def test_limits_and_provenance(self):
        for key in ('energy_measured','ane_execution_verified','quantization_equivalence_verified',
                    'hardware_utilization_profiled','general_offloading_advantage_proved'):
            self.assertIs(self.data[key],False)
        for key in ('source_report_sha256','measured_runner_sha256','measured_r3_source_sha256'):
            self.assertRegex(self.data[key],r'^[a-f0-9]{64}$')
        self.assertIs(self.data['public_runner_adapted'],True)
if __name__=='__main__':
    unittest.main()
