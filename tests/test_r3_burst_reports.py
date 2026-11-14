"""Check private output containment and no live work on invalid requests."""
from pathlib import Path
import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import r3_burst_workload as b

class BurstReportTests(unittest.TestCase):
    def test_refuses_repository_output_before_network(self):
        root=Path(b.__file__).resolve().parents[1]
        with patch.object(b.r3,'PRIVATE',root/'results'),patch.object(b.r3,'model_integrity') as network,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                b.main(['--execute','--report',str(root/'results/new-private-report.json')])
        network.assert_not_called()

    def test_refuses_existing_report_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'existing.json'
            path.write_text('preserved')
            with patch.object(b.r3,'PRIVATE',Path(directory)),patch.object(b.r3,'model_integrity') as network,contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    b.main(['--execute','--report',str(path)])
            self.assertEqual(path.read_text(),'preserved')
            network.assert_not_called()

    def test_baseline_only_report_needs_no_network_or_phone(self):
        with tempfile.TemporaryDirectory() as directory:
            private=Path(directory)/'new-directory'
            report=private/'trial.json'
            with patch.object(b.r3,'PRIVATE',private),patch.object(b.r3,'model_integrity') as network,patch.object(b,'NanoUSBClient') as phone,patch.object(b,'burst_window',side_effect=lambda *args:{'stop_reason':None}),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(b.main(['--execute','--targets','baseline','--report',str(report)]),0)
            saved=json.loads(report.read_text())
            self.assertTrue(saved['complete'])
            network.assert_not_called()
            phone.assert_not_called()
if __name__=='__main__':
    unittest.main()
