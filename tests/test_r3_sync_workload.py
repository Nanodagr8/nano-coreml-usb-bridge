from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import collections, contextlib, io, multiprocessing, unittest
from unittest.mock import MagicMock, patch
import r3_sync_burst_workload as b

TARGETS=['baseline','windows_cpu','windows_gpu_candidate','iphone_usb_coreml']
class SynchronizedTests(unittest.TestCase):
    def test_every_permutation_and_position_balanced(self):
        order=b.balanced_plan(TARGETS,6)
        self.assertEqual(len(order),25)
        triples=[tuple(order[i*4+1:i*4+4]) for i in range(6)]
        self.assertEqual(len(set(triples)),6)
        for position in range(3):
            self.assertEqual(collections.Counter(t[position] for t in triples),
                collections.Counter({t:2 for t in TARGETS[1:]}))
        self.assertTrue(all(order[i*4]=='baseline' for i in range(7)))
    def test_guards(self):
        for targets,runs in ((TARGETS,2),(TARGETS,7),(TARGETS[1:],1),(['baseline'],1)):
            with self.assertRaises(ValueError):
                b.balanced_plan(targets,runs)
        with self.assertRaises(ValueError):
            b.burst_window('baseline',5,5,4)
    def test_dry_run_no_network(self):
        with patch.object(b.r3,'infer') as inference,patch.object(b,'NanoUSBClient') as phone,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(b.main([]),0)
        inference.assert_not_called()
        phone.assert_not_called()
    def test_real_spawn_barrier_no_inference(self):
        before={c.pid for c in multiprocessing.active_children()}
        with patch.object(b.r3,'infer') as inference:
            row=b.burst_window('baseline',.5,4,4)
        self.assertIsNone(row['stop_reason'])
        self.assertEqual(len(row['worker_intervals']),4)
        self.assertGreater(row['host_hash_mib_s'],0)
        self.assertLessEqual(row['worker_start_spread_s'],.05)
        for interval in row['worker_intervals']:
            self.assertGreaterEqual(interval['start_offset_s'],0)
            self.assertGreaterEqual(interval['end_offset_s']-interval['start_offset_s'],.49999)
        inference.assert_not_called()
        self.assertEqual({c.pid for c in multiprocessing.active_children()},before)
    def test_barrier_failure_cleans_children(self):
        context=MagicMock()
        child=context.Process.return_value
        child.is_alive.return_value=True
        context.Queue.return_value.get.return_value=('error',0,'fixture')
        with patch.object(multiprocessing,'get_context',return_value=context):
            with self.assertRaises(RuntimeError):
                b.burst_window('baseline',.5,4,4)
        self.assertEqual(child.terminate.call_count,4)
        context.Queue.return_value.close.assert_called_once()
    def test_worker_times_out_without_start(self):
        event=MagicMock()
        event.wait.return_value=False
        queue=MagicMock()
        b.synchronized_worker(0,.5,event,MagicMock(),queue)
        self.assertEqual(queue.put.call_args_list[0].args[0],('ready',0))
        self.assertEqual(queue.put.call_args_list[-1].args[0],('error',0,'RuntimeError'))
if __name__=='__main__':
    unittest.main()
