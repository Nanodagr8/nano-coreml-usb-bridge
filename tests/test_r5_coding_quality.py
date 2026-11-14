import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'client'))
import r5_coding_quality as r5
from nano_usb_client import PinMismatch

class Adapter:
    def __init__(self, wrong=False, fail=None):
        self.calls=0; self.wrong=wrong; self.fail=fail
    def status(self): return None
    def generate(self, target, prompt):
        self.calls+=1
        if self.fail: raise self.fail('do not serialize secret arbitrary exception')
        case=next(c for c in r5.CASES if c['prompt']==prompt)
        return {'text':'WRONG' if self.wrong else case['expected'], 'tokens':4, 'wall_s':.1,
                'model_elapsed_s':.08, 'source':'on_device_coreml_generator' if target=='iphone_usb_coreml' else 'ollama_reported'}

class QualityTests(unittest.TestCase):
    def test_rubric_accepts_formatting_but_never_executes_code(self):
        case={'kind':'python_expression','expected':'type(tokens) is int and 1 <= tokens <= 32'}
        self.assertTrue(r5.grade(case,'type(tokens) is int and 1<=tokens<=32'))
        for bad in ['isinstance(tokens, int) and 1 <= tokens <= 32', '__import__("os").system("echo unsafe")', '```python\n'+case['expected']+'\n```', 'x'*9000]:
            self.assertFalse(r5.grade(case,bad))
        self.assertFalse(r5.grade({'kind':'json','expected':'false'},'0'))
        self.assertFalse(r5.grade({'kind':'json','expected':'[2]'},'[2.0]'))

    def test_corpus_and_order_are_fixed_and_balanced(self):
        self.assertEqual(len(r5.CASES),12)
        self.assertEqual(len({c['id'] for c in r5.CASES}),12)
        self.assertTrue(all(r5.grade(c,c['expected']) for c in r5.CASES))
        order=r5.sequence('study')
        self.assertEqual(len(order),36)
        for target in r5.TARGETS:
            self.assertEqual(sum(t==target for _,t in order),12)
            for pos in range(3): self.assertEqual(sum(order[i+pos][1]==target for i in range(0,36,3)),4)

    def test_wrong_answers_continue_and_are_counted(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'private.json'; a=Adapter(wrong=True)
            report=r5.run_session(a,path,'study','owner','a'*64)
            self.assertTrue(report['complete']); self.assertEqual(a.calls,36)
            self.assertFalse(any(x['passed_rubric'] for x in report['samples']))
            public=r5.public_report(report,True)
            summary=r5.summarize(public)
            self.assertEqual([v['passed'] for v in summary['by_target'].values()],[0,0,0])
            text=json.dumps(public)
            for forbidden in ('owner_nonce','WRONG','prompt','do not serialize'):
                self.assertNotIn(forbidden,text)

    def test_transport_failure_stops_and_preserves_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'private.json';a=Adapter(fail=PinMismatch)
            report=r5.run_session(a,path,'pilot','owner','a'*64)
            self.assertFalse(report['complete']);self.assertEqual(a.calls,1)
            self.assertEqual(report['stop']['code'],'pin_rejected')
            self.assertNotIn('arbitrary exception',path.read_text())
            with self.assertRaises(FileExistsError):r5.run_session(a,path,'pilot','other','a'*64)

    def test_metrics_are_gates_and_raw_fields_cannot_escape(self):
        for field,value in [('tokens',True),('tokens',65),('wall_s',float('nan')),('model_elapsed_s',0),('source','unverified')]:
            with self.subTest(field=field):
                row=Adapter().generate('iphone_usb_coreml',r5.CASES[0]['prompt']);row[field]=value
                with self.assertRaises(r5.InvalidMetrics):r5.validate_metrics(row,'iphone_usb_coreml')
        r=Adapter().generate('iphone_usb_coreml',r5.CASES[0]['prompt']);r['secret']='canary'
        self.assertNotIn('secret',r5.validate_metrics(r,'iphone_usb_coreml'))

    def test_analyzer_rejects_missing_duplicate_and_promoted_claims(self):
        with tempfile.TemporaryDirectory() as d:
            report=r5.public_report(r5.run_session(Adapter(),Path(d)/'p.json','study','o','a'*64),True)
        self.assertTrue(r5.summarize(report)['complete'])
        for mutate in (lambda x:x['samples'].pop(), lambda x:x['samples'].__setitem__(1,x['samples'][0]),
                       lambda x:x.update(hardware_placement_verified=True),lambda x:x.update(protected_configuration_unchanged=False)):
            bad=json.loads(json.dumps(report));mutate(bad)
            with self.assertRaises(ValueError):r5.summarize(bad)

    def test_default_dry_mode_never_constructs_adapter(self):
        with patch.object(r5,'LiveAdapter',side_effect=AssertionError('network invoked')):
            self.assertEqual(r5.main([]),0)

    def test_frozen_answers_match_independent_reference_checks(self):
        tokens=True;owned=True;done=False;config={};requested=80;items=None
        log=[]
        try:
            log.append('start');raise ValueError()
        except ValueError:pass
        finally:log.append('close')
        reference=[list(range(1,3+1)),type(tokens) is int and 1<=tokens<=32,
            owned and not done,config.get('max_tokens',32),min(max(requested,1),64),
            [] if items is None else items,[0,1,2,3,4][1:4:2],
            [isinstance(tokens,int),type(tokens) is int],log,list(dict.fromkeys(['b','a','b','c','a'])),
            [r['id'] for r in [{'id':1,'done':True},{'id':2,'done':False},{'id':3,'done':False}] if not r['done']],
            min(max(80,1),32)]
        self.assertEqual(reference,[[1,2,3],False,True,32,64,[],[1,3],[True,False],['start','close'],['b','a','c'],[2,3],32])
        for case,value in zip(r5.CASES[6:],reference[6:]):
            self.assertEqual(json.loads(case['expected']),value)

    def test_backend_requests_stay_local_with_explicit_options_and_cap(self):
        a=object.__new__(r5.LiveAdapter)
        response={'model':r5.WINDOWS_MODEL,'done':True,'response':'32','eval_count':1,'eval_duration':1000000}
        with patch.object(r5,'ollama',return_value=response) as api:
            for target,gpu in [('windows_cpu',0),('windows_gpu_candidate',99)]:
                a.generate(target,'synthetic')
                payload=api.call_args.args[1]
                self.assertEqual(payload['options']['num_gpu'],gpu)
                self.assertEqual(payload['options']['num_predict'],64)
                self.assertIs(payload['think'],False)
        with self.assertRaises(ValueError):r5.ollama('https://example.com')

if __name__=='__main__':unittest.main()
