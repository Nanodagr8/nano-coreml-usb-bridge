"""Bounded warm-cache application recompile/link worker; no install or signing."""
from pathlib import Path
import argparse,hashlib,json,os,signal,subprocess,sys,threading,time,shlex
import r3_native_build as native
from r3_swift_prepare import load_spec,canonical_sha
REPO=Path(__file__).resolve().parents[1]
SPEC=REPO/'results/r3_native_concurrent_source_spec_20261113.json'
def dependency_identity(root):
 target=Path(root)/'.build/arm64-apple-ios/debug'
 records={}
 for f in sorted(target.rglob('*')):
  if not f.is_file():continue
  relative=f.relative_to(target)
  if relative.parts[0].startswith('NanoANEBridge'):continue
  if relative.parts[0]=='Modules' and f.name.startswith('NanoANEBridge'):continue
  if f.suffix in ('.o','.a','.swiftmodule','.swiftdoc','.swiftsourceinfo'):
   records[relative.as_posix()]=native.sha(f)
 return canonical_sha(records),len(records)
def normalized_argv(args,root,c):
 return [a.replace(Path(root).as_posix(),'{workspace}').replace(c['swift_bin'],'{swift_bin}').replace(c['swift_sdks'],'{swift_sdks}') for a in args]
def fresh_artifacts(root,began_ns):
 target=Path(root)/'.build/arm64-apple-ios/debug'
 objects=list((target/'NanoANEBridge.build').glob('*.swift.o'))
 binary=target/'NanoANEBridge-App'
 lists=list((target/'NanoANEBridge-App.product').glob('Objects.LinkFileList'))
 entries=shlex.split(lists[0].read_text()) if len(lists)==1 else []
 expected={str(f) for f in objects}
 linked=len(objects)==10 and expected<=set(entries) and all(s in expected for s in entries if '/NanoANEBridge.build/' in s)
 return {'fresh_application_objects':sum(f.stat().st_mtime_ns>=began_ns for f in objects),
  'fresh_linked_binary':binary.exists() and binary.stat().st_mtime_ns>=began_ns,
  'new_application_objects_linked':linked,'binary_sha256':native.sha(binary) if binary.exists() else None,
  'binary_bytes':binary.stat().st_size if binary.exists() else None,
  'macho':native.macho_info(binary.read_bytes()) if binary.exists() else None}
def reset_app_outputs(root,saved):
 root=Path(root);target=root/'.build/arm64-apple-ios/debug'
 paths=[target/'NanoANEBridge-App']
 for name in ('NanoANEBridge.build','NanoANEBridge-App.build'):
  paths+=sorted((target/name).rglob('*.o'))
 paths+=list((target/'Modules').glob('NanoANEBridge.*'))+list((target/'Modules').glob('NanoANEBridge_App.*'))
 for i,path in enumerate(paths):
  if path.exists():native.within(path,root);path.rename(Path(saved)/(str(i)+'-'+path.name))
def assess(r):
 if r['exit_code']!=0 or r['timed_out']:return 'native_build_failed'
 if not r['source_unchanged'] or not r['dependency_inputs_unchanged']:return 'input_changed'
 if r['fresh_application_objects']!=10 or not r['fresh_linked_binary'] or not r['new_application_objects_linked']:return 'stale_artifact'
 if not r['live_native_frontend_observed']:return 'native_frontend_not_witnessed'
 if not r['network_namespace_isolated'] or not r['input_mounts_readonly']:return 'isolation_missing'
 info=r['macho']
 if not info or info['architecture']!='arm64' or info['file_type']!='MH_EXECUTE' or info['code_signature_present'] or info['platform']!=2 or info['minimum_os']!=18<<16 or info['sdk']!=(27<<16|1<<8):return 'invalid_unsigned_ios_artifact'
 return None
def main(argv=None):
 p=argparse.ArgumentParser()
 p.add_argument('label');p.add_argument('--job-manifest',type=Path,required=True);p.add_argument('--expected-sha',required=True)
 p.add_argument('--phase-root',type=Path,required=True);p.add_argument('--phase-dir',type=Path,required=True)
 a=p.parse_args(argv)
 if sys.platform!='linux' or os.geteuid()!=0:raise ValueError('ExistingLinuxPrivilegesRequired')
 if not a.label.replace('_','').isalnum() or len(a.label)>64:raise ValueError('InvalidLabel')
 raw=a.job_manifest.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=a.expected_sha:raise ValueError('ManifestChanged')
 m=json.loads(raw);root=a.job_manifest.resolve().parent
 if str(root)!=m['stage']:raise ValueError('WorkspaceMismatch')
 spec=json.loads(SPEC.read_text());source=load_spec()
 if m['native_spec_sha256']!=canonical_sha(spec) or m['source_spec_sha256']!=canonical_sha(source):raise ValueError('LogicalSpecChanged')
 if m['supporting_runner_sha256']!=native.sha(Path(native.__file__)):raise ValueError('SupportingRunnerChanged')
 c=m['child_config']
 if normalized_argv(c['build_argv'],root,c)!=spec['build_argv_template']:raise ValueError('NativeArgumentsChanged')
 if dependency_identity(root)!=(m['dependency_inputs_sha256'],m['dependency_input_count']):raise ValueError('DependencyInputsChanged')
 source_ok=lambda:all(native.sha(root/'Sources/NanoANEBridge'/n)==h for n,h in source['source_files_sha256'].items())
 if not source_ok():raise ValueError('SourceChanged')
 phase_dir=native.within(a.phase_dir,a.phase_root);phase=phase_dir/(a.label+'.started.json')
 if not phase_dir.is_dir() or phase.exists():raise ValueError('NewPhaseRequired')
 jobs=root/'ConcurrentJobs';jobs.mkdir(exist_ok=True);job=jobs/a.label
 job.mkdir();saved=job/'PreviousArtifacts';saved.mkdir()
 target=root/'.build/arm64-apple-ios/debug'
 reset_app_outputs(root,saved)
 c=dict(c,parent_netns=os.readlink('/proc/self/ns/net'))
 config=job/'child-private.json';config.write_text(json.dumps(c))
 observed=threading.Event();finished=threading.Event();observed_offset=[None]
 began_ns=time.time_ns();began=time.perf_counter()
 def witness():
  needle=str(root/'Sources/NanoANEBridge').encode()
  while not finished.is_set():
   for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
     if (proc/'comm').read_text().strip()=='swift-frontend' and needle in (proc/'cmdline').read_bytes():
      observed_offset[0]=round(time.perf_counter()-began,6)
      data={'phase':'compiler_started','job_manifest_sha256':a.expected_sha,'live_native_frontend_observed':True}
      temp=phase.with_suffix('.tmp');temp.write_text(json.dumps(data));temp.replace(phase)
      observed.set();return
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
   finished.wait(.01)
 timed_out=False
 with (job/'build.private.log').open('x') as log:
  process=subprocess.Popen(['unshare','--mount','--net','--',sys.executable,str(Path(native.__file__).resolve()),
   '--network-child',str(config)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
   env={k:v for k,v in os.environ.items() if not k.startswith('NANO_USB_')})
  watcher=threading.Thread(target=witness,daemon=True);watcher.start()
  try:rc=process.wait(timeout=45)
  except subprocess.TimeoutExpired:
   timed_out=True;os.killpg(process.pid,signal.SIGKILL);rc=process.wait()
  finally:finished.set();watcher.join(timeout=2)
 elapsed=time.perf_counter()-began
 isolation=root/'isolation.json'
 proof=json.loads(isolation.read_text()) if isolation.exists() and isolation.stat().st_mtime_ns>=began_ns else {}
 r={'schema':'nano-r3-native-job-v1','label':a.label,'elapsed_s':round(elapsed,6),'exit_code':rc,'timed_out':timed_out,
  'source_unchanged':source_ok(),'source_count':10,'source_commit':source['source_commit'],
  'logical_spec_sha256':canonical_sha(source),'native_spec_sha256':canonical_sha(spec),
  'dependency_inputs_unchanged':dependency_identity(root)==(m['dependency_inputs_sha256'],m['dependency_input_count']),
  'dependency_inputs_sha256':m['dependency_inputs_sha256'],'dependency_input_count':m['dependency_input_count'],
  'live_native_frontend_observed':observed.is_set(),'native_frontend_observed_offset_s':observed_offset[0],
  'network_namespace_isolated':proof.get('network_namespace_isolated',False),'input_mounts_readonly':proof.get('input_mounts_readonly',False),
  'phone_install':False,'signing':False,'compiler_output_bytes':(job/'build.private.log').stat().st_size,'job_manifest_sha256':a.expected_sha,'job_runner_sha256':native.sha(__file__),
  'supporting_runner_sha256':native.sha(Path(native.__file__)),**fresh_artifacts(root,began_ns)}
 r['stop_reason']=assess(r);r['passed']=r['stop_reason'] is None
 (job/'result.json').write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps(r),flush=True)
 return 0 if r['passed'] else 2
if __name__=='__main__':raise SystemExit(main())
