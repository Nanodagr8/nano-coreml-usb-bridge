"""Create a private warm-native job manifest from an existing qualified workspace."""
from pathlib import Path
import argparse,json
import r3_native_build as native
import r3_native_job as worker
from r3_swift_prepare import canonical_sha,load_spec
ROOT=Path(__file__).resolve().parents[1]
def manifest_for(root):
 root=Path(root).resolve()
 if root==ROOT or ROOT in root.parents:raise ValueError('PrivateWorkspaceOutsideRepositoryRequired')
 cold=json.loads((root/'result.json').read_text(encoding='utf-8'))
 if not cold['passed'] or not native.assess(cold):raise ValueError('QualifiedColdWorkspaceRequired')
 c=json.loads((root/'child-private.json').read_text(encoding='utf-8'))
 spec=json.loads(worker.SPEC.read_text(encoding='utf-8-sig'))
 if worker.normalized_argv(c['build_argv'],root,c)!=spec['build_argv_template']:raise ValueError('NativeArgumentMismatch')
 source=load_spec()
 for name,digest in source['source_files_sha256'].items():
  if native.sha(root/'Sources/NanoANEBridge'/name)!=digest:raise ValueError('SourceSnapshotMismatch')
 if native.sha(root/'Package.resolved')!=source['dependency_lock_sha256']:raise ValueError('DependencyLockMismatch')
 digest,count=worker.dependency_identity(root)
 return {'schema':'nano-native-concurrent-private-job-v1','stage':str(root),'child_config':c,
  'source_spec_sha256':canonical_sha(source),'native_spec_sha256':canonical_sha(spec),
  'dependency_inputs_sha256':digest,'dependency_input_count':count,'supporting_runner_sha256':native.sha(Path(native.__file__))}
def prepare(root):
 root=Path(root).resolve()
 if root==ROOT or ROOT in root.parents:raise ValueError('PrivateWorkspaceOutsideRepositoryRequired')
 path=root/'study-job.json'
 if path.exists():raise ValueError('RefuseExistingNativeManifest')
 manifest=manifest_for(root)
 with path.open('x',encoding='utf-8',newline='\n') as out:out.write(json.dumps(manifest,indent=2)+'\n')
 return {'prepared':True,'job_manifest_sha256':native.sha(path),'native_spec_sha256':manifest['native_spec_sha256'],
  'dependency_inputs_sha256':manifest['dependency_inputs_sha256'],'dependency_input_count':manifest['dependency_input_count']}
def main():
 p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
 print(json.dumps(prepare(a.workspace)))
if __name__=='__main__':main()
