"""Private output guards and failure accounting, without inference."""
from pathlib import Path
import contextlib, io, json, sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import r3_sync_burst_workload as b

class SynchronizedReportTests(unittest.TestCase):
    def test_refuses_repository_output_before_network(self):
        root=Path(b.__file__).resolve().parents[1]
        with patch.object(b.r3,'PRIVATE',root/'results'),patch.object(b.r3,'model_integrity') as network,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                b.main(['--execute','--report',str(root/'results/private-sync.json')])
        network.assert_not_called()

    def test_refuses_existing_report_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'existing.json'
            report.write_text('preserved')
            with patch.object(b.r3,'PRIVATE',Path(directory)),patch.object(b.r3,'model_integrity') as network,contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    b.main(['--execute','--report',str(report)])
            self.assertEqual(report.read_text(),'preserved')
            network.assert_not_called()

    def test_placement_failure_records_incomplete_run(self):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'incomplete.json'
            with patch.object(b.r3,'PRIVATE',Path(directory)),patch.object(b.r3,'model_integrity'),patch.object(b.r3,'infer',return_value={'passed_exact_answer':True}),patch.object(b,'read_placement',side_effect=ValueError('fixture')),patch.object(b,'burst_window',side_effect=lambda *args:{'stop_reason':None,'target':args[0]}),contextlib.redirect_stdout(io.StringIO()):
                rc=b.main(['--execute','--targets','baseline,windows_cpu','--report',str(report)])
            self.assertEqual(rc,2)
            saved=json.loads(report.read_text())
            self.assertIs(saved['complete'],False)
            self.assertEqual(saved['stop_reason'],'ValueError')
            self.assertEqual(len(saved['samples']),1)
            self.assertEqual(saved['samples'][0]['target'],'baseline')
if __name__=='__main__':
    unittest.main()
