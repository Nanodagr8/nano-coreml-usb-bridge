import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import r6_diagnostic_grading as r6

class DiagnosticTests(unittest.TestCase):
    def test_exact_match_and_whitespace_preserve_strict_score(self):
        row=r6.diagnose('py_inclusive_range',' range(1,n+1) ')
        self.assertTrue(row['strict_pass']);self.assertTrue(row['normalized_pass'])
        self.assertEqual(row['classification'],'exact_match')

    def test_one_complete_code_fence_is_only_a_diagnostic_normalization(self):
        row=r6.diagnose('py_inclusive_range','```python\nrange(1,n+1)\n```')
        self.assertFalse(row['strict_pass']);self.assertTrue(row['normalized_pass'])
        self.assertEqual(row['classification'],'code_fence_normalized')
        self.assertEqual(row['semantic_correctness'],'not_assessed')

    def test_prose_multiple_fences_and_wrong_language_are_not_extracted(self):
        for text in ('Here is code:\n```python\nrange(1,n+1)\n```',
                     '```python\nrange(1,n+1)\n```\n```python\n0\n```',
                     '```javascript\nrange(1,n+1)\n```'):
            with self.subTest(text=text):
                row=r6.diagnose('py_inclusive_range',text)
                self.assertEqual(row['classification'],'wrapper_rejected')
                self.assertIsNone(row['strict_pass']);self.assertFalse(row['normalized_pass'])

    def test_valid_python_alternatives_and_errors_do_not_imply_semantics(self):
        for text in ('range(1,1+n)','range(1,n)','__import__("os").getcwd()'):
            row=r6.diagnose('py_inclusive_range',text)
            self.assertEqual(row['classification'],'python_noncanonical')
            self.assertFalse(row['strict_pass']);self.assertEqual(row['semantic_correctness'],'not_assessed')
        self.assertEqual(r6.diagnose('py_inclusive_range','range(')['classification'],'invalid_syntax')

    def test_json_types_and_fences_remain_explicit(self):
        for text,classification in [('[true,false]','exact_match'),('[1,0]','json_value_mismatch'),
                                     ('[true,]','invalid_json'),('NaN','invalid_json'),
                                     ('```json\n[true,false]\n```','code_fence_normalized')]:
            self.assertEqual(r6.diagnose('py_bool_trace',text)['classification'],classification)
        self.assertEqual(r6.diagnose('swift_clamp_trace','32.0')['classification'],'json_value_mismatch')

    def test_preparse_resource_limits_and_unicode_are_fail_closed(self):
        for text in ('x'*4097,'('*25+'1'+')'*25,'9'*65,'+'.join(['x']*140)):
            row=r6.diagnose('py_inclusive_range',text)
            self.assertEqual(row['classification'],'resource_limit')
            self.assertIsNone(row['strict_pass'])
        self.assertEqual(r6.diagnose('py_inclusive_range','\ud800')['classification'],'invalid_input')
        with patch.object(r6.ast,'parse',side_effect=AssertionError('parser called before guard')):
            self.assertEqual(r6._assess('py_inclusive_range','('*25+'1'+')'*25)['classification'],'resource_limit')

    def test_parsed_ast_depth_limit_is_enforced(self):
        row=r6.diagnose('py_inclusive_range','+'.join(['x']*80))
        self.assertEqual(row['classification'],'resource_limit')
        self.assertIsNone(row['strict_pass'])

    def test_input_code_is_never_executed_and_text_is_not_returned(self):
        with tempfile.TemporaryDirectory() as d:
            marker=Path(d)/'must-not-exist'
            text=f'__import__("pathlib").Path({str(marker)!r}).write_text("secret-canary")'
            row=r6.diagnose('py_inclusive_range',text)
            self.assertFalse(marker.exists())
            self.assertFalse(row['code_executed']);self.assertFalse(row['raw_text_retained'])
            self.assertNotIn('secret-canary',json.dumps(row));self.assertNotIn(str(marker),json.dumps(row))

    def test_worker_receives_no_credentials_or_input_in_command_line(self):
        fake=Mock();fake.returncode=0
        expected=r6._assess('swift_clamp_trace','32')
        fake.communicate.return_value=(json.dumps(expected).encode(),None)
        with patch.dict(r6.os.environ,{'NANO_USB_BEARER':'secret-canary','OPENAI_API_KEY':'secret-canary'}),patch.object(r6.subprocess,'Popen',return_value=fake) as launch:
            row=r6.diagnose('swift_clamp_trace','32')
            self.assertTrue(row['strict_pass'])
            self.assertNotIn('NANO_USB_BEARER',launch.call_args.kwargs['env'])
            self.assertNotIn('OPENAI_API_KEY',launch.call_args.kwargs['env'])
            self.assertNotIn('32',launch.call_args.args[0]);self.assertIn('-I',launch.call_args.args[0])

    def test_timeout_kills_and_drains_owned_worker(self):
        fake=Mock();fake.communicate.side_effect=[subprocess.TimeoutExpired('worker',2),(b'',None)]
        with patch.object(r6.subprocess,'Popen',return_value=fake):
            row=r6.diagnose('py_inclusive_range','range(1,n+1)')
        self.assertEqual(row['classification'],'worker_timeout');self.assertIsNone(row['strict_pass'])
        fake.kill.assert_called_once();self.assertEqual(fake.communicate.call_count,2)
        self.assertNotIn('input',fake.communicate.call_args.kwargs)

    def test_bad_worker_output_is_not_trusted_or_repeated(self):
        fake=Mock();fake.returncode=0;fake.communicate.return_value=(b'{"text":"secret-canary"}',None)
        with patch.object(r6.subprocess,'Popen',return_value=fake):row=r6.diagnose('swift_clamp_trace','32')
        self.assertEqual(row['classification'],'worker_invalid')
        self.assertNotIn('secret-canary',json.dumps(row))
        malformed=r6._assess('swift_clamp_trace','32');malformed['classification']=[]
        fake.communicate.return_value=(json.dumps(malformed).encode(),None)
        with patch.object(r6.subprocess,'Popen',return_value=fake):
            self.assertEqual(r6.diagnose('swift_clamp_trace','32')['classification'],'worker_invalid')

    def test_unknown_cases_and_dry_mode_do_not_launch(self):
        with patch.object(r6.subprocess,'Popen',side_effect=AssertionError('worker unexpectedly launched')):
            self.assertEqual(r6.diagnose('secret-canary','32')['classification'],'invalid_case')
            self.assertEqual(r6.main([]),0)

    def test_qualification_is_deterministic_and_only_synthetic(self):
        report=r6.qualify()
        self.assertTrue(report['complete']);self.assertGreaterEqual(report['fixture_count'],16)
        self.assertEqual(report['passed'],report['fixture_count'])
        self.assertEqual(report['scope'],'offline_synthetic_fixtures_only')
        self.assertFalse(report['r5_rescored']);self.assertFalse(report['live_inference'])

    def test_reference_rule_agrees_with_frozen_r5_for_processed_fixtures(self):
        import r5_coding_quality as r5
        self.assertEqual(list(r6.CASES.values()),list(r5.CASES))
        for case in r5.CASES:
            for text in (case['expected'],'  '+case['expected']+'  ','```\n'+case['expected']+'\n```','not a valid answer'):
                result=r6._assess(case['id'],text)
                if result['strict_pass'] is not None:
                    self.assertEqual(result['strict_pass'],r5.grade(case,text))

    def test_pipe_failure_also_cleans_up_and_size_guard_avoids_encoding(self):
        fake=Mock();fake.communicate.side_effect=[OSError('secret-canary'),(b'',None)]
        with patch.object(r6.subprocess,'Popen',return_value=fake):
            result=r6.diagnose('swift_clamp_trace','32')
        fake.kill.assert_called_once();self.assertEqual(result['classification'],'worker_failed')
        class Large(str):
            def encode(self,*args,**kwargs):raise AssertionError('oversized input encoded')
        self.assertEqual(r6.diagnose('swift_clamp_trace',Large('x'*4097))['classification'],'resource_limit')

if __name__=='__main__':unittest.main()
