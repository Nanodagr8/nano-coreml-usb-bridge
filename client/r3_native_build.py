"""Offline, unsigned application rebuild qualification; dry plan by default."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,signal,socket,struct,subprocess,sys,time
from datetime import datetime,timezone
from r3_swift_prepare import load_spec,canonical_sha
REPO=Path(__file__).resolve().parents[1]
TIMEOUT=180
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
 return h.hexdigest()
def tree_identity(root):
 root=Path(root);records=[]
 for f in sorted(root.rglob('*')):
  if f.is_symlink(): value='link:'+os.readlink(f)
  elif f.is_file(): value=sha(f)
  else: continue
  records.append((f.relative_to(root).as_posix(),value))
 return canonical_sha(records),len(records)
def within(path,root):
 path=Path(path).resolve();root=Path(root).resolve()
 if root not in path.parents: raise ValueError('PathEscapesOwnedWorkspace')
 return path
def macho_info(data):
 if len(data)<32: raise ValueError('TruncatedMachO')
 magic,cpu,subtype,kind,ncmds,size,flags,reserved=struct.unpack_from('<8I',data)
 if magic!=0xfeedfacf or cpu!=0x100000c or kind!=2:
  raise ValueError('ExpectedARM64Executable')
 if 32+size>len(data): raise ValueError('TruncatedLoadCommands')
 offset=32;signature=False;platform=None;minimum=None;sdk=None
 for _ in range(ncmds):
  if offset+8>32+size: raise ValueError('InvalidLoadCommand')
  cmd,length=struct.unpack_from('<2I',data,offset)
  if length<8 or offset+length>32+size: raise ValueError('InvalidLoadCommand')
  if cmd==0x1d: signature=True
  if cmd==0x32:
   if length<24: raise ValueError('InvalidBuildVersion')
   platform,minimum,sdk=struct.unpack_from('<3I',data,offset+8)
  offset+=length
 if offset!=32+size: raise ValueError('LoadCommandSizeMismatch')
 return {'architecture':'arm64','file_type':'MH_EXECUTE','code_signature_present':signature,
  'platform':platform,'minimum_os':minimum,'sdk':sdk}
def assess(result):
 if result['return_code']!=0 or result['timed_out']: raise ValueError('BuildFailed')
 if not result['source_unchanged'] or not result['cached_inputs_unchanged']: raise ValueError('InputChanged')
 if result['fresh_application_objects']!=10 or not result['fresh_linked_binary']: raise ValueError('StaleBuildOutput')
 if result['source_count']!=10 or result['logical_spec_sha256']!=canonical_sha(load_spec()): raise ValueError('SourceIdentityMismatch')
 if not result['network_namespace_isolated'] or not result['input_mounts_readonly']: raise ValueError('IsolationMissing')
 if result['compiler_sdk_basename']!='iPhoneOS27.1.sdk' or result['compiler_sdk_version']!='27.1' or not result['compiler_sdk_arguments_consistent']:
  raise ValueError('CompilerSDKMismatch')
 info=result['macho']
 if info['architecture']!='arm64' or info['file_type']!='MH_EXECUTE' or info['code_signature_present'] or info['platform']!=2 or info['minimum_os']!=18<<16 or info['sdk']!=(27<<16|1<<8):
  raise ValueError('UnsignedIOSExecutableRequired')
 return True
def child(config_path):
 c=json.loads(Path(config_path).read_text());root=Path(c['workspace'])
 subprocess.run(['mount','--make-rprivate','/'],check=True)
 for path in c['readonly_roots']:
  subprocess.run(['mount','--bind',path,path],check=True)
  subprocess.run(['mount','-o','remount,bind,ro',path],check=True)
 isolated=os.readlink('/proc/self/ns/net')!=c['parent_netns']
 interfaces=[name for index,name in socket.if_nameindex()]
 if not isolated or interfaces!=['lo']: raise ValueError('NetworkIsolationUnavailable')
 (root/'isolation.json').write_text(json.dumps({'network_namespace_isolated':True,'interfaces':interfaces,'input_mounts_readonly':True}))
 env={'HOME':str(root/'Home'),'PATH':c['swift_bin']+':/usr/bin:/bin',
  'GIT_TERMINAL_PROMPT':'0','SWIFTPM_DISABLE_AUTOMATIC_RESOLUTION':'1','LANG':'C.UTF-8'}
 args=['setpriv','--reuid='+str(c['uid']),'--regid='+str(c['gid']),'--clear-groups','--',
  'env',*[k+'='+v for k,v in env.items()],*c['build_argv']]
 os.execv('/usr/bin/setpriv',args)
def execute(c):
 if sys.platform!='linux' or os.geteuid()!=0: raise ValueError('ExistingLinuxNamespacePrivilegesRequired')
 expected={'workspace','cached_project','swift_bin','swift_sdks','uid','gid'}
 if set(c)!=expected: raise ValueError('UnexpectedPrivateConfig')
 root=Path(c['workspace']).resolve();original=Path(c['cached_project']).resolve()
 if root.exists() or root==REPO or REPO in root.parents or root==original or original in root.parents:
  raise ValueError('NewPrivateWorkspaceRequired')
 if not all(Path(c[k]).is_absolute() and Path(c[k]).is_dir() for k in ('cached_project','swift_bin','swift_sdks')):
  raise ValueError('ExistingAbsoluteToolchainPathsRequired')
 spec=load_spec();source=original/'Sources/NanoANEBridge'
 if sorted(f.name for f in source.iterdir() if f.is_file())!=sorted(spec['source_files_sha256']): raise ValueError('UnexpectedApplicationSource')
 if (original/'Package.swift').read_text()!=(REPO/'ios/Package.swift').read_text(): raise ValueError('PackageDefinitionMismatch')
 for name,digest in spec['source_files_sha256'].items():
  if sha(source/name)!=digest: raise ValueError('FrozenSourceMismatch')
 if sha(original/'Package.resolved')!=spec['dependency_lock_sha256']: raise ValueError('DependencyLockMismatch')
 version=subprocess.run([str(Path(c['swift_bin'])/'swiftc'),'--version'],check=True,capture_output=True,text=True,timeout=5).stdout
 if 'Swift version '+spec['compiler_version'] not in version: raise ValueError('CompilerVersionMismatch')
 identity,count=tree_identity(original)
 if shutil.disk_usage(root.parent).free<2*1024**3: raise ValueError('TwoGiBFreeSpaceRequired')
 root.mkdir(mode=0o700);(root/'Home').mkdir();(root/'Sources').mkdir()
 shutil.copytree(source,root/'Sources/NanoANEBridge',symlinks=False)
 for name in ('Package.swift','Package.resolved'): shutil.copyfile(original/name,root/name)
 subprocess.run(['cp','-a','--reflink=auto',str(original/'.build'),str(root/'.build')],check=True,timeout=90)
 wrapper=root/'xtool/.xtool-tmp';wrapper.mkdir(parents=True)
 shutil.copyfile(original/'xtool/.xtool-tmp/Package.swift',wrapper/'Package.swift')
 shutil.copytree(original/'xtool/.xtool-tmp/Sources',wrapper/'Sources')
 # Move stale caches and app outputs only within the new owned workspace.
 saved=root/'PreservedPriorArtifacts';saved.mkdir()
 candidates=list((root/'.build').rglob('ModuleCache'))
 target=root/'.build/arm64-apple-ios/debug'
 candidates += [target/'NanoANEBridge.build',target/'NanoANEBridge-App.build',target/'NanoANEBridge-App']
 candidates += list((target/'Modules').glob('NanoANEBridge.*'))
 candidates += list((target/'Modules').glob('NanoANEBridge_App.*'))
 moved=0
 for path in candidates:
  if not path.exists(): continue
  within(path,root)
  path.rename(saved/(str(moved)+'-'+path.name));moved+=1
 if (target/'NanoANEBridge-App').exists() or (target/'NanoANEBridge.build').exists():
  raise ValueError('StaleApplicationArtifactsRemain')
 argv=[str(Path(c['swift_bin'])/'swift'),'build','--build-system','native','--package-path',str(wrapper),
  '--product','NanoANEBridge-App','--swift-sdks-path',c['swift_sdks'],'--swift-sdk','darwin',
  '--triple','arm64-apple-ios','--scratch-path',str(root/'.build'),'--disable-automatic-resolution',
  '--cache-path',str(root/'Cache'),'--config-path',str(root/'Config'),'--security-path',str(root/'Security'),
  '-j','4','-debug-info-format','none','-Xlinker','-no_adhoc_codesign',
  '-Xlinker','-platform_version','-Xlinker','ios','-Xlinker','18.0','-Xlinker','27.1']
 c=dict(c,build_argv=argv,readonly_roots=[str(original),c['swift_sdks'],str(Path(c['swift_bin']).parent.parent)],
  parent_netns=os.readlink('/proc/self/ns/net'))
 child_config=root/'child-private.json';child_config.write_text(json.dumps(c))
 subprocess.run(['chown','-R',str(c['uid'])+':'+str(c['gid']),str(root)],check=True,timeout=60)
 began_ns=time.time_ns();began=time.monotonic();timed_out=False
 with (root/'build.private.log').open('x') as log:
  process=subprocess.Popen(['unshare','--mount','--net','--',sys.executable,str(Path(__file__).resolve()),
   '--network-child',str(child_config)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
   env={k:v for k,v in os.environ.items() if not k.startswith('NANO_USB_')})
  try: rc=process.wait(timeout=TIMEOUT)
  except subprocess.TimeoutExpired:
   timed_out=True;os.killpg(process.pid,signal.SIGKILL);rc=process.wait()
 elapsed=time.monotonic()-began
 description=json.loads((target/'description.json').read_text())
 commands=[v for v in description['swiftCommands'].values() if v.get('moduleName')=='NanoANEBridge']
 if len(commands)!=1: raise ValueError('ApplicationCompileCommandMissing')
 arguments=commands[0]['otherArguments']
 sdks=[Path(arguments[i+1]) for i,arg in enumerate(arguments[:-1]) if arg=='-sdk']
 selected_sdk=sdks[0] if sdks else None
 sdk_ok=bool(sdks) and all(s.resolve()==selected_sdk.resolve() for s in sdks)
 if sdk_ok: within(selected_sdk,Path(c['swift_sdks']))
 sdk_version=json.loads((selected_sdk/'SDKSettings.json').read_text()).get('Version') if selected_sdk else None
 unchanged=tree_identity(original)==(identity,count)
 source_ok=all(sha(root/'Sources/NanoANEBridge'/name)==digest for name,digest in spec['source_files_sha256'].items())
 binary=target/'NanoANEBridge-App'
 objects=list((target/'NanoANEBridge.build').glob('*.swift.o'))
 fresh=sum(f.stat().st_mtime_ns>=began_ns for f in objects)
 witness=json.loads((root/'isolation.json').read_text()) if (root/'isolation.json').exists() else {}
 result={'schema':'nano-r3-native-build-result-v1','completed_utc':datetime.now(timezone.utc).isoformat(),
  'source_commit':spec['source_commit'],'source_count':10,'logical_spec_sha256':canonical_sha(spec),
  'runner_sha256':sha(__file__),'package_text_sha256':hashlib.sha256((root/'Package.swift').read_text().encode()).hexdigest(),
  'wrapper_package_sha256':sha(wrapper/'Package.swift'),'wrapper_sources_sha256':tree_identity(wrapper/'Sources')[0],
  'compiler_sha256':sha(Path(c['swift_bin'])/'swiftc'),
  'compiler_sdk_basename':selected_sdk.name if selected_sdk else None,'compiler_sdk_version':sdk_version,
  'compiler_sdk_arguments_consistent':sdk_ok,'debug_info_format':'none','explicit_linker_sdk_version':'27.1',
  'return_code':rc,'timed_out':timed_out,'elapsed_s':round(elapsed,6),
  'source_unchanged':source_ok,'cached_inputs_unchanged':unchanged,'cached_input_tree_sha256':identity,
  'cached_input_file_count':count,'fresh_application_objects':fresh,
  'fresh_linked_binary':binary.exists() and binary.stat().st_mtime_ns>=began_ns,
  'binary_sha256':sha(binary) if binary.exists() else None,'binary_bytes':binary.stat().st_size if binary.exists() else None,
  'macho':macho_info(binary.read_bytes()) if binary.exists() else None,
  'network_namespace_isolated':witness.get('network_namespace_isolated',False),
  'input_mounts_readonly':witness.get('input_mounts_readonly',False),'phone_install':False,'identity_signing':False,
  'new_downloads':False,'ai_requests':0,'cached_dependencies':True,'build_timeout_s':TIMEOUT,'passed':False}
 try: result['passed']=assess(result)
 except ValueError as error: result['failure_category']=str(error)
 (root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result),flush=True)
 return 0 if result['passed'] else 2
def main(argv=None):
 p=argparse.ArgumentParser()
 p.add_argument('--execute',action='store_true');p.add_argument('--config',type=Path)
 p.add_argument('--network-child',type=Path,help=argparse.SUPPRESS)
 a=p.parse_args(argv)
 if a.network_child: return child(a.network_child)
 if not a.execute:
  print(json.dumps({'mode':'DRY_PLAN','job':'offline_cached_dependency_app_rebuild_and_link','compile_sources':10,
   'timeout_s':TIMEOUT,'network':'isolated','signing':False,'phone_install':False,'ai_requests':0}))
  return 0
 if a.config is None or a.config.resolve()==REPO or REPO in a.config.resolve().parents:
  raise ValueError('ExternalPrivateConfigRequired')
 return execute(json.loads(a.config.read_text(encoding='utf-8-sig')))
if __name__=='__main__': raise SystemExit(main())
