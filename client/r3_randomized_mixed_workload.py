"""R3 registered randomized-order mixed-task replication."""
from pathlib import Path
import argparse, hashlib, json, os, statistics, subprocess, sys, time
from datetime import datetime, timezone
import r3_system_workload as r3
from nano_usb_client import NanoUSBClient
PLAN_PATH=Path(__file__).resolve().parents[1]/'results/r3_randomized_protocol_20261113.json'
PLAN_BYTES=PLAN_PATH.read_bytes()
if hashlib.sha256(PLAN_BYTES).hexdigest()!='2212fcadb78d8e2631026ff40bd75a1354fb95d30f75b9054fa7192398b19b3a':
    raise RuntimeError('RegisteredProtocolChanged')
PROTOCOL=json.loads(PLAN_BYTES)



def validate_placement(api, cli, target):
    models=[m for m in api.get('models',[]) if m.get('name')==r3.MODEL]
    if len(models)!=1:
        raise ValueError('ExpectedLoadedModelMissing')
    m=models[0]
    if m.get('digest')!=r3.MODEL_DIGEST:
        raise ValueError('LoadedModelDigestMismatch')
    size=m.get('size')
    vram=m.get('size_vram')
    if type(size) is not int or size<=0 or type(vram) is not int or vram<0:
        raise ValueError('InvalidPlacementMetrics')
    lines=[line for line in cli.splitlines() if line.split() and line.split()[0]==r3.MODEL]
    expected='100% CPU' if target=='windows_cpu' else '100% GPU'
    if target not in ('windows_cpu','windows_gpu_candidate'):
        raise ValueError('UnexpectedPlacementTarget')
    if len(lines)!=1 or expected not in lines[0]:
        raise ValueError('ProcessorColumnMismatch')
    if (target=='windows_cpu' and vram!=0) or (target=='windows_gpu_candidate' and vram<=0):
        raise ValueError('PlacementMemoryMismatch')
    return {'expected_condition':target,'ollama_processor':expected,'size_bytes':size,
        'size_vram_bytes':vram,'digest_matches':True,'placement_check_passed':True}

def read_placement(target):
    from urllib.request import Request,ProxyHandler,build_opener
    with build_opener(ProxyHandler({})).open(Request('http://127.0.0.1:11434/api/ps'),timeout=5) as response:
        api=json.loads(response.read(262144))
    cli=subprocess.run(['ollama','ps'],capture_output=True,text=True,timeout=5,check=True).stdout
    return validate_placement(api,cli,target)


def mixed_labels(requests):
    if requests!=4:
        raise ValueError('MixedSuiteRequiresFourRequests')
    return ('arithmetic','format','arithmetic','format')

def balanced_plan(targets,runs):
    import itertools
    r3.plan(targets,runs,5,4)
    other=[t for t in targets if t!='baseline']
    if 'baseline' not in targets or not other:
        raise ValueError('BracketedAIConditionsRequired')
    orders=list(itertools.permutations(other))
    if other==PROTOCOL['ai_targets']:
        registered=[tuple(x) for x in PROTOCOL['condition_orders']]
        if len(registered)!=6 or set(registered)!=set(orders):
            raise ValueError('InvalidRegisteredOrders')
        orders=registered
    if runs not in (1,len(orders)):
        raise ValueError('UseOnePilotOrAllPermutations')
    sequence=['baseline']
    for order in orders[:runs]:
        sequence.extend(order)
        sequence.append('baseline')
    if len(sequence)>25:
        raise ValueError('AtMost25Windows')
    return sequence

def synchronized_worker(index,seconds,event,start_ns,queue):
    try:
        payload=(b'NANO-R3-fixed-host-workload-'*(r3.WORK_UNIT_BYTES//28+1))[:r3.WORK_UNIT_BYTES]
        queue.put(('ready',index))
        if not event.wait(12):
            raise RuntimeError('StartBarrierTimeout')
        scheduled=start_ns.value/1e9
        remaining=scheduled-time.perf_counter()
        if remaining>0:
            time.sleep(remaining)
        begin=time.perf_counter()
        units=0
        while time.perf_counter()-begin<seconds:
            hashlib.sha256(payload).digest()
            units+=1
        finish=time.perf_counter()
        queue.put(('result',index,{'units':units,'seconds':finish-begin,
            'start_offset_s':begin-scheduled,'end_offset_s':finish-scheduled,
            'bytes_per_unit':len(payload)}))
    except Exception as exc:
        queue.put(('error',index,type(exc).__name__))

def burst_window(target,seconds,workers,requests,client=None):
    import multiprocessing
    if workers!=4 or not .5<=seconds<=5 or not 1<=requests<=4:
        raise ValueError('InvalidSynchronizedBounds')
    context=multiprocessing.get_context('spawn')
    event=context.Event()
    start_ns=context.Value('q',0,lock=False)
    queue=context.Queue()
    children=[]
    answers=[]
    stop=None
    metrics=[]
    began=time.perf_counter()
    try:
        for index in range(workers):
            child=context.Process(target=synchronized_worker,args=(index,seconds,event,start_ns,queue))
            child.start()
            children.append(child)
        ready=set()
        deadline=time.perf_counter()+10
        while len(ready)<workers:
            message=queue.get(timeout=max(.01,deadline-time.perf_counter()))
            if message[0]!='ready' or message[1] in ready:
                raise RuntimeError('WorkerReadinessFailure')
            ready.add(message[1])
        start_ns.value=time.perf_counter_ns()+200_000_000
        scheduled=start_ns.value/1e9
        event.set()
        time.sleep(max(0,scheduled+.3-time.perf_counter()))
        if target!='baseline':
            for task_label in mixed_labels(requests):
                if time.perf_counter()-scheduled>seconds-1.25:
                    stop='insufficient_window_remaining'
                    break
                before=time.perf_counter()-scheduled
                answer=r3.infer(target,task_label,client)
                after=time.perf_counter()-scheduled
                answers.append(dict(answer,task_label=task_label,start_offset_s=round(before,5),finish_offset_s=round(after,5)))
                if not answer['passed_exact_answer']:
                    stop='task_quality_failure'
                    break
                if after>seconds:
                    stop='request_exceeded_work_window'
                    break
        deadline=time.perf_counter()+seconds+8
        indexes=set()
        while len(metrics)<workers:
            message=queue.get(timeout=max(.01,deadline-time.perf_counter()))
            if message[0]!='result' or message[1] in indexes:
                raise RuntimeError('WorkerResultFailure')
            indexes.add(message[1])
            m=message[2]
            if m['units']<=0 or m['bytes_per_unit']!=r3.WORK_UNIT_BYTES:
                raise ValueError('InvalidWorkerMetrics')
            metrics.append(m)
        for child in children:
            child.join(timeout=2)
            if child.exitcode!=0:
                raise RuntimeError('WorkerExitFailure')
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
            child.join(timeout=2)
        queue.close()
    latest_start=max(m['start_offset_s'] for m in metrics)
    earliest_end=min(m['end_offset_s'] for m in metrics)
    if latest_start>.05:
        stop=stop or 'worker_start_skew_exceeded'
    overlap=all(a['start_offset_s']>=latest_start and a['finish_offset_s']<=earliest_end for a in answers)
    if not overlap:
        stop=stop or 'ai_outside_common_worker_interval'
    rate=sum(m['units'] for m in metrics)*r3.WORK_UNIT_BYTES/1048576/statistics.mean(m['seconds'] for m in metrics)
    return {'target':target,'host_hash_mib_s':round(rate,3),'workers':workers,'seconds':seconds,
        'requested_ai_count':requests if target!='baseline' else 0,'ai_requests':answers,
        'worker_intervals':[{'start_offset_s':round(m['start_offset_s'],6),'end_offset_s':round(m['end_offset_s'],6)} for m in metrics],
        'worker_start_spread_s':round(latest_start-min(m['start_offset_s'] for m in metrics),6),
        'all_ai_within_common_worker_interval':overlap,'stop_reason':stop,'wall_s':round(time.perf_counter()-began,5)}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--targets',default='baseline,windows_cpu,windows_gpu_candidate')
    parser.add_argument('--runs',type=int,default=1)
    parser.add_argument('--requests',type=int,default=4)
    parser.add_argument('--report',type=Path)
    a=parser.parse_args(argv)
    if a.requests!=4:
        parser.error('Mixed suite requires four requests')
    targets=a.targets.split(',')
    order=balanced_plan(targets,a.runs)
    if len(order)>25:
        parser.error('At most 25 windows')
    if not a.execute:
        print(json.dumps({'mode':'DRY_RUN','order':order,'requests_per_ai_window':a.requests,
            'max_measured_ai_requests':sum(t!='baseline' for t in order)*a.requests,
            'window_s':5,'workers':4}))
        return 0
    if targets!=PROTOCOL['targets']:
        parser.error('Registered execution requires explicit baseline and all three AI targets')
    private=r3.PRIVATE.resolve()
    repo=Path(__file__).resolve().parents[1]
    if private==repo or repo in private.parents:
        parser.error('Report directory must be outside the repository')
    if a.report is None or a.report.resolve().parent!=private or a.report.exists():
        parser.error('New report in private directory required')
    if any(t.startswith('windows_') for t in targets):
        r3.model_integrity()
    client=None
    if 'iphone_usb_coreml' in targets:
        client=NanoUSBClient('https://127.0.0.1:49443',os.getenv('NANO_USB_TLS_PIN',''),os.getenv('NANO_USB_BEARER',''))
        if client.status().get('status')!='ready':
            raise RuntimeError('PhoneNotReady')
    rows=[]
    warmups=[]
    stop=None
    for i,target in enumerate(order):
        try:
            if target!='baseline':
                for label in ('arithmetic','format'):
                    warmed=r3.infer(target,label,client)
                    warmups.append(dict(warmed,target=target,task_label=label,window_sequence=i))
                    if not warmed['passed_exact_answer']:
                        stop='warmup_quality_failure_'+label
                        break
                if stop:
                    break
            before=read_placement(target) if target.startswith('windows_') else None
            row=burst_window(target,5,4,a.requests,client)
            row['placement_before']=before
            row['placement_after']=read_placement(target) if target.startswith('windows_') else None
            row['sequence']=i
            rows.append(row)
            stop=row['stop_reason']
            print('R3_BURST_WINDOW_'+str(i+1)+'='+('PASS' if not stop else 'STOP'),flush=True)
            if stop:
                break
        except Exception as e:
            stop=type(e).__name__
            break
    report={'schema':'nano-r3-randomized-mixed-burst-v5','timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'complete':len(rows)==len(order) and stop is None,'stop_reason':stop,
        'order':order,'requests_per_ai_window':a.requests,'samples':rows,'warmups':warmups,
        'fixed_task':'mixed_arithmetic_format','order_design':'preregistered_randomized_permutation_round_order','protocol_sha256':hashlib.sha256(PLAN_BYTES).hexdigest(),'public_order_seed':PROTOCOL['public_order_seed'],'synchronized_workers':True,'warmup_per_ai_window':2,'energy_measured':False,
        'ane_execution_verified':False,'quantization_equivalence_verified':False,
        'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'placement_evidence':'ollama_ps_and_loaded_model_api_before_after_each_windows_window',
        'r3_source_sha256':hashlib.sha256(Path(r3.__file__).read_bytes()).hexdigest()}
    private.mkdir(parents=True,exist_ok=True)
    with a.report.open('x',encoding='utf-8') as output:
        output.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('R3_BURST_COMPLETE='+str(report['complete']),flush=True)
    return 0 if report['complete'] else 2

if __name__=='__main__':
    raise SystemExit(main())
