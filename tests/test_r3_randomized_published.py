"""Recompute public conclusions from numeric observations; no live services."""
import json
import math
from pathlib import Path
import statistics
import unittest

ROOT=Path(__file__).resolve().parents[1]
TARGETS=['windows_cpu','windows_gpu_candidate','iphone_usb_coreml']

class RegisteredEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=(ROOT/'results/r3_randomized_mixed_20261113.json').read_text()
        cls.data=json.loads(cls.text)
        cls.rows=cls.data['observations']

    def test_counts_order_and_privacy_shape(self):
        self.assertEqual(self.data['schema'],'nano-r3-randomized-mixed-published-v1')
        order=['baseline']
        import itertools
        for permutation in json.loads((ROOT/'results/r3_randomized_protocol_20261113.json').read_text())['condition_orders']:
            order.extend(permutation)
            order.append('baseline')
        self.assertEqual([x['target'] for x in self.rows],order)
        self.assertEqual(sum(len(x['ai_requests']) for x in self.rows),72)
        keys={'sequence','target','host_hash_mib_s','workers','seconds','requested_ai_count',
              'ai_requests','stop_reason','wall_s','placement_before','placement_after',
              'worker_intervals','worker_start_spread_s','all_ai_within_common_worker_interval'}
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
                self.assertEqual(set(a),{'task_label','wall_s','completion_tokens','model_elapsed_ms',
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
        doc=(ROOT/'docs/R3_RANDOMIZED_20261113.md').read_text()
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

    def test_worker_overlap_and_recorded_spreads(self):
        from collections import Counter
        counts=[Counter(self.rows[i*4+j+1]['target'] for i in range(6)) for j in range(3)]
        self.assertTrue(all(c==Counter({t:2 for t in TARGETS}) for c in counts))
        self.assertIs(self.data['synchronized_workers'],True)
        self.assertIs(self.data['all_six_permutations'],True)
        self.assertIs(self.data['randomized'],True)
        total=0
        for row in self.rows:
            intervals=row['worker_intervals']
            self.assertEqual(len(intervals),4)
            self.assertIs(row['all_ai_within_common_worker_interval'],True)
            latest=max(w['start_offset_s'] for w in intervals)
            earliest_end=min(w['end_offset_s'] for w in intervals)
            self.assertLessEqual(latest,.05)
            spread=latest-min(w['start_offset_s'] for w in intervals)
            self.assertAlmostEqual(row['worker_start_spread_s'],spread,places=5)
            for w in intervals:
                self.assertEqual(set(w),{'start_offset_s','end_offset_s'})
                self.assertGreaterEqual(w['start_offset_s'],0)
                self.assertGreaterEqual(w['end_offset_s']-w['start_offset_s'],4.99999)
            for a in row['ai_requests']:
                self.assertGreaterEqual(a['start_offset_s'],latest)
                self.assertLessEqual(a['finish_offset_s'],earliest_end)
            total+=len(intervals)
        self.assertEqual(total,100)
        doc=(ROOT/'docs/R3_RANDOMIZED_20261113.md').read_text()
        self.assertIn('%.3f ms'%(max(x['worker_start_spread_s'] for x in self.rows)*1000),doc)
        self.assertIn('%.3f ms'%(max(w['start_offset_s'] for x in self.rows for w in x['worker_intervals'])*1000),doc)


    def test_tasks_warmups_and_per_task_conclusions(self):
        from collections import Counter
        requests=[a for row in self.rows for a in row['ai_requests']]
        self.assertEqual(Counter(a['task_label'] for a in requests),Counter(arithmetic=36,format=36))
        self.assertEqual(len(self.data['warmups']),36)
        for row in self.rows:
            if row['target']=='baseline':
                continue
            self.assertEqual([a['task_label'] for a in row['ai_requests']],['arithmetic','format','arithmetic','format'])
            warmed=[w for w in self.data['warmups'] if w['window_sequence']==row['sequence']]
            self.assertEqual([w['task_label'] for w in warmed],['arithmetic','format'])
            for w in warmed:
                self.assertEqual(set(w),{'target','task_label','window_sequence','wall_s',
                    'completion_tokens','model_elapsed_ms','passed_exact_answer'})
                self.assertEqual(w['target'],row['target'])
                self.assertIs(w['passed_exact_answer'],True)
                self.assertTrue(1<=w['completion_tokens']<=32)
                self.assertTrue(0<w['wall_s'] and math.isfinite(w['wall_s']))
                self.assertTrue(w['model_elapsed_ms']>=0 and math.isfinite(w['model_elapsed_ms']))
        self.assertEqual(len(self.data['task_summary']),6)
        doc=(ROOT/'docs/R3_RANDOMIZED_20261113.md').read_text()
        for summary in self.data['task_summary']:
            selected=[a for row in self.rows if row['target']==summary['target']
                      for a in row['ai_requests'] if a['task_label']==summary['task_label']]
            self.assertEqual(len(selected),12)
            self.assertEqual(summary['requests'],12)
            self.assertEqual(summary['correct'],sum(a['passed_exact_answer'] for a in selected))
            self.assertEqual(summary['median_request_s'],round(statistics.median(a['wall_s'] for a in selected),5))
            self.assertEqual(summary['observed_completion_tokens'],sorted(set(a['completion_tokens'] for a in selected)))
            self.assertIn('%.5f'%summary['median_request_s'],doc)


    def test_preregistration_primary_outcome_and_byte_integrity(self):
        from datetime import datetime
        import hashlib,itertools,random
        path=ROOT/'results/r3_randomized_protocol_20261113.json'
        raw=path.read_bytes()
        protocol=json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),self.data['protocol_sha256'])
        self.assertEqual(self.data['protocol_sha256'],'2212fcadb78d8e2631026ff40bd75a1354fb95d30f75b9054fa7192398b19b3a')
        self.assertEqual(self.data['public_order_seed'],protocol['public_order_seed'])
        orders=list(itertools.permutations(TARGETS))
        random.Random(protocol['public_order_seed']).shuffle(orders)
        self.assertEqual(orders,[tuple(x) for x in protocol['condition_orders']])
        self.assertEqual(self.data['primary_metric'],protocol['primary_metric'])
        self.assertEqual(self.data['primary_median_phone_cpu_percent'],
                         round(statistics.median(self.data['phone_vs_cpu_percent']),2))
        self.assertEqual(self.data['full_run_attempts'],1)
        self.assertIs(self.data['pooled_with_prior_data'],False)
        self.assertIs(self.data['outliers_excluded'],False)
        self.assertLess(datetime.fromisoformat(self.data['registration_created_utc'].replace('Z','+00:00')),
                        datetime.fromisoformat(self.data['run_started_utc']))
        self.assertLess(datetime.fromisoformat(self.data['run_started_utc']),
                        datetime.fromisoformat(self.data['run_completed_utc']))
        self.assertEqual(self.data['registration_url'],
                         'https://github.com/Nanodagr8/nano-coreml-usb-bridge/issues/4#issuecomment-6854803471')
        self.assertIn('results/r3_randomized_protocol_20261113.json -text',(ROOT/'.gitattributes').read_text())
        doc=(ROOT/'docs/R3_RANDOMIZED_20261113.md').read_text()
        self.assertIn('%+.2f%%'%self.data['primary_median_phone_cpu_percent'],doc)

if __name__=='__main__':
    unittest.main()
