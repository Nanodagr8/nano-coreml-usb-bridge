"""Materialize a fixed validation job from existing, trusted SDK/dependency paths."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json
SPEC=Path(__file__).resolve().parents[1]/'results/r3_application_source_spec_20261113.json'
REPO=Path(__file__).resolve().parents[1]
def canonical_sha(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')).hexdigest()
def load_spec():
 return json.loads(SPEC.read_text(encoding='utf-8-sig'))
def expected_argv(spec,paths,workspace):
 required={'compiler','dependency_modules','yyjson_module_map','yyjson_headers',
           'swift_resource_dir','toolset_bin','sdk','platform_swift_lib'}
 if set(paths)!=required or any(not isinstance(v,str) or not PurePosixPath(v).is_absolute() for v in paths.values()):
  raise ValueError('AbsoluteExistingToolchainPathsRequired')
 return [a.format_map(dict(paths,workspace=str(workspace))) for a in spec['argv_template']]
def validate_identity(manifest,spec,check_files=True):
 root=Path(manifest['stage']).resolve()
 if manifest['source_files_sha256']!=spec['source_files_sha256'] or manifest['source_commit']!=spec['source_commit']:
  raise ValueError('FrozenSourceMismatch')
 if manifest['source_count']!=10 or manifest['logical_spec_sha256']!=canonical_sha(spec):
  raise ValueError('LogicalSpecMismatch')
 if manifest['argv']!=expected_argv(spec,manifest['materialization_paths'],root):
  raise ValueError('CompilerArgumentsMismatch')
 if Path(manifest['materialization_paths']['sdk']).name!=spec['sdk_basename']:
  raise ValueError('SDKVersionMismatch')
 if check_files:
  lock=Path(manifest['dependency_lock_file'])
  if hashlib.sha256(lock.read_bytes()).hexdigest()!=spec['dependency_lock_sha256']:
   raise ValueError('DependencyLockMismatch')
  for name,digest in spec['source_files_sha256'].items():
   if Path(name).name!=name or hashlib.sha256((root/'Sources'/name).read_bytes()).hexdigest()!=digest:
    raise ValueError('SourceChanged')
 return canonical_sha(spec)
def materialize(config):
 spec=load_spec()
 root=Path(config['workspace']).resolve()
 if root.exists() or root==REPO or REPO in root.parents:
  raise ValueError('UseNewPrivateWorkspaceOutsideRepository')
 source=Path(config['source_tree']).resolve()
 inputs={}
 for name,digest in spec['source_files_sha256'].items():
  if Path(name).name!=name:
   raise ValueError('InvalidSourceName')
  data=(source/name).read_bytes()
  if hashlib.sha256(data).hexdigest()!=digest:
   raise ValueError('SourceSnapshotMismatch')
  inputs[name]=data
 paths=config['paths']
 argv=expected_argv(spec,paths,root)
 if not Path(paths['compiler']).is_file() or not Path(paths['dependency_modules']).is_dir():
  raise ValueError('ExistingCompilerAndModulesRequired')
 if hashlib.sha256(Path(config['dependency_lock_file']).read_bytes()).hexdigest()!=spec['dependency_lock_sha256']:
  raise ValueError('DependencyLockMismatch')
 root.mkdir(parents=True)
 (root/'Sources').mkdir()
 (root/'ModuleCache').mkdir()
 for name,data in inputs.items():
  (root/'Sources'/name).write_bytes(data)
 manifest={'schema':'nano-r3-swift-validation-job-v1','source_commit':spec['source_commit'],
  'source_count':10,'source_files_sha256':spec['source_files_sha256'],'argv':argv,
  'stage':str(root),'deadline_seconds':45,'phone_install':False,'signing':False,
  'automatic_dependency_resolution':False,'new_downloads':False,'job_kind':'swift_typecheck_on_windows_wsl',
  'materialization_paths':paths,'dependency_lock_file':config['dependency_lock_file'],
  'logical_spec_sha256':canonical_sha(spec)}
 validate_identity(manifest,spec)
 path=root/'job.json'
 with path.open('x',encoding='utf-8') as out: out.write(json.dumps(manifest,indent=2)+'\n')
 return {'prepared':True,'job_manifest_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
         'logical_spec_sha256':canonical_sha(spec)}
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--config',type=Path,required=True)
 a=parser.parse_args()
 print(json.dumps(materialize(json.loads(a.config.read_text(encoding='utf-8-sig')))))
if __name__=='__main__':
 main()
