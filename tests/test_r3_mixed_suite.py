from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import r3_mixed_burst_workload as b

class MixedTests(unittest.TestCase):
    def test_exact_equal_task_counts(self):
        self.assertEqual(b.mixed_labels(4),('arithmetic','format','arithmetic','format'))
        for count in (0,1,2,3,5):
            with self.assertRaises(ValueError):
                b.mixed_labels(count)
    def test_warmup_quality_failure_is_preserved(self):
        def infer(target,label,client):
            return {'passed_exact_answer':label=='arithmetic','wall_s':.1,
                    'completion_tokens':2,'model_elapsed_ms':80}
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'failure.json'
            with patch.object(b.r3,'PRIVATE',Path(directory)),patch.object(b.r3,'model_integrity'),patch.object(b.r3,'infer',side_effect=infer),patch.object(b,'read_placement') as placement,patch.object(b,'burst_window',side_effect=lambda *args:{'target':args[0],'stop_reason':None}),contextlib.redirect_stdout(io.StringIO()):
                rc=b.main(['--execute','--targets','baseline,windows_cpu','--report',str(report)])
            saved=json.loads(report.read_text())
        self.assertEqual(rc,2)
        self.assertIs(saved['complete'],False)
        self.assertEqual(saved['stop_reason'],'warmup_quality_failure_format')
        self.assertEqual(len(saved['samples']),1)
        self.assertEqual([x['task_label'] for x in saved['warmups']],['arithmetic','format'])
        self.assertIs(saved['warmups'][1]['passed_exact_answer'],False)
        placement.assert_not_called()
    def test_both_tasks_warmed(self):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'pass.json'
            with patch.object(b.r3,'PRIVATE',Path(directory)),patch.object(b.r3,'model_integrity'),patch.object(b.r3,'infer',return_value={'passed_exact_answer':True}) as infer,patch.object(b,'read_placement',return_value={}),patch.object(b,'burst_window',side_effect=lambda *args:{'target':args[0],'stop_reason':None}),contextlib.redirect_stdout(io.StringIO()):
                rc=b.main(['--execute','--targets','baseline,windows_cpu','--report',str(report)])
            saved=json.loads(report.read_text())
        self.assertEqual(rc,0)
        self.assertEqual([c.args[1] for c in infer.call_args_list],['arithmetic','format'])
        self.assertEqual(saved['warmup_per_ai_window'],2)
    def test_measured_task_sequence_with_real_workers(self):
        def infer(target,label,client):
            return {'passed_exact_answer':True,'wall_s':.00001,'completion_tokens':2,'model_elapsed_ms':.001}
        with patch.object(b.r3,'infer',side_effect=infer) as requests:
            row=b.burst_window('windows_cpu',2,4,4)
        self.assertIsNone(row['stop_reason'])
        self.assertTrue(row['all_ai_within_common_worker_interval'])
        self.assertEqual([c.args[1] for c in requests.call_args_list],list(b.mixed_labels(4)))
        self.assertEqual([a['task_label'] for a in row['ai_requests']],list(b.mixed_labels(4)))
if __name__=='__main__':
    unittest.main()
