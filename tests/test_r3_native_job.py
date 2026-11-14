import contextlib,io,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import r3_native_job as job
class NativeJobTests(unittest.TestCase):
 def valid(self):
  return {'exit_code':0,'timed_out':False,'source_unchanged':True,'dependency_inputs_unchanged':True,
   'fresh_application_objects':10,'fresh_linked_binary':True,'new_application_objects_linked':True,
   'live_native_frontend_observed':True,'network_namespace_isolated':True,'input_mounts_readonly':True,
   'macho':{'architecture':'arm64','file_type':'MH_EXECUTE','code_signature_present':False,'platform':2,'minimum_os':18<<16,'sdk':27<<16|1<<8}}
 def test_valid_native_artifact(self):self.assertIsNone(job.assess(self.valid()))
 def test_reject_changed_inputs_stale_objects_or_unwitnessed_frontend(self):
  for key,value in (('dependency_inputs_unchanged',False),('source_unchanged',False),('fresh_application_objects',9),('fresh_linked_binary',False),('new_application_objects_linked',False),('live_native_frontend_observed',False)):
   r=self.valid();r[key]=value
   self.assertIsNotNone(job.assess(r))
 def test_reject_signature_or_incorrect_sdk(self):
  for key,value in (('code_signature_present',True),('sdk',18<<16),('platform',1)):
   r=self.valid();r['macho'][key]=value
   self.assertIsNotNone(job.assess(r))
 def test_reject_build_timeout_and_missing_isolation(self):
  for key,value in (('exit_code',-9),('timed_out',True),('input_mounts_readonly',False),('network_namespace_isolated',False)):
   r=self.valid();r[key]=value
   self.assertIsNotNone(job.assess(r))
 def test_dependency_ledger_excludes_app_but_detects_dependency_changes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);target=root/'.build/arm64-apple-ios/debug'
   dep=target/'CoreMLLLM.build';dep.mkdir(parents=True);(dep/'a.o').write_bytes(b'fixed')
   app=target/'NanoANEBridge.build';app.mkdir();(app/'a.swift.o').write_bytes(b'app1')
   first=job.dependency_identity(root)
   (app/'a.swift.o').write_bytes(b'app2');self.assertEqual(first,job.dependency_identity(root))
   (dep/'a.o').write_bytes(b'changed');self.assertNotEqual(first,job.dependency_identity(root))
 def test_path_normalization_is_machine_independent(self):
  self.assertEqual(job.normalized_argv(['/tool/bin/swift','/work/.build','/sdk'],Path('/work'),{'swift_bin':'/tool/bin','swift_sdks':'/sdk'}),['{swift_bin}/swift','{workspace}/.build','{swift_sdks}'])
 def test_reset_preserves_compiler_bookkeeping_and_moves_old_objects(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);target=root/'.build/arm64-apple-ios/debug'
   app=target/'NanoANEBridge.build';app.mkdir(parents=True)
   (app/'output-file-map.json').write_text('{}');(app/'a.swift.o').write_bytes(b'old')
   (target/'NanoANEBridge-App').write_bytes(b'old-binary')
   saved=root/'saved';saved.mkdir()
   job.reset_app_outputs(root,saved)
   self.assertTrue((app/'output-file-map.json').exists())
   self.assertFalse((app/'a.swift.o').exists())
   self.assertFalse((target/'NanoANEBridge-App').exists())
   self.assertEqual(len(list(saved.iterdir())),2)
if __name__=='__main__':unittest.main()
