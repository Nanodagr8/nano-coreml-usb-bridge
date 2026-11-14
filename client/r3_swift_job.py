"""Fixed-work Swift job with hash validation, private logs and an owned watchdog."""
from pathlib import Path
import argparse,hashlib,json,os,signal,subprocess,threading,time

def main(argv=None):
 parser=argparse.ArgumentParser()
 parser.add_argument('label')
 parser.add_argument('--job-manifest',type=Path,required=True)
 parser.add_argument('--expected-sha',required=True)
 parser.add_argument('--phase-root',type=Path,required=True)
 parser.add_argument('--phase-dir',type=Path,required=True)
 a=parser.parse_args(argv)
 root=a.job_manifest.resolve().parent
 assert a.label.replace('_','').isalnum() and len(a.label)<64
 allowed=a.phase_root.resolve()
 phase_dir=a.phase_dir.resolve()
 assert allowed in phase_dir.parents and phase_dir.is_dir()
 result_path=root/(a.label+'.json')
 log=root/(a.label+'.log')
 phase=phase_dir/(a.label+'.started.json')
 assert not result_path.exists() and not log.exists() and not phase.exists()
 manifest_bytes=a.job_manifest.resolve().read_bytes()
 manifest_sha=hashlib.sha256(manifest_bytes).hexdigest()
 assert len(a.expected_sha)==64 and manifest_sha==a.expected_sha
 manifest=json.loads(manifest_bytes)
 from r3_swift_prepare import load_spec,validate_identity
 spec=load_spec()
 logical_sha=validate_identity(manifest,spec)
 version=subprocess.run([manifest['argv'][0],'--version'],capture_output=True,text=True,check=True,timeout=5).stdout
 assert 'Swift version '+spec['compiler_version'] in version
 assert root==Path(manifest['stage']).resolve()
 assert Path(manifest['argv'][0]).name=='swiftc' and '-typecheck' in manifest['argv']
 assert manifest['deadline_seconds']<=45
 for name,digest in manifest['source_files_sha256'].items():
  assert hashlib.sha256((root/'Sources'/name).read_bytes()).hexdigest()==digest
 env={k:v for k,v in os.environ.items() if not k.startswith('NANO_USB_')}
 timed_out=threading.Event()
 def terminate_owned_group(child):
  if child.poll() is None:
   timed_out.set()
   try: os.killpg(child.pid,signal.SIGKILL)
   except ProcessLookupError: pass
 with log.open('x') as output:
  start=time.perf_counter()
  child=subprocess.Popen(manifest['argv'],cwd=root,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
  watchdog=threading.Timer(manifest['deadline_seconds'],terminate_owned_group,args=(child,))
  watchdog.start()
  try:
   phase.write_text(json.dumps({'phase':'compiler_started','label':a.label,'job_manifest_sha256':manifest_sha})+'\n')
   rc=child.wait()
  finally:
   watchdog.cancel()
   if child.poll() is None:
    terminate_owned_group(child)
    child.wait()
  elapsed=time.perf_counter()-start
 source_unchanged=all(hashlib.sha256((root/'Sources'/name).read_bytes()).hexdigest()==digest for name,digest in manifest['source_files_sha256'].items())
 result={'schema':'nano-r3-swift-validation-result-v2','label':a.label,'elapsed_s':round(elapsed,6),
  'exit_code':rc,'passed':rc==0 and source_unchanged and not timed_out.is_set(),'timed_out':timed_out.is_set(),
  'source_unchanged':source_unchanged,'source_count':10,'source_commit':manifest['source_commit'],
  'compiler_output_bytes':log.stat().st_size,'phone_install':False,'signing':False,
  'logical_spec_sha256':logical_sha,'job_manifest_sha256':manifest_sha,'job_runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 result_path.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result),flush=True)
 return 0 if result['passed'] else 2

if __name__=='__main__':
 raise SystemExit(main())
