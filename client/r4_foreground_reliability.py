"""Bounded sampled continuity checks for an existing pinned foreground USB service."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,math,os,socket,ssl,subprocess,sys,time,uuid
from nano_usb_client import NanoUSBClient,PinMismatch,AuthenticationError,TransportError
ROOT=Path(__file__).resolve().parents[1]
MODEL='qwen3.5-0.8b'
TASKS=(('arithmetic','What is 17 + 25? Reply with exactly the integer, digits only.','42'),
 ('format','Reply with exactly the word BLUE in capitals. No other characters.','BLUE'))
class CheckFailure(Exception):
 def __init__(self,code):self.code=code
def classify(exc):
 if isinstance(exc,CheckFailure):return exc.code if exc.code in {'model_identity_invalid','telemetry_invalid','answer_invalid','tokens_invalid','metrics_invalid','model_not_ready','study_budget_expired'} else 'unexpected_error'
 for kind,code in ((PinMismatch,'pin_rejected'),(AuthenticationError,'authorization_rejected'),
  (ConnectionResetError,'connection_reset'),(ConnectionRefusedError,'connection_refused'),
  (TimeoutError,'transport_timeout'),(ssl.SSLError,'tls_failed'),(TransportError,'protocol_rejected')):
  if isinstance(exc,kind):return code
 return 'unexpected_error'
def check_response(value,expected,wall):
 if not isinstance(value,dict) or value.get('model_id')!=MODEL:raise CheckFailure('model_identity_invalid')
 if value.get('metrics_source')!='on_device_coreml_generator':raise CheckFailure('telemetry_invalid')
 if not isinstance(value.get('text'),str) or value['text'].strip()!=expected:raise CheckFailure('answer_invalid')
 tokens=value.get('completion_tokens')
 if type(tokens) is not int or not 1<=tokens<=32:raise CheckFailure('tokens_invalid')
 numbers=[value.get('model_elapsed_ms'),value.get('generator_tokens_per_second'),wall]
 if any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in numbers) or numbers[0]<=0 or numbers[1]<=0:
  raise CheckFailure('metrics_invalid')
 return {'passed_exact_answer':True,'completion_tokens':tokens,'wall_s':round(wall,6),
  'model_elapsed_ms':round(numbers[0],3),'generator_tokens_per_second':round(numbers[1],3),'on_device_metrics_verified':True}
def checkpoint(path,report):
 temp=path.with_name(path.name+'.checkpoint.tmp')
 with temp.open('w',encoding='utf-8') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
 os.replace(temp,path)
def run_session(factory,path,plan,plan_sha,nonce,clock=time.monotonic,sleep=time.sleep):
 report={'schema':'nano-r4-foreground-continuity-v1','owner_nonce':nonce,'plan_sha256':plan_sha,
  'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'supporting_client_sha256':hashlib.sha256(Path(__file__).with_name('nano_usb_client.py').read_bytes()).hexdigest(),'stage':plan['stage'],'started_utc':datetime.now(timezone.utc).isoformat(),'complete':False,'stop':None,
  'model_id':MODEL,'target':'iphone_usb_coreml','statuses':[],'samples':[],'idle_intervals':[],
  'status_attempts':0,'generation_attempts':0,'runtime_build_attested':False,'wakelock_runtime_verified':False,
  'foreground_state_instrumented':False,'energy_measured':False,'ane_profiled':False,'automatic_retries':False}
 with path.open('x',encoding='utf-8') as f:json.dump(report,f);f.write('\n')
 began=clock();phase='configuration';round_number=0;task=None
 def budget():
  if clock()-began>=plan['budget_s']:raise CheckFailure('study_budget_expired')
 def status(client,where):
  nonlocal phase
  budget();phase=where;report['status_attempts']+=1;checkpoint(path,report)
  start=clock();value=client.status()
  if value.get('model_id')!=MODEL:raise CheckFailure('model_identity_invalid')
  if value.get('status')!='ready':raise CheckFailure('model_not_ready')
  report['statuses'].append({'round':round_number,'phase':where,'wall_s':round(clock()-start,6),
   'elapsed_s':round(clock()-began,6),'pinned_authenticated_ready':True})
  checkpoint(path,report)
 try:
  client=factory()
  for round_number in range(1,plan['rounds']+1):
   status(client,'before_round')
   for task,prompt,expected in TASKS:
    budget();phase='generation';report['generation_attempts']+=1;checkpoint(path,report)
    start=clock();response=client.generate(prompt,32)
    sample=check_response(response,expected,clock()-start)
    report['samples'].append(dict(sample,round=round_number,task=task,elapsed_s=round(clock()-began,6)))
    checkpoint(path,report)
   task=None;status(client,'after_round');phase='idle';budget();start=clock()
   sleep(plan['idle_seconds'])
   report['idle_intervals'].append({'round':round_number,'requested_s':plan['idle_seconds'],'observed_s':round(clock()-start,6)})
   checkpoint(path,report)
  status(client,'final_status');budget();report['complete']=True
 except Exception as exc:
  report['stop']={'code':'configuration_invalid' if phase=='configuration' else classify(exc),'phase':phase,'round':round_number,'task':task}
 finally:
  report['finished_utc']=datetime.now(timezone.utc).isoformat()
  report['observed_elapsed_s']=round(clock()-began,6);checkpoint(path,report)
 return report
def validate_plan(plan):
 expected={'pilot':(1,0,60),'soak':(6,120,900)}
 if plan.get('stage') not in expected:raise ValueError('UnknownContinuityStage')
 if (plan['rounds'],plan['idle_seconds'],plan['budget_s'])!=expected[plan['stage']]:raise ValueError('ContinuityBoundsChanged')
 if plan['tasks']!=['arithmetic','format'] or plan['max_tokens']!=32:raise ValueError('ContinuityTaskContractChanged')
 if plan['supporting_client_sha256']!=hashlib.sha256(Path(__file__).with_name('nano_usb_client.py').read_bytes()).hexdigest():raise ValueError('PinnedClientChanged')
 if plan['runner_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():raise ValueError('ContinuityRunnerChanged')
def owned_failure(path,nonce,code):
 if not path.exists():return None
 r=json.loads(path.read_text(encoding='utf-8'))
 if r.get('owner_nonce')!=nonce:raise ValueError('ForeignCheckpoint')
 r['complete']=False;r['stop']={'code':code,'phase':'supervisor','round':None,'task':None}
 r['finished_utc']=datetime.now(timezone.utc).isoformat();checkpoint(path,r);return r
def supervise(args,path,nonce,budget):
 log=path.with_name(path.name+'.private-worker.log')
 with log.open('x',encoding='utf-8') as out:
  child=subprocess.Popen(args,stdout=out,stderr=subprocess.STDOUT)
  try:return child.wait(timeout=budget)
  except subprocess.TimeoutExpired:
   child.terminate()
   try:child.wait(timeout=5)
   except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
   owned_failure(path,nonce,'study_budget_expired');return 2
def main(argv=None):
 p=argparse.ArgumentParser()
 p.add_argument('--execute',action='store_true');p.add_argument('--plan',type=Path);p.add_argument('--plan-sha256')
 p.add_argument('--report',type=Path);p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);p.add_argument('--nonce',help=argparse.SUPPRESS)
 a=p.parse_args(argv)
 if not a.execute and not a.worker:
  print(json.dumps({'mode':'DRY_PLAN','soak_rounds':6,'inference_requests':12,'idle_seconds':120,'hard_budget_s':900,'max_tokens':32,'automatic_retries':False}))
  return 0
 if a.plan is None or a.report is None or not a.plan_sha256:p.error('Explicit locked plan, SHA and private report are required')
 raw=a.plan.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=a.plan_sha256:raise ValueError('ContinuityProtocolChanged')
 plan=json.loads(raw);validate_plan(plan);path=a.report.resolve()
 if path.exists() or path==ROOT or ROOT in path.parents or not path.parent.is_dir():raise ValueError('NewPrivateReportOutsideRepositoryRequired')
 if a.worker:
  if not a.nonce:raise ValueError('MissingCheckpointOwner')
  report=run_session(lambda:NanoUSBClient('https://127.0.0.1:49443',os.getenv('NANO_USB_TLS_PIN',''),os.getenv('NANO_USB_BEARER','')),path,plan,a.plan_sha256,a.nonce)
  return 0 if report['complete'] else 2
 nonce=uuid.uuid4().hex
 args=[sys.executable,str(Path(__file__).resolve()),'--worker','--plan',str(a.plan.resolve()),'--plan-sha256',a.plan_sha256,'--report',str(path),'--nonce',nonce]
 rc=supervise(args,path,nonce,plan['budget_s'])
 if rc and path.exists():
  report=json.loads(path.read_text(encoding='utf-8'))
  if report.get('stop') is None:owned_failure(path,nonce,'worker_process_failed')
 report=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
 print(json.dumps({'complete':report.get('complete',False),'status_checks_passed':len(report.get('statuses',[])),
  'answers_passed':len(report.get('samples',[])),'stop':report.get('stop')}))
 return rc
if __name__=='__main__':raise SystemExit(main())
