"""Audit native artifact/overlap evidence and recompute separate-session outcomes."""
from pathlib import Path
from datetime import datetime
import argparse,copy,hashlib,json,math,statistics
import r3_native_job as job
from r3_swift_prepare import load_spec,canonical_sha
from r3_application_analyze import analyze as paired_analysis
ROOT=Path(__file__).resolve().parents[1]
JOB_FIELDS={'schema','label','elapsed_s','exit_code','timed_out','source_unchanged','source_count','source_commit',
 'logical_spec_sha256','native_spec_sha256','dependency_inputs_unchanged','dependency_inputs_sha256','dependency_input_count',
 'live_native_frontend_observed','native_frontend_observed_offset_s','network_namespace_isolated','input_mounts_readonly',
 'phone_install','signing','compiler_output_bytes','job_manifest_sha256','job_runner_sha256','supporting_runner_sha256',
 'fresh_application_objects','fresh_linked_binary','new_application_objects_linked','binary_sha256','binary_bytes',
 'macho','stop_reason','passed'}
PROJECTED_FIELDS={'schema','label','elapsed_s','exit_code','passed','timed_out','source_unchanged','source_count','source_commit',
 'compiler_output_bytes','phone_install','signing','job_manifest_sha256','job_runner_sha256','logical_spec_sha256'}
def audit_jobs(d,allow_stopped_final=False):
 native_spec=canonical_sha(json.loads(job.SPEC.read_text(encoding='utf-8-sig')))
 if d['native_spec_sha256']!=native_spec or d['logical_spec_sha256']!=canonical_sha(load_spec()):
  raise ValueError('NativeSpecMismatch')
 for row in d['samples']+d['compiler_warmups']:
  r=row['compiler_job']
  if set(r)!=JOB_FIELDS:raise ValueError('UnexpectedNativeEvidenceFields')
  allowed_stop=allow_stopped_final and row is d['samples'][-1] and row['stop_reason']==d['stop_reason']
  if (row['stop_reason'] is not None and not allowed_stop) or r['stop_reason'] is not None or not r['passed'] or job.assess(r):
   raise ValueError('NativeArtifactQualityFailure')
  for key in ('native_spec_sha256','logical_spec_sha256','dependency_inputs_sha256','dependency_input_count','job_manifest_sha256'):
   if r[key]!=d[key]:raise ValueError('NativeWorkloadIdentityMismatch')
  if r['job_runner_sha256']!=d['worker_sha256'] or r['supporting_runner_sha256']!=d['supporting_runner_sha256']:
   raise ValueError('NativeCodeIdentityMismatch')
  if r['source_commit']!=load_spec()['source_commit'] or r['source_count']!=10:
   raise ValueError('FrozenSourceMismatch')
  if not math.isfinite(r['elapsed_s']) or not 0<r['elapsed_s']<45 or not 0<=r['native_frontend_observed_offset_s']<r['elapsed_s']:
   raise ValueError('InvalidNativeTiming')
  if r['phone_install'] or r['signing']:raise ValueError('UnexpectedDeployment')
  if len(r['binary_sha256'])!=64 or r['binary_bytes']<=0:raise ValueError('NativeBinaryMissing')
  if row['target'].startswith('windows_'):
   expected='100% CPU' if row['target']=='windows_cpu' else '100% GPU'
   for field in ('placement_before','placement_after'):
    c=row[field]
    if not c or not c['placement_check_passed'] or not c['digest_matches'] or c['ollama_processor']!=expected:raise ValueError('NativePlacementMismatch')
    if (expected=='100% CPU' and c['size_vram_bytes']!=0) or (expected=='100% GPU' and c['size_vram_bytes']<=0):raise ValueError('NativePlacementMemoryMismatch')

def analyze(d):
 if d['schema']!='nano-native-concurrent-evidence-v1':raise ValueError('UnknownNativeEvidenceSchema')
 if d['externally_preregistered']:
  if not datetime.fromisoformat(d['registration_created_utc'].replace('Z','+00:00'))<datetime.fromisoformat(d['started_utc'])<datetime.fromisoformat(d['completed_utc']):
   raise ValueError('NativeRegistrationTimingMismatch')

 if not d['complete']:
  if [r['target'] for r in d['samples']]!=d['registered_sequence'][:len(d['samples'])]:raise ValueError('StoppedOrderMismatch')
  audit_jobs(d,allow_stopped_final=True)
  answers=[a for row in d['samples'] for a in row['ai_requests']]
  if d['stop_reason']!='warmup_quality_failure' and not all(w['passed_exact_answer'] for w in d['ai_warmups']):raise ValueError('StoppedWarmupQualityMismatch')
  if not all(a['passed_exact_answer'] and 1<=a['completion_tokens']<=32 for a in answers):raise ValueError('StoppedRecordedAnswerInvalid')
  return {'complete':False,'stop_reason':d['stop_reason'],'recorded_native_windows':len(d['samples']),
   'fully_valid_windows':sum(r['stop_reason'] is None for r in d['samples']),
   'passed_native_jobs':sum(r['compiler_job']['passed'] for r in d['samples']),
   'passed_native_warmups':sum(r['compiler_job']['passed'] for r in d['compiler_warmups']),
   'correct_measured_answers_recorded':len(answers),'correct_ai_warmups_recorded':sum(w['passed_exact_answer'] for w in d['ai_warmups']),
   'primary_outcome_reported':False,'notice':'Stopped registered attempt retained; no registered primary estimate or confidence interval is reported.'}

 elapsed=(datetime.fromisoformat(d['completed_utc'])-datetime.fromisoformat(d['started_utc'])).total_seconds()
 if not 0<elapsed<=(1200 if d['stage']=='registered' else 240):raise ValueError('OverallNativeBudgetExceeded')
 audit_jobs(d)
 for row in d['samples']:
  for answer in row['ai_requests']:
   if answer['start_offset_from_launch_s']<row['compiler_job']['native_frontend_observed_offset_s']:
    raise ValueError('InferencePrecededNativeFrontendWitness')
 if [r['target'] for r in d['samples']]!=d['registered_sequence']:raise ValueError('OrderMismatch')
 if d['stage']=='registered':
  projected=copy.deepcopy(d);projected['schema']='nano-r3-application-evidence-v1'
  projected['session_id']='native_registered'
  for row in projected['samples']+projected['compiler_warmups']:
   row['compiler_job']={key:row['compiler_job'][key] for key in PROJECTED_FIELDS}
  result=paired_analysis(projected)
 else:
  if len(d['samples'])!=5 or len(d['compiler_warmups'])!=5 or len(d['ai_warmups'])!=6:
   raise ValueError('PilotCountMismatch')
  if not all(w['passed_exact_answer'] for w in d['ai_warmups']):raise ValueError('PilotWarmupQualityFailure')
  requests=0
  for row in d['samples']:
   answers=row['ai_requests']
   if row['target']=='baseline':
    if answers:raise ValueError('BaselineInference')
    continue
   if [a['task_label'] for a in answers]!=['arithmetic','format']:raise ValueError('PilotTaskOrder')
   for a in answers:
    if not a['passed_exact_answer'] or not 1<=a['completion_tokens']<=32:raise ValueError('PilotQualityFailure')
    if not 0<a['start_offset_from_launch_s']<a['finish_offset_from_launch_s'] or a['finish_offset_from_launch_s']+.25>row['compiler_job']['elapsed_s']:
     raise ValueError('PilotOverlapFailure')
    requests+=1
  summary=[]
  for t in ('baseline','windows_cpu','windows_gpu_candidate','iphone_usb_coreml'):
   rows=[r for r in d['samples'] if r['target']==t]
   summary.append({'target':t,'jobs':len(rows),'median_compiler_s':statistics.median(r['compiler_job']['elapsed_s'] for r in rows),
    'median_ai_s':statistics.median(a['wall_s'] for r in rows for a in r['ai_requests']) if t!='baseline' else None})
  baselines=[r['compiler_job']['elapsed_s'] for r in d['samples'] if r['target']=='baseline']
  result={'complete':True,'measured_jobs':5,'measured_ai_requests':requests,'compiler_warmups':5,'ai_warmups':6,
   'summary':summary,'baseline_spread_percent':100*(max(baselines)-min(baselines))/statistics.median(baselines),
   'notice':'Feasibility pilot; one native rebuild per AI condition, no advantage inference.'}
 for row in result['summary']:row['median_native_build_s']=row.pop('median_compiler_s')
 result['native_artifact_checks_passed']=len(d['samples'])+len(d['compiler_warmups'])
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);a=p.parse_args()
 print(json.dumps(analyze(json.loads(a.evidence.read_text(encoding='utf-8-sig'))),indent=2,allow_nan=False))
if __name__=='__main__':main()
