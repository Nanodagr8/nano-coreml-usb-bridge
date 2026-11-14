"""Audit numeric application evidence and quantify conditional within-session uncertainty."""
from datetime import datetime
import argparse,json,math,random,statistics
from pathlib import Path
TARGETS=('windows_cpu','windows_gpu_candidate','iphone_usb_coreml')
def percentile(values,p):
 values=sorted(values);k=(len(values)-1)*p;i=int(k)
 return values[i]+(values[min(i+1,len(values)-1)]-values[i])*(k-i)
def bootstrap(values,seed=20261113,n=10000):
 rng=random.Random(seed)
 draws=[statistics.median([rng.choice(values) for _ in values]) for _ in range(n)]
 return [round(percentile(draws,.025),4),round(percentile(draws,.975),4)]
def analyze(d):
 if d['schema']!='nano-r3-application-evidence-v1':
  raise ValueError('UnexpectedEvidenceSchema')
 rows=d['samples']
 if not d['complete']:
  return {'complete':False,'stop_reason':d['stop_reason'],'measured_jobs':len(rows)}
 if [r['target'] for r in rows]!=d['registered_sequence'] or len(rows)!=25:
  raise ValueError('RegisteredSequenceMismatch')
 if len(d['compiler_warmups'])!=25 or len(d['ai_warmups'])!=36:
  raise ValueError('WarmupCountMismatch')
 if not all(w['passed_exact_answer'] for w in d['ai_warmups']):
  raise ValueError('WarmupQualityFailure')
 if not datetime.fromisoformat(d['registration_created_utc'].replace('Z','+00:00'))<datetime.fromisoformat(d['started_utc'])<datetime.fromisoformat(d['completed_utc']):
  raise ValueError('RegistrationTimingMismatch')
 ai_keys={'wall_s','completion_tokens','model_elapsed_ms','passed_exact_answer','task_label',
  'start_offset_from_launch_s','finish_offset_from_launch_s'}
 warm_keys={'wall_s','completion_tokens','model_elapsed_ms','passed_exact_answer','target','task_label'}
 def check_ai(a,keys):
  if set(a)!=keys: raise ValueError('UnexpectedAIField')
  if type(a['completion_tokens']) is not int or not 1<=a['completion_tokens']<=32:
   raise ValueError('InvalidTokenCount')
  if type(a['wall_s']) not in (int,float) or not math.isfinite(a['wall_s']) or a['wall_s']<=0:
   raise ValueError('InvalidAILatency')
  if a['passed_exact_answer'] is not True: raise ValueError('AIQualityFailure')
 for w in d['ai_warmups']: check_ai(w,warm_keys)
 expected_job={'schema','label','elapsed_s','exit_code','passed','timed_out','source_unchanged',
  'source_count','source_commit','compiler_output_bytes','phone_install','signing',
  'job_manifest_sha256','job_runner_sha256'}
 measured_requests=0;placements=0;warm_index=0
 for row in rows+d['compiler_warmups']:
  job=row['compiler_job']
  if not expected_job<=set(job) or set(job)-expected_job-{'logical_spec_sha256'}:
   raise ValueError('UnexpectedJobField')
  if row['stop_reason'] is not None or not job['passed'] or job['exit_code']!=0 or not job['source_unchanged'] or job['timed_out']:
   raise ValueError('CompilerValidationFailure')
  if job['source_count']!=10 or job['source_commit']!=d['source_commit'] or job['job_manifest_sha256']!=d['job_manifest_sha256']:
   raise ValueError('WorkloadIdentityMismatch')
  if ('logical_spec_sha256' in job and job['logical_spec_sha256']!=d['logical_spec_sha256']) or (d['session_id']=='session2' and 'logical_spec_sha256' not in job):
   raise ValueError('LogicalWorkloadMismatch')
  if not math.isfinite(job['elapsed_s']) or not 0<job['elapsed_s']<45:
   raise ValueError('JobDurationInvalid')
  if job['phone_install'] or job['signing']:
   raise ValueError('UnexpectedDeployment')
 for row in rows:
  ai=row['ai_requests']
  if row['target']=='baseline':
   if ai: raise ValueError('BaselineHasInference')
   continue
  if [a['task_label'] for a in ai]!=['arithmetic','format']:
   raise ValueError('TaskSequenceMismatch')
  warmed=d['ai_warmups'][warm_index:warm_index+2];warm_index+=2
  if [w['task_label'] for w in warmed]!=['arithmetic','format'] or any(w['target']!=row['target'] for w in warmed):
   raise ValueError('WarmupOrderMismatch')
  for a in ai:
   check_ai(a,ai_keys)
   if not a['passed_exact_answer'] or not 1<=a['completion_tokens']<=32:
    raise ValueError('MeasuredQualityFailure')
   if not 0<a['start_offset_from_launch_s']<a['finish_offset_from_launch_s']:
    raise ValueError('InvalidRequestOffsets')
   if a['finish_offset_from_launch_s']+.25>row['compiler_job']['elapsed_s']:
    raise ValueError('OverlapFailure')
   measured_requests+=1
  if row['target'].startswith('windows_'):
   for key in ('placement_before','placement_after'):
    c=row[key]
    expected='100% CPU' if row['target']=='windows_cpu' else '100% GPU'
    if not c['placement_check_passed'] or not c['digest_matches'] or c['ollama_processor']!=expected:
     raise ValueError('ReportedPlacementFailure')
    if (expected=='100% CPU' and c['size_vram_bytes']!=0) or (expected=='100% GPU' and c['size_vram_bytes']<=0):
     raise ValueError('PlacementMemoryMismatch')
    placements+=1
 reductions=[];normalized={t:[] for t in TARGETS}
 for i in range(6):
  block=rows[i*4:i*4+5]
  if block[0]['target']!='baseline' or block[-1]['target']!='baseline':
   raise ValueError('MissingBracketBaseline')
  ref=(block[0]['compiler_job']['elapsed_s']+block[-1]['compiler_job']['elapsed_s'])/2
  times={r['target']:r['compiler_job']['elapsed_s'] for r in block[1:-1]}
  reductions.append(100*(times['windows_cpu']-times['iphone_usb_coreml'])/times['windows_cpu'])
  for t in TARGETS: normalized[t].append(100*(times[t]/ref-1))
 summary=[]
 for t in ('baseline',)+TARGETS:
  selected=[r for r in rows if r['target']==t]
  ai=[a for r in selected for a in r['ai_requests']]
  summary.append({'target':t,'jobs':len(selected),
   'median_compiler_s':round(statistics.median(r['compiler_job']['elapsed_s'] for r in selected),6),
   'median_ai_s':round(statistics.median(a['wall_s'] for a in ai),6) if ai else None})
 baselines=[r['compiler_job']['elapsed_s'] for r in rows if r['target']=='baseline']
 return {'complete':True,'measured_jobs':25,'measured_ai_requests':measured_requests,
  'compiler_warmups':25,'ai_warmups':36,'placement_snapshots':placements,'summary':summary,
  'paired_reductions_percent':[round(v,4) for v in reductions],
  'primary_median_reduction_percent':round(statistics.median(reductions),4),
  'rounds_favoring_iphone':sum(v>0 for v in reductions),
  'conditional_bootstrap_95_percent':bootstrap(reductions),
  'uncertainty_notice':'Conditional paired-round resampling assumes exchangeable rounds; serial/carryover effects and between-session/system uncertainty are not covered.',
  'baseline_spread_percent':round(100*(max(baselines)-min(baselines))/statistics.median(baselines),4),
  'median_bracket_change_percent':{t:round(statistics.median(v),4) for t,v in normalized.items()}}
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('evidence',type=Path)
 a=parser.parse_args()
 print(json.dumps(analyze(json.loads(a.evidence.read_text(encoding='utf-8-sig'))),indent=2,allow_nan=False))
if __name__=='__main__': main()
