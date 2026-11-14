from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import contextlib, io, itertools, json, unittest
from unittest.mock import MagicMock, patch
import r3_burst_workload as b

class BurstSafetyTests(unittest.TestCase):
    def child(self,alive=False):
        c=MagicMock()
        c.communicate.return_value=(json.dumps({'units':10,'bytes_per_unit':262144,'seconds':5}),'')
        c.returncode=0
        c.poll.return_value=None if alive else 0
        return c
    def run_case(self,infer):
        c=self.child()
        with patch.object(b.subprocess,'Popen',return_value=c),patch.object(b.time,'sleep'),patch.object(b.time,'perf_counter',side_effect=itertools.count(0,.1)),patch.object(b.r3,'infer',side_effect=infer):
            return b.burst_window('iphone_usb_coreml',5,4,4)
    def test_equal_count_and_offsets(self):
        a={'wall_s':.1,'passed_exact_answer':True,'completion_tokens':2,'model_elapsed_ms':90}
        r=self.run_case(lambda *args:a)
        self.assertEqual(len(r['ai_requests']),4)
        self.assertIsNone(r['stop_reason'])
        self.assertTrue(all(x['start_offset_s']<x['finish_offset_s']<5 for x in r['ai_requests']))
    def test_quality_stops_burst(self):
        r=self.run_case(lambda *args:{'passed_exact_answer':False})
        self.assertEqual(len(r['ai_requests']),1)
        self.assertEqual(r['stop_reason'],'task_quality_failure')
    def test_exception_cleans_workers(self):
        children=[self.child(True) for _ in range(4)]
        with patch.object(b.subprocess,'Popen',side_effect=children),patch.object(b.time,'sleep'),patch.object(b.r3,'infer',side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                b.burst_window('iphone_usb_coreml',5,4,4)
        for c in children:
            c.kill.assert_called_once()
            c.communicate.assert_called_once()
    def test_no_late_request(self):
        c=self.child()
        with patch.object(b.subprocess,'Popen',return_value=c),patch.object(b.time,'sleep'),patch.object(b.time,'perf_counter',side_effect=[0,4,5.1]),patch.object(b.r3,'infer') as infer:
            r=b.burst_window('iphone_usb_coreml',5,4,4)
        infer.assert_not_called()
        self.assertEqual(r['stop_reason'],'insufficient_window_remaining')
    def test_dry_run_does_not_infer(self):
        with patch.object(b.r3,'infer') as infer,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(b.main([]),0)
        infer.assert_not_called()
    def test_guardrails(self):
        with contextlib.redirect_stderr(io.StringIO()):
            for args in (['--requests','5'],['--runs','7','--targets','baseline,windows_cpu,windows_gpu_candidate,iphone_usb_coreml']):
                with self.assertRaises(SystemExit):
                    b.main(args)
if __name__=='__main__':
    unittest.main()
