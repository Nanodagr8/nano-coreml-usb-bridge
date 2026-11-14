"""Recompute sampled continuity evidence; no uptime or wake-lock certification."""
from datetime import datetime
from pathlib import Path
import argparse,json,math,statistics
STATUS={'round','phase','wall_s','elapsed_s','pinned_authenticated_ready'}
SAMPLE={'round','task','elapsed_s','passed_exact_answer','completion_tokens','wall_s','model_elapsed_ms','generator_tokens_per_second','on_device_metrics_verified'}
IDLE={'round','requested_s','observed_s'}
CODES={'configuration_invalid','pin_rejected','authorization_rejected','connection_reset','connection_refused','transport_timeout',
 'tls_failed','protocol_rejected','model_identity_invalid','model_not_ready','telemetry_invalid','answer_invalid','tokens_invalid',
 'metrics_invalid','unexpected_error','study_budget_expired','worker_process_failed'}
def finite(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
def normalized_elapsed(raw):
 if 'observed_elapsed_s' in raw:return raw['observed_elapsed_s'],'worker_monotonic'
 if raw.get('stop',{}).get('phase')!='supervisor':raise ValueError('MissingFinalWorkerTiming')
 value=(datetime.fromisoformat(raw['finished_utc'])-datetime.fromisoformat(raw['started_utc'])).total_seconds()
 return value,'supervisor_utc'
def analyze(d):
 if d['schema']!='nano-r4-continuity-evidence-v1':raise ValueError('UnknownContinuitySchema')
 if d['target']!='iphone_usb_coreml' or d['model_id']!='qwen3.5-0.8b':raise ValueError('UnexpectedContinuityTarget')
 rounds,idle,budget={'pilot':(1,0,60),'soak':(6,120,900)}[d['stage']]
 if any(d[k] for k in ('runtime_build_attested','wakelock_runtime_verified','foreground_state_instrumented','energy_measured','ane_profiled','automatic_retries')):
  raise ValueError('UnsupportedRuntimeClaim')
 if d['externally_registered'] and not datetime.fromisoformat(d['registration_created_utc'].replace('Z','+00:00'))<datetime.fromisoformat(d['started_utc']):
  raise ValueError('ContinuityRegistrationTiming')
 if not d['protected_configuration_unchanged']:raise ValueError('PrivateConfigurationChanged')
 for s in d['statuses']:
  if set(s)!=STATUS or not s['pinned_authenticated_ready'] or not finite(s['wall_s']) or not finite(s['elapsed_s']):
   raise ValueError('InvalidReadyObservation')
 for s in d['samples']:
  if set(s)!=SAMPLE or not s['passed_exact_answer'] or not s['on_device_metrics_verified'] or type(s['completion_tokens']) is not int or not 1<=s['completion_tokens']<=32:
   raise ValueError('InvalidGenerationObservation')
  if not all(finite(s[k]) for k in ('wall_s','elapsed_s','model_elapsed_ms','generator_tokens_per_second')) or s['model_elapsed_ms']<=0 or s['generator_tokens_per_second']<=0:
   raise ValueError('InvalidContinuityMetrics')
 if len(d['samples'])>2*rounds or len(d['statuses'])>2*rounds+1:raise ValueError('ContinuityCountOverflow')
 for i,s in enumerate(d['samples']):
  if s['round']!=i//2+1 or s['task']!=('arithmetic','format')[i%2]:raise ValueError('ContinuityTaskSequence')
 for i,s in enumerate(d['idle_intervals']):
  if set(s)!=IDLE or s['round']!=i+1 or s['requested_s']!=idle or not finite(s['observed_s']) or s['observed_s']+1e-6<idle:
   raise ValueError('InvalidIdleObservation')
 if not finite(d['observed_elapsed_s']) or sum(s['observed_s'] for s in d['idle_intervals'])>d['observed_elapsed_s']+.01:raise ValueError('InconsistentIdleBudget')
 if d['complete']:
  if d['stop'] is not None or len(d['samples'])!=2*rounds or len(d['statuses'])!=2*rounds+1 or len(d['idle_intervals'])!=rounds:
   raise ValueError('IncompleteContinuityCounts')
  expected=[(r,p) for r in range(1,rounds+1) for p in ('before_round','after_round')]+[(rounds,'final_status')]
  if [(s['round'],s['phase']) for s in d['statuses']]!=expected:raise ValueError('ContinuityStatusSequence')
  if d['status_attempts']!=2*rounds+1 or d['generation_attempts']!=2*rounds:raise ValueError('UnrecordedContinuityAttempts')
  if not finite(d['observed_elapsed_s']) or not idle*rounds<=d['observed_elapsed_s']<budget:raise ValueError('ContinuityBudgetViolation')
 elif not d['stop'] or set(d['stop'])!={'code','phase','round','task'} or d['stop']['code'] not in CODES or d['stop']['phase'] not in {'configuration','before_round','generation','after_round','idle','final_status','supervisor'} or d['stop']['task'] not in (None,'arithmetic','format'):
  raise ValueError('UnsanitizedContinuityStop')
 return {'observation_complete':d['complete'],'ready_checks_passed':len(d['statuses']),'correct_answers':len(d['samples']),
  'idle_intervals_completed':len(d['idle_intervals']),'observed_elapsed_s':d['observed_elapsed_s'],
  'idle_seconds_observed':round(sum(s['observed_s'] for s in d['idle_intervals']),6),
  'median_generation_wall_s':round(statistics.median(s['wall_s'] for s in d['samples']),6) if d['samples'] else None,
  'stop':d['stop'],'notice':'Sampled continuity only; not continuous uptime, an availability probability, build attribution or wake-lock certification.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);a=p.parse_args()
 print(json.dumps(analyze(json.loads(a.evidence.read_text(encoding='utf-8-sig'))),indent=2))
if __name__=='__main__':main()
