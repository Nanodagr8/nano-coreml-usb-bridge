"""Small frozen coding-task qualification; no generated code is executed or saved."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ast
import hashlib
import itertools
import json
import math
import os
import statistics
import sys
import time
from urllib.request import Request, ProxyHandler, build_opener

from nano_usb_client import NanoUSBClient
import r4_foreground_reliability as continuity

ROOT=Path(__file__).resolve().parents[1]
TARGETS=('windows_cpu','windows_gpu_candidate','iphone_usb_coreml')
WINDOWS_MODEL='qwen3.5:0.8b'
MAX_TOKENS=64
CASES=(
 {'id':'py_inclusive_range','kind':'python_expression','expected':'range(1, n + 1)',
  'prompt':'Python repair: range(1, n) omits n. Return only the replacement range(...) expression that iterates 1 through n inclusive. Keep start=1 and step implicit. No markdown.'},
 {'id':'py_bool_token_guard','kind':'python_expression','expected':'type(tokens) is int and 1 <= tokens <= 32',
  'prompt':'Python repair: isinstance(tokens, int) accepts bools. Return only a boolean expression using type(tokens) is int, followed by and and the chained comparison 1 <= tokens <= 32. No markdown.'},
 {'id':'py_owned_cancel','kind':'python_expression','expected':'owned and not done',
  'prompt':'Python repair: cancellation is permitted only when owned is True and done is False. Variables are booleans. Return only the expression using owned, and, not, done, in that order. No markdown.'},
 {'id':'py_safe_lookup','kind':'python_expression','expected':"config.get('max_tokens', 32)",
  'prompt':'Python repair: config["max_tokens"] raises KeyError for absent keys. Return only the replacement using config.get with key "max_tokens" and default 32. No markdown.'},
 {'id':'py_cap_tokens','kind':'python_expression','expected':'min(max(requested, 1), 64)',
  'prompt':'Python repair: clamp integer requested into [1,64]. Use an outer min and an inner max, with requested before the lower bound. Return only the expression, not a function or markdown.'},
 {'id':'py_fresh_list','kind':'python_expression','expected':'[] if items is None else items',
  'prompt':'Python repair: items defaults to None. Create a fresh empty list only when items is None; otherwise preserve the original object. Return only one Python conditional expression with the empty-list branch first. No markdown.'},
 {'id':'py_slice_trace','kind':'json','expected':'[1,3]',
  'prompt':'Read Python code: values = [0,1,2,3,4]; result = values[1:4:2]. Return result as a JSON array only. No markdown.'},
 {'id':'py_bool_trace','kind':'json','expected':'[true,false]',
  'prompt':'Read Python code: tokens=True; result=[isinstance(tokens,int), type(tokens) is int]. Return result as a JSON array of booleans only. No markdown.'},
 {'id':'py_finally_trace','kind':'json','expected':'["start","close"]',
  'prompt':'Read Python code:\nlog=[]\ntry:\n log.append("start")\n raise ValueError()\nexcept ValueError:\n pass\nfinally:\n log.append("close")\nReturn log as a JSON array only. No markdown.'},
 {'id':'py_dedupe_trace','kind':'json','expected':'["b","a","c"]',
  'prompt':'Read Python code: result = list(dict.fromkeys(["b","a","b","c","a"])). Return result as a JSON array only. No markdown.'},
 {'id':'ts_filter_trace','kind':'json','expected':'[2,3]',
  'prompt':'Read TypeScript code: const rows=[{id:1,done:true},{id:2,done:false},{id:3,done:false}]; const result=rows.filter(r=>!r.done).map(r=>r.id); Return result as a JSON array only. No markdown.'},
 {'id':'swift_clamp_trace','kind':'json','expected':'32',
  'prompt':'Read Swift code: let requested = 80; let result = min(max(requested, 1), 32). Return result as a JSON integer only. No markdown.'},
)

class InvalidMetrics(Exception):pass

def grade(case,text):
    if not isinstance(text,str) or len(text.encode('utf-8'))>8192:return False
    try:
        if case['kind']=='python_expression':
            actual=ast.parse(text.strip(),mode='eval')
            if sum(1 for _ in ast.walk(actual))>512:return False
            return ast.dump(actual)==ast.dump(ast.parse(case['expected'],mode='eval'))
        actual=json.loads(text)
        # Canonical JSON distinguishes bool/int and int/float. No code evaluation.
        return json.dumps(actual,sort_keys=True,allow_nan=False)==json.dumps(json.loads(case['expected']),sort_keys=True,allow_nan=False)
    except (ValueError,SyntaxError,TypeError,RecursionError):return False

def sequence(stage):
    if stage not in ('pilot','study'):raise ValueError('UnknownStage')
    cases=CASES[:2] if stage=='pilot' else CASES
    permutations=list(itertools.permutations(TARGETS))
    return [(case['id'],target) for i,case in enumerate(cases) for target in permutations[i%6]]

def validate_metrics(row,target):
    if not isinstance(row,dict) or not isinstance(row.get('text'),str):raise InvalidMetrics()
    tokens=row.get('tokens')
    if type(tokens) is not int or not 1<=tokens<=MAX_TOKENS:raise InvalidMetrics()
    for field in ('wall_s','model_elapsed_s'):
        x=row.get(field)
        if type(x) not in (int,float) or not math.isfinite(x) or x<=0:raise InvalidMetrics()
    expected='on_device_coreml_generator' if target=='iphone_usb_coreml' else 'ollama_reported'
    if row.get('source')!=expected:raise InvalidMetrics()
    return {'completion_tokens':tokens,'wall_s':round(row['wall_s'],6),
            'model_elapsed_s':round(row['model_elapsed_s'],6),'metrics_source':expected}

def ollama(path,payload=None):
    if path not in ('tags','generate'):raise ValueError('FixedLoopbackOnly')
    raw=None if payload is None else json.dumps(payload,separators=(',',':')).encode('utf-8')
    req=Request('http://127.0.0.1:11434/api/'+path,data=raw,
                headers={'Content-Type':'application/json'},method='GET' if raw is None else 'POST')
    with build_opener(ProxyHandler({})).open(req,timeout=25) as response:
        if response.status!=200:raise ValueError('UnexpectedLocalStatus')
        body=response.read(1048577)
    if len(body)>1048576:raise ValueError('LocalResponseTooLarge')
    value=json.loads(body)
    if not isinstance(value,dict):raise ValueError('LocalResponseNotObject')
    return value

class LiveAdapter:
    def __init__(self):
        self.phone=NanoUSBClient('https://127.0.0.1:49443',os.getenv('NANO_USB_TLS_PIN',''),os.getenv('NANO_USB_BEARER',''))
    def status(self):
        if self.phone.status().get('status')!='ready':raise ValueError('ServiceNotReady')
        models=ollama('tags').get('models',[])
        if not any(x.get('name')==WINDOWS_MODEL for x in models):raise ValueError('ExistingModelMissing')
    def generate(self,target,prompt):
        began=time.monotonic()
        if target=='iphone_usb_coreml':
            v=self.phone.generate(prompt,MAX_TOKENS)
            return {'text':v.get('text'),'tokens':v.get('completion_tokens'),'wall_s':time.monotonic()-began,
                    'model_elapsed_s':v.get('model_elapsed_ms',0)/1000,'source':v.get('metrics_source')}
        if target not in TARGETS:raise ValueError('UnsupportedTarget')
        v=ollama('generate',{'model':WINDOWS_MODEL,'prompt':prompt,'stream':False,'think':False,
            'options':{'temperature':0,'seed':42,'num_predict':MAX_TOKENS,'num_gpu':0 if target=='windows_cpu' else 99},'keep_alive':'1m'})
        if v.get('model')!=WINDOWS_MODEL or v.get('done') is not True:raise InvalidMetrics()
        return {'text':v.get('response'),'tokens':v.get('eval_count'),'wall_s':time.monotonic()-began,
                'model_elapsed_s':v.get('eval_duration',0)/1e9,'source':'ollama_reported'}

def identities():
    return {name:hashlib.sha256((ROOT/'client'/name).read_bytes()).hexdigest()
            for name in ('r5_coding_quality.py','nano_usb_client.py','r4_foreground_reliability.py')}

def run_session(adapter,path,stage,nonce,plan_sha,clock=time.monotonic):
    report={'schema':'nano-r5-coding-quality-v1','stage':stage,'owner_nonce':nonce,'protocol_sha256':plan_sha,
        'source_sha256':identities(),'started_utc':datetime.now(timezone.utc).isoformat(),'complete':False,
        'stop':None,'samples':[],'status_checks_passed':0,'generation_attempts':0,
        'hardware_placement_verified':False,'model_parity_verified':False,'runtime_build_attested':False,
        'energy_measured':False,'generated_code_executed':False,'raw_response_saved':False,'automatic_retries':False}
    with path.open('x',encoding='utf-8') as f:json.dump(report,f)
    began=clock();phase='initial_readiness';case_id=None;target=None
    try:
        adapter.status();report['status_checks_passed']+=1;continuity.checkpoint(path,report)
        cases={c['id']:c for c in CASES}
        for case_id,target in sequence(stage):
            if clock()-began>=600:raise TimeoutError()
            phase='generation';report['generation_attempts']+=1;continuity.checkpoint(path,report)
            row=adapter.generate(target,cases[case_id]['prompt']);metrics=validate_metrics(row,target)
            sample={'case_id':case_id,'target':target,'model_id':'qwen3.5-0.8b' if target=='iphone_usb_coreml' else WINDOWS_MODEL,
                    'passed_rubric':grade(cases[case_id],row['text']),
                    'response_sha256':hashlib.sha256(row['text'].encode('utf-8')).hexdigest(),**metrics}
            report['samples'].append(sample);continuity.checkpoint(path,report)
        phase='final_readiness';adapter.status();report['status_checks_passed']+=1
        if clock()-began>=600:raise TimeoutError()
        report['complete']=True
    except Exception as exc:
        code='metrics_invalid' if isinstance(exc,InvalidMetrics) else continuity.classify(exc)
        report['stop']={'code':code,'phase':phase,'case_id':case_id,'target':target}
    finally:
        report['finished_utc']=datetime.now(timezone.utc).isoformat();report['observed_elapsed_s']=round(clock()-began,6)
        continuity.checkpoint(path,report)
    return report

def public_report(raw,protected_unchanged):
    keys=('schema','stage','protocol_sha256','source_sha256','started_utc','finished_utc','complete','stop',
          'samples','status_checks_passed','generation_attempts','observed_elapsed_s',
          'hardware_placement_verified','model_parity_verified','runtime_build_attested','energy_measured',
          'generated_code_executed','raw_response_saved','automatic_retries')
    result={k:raw[k] for k in keys if k in raw}
    result['protected_configuration_unchanged']=protected_unchanged
    return result

def summarize(report):
    def require(value):
        if not value:raise ValueError('InvalidCodingEvidence')
    require(report.get('schema')=='nano-r5-coding-quality-v1')
    for flag in ('hardware_placement_verified','model_parity_verified','runtime_build_attested','energy_measured',
                 'generated_code_executed','raw_response_saved','automatic_retries'):
        require(report.get(flag) is False)
    require(report.get('protected_configuration_unchanged') is True)
    require(type(report.get('complete')) is bool)
    rows=report['samples'];order=sequence(report['stage'])
    require([(x['case_id'],x['target']) for x in rows]==order[:len(rows)] and len(rows)<=len(order))
    for x in rows:
        require(set(x)=={'case_id','target','model_id','passed_rubric','response_sha256','completion_tokens','wall_s','model_elapsed_s','metrics_source'})
        require(isinstance(x['response_sha256'],str) and len(x['response_sha256'])==64 and all(c in '0123456789abcdef' for c in x['response_sha256']))
        require(type(x['passed_rubric']) is bool)
        require(x['model_id']==('qwen3.5-0.8b' if x['target']=='iphone_usb_coreml' else WINDOWS_MODEL))
        validate_metrics({'text':'unused','tokens':x['completion_tokens'],'wall_s':x['wall_s'],
                          'model_elapsed_s':x['model_elapsed_s'],'source':x['metrics_source']},x['target'])
    require(type(report.get('generation_attempts')) is int and len(rows)<=report['generation_attempts']<=len(order))
    if report['complete']:
        require(len(rows)==len(order) and report['stop'] is None and report['status_checks_passed']==2)
        elapsed=report['observed_elapsed_s'];require(type(elapsed) in (int,float) and math.isfinite(elapsed) and 0<=elapsed<600)
    else:
        require(isinstance(report.get('stop'),dict))
        require(report['stop'].get('code') in {'metrics_invalid','pin_rejected','authorization_rejected',
            'connection_reset','connection_refused','transport_timeout','tls_failed','protocol_rejected',
            'unexpected_error','study_budget_expired','worker_process_failed'})
    return {'complete':report['complete'],'completed_requests':len(rows),'by_target':{
        t:{'passed':sum(x['passed_rubric'] for x in rows if x['target']==t),
           'attempted_and_scored':sum(x['target']==t for x in rows),
           'median_wall_s':statistics.median([x['wall_s'] for x in rows if x['target']==t]) if any(x['target']==t for x in rows) else None}
        for t in TARGETS},'claim':'Descriptive fixed-suite qualification only; no productivity or hardware-speed ranking.'}

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true')
    parser.add_argument('--plan',type=Path);parser.add_argument('--plan-sha256');parser.add_argument('--report',type=Path)
    parser.add_argument('--analyze',type=Path);parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--nonce',help=argparse.SUPPRESS);args=parser.parse_args(argv)
    if args.analyze:
        print(json.dumps(summarize(json.loads(args.analyze.read_text(encoding='utf-8')))));return 0
    if not args.execute and not args.worker:
        print(json.dumps({'mode':'DRY_PLAN','study_requests':36,'pilot_requests':6,'max_tokens':64,'budget_s':600,
                          'generated_code_executed':False}));return 0
    if args.plan is None or args.report is None or not args.plan_sha256:parser.error('Explicit locked plan, SHA and new private report required')
    raw=args.plan.read_bytes();plan=json.loads(raw)
    if hashlib.sha256(raw).hexdigest()!=args.plan_sha256 or plan['source_sha256']!=identities():raise ValueError('FrozenStudyIdentityChanged')
    if plan['sequence']!=[list(x) for x in sequence(plan['stage'])] or plan['cases']!=list(CASES):raise ValueError('FrozenCasesChanged')
    if plan['max_tokens']!=64 or plan['budget_s']!=600:raise ValueError('StudyBoundsChanged')
    path=args.report.resolve()
    if path.exists() or path==ROOT or ROOT in path.parents or not path.parent.is_dir():raise ValueError('NewPrivateReportOutsideRepositoryRequired')
    if args.worker:
        if not args.nonce:raise ValueError('CheckpointOwnerMissing')
        report=run_session(LiveAdapter(),path,plan['stage'],args.nonce,args.plan_sha256)
        return 0 if report['complete'] else 2
    nonce=__import__('uuid').uuid4().hex
    child=[sys.executable,str(Path(__file__).resolve()),'--worker','--plan',str(args.plan.resolve()),
           '--plan-sha256',args.plan_sha256,'--report',str(path),'--nonce',nonce]
    rc=continuity.supervise(child,path,nonce,600)
    if rc and path.exists():
        report=json.loads(path.read_text(encoding='utf-8'))
        if report.get('stop') is None:continuity.owned_failure(path,nonce,'worker_process_failed')
    print(json.dumps({'complete':rc==0,'report_created':path.exists()}));return rc

if __name__=='__main__':raise SystemExit(main())
