"""Offline diagnostics alongside frozen R5 scores; never execute candidate code."""
from pathlib import Path
import argparse
import ast
import hashlib
import io
import json
import os
import subprocess
import sys
import token
import tokenize

# Keep the parser worker standard-library-only. Importing the R5 live runner
# would require user-site cryptography packages excluded by isolated startup.
CLIENT=Path(__file__).resolve().parent
REFERENCE_PROTOCOL=CLIENT.parent/'results/r5_coding_study_protocol_20261114.json'
REFERENCE_SHA256='c1533bd659b24e113a6d1e12b5801d018302b2f03f2efc0ad4efb8733588979f'
REFERENCE_BYTES=REFERENCE_PROTOCOL.read_bytes()
if hashlib.sha256(REFERENCE_BYTES).hexdigest()!=REFERENCE_SHA256:raise ValueError('ReferenceProtocolChanged')
CASES={case['id']:case for case in json.loads(REFERENCE_BYTES)['cases']}
MAX_BYTES=4096
MAX_LEXEMES=256
MAX_NESTING=24
MAX_NUMBER_CHARS=64
MAX_AST_NODES=512
MAX_AST_DEPTH=64
WORKER_TIMEOUT_S=2
WIRE_LIMIT=32768
CLASSIFICATIONS=frozenset(('exact_match','code_fence_normalized','wrapper_rejected','python_noncanonical',
    'json_value_mismatch','invalid_syntax','invalid_json','empty_output','resource_limit','invalid_input',
    'invalid_case','worker_timeout','worker_failed','worker_invalid'))
FIELDS=frozenset(('schema','case_id','classification','strict_pass','normalized_pass','semantic_correctness',
                  'raw_text_retained','code_executed','input_sha256','input_bytes'))

def _result(case_id,text,classification,strict=None,normalized=False):
    try:raw=text.encode('utf-8') if isinstance(text,str) else None
    except UnicodeError:raw=None
    return {'schema':'nano-r6-diagnostic-v1','case_id':case_id if case_id in CASES else None,
        'classification':classification,'strict_pass':strict,'normalized_pass':normalized,
        'semantic_correctness':'not_assessed','raw_text_retained':False,'code_executed':False,
        'input_sha256':hashlib.sha256(raw).hexdigest() if raw is not None else None,
        'input_bytes':len(raw) if raw is not None else None}

def _unwrap(text,kind):
    lines=text.strip().splitlines()
    if not any('```' in line for line in lines):return text.strip(),False
    allowed={'```','```python'} if kind=='python_expression' else {'```','```json'}
    if len(lines)<3 or lines[0] not in allowed or lines[-1]!='```':return None,False
    if any('```' in line for line in lines[1:-1]):return None,False
    return '\n'.join(lines[1:-1]).strip(),True

def _lexical_guard(text):
    """Apply small lexical limits before AST/JSON parsing; do not evaluate tokens."""
    count=0;depth=0
    try:
        for item in tokenize.generate_tokens(io.StringIO(text).readline):
            if item.type in (token.ENDMARKER,token.NEWLINE,tokenize.NL,token.INDENT,token.DEDENT):continue
            count+=1
            if count>MAX_LEXEMES:return 'resource_limit'
            if item.type==token.NUMBER and len(item.string)>MAX_NUMBER_CHARS:return 'resource_limit'
            if item.type==token.OP:
                if item.string in ('(','[','{'):
                    depth+=1
                    if depth>MAX_NESTING:return 'resource_limit'
                elif item.string in (')',']','}'):depth-=1
    except (tokenize.TokenError,SyntaxError,IndentationError):return 'lexical_error'
    return None

def _ast_guard(tree):
    stack=[(tree,0)];count=0
    while stack:
        node,depth=stack.pop();count+=1
        if count>MAX_AST_NODES or depth>MAX_AST_DEPTH:return False
        stack.extend((child,depth+1) for child in ast.iter_child_nodes(node))
    return True

def _reject_constant(_):raise ValueError('NonFiniteJSON')

def _reference_grade(case,text):
    """Frozen R5 AST/canonical-JSON rule, checked against R5 by regression tests.

    Called only after resource checks. No transport/model module is imported.
    """
    try:
        if case['kind']=='python_expression':
            return ast.dump(ast.parse(text.strip(),mode='eval'))==ast.dump(ast.parse(case['expected'],mode='eval'))
        return json.dumps(json.loads(text),sort_keys=True,allow_nan=False)==json.dumps(json.loads(case['expected']),sort_keys=True,allow_nan=False)
    except (ValueError,SyntaxError,TypeError,RecursionError):return False

def _assess(case_id,text):
    """Trusted worker implementation. Public callers use diagnose for isolation."""
    if not isinstance(case_id,str) or case_id not in CASES:return _result(None,None,'invalid_case')
    if not isinstance(text,str):return _result(case_id,None,'invalid_input')
    if len(text)>MAX_BYTES:return _result(case_id,None,'resource_limit')
    try:raw=text.encode('utf-8')
    except UnicodeError:return _result(case_id,None,'invalid_input')
    if len(raw)>MAX_BYTES:return _result(case_id,text,'resource_limit')
    case=CASES[case_id];candidate,wrapped=_unwrap(text,case['kind'])
    if candidate is None:return _result(case_id,text,'wrapper_rejected')
    if not candidate:return _result(case_id,text,'empty_output',False)
    guard=_lexical_guard(candidate)
    if guard=='resource_limit':return _result(case_id,text,'resource_limit')
    invalid='invalid_syntax' if case['kind']=='python_expression' else 'invalid_json'
    if guard=='lexical_error':return _result(case_id,text,invalid,False)
    try:
        if case['kind']=='python_expression':
            tree=ast.parse(candidate,mode='eval')
            if not _ast_guard(tree):return _result(case_id,text,'resource_limit')
        else:
            json.loads(candidate,parse_constant=_reject_constant)
    except (ValueError,SyntaxError,TypeError,RecursionError):return _result(case_id,text,invalid,False)
    strict=_reference_grade(case,text)
    normalized=_reference_grade(case,candidate)
    classification=('exact_match' if strict else 'code_fence_normalized') if normalized else (
        'python_noncanonical' if case['kind']=='python_expression' else 'json_value_mismatch')
    return _result(case_id,text,classification,strict,normalized)

def _valid_worker_result(value,case_id,text):
    if not isinstance(value,dict) or set(value)!=FIELDS:return False
    if value.get('schema')!='nano-r6-diagnostic-v1' or value.get('case_id')!=case_id:return False
    if not isinstance(value.get('classification'),str) or value['classification'] not in CLASSIFICATIONS:return False
    if value.get('semantic_correctness')!='not_assessed':return False
    if value.get('raw_text_retained') is not False or value.get('code_executed') is not False:return False
    if value.get('strict_pass') is not None and type(value['strict_pass']) is not bool:return False
    if type(value.get('normalized_pass')) is not bool:return False
    raw=text.encode('utf-8')
    if value.get('input_sha256')!=hashlib.sha256(raw).hexdigest() or type(value.get('input_bytes')) is not int or value['input_bytes']!=len(raw):return False
    if value['classification']=='exact_match':return value['strict_pass'] is True and value['normalized_pass'] is True
    if value['classification']=='code_fence_normalized':return value['strict_pass'] is False and value['normalized_pass'] is True
    return value['normalized_pass'] is False and value['strict_pass'] is not True

def _kill_and_drain(child):
    try:child.kill()
    except OSError:pass
    try:child.communicate(timeout=1)
    except (OSError,subprocess.TimeoutExpired):return False
    return True

def diagnose(case_id,text):
    if not isinstance(case_id,str) or case_id not in CASES:return _result(None,None,'invalid_case')
    if not isinstance(text,str):return _result(case_id,None,'invalid_input')
    if len(text)>MAX_BYTES:return _result(case_id,None,'resource_limit')
    try:raw=text.encode('utf-8')
    except UnicodeError:return _result(case_id,None,'invalid_input')
    if len(raw)>MAX_BYTES:return _result(case_id,text,'resource_limit')
    # Candidate text travels only through stdin; no credentials, model config or
    # arbitrary parent variables are inherited by the parser process.
    env={k:os.environ[k] for k in ('SYSTEMROOT','WINDIR','TEMP','TMP') if k in os.environ}
    args=[sys.executable,'-I','-B','-X','utf8',str(Path(__file__).resolve()),'--worker']
    payload=json.dumps({'case_id':case_id,'text':text},ensure_ascii=False).encode('utf-8')
    child=None
    try:
        child=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        output,_=child.communicate(input=payload,timeout=WORKER_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        clean=_kill_and_drain(child)
        return _result(case_id,text,'worker_timeout' if clean else 'worker_failed')
    except OSError:
        if child is not None:_kill_and_drain(child)
        return _result(case_id,text,'worker_failed')
    if child.returncode!=0:return _result(case_id,text,'worker_failed')
    if not isinstance(output,bytes) or len(output)>2048:return _result(case_id,text,'worker_invalid')
    try:value=json.loads(output)
    except (ValueError,UnicodeError):return _result(case_id,text,'worker_invalid')
    return value if _valid_worker_result(value,case_id,text) else _result(case_id,text,'worker_invalid')

FIXTURES=(
 ('exact_python','py_inclusive_range','range(1,n+1)','exact_match'),
 ('whitespace','py_inclusive_range','  range(1, n + 1)  ','exact_match'),
 ('fenced_python','py_inclusive_range','```python\nrange(1,n+1)\n```','code_fence_normalized'),
 ('bare_fence','py_inclusive_range','```\nrange(1,n+1)\n```','code_fence_normalized'),
 ('prose_rejected','py_inclusive_range','Here:\n```python\nrange(1,n+1)\n```','wrapper_rejected'),
 ('wrong_language','py_inclusive_range','```javascript\nrange(1,n+1)\n```','wrapper_rejected'),
 ('noncanonical_variant','py_inclusive_range','range(1,1+n)','python_noncanonical'),
 ('noncanonical_bug','py_inclusive_range','range(1,n)','python_noncanonical'),
 ('syntax_error','py_inclusive_range','range(','invalid_syntax'),
 ('json_exact','py_bool_trace','[true, false]','exact_match'),
 ('json_fenced','py_bool_trace','```json\n[true,false]\n```','code_fence_normalized'),
 ('json_type_difference','py_bool_trace','[1,0]','json_value_mismatch'),
 ('json_float_difference','swift_clamp_trace','32.0','json_value_mismatch'),
 ('json_invalid','py_bool_trace','[true,]','invalid_json'),
 ('json_nonfinite','swift_clamp_trace','NaN','invalid_json'),
 ('empty','py_inclusive_range',' ','empty_output'),
 ('nesting_limit','py_inclusive_range','('*25+'1'+')'*25,'resource_limit'),
 ('number_limit','py_inclusive_range','9'*65,'resource_limit'),
 ('token_limit','py_inclusive_range','+'.join(['x']*140),'resource_limit'),
 ('ast_depth_limit','py_inclusive_range','+'.join(['x']*80),'resource_limit'),
)

def qualify():
    rows=[]
    for fixture_id,case_id,text,expected in FIXTURES:
        result=diagnose(case_id,text)
        rows.append({'fixture_id':fixture_id,'expected_classification':expected,
                     'classification':result['classification'],'passed':result['classification']==expected,
                     'strict_pass':result['strict_pass'],'normalized_pass':result['normalized_pass']})
    passed=sum(x['passed'] for x in rows)
    return {'schema':'nano-r6-fixture-qualification-v1','scope':'offline_synthetic_fixtures_only',
        'complete':passed==len(rows),'fixture_count':len(rows),'passed':passed,'fixtures':rows,
        'r5_rescored':False,'live_inference':False,'generated_code_executed':False,'reference_protocol_sha256':REFERENCE_SHA256,
        'source_sha256':{name:hashlib.sha256((CLIENT/name).read_bytes()).hexdigest() for name in (
            'r6_diagnostic_grading.py','r5_coding_quality.py','r4_foreground_reliability.py','nano_usb_client.py')}}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--case-id');parser.add_argument('--text-file',type=Path)
    args=parser.parse_args(argv)
    if args.worker:
        try:
            wire=sys.stdin.buffer.read(WIRE_LIMIT+1)
            if len(wire)>WIRE_LIMIT:return 2
            value=json.loads(wire)
            if not isinstance(value,dict) or set(value)!={'case_id','text'}:return 2
            result=_assess(value['case_id'],value['text'])
        except Exception:return 2
        print(json.dumps(result,allow_nan=False));return 0
    if args.qualify:
        report=qualify();print(json.dumps(report,allow_nan=False));return 0 if report['complete'] else 2
    if args.case_id is None and args.text_file is None:
        print(json.dumps({'mode':'DRY_PLAN','input_limit_bytes':MAX_BYTES,'worker_timeout_s':WORKER_TIMEOUT_S,
                          'generated_code_executed':False,'network_requests':0}));return 0
    if args.case_id not in CASES or args.text_file is None:
        print(json.dumps(_result(None,None,'invalid_case')));return 2
    try:
        with args.text_file.open('rb') as f:raw=f.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:
            print(json.dumps(_result(args.case_id,None,'resource_limit')));return 2
        text=raw.decode('utf-8')
    except (OSError,UnicodeError):
        print(json.dumps(_result(args.case_id,None,'invalid_input')));return 2
    result=diagnose(args.case_id,text);print(json.dumps(result,allow_nan=False));return 0

if __name__=='__main__':raise SystemExit(main())
