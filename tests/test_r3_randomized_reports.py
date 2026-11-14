"""Registered target/output guards and incomplete quality failures."""
from pathlib import Path
import contextlib,io,json,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import r3_randomized_mixed_workload as b

class RegisteredReportTests(unittest.TestCase):
    def args(self,report):
        return ['--execute','--targets',','.join(b.PROTOCOL['targets']),'--report',str(report)]
    def test_repository_output_refused_before_network(self):
        root=Path(b.__file__).resolve().parents[1]
        with patch.object(b.r3,'PRIVATE',root/'results'),patch.object(b.r3,'model_integrity') as network,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                b.main(self.args(root/'results/private-registered.json'))
        network.assert_not_called()
    def test_existing_report_refused_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'existing.json'
            report.write_text('preserved')
            with patch.object(b.r3,'PRIVATE',Path(directory)),patch.object(b.r3,'model_integrity') as network,contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    b.main(self.args(report))
            self.assertEqual(report.read_text(),'preserved')
            network.assert_not_called()
    def test_failed_quality_is_not_complete(self):
        def infer(target,label,client):
            return {'passed_exact_answer':label=='arithmetic'}
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'incomplete.json'
            with patch.object(b.r3,'PRIVATE',Path(directory)),patch.object(b.r3,'model_integrity'),patch.object(b.r3,'infer',side_effect=infer),patch.object(b,'NanoUSBClient') as phone,patch.object(b,'burst_window',side_effect=lambda *args:{'target':args[0],'stop_reason':None}),patch.object(b,'read_placement') as placement,contextlib.redirect_stdout(io.StringIO()):
                phone.return_value.status.return_value={'status':'ready'}
                self.assertEqual(b.main(self.args(report)),2)
            saved=json.loads(report.read_text())
            self.assertIs(saved['complete'],False)
            self.assertEqual(saved['stop_reason'],'warmup_quality_failure_format')
            self.assertEqual(len(saved['samples']),1)
            self.assertEqual(len(saved['warmups']),2)
            placement.assert_not_called()
if __name__=='__main__':
    unittest.main()
