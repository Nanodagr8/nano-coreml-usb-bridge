"""Bounded R3 equal-count bursts with Ollama-reported placement checks."""
from pathlib import Path
import argparse, hashlib, json, os, statistics, subprocess, sys, time
from datetime import datetime, timezone
import r3_system_workload as r3
from nano_usb_client import NanoUSBClient


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

def burst_window(target, seconds, workers, requests, client=None):
    children=[]
    start=time.perf_counter()
    answers=[]
    stop=None
    try:
        for _ in range(workers):
            children.append(subprocess.Popen([sys.executable,r3.__file__,'--worker',str(seconds)],
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True))
        time.sleep(0.3)
        if target!='baseline':
            for i in range(requests):
                if time.perf_counter()-start>seconds-1.25:
                    stop='insufficient_window_remaining'
                    break
                before=time.perf_counter()-start
                a=r3.infer(target,'arithmetic',client)
                after=time.perf_counter()-start
                answers.append(dict(a,start_offset_s=round(before,5),finish_offset_s=round(after,5)))
                if not a['passed_exact_answer']:
                    stop='task_quality_failure'
                    break
                if after>seconds:
                    stop='request_exceeded_work_window'
                    break
        metrics=[]
        for child in children:
            output,_=child.communicate(timeout=seconds+12)
            if child.returncode!=0:
                raise RuntimeError('HostWorkerFailure')
            m=json.loads(output)
            if m['units']<=0 or m['bytes_per_unit']!=r3.WORK_UNIT_BYTES:
                raise ValueError('InvalidWorkerMetrics')
            metrics.append(m)
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.communicate()
    rate=sum(m['units'] for m in metrics)*r3.WORK_UNIT_BYTES/1048576/statistics.mean(m['seconds'] for m in metrics)
    return {'target':target,'host_hash_mib_s':round(rate,3),
        'workers':workers,'seconds':seconds,'requested_ai_count':requests if target!='baseline' else 0,
        'ai_requests':answers,'stop_reason':stop,'wall_s':round(time.perf_counter()-start,5)}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--targets',default='baseline,windows_cpu,windows_gpu_candidate')
    parser.add_argument('--runs',type=int,default=1)
    parser.add_argument('--requests',type=int,default=4)
    parser.add_argument('--report',type=Path)
    a=parser.parse_args(argv)
    if not 1<=a.requests<=4:
        parser.error('Requests must be 1..4')
    targets=a.targets.split(',')
    order=r3.plan(targets,a.runs,5,4)
    if len(order)>25:
        parser.error('At most 25 windows')
    if not a.execute:
        print(json.dumps({'mode':'DRY_RUN','order':order,'requests_per_ai_window':a.requests,
            'max_measured_ai_requests':sum(t!='baseline' for t in order)*a.requests,
            'window_s':5,'workers':4}))
        return 0
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
    stop=None
    for i,target in enumerate(order):
        try:
            if target!='baseline':
                if not r3.infer(target,'arithmetic',client)['passed_exact_answer']:
                    stop='warmup_quality_failure'
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
    report={'schema':'nano-r3-placement-burst-v2','timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'complete':len(rows)==len(order) and stop is None,'stop_reason':stop,
        'order':order,'requests_per_ai_window':a.requests,'samples':rows,
        'fixed_task':'arithmetic','warmup_per_ai_window':1,'energy_measured':False,
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
