"""Native application recompile/link alongside bounded AI; dry plan by default."""
from pathlib import Path
import argparse,hashlib,json,math,os,subprocess,sys,time
from datetime import datetime,timezone
REPO=Path(__file__).resolve().parents[1]
WORK=Path(os.getenv('NANO_R3_PRIVATE_DIR',str(Path.home()/'nano-r3-private'))).resolve()
import r3_system_workload as r3
from r3_burst_workload import read_placement
from nano_usb_client import NanoUSBClient
import r3_native_job as native_job
from r3_swift_prepare import canonical_sha
MANIFEST=None
CONFIG=None
JOB_RUNNER=Path(__file__).with_name('r3_native_job.py')
LINUX_RUNNER=None
TASKS=('arithmetic','format')
PLAN_BYTES=b''
PROTOCOL={}
ORDER=[]
PREFIX='native'
def load_plan(path,expected_sha=None):
 global PLAN_BYTES,PROTOCOL,ORDER,PREFIX
 PLAN_BYTES=Path(path).read_bytes()
 if expected_sha is not None and hashlib.sha256(PLAN_BYTES).hexdigest()!=expected_sha:
  raise ValueError('LockedNativeProtocolChanged')
 PROTOCOL=json.loads(PLAN_BYTES)
 if PROTOCOL['stage'] not in ('pilot','registered'): raise ValueError('UnknownStudyStage')
 if PROTOCOL['controller_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
  raise ValueError('NativeControllerChanged')
 if PROTOCOL['worker_sha256']!=hashlib.sha256(JOB_RUNNER.read_bytes()).hexdigest():
  raise ValueError('NativeWorkerChanged')
 if PROTOCOL['native_spec_sha256']!=canonical_sha(json.loads(native_job.SPEC.read_text(encoding='utf-8-sig'))):
  raise ValueError('NativeSourceSpecChanged')
 ORDER=PROTOCOL['sequence'];PREFIX='native_'+PROTOCOL['stage']
 targets={'windows_cpu','windows_gpu_candidate','iphone_usb_coreml'}
 if ORDER[0]!='baseline' or ORDER[-1]!='baseline' or set(ORDER)-targets-{'baseline'}:
  raise ValueError('InvalidNativeStudyOrder')
 if len(ORDER)!=(5 if PROTOCOL['stage']=='pilot' else 25):
  raise ValueError('InvalidNativeStudySize')
 if PROTOCOL['native_job_deadline_s']!=45 or PROTOCOL['tasks']!=['arithmetic','format']:
  raise ValueError('NativeQualityBudgetChanged')
PHASE=WORK/'status'

LINUX_PHASE=None
def configure(reproduction=False):
 global CONFIG,MANIFEST,LINUX_RUNNER,LINUX_PHASE
 config_path=Path(os.environ.get('NANO_SWIFT_STUDY_CONFIG','')).resolve()
 if not config_path.is_file() or config_path==REPO or REPO in config_path.parents:
  raise ValueError('UsePrivateStudyConfigOutsideRepository')
 c=json.loads(config_path.read_text(encoding='utf-8-sig'))
 expected={'job_manifest_linux','job_manifest_sha256','linux_runner','linux_phase_root','wsl_distribution'}
 if set(c)!=expected or len(c['job_manifest_sha256'])!=64 or (not reproduction and c['job_manifest_sha256']!=PROTOCOL['job_manifest_sha256']):
  raise ValueError('StudyConfigMismatch')
 if WORK==REPO or REPO in WORK.parents:
  raise ValueError('OutputDirectoryMustBePrivate')
 CONFIG=c
 MANIFEST=c['job_manifest_sha256']
 LINUX_RUNNER=c['linux_runner']
 LINUX_PHASE=c['linux_phase_root'].rstrip('/')+'/status'

def assess(result,answers,is_ai):
 reason=native_job.assess(result)
 if reason: return reason
 if result.get('native_spec_sha256')!=PROTOCOL['native_spec_sha256']: return 'native_spec_mismatch'
 if not result.get('passed') or result.get('exit_code')!=0 or not result.get('source_unchanged'):
  return 'compiler_validation_failure'
 if result.get('logical_spec_sha256')!=PROTOCOL['logical_spec_sha256']:
  return 'logical_workload_mismatch'
 if result.get('job_manifest_sha256')!=MANIFEST or result.get('source_count')!=10:
  return 'job_identity_mismatch'
 if type(result.get('elapsed_s')) not in (int,float) or not math.isfinite(result['elapsed_s']) or not 0<result['elapsed_s']<45:
  return 'invalid_job_duration'
 if is_ai:
  if [a['task_label'] for a in answers]!=list(TASKS):
   return 'incomplete_ai_burst'
  if not all(a['passed_exact_answer'] for a in answers):
   return 'ai_quality_failure'
  # Compiler start follows Windows launch. Finishing before launch+D-0.25
  # is a conservative overlap test without synchronizing OS clock epochs.
  if max(a['finish_offset_from_launch_s'] for a in answers)+.25>result['elapsed_s']:
   return 'conservative_overlap_gate_failed'
 return None
def run_job(target,index,client):
 label=PREFIX+'_'+str(index)
 phase=PHASE/(label+'.started.json')
 env={k:v for k,v in os.environ.items() if not k.startswith('NANO_USB_')}
 began=time.perf_counter()
 child=subprocess.Popen(['wsl','-d',CONFIG['wsl_distribution'],'-u','root','--','python3',LINUX_RUNNER,label,
 '--phase-dir',LINUX_PHASE,'--phase-root',CONFIG['linux_phase_root'],
 '--job-manifest',CONFIG['job_manifest_linux'],'--expected-sha',MANIFEST],
     stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',env=env)
 answers=[]
 stop=None
 try:
  if target!='baseline':
   deadline=time.perf_counter()+10
   while True:
    if phase.exists():
     try:
      marker=json.loads(phase.read_text())
      assert marker['phase']=='compiler_started' and marker['job_manifest_sha256']==MANIFEST and marker['live_native_frontend_observed']
      break
     except json.JSONDecodeError:
      pass
    if child.poll() is not None or time.perf_counter()>deadline:
     raise RuntimeError('CompilerStartWitnessMissing')
    time.sleep(.02)
   time.sleep(.15)
   for task in TASKS:
    if child.poll() is not None:
     stop='job_ended_before_ai_burst'
     break
    start=time.perf_counter()-began
    a=r3.infer(target,task,client)
    finish=time.perf_counter()-began
    answers.append(dict(a,task_label=task,start_offset_from_launch_s=round(start,6),
                        finish_offset_from_launch_s=round(finish,6)))
    if not a['passed_exact_answer']:
     stop='ai_quality_failure'
     break
 except Exception as exc:
  stop=type(exc).__name__
 try:
  output,error=child.communicate(timeout=60)
 except subprocess.TimeoutExpired:
  child.kill()
  output,error=child.communicate()
  raise RuntimeError('CompilerControllerTimeout')
 (WORK/(label+'.private-output.log')).write_text(output+'\n'+error,encoding='utf-8')
 result=json.loads(output.strip().splitlines()[-1])
 if result.get('job_runner_sha256')!=hashlib.sha256(JOB_RUNNER.read_bytes()).hexdigest():
  stop=stop or 'job_runner_identity_mismatch'
 stop=stop or assess(result,answers,target!='baseline')
 return {'sequence':index,'target':target,'compiler_job':result,'ai_requests':answers,
   'windows_launch_to_return_s':round(time.perf_counter()-began,6),'stop_reason':stop}
def main(argv=None):
 parser=argparse.ArgumentParser()
 parser.add_argument('--execute',action='store_true')
 parser.add_argument('--plan',type=Path)
 parser.add_argument('--plan-sha256')
 parser.add_argument('--reproduce',action='store_true',help='Allow local path materialization with the same logical source/job spec')
 parser.add_argument('--report',type=Path)
 a=parser.parse_args(argv)
 if a.execute and (a.plan is None or a.plan_sha256 is None): parser.error('Explicit locked plan and SHA required')
 if a.plan is not None: load_plan(a.plan,a.plan_sha256)
 if not a.execute:
  print(json.dumps({'mode':'DRY_PLAN','job':'frozen_nano_native_recompile_and_link','order':ORDER,
      'requests_per_ai_job':2,'fixed_work_source_files':10,'signing':False,'phone_install':False}))
  return 0
 if a.report is None or a.report.resolve().parent!=WORK or a.report.exists() or PHASE.exists():
  parser.error('Use new private report and status directory')
 configure(a.reproduce)
 r3.model_integrity()
 client=NanoUSBClient('https://127.0.0.1:49443',os.getenv('NANO_USB_TLS_PIN',''),os.getenv('NANO_USB_BEARER',''))
 if client.status().get('status')!='ready':
  raise RuntimeError('PhoneNotReady')
 PHASE.mkdir()
 rows=[]
 compiler_warmups=[]
 warmups=[]
 stop=None
 started_utc=datetime.now(timezone.utc).isoformat()
 began_study=time.monotonic()
 for i,target in enumerate(ORDER):
  if time.monotonic()-began_study>PROTOCOL['overall_deadline_s']:
   stop='overall_time_budget_exceeded'
   break
  try:
   if target!='baseline':
    for task in TASKS:
     w=r3.infer(target,task,client)
     warmups.append(dict(w,target=target,task_label=task))
     if not w['passed_exact_answer']:
      stop='warmup_quality_failure'
      break
    if stop: break
   compiler_warm=run_job('baseline','warm_'+str(i),client)
   compiler_warmups.append(compiler_warm)
   if compiler_warm['stop_reason']:
    stop=compiler_warm['stop_reason']
    break
   print('APPLICATION_CACHE_WARMUP_'+str(i+1)+'=PASS',flush=True)
   before=read_placement(target) if target.startswith('windows_') else None
   row=run_job(target,i,client)
   row['placement_before']=before
   row['placement_after']=read_placement(target) if target.startswith('windows_') else None
   rows.append(row)
   stop=row['stop_reason']
   print('APPLICATION_JOB_'+str(i+1)+'='+('PASS' if not stop else 'STOP'),flush=True)
   if stop: break
  except Exception as exc:
   stop=type(exc).__name__
   break
 report={'schema':'nano-r3-native-concurrent-raw-v1','protocol_sha256':hashlib.sha256(PLAN_BYTES).hexdigest(),'public_order_seed':PROTOCOL['public_order_seed'],'timestamp_utc':datetime.now(timezone.utc).isoformat(),'started_utc':started_utc,
  'complete':len(rows)==len(ORDER) and stop is None,'stop_reason':stop,'samples':rows,'warmups':warmups,'compiler_warmups':compiler_warmups,'per_condition_compiler_warmup':True,
  'job':'frozen_v11_native_recompile_and_link_via_windows_wsl','job_manifest_sha256':MANIFEST,
  'cold_and_cache_warm_calibrations_excluded':True,'primary_metric':'compiler_completion_seconds',
  'sample_size_notice':'native build observations reported separately from prior typecheck studies',
  'energy_measured':False,'ane_execution_verified':False,'phone_install':False,'signing':False,
  'session_id':'native_'+PROTOCOL['stage'],'native_spec_sha256':PROTOCOL['native_spec_sha256'],'registered_environment_reproduction':a.reproduce,'logical_spec_sha256':PROTOCOL['logical_spec_sha256'],'controller_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 with a.report.open('x',encoding='utf-8') as output:
  output.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
 print('NATIVE_CONCURRENT_COMPLETE='+str(report['complete']),flush=True)
 return 0 if report['complete'] else 2
if __name__=='__main__':
 raise SystemExit(main())
