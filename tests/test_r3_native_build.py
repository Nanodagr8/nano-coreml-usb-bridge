import contextlib,copy,io,json,struct,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'client'))
import r3_native_build as build
class NativeBuildTests(unittest.TestCase):
 def image(self,signature=False):
  commands=struct.pack('<6I',0x32,24,2,18<<16,27<<16|1<<8,0)
  if signature: commands+=struct.pack('<4I',0x1d,16,0,0)
  return struct.pack('<8I',0xfeedfacf,0x100000c,0,2,1+signature,len(commands),0,0)+commands
 def valid(self):
  return {'return_code':0,'timed_out':False,'source_unchanged':True,'cached_inputs_unchanged':True,
   'fresh_application_objects':10,'fresh_linked_binary':True,'source_count':10,
   'logical_spec_sha256':build.canonical_sha(build.load_spec()),'network_namespace_isolated':True,
   'input_mounts_readonly':True,'macho':build.macho_info(self.image()),
   'compiler_sdk_basename':'iPhoneOS27.1.sdk','compiler_sdk_version':'27.1','compiler_sdk_arguments_consistent':True}
 def test_unsigned_arm64_ios_executable(self):
  self.assertTrue(build.assess(self.valid()))
  info=build.macho_info(self.image(True));self.assertTrue(info['code_signature_present'])
 def test_reject_signature_wrong_platform_and_sdk(self):
  for field,value in (('code_signature_present',True),('platform',1),('sdk',26<<16)):
   r=self.valid();r['macho'][field]=value
   with self.assertRaises(ValueError):build.assess(r)
 def test_reject_truncated_and_malformed_load_commands(self):
  for data in (b'',self.image()[:31],self.image()[:-1]):
   with self.assertRaises(ValueError):build.macho_info(data)
  data=bytearray(self.image());struct.pack_into('<I',data,36,4)
  with self.assertRaises(ValueError):build.macho_info(data)
 def test_reject_non_executable_or_other_cpu(self):
  for offset in (4,12):
   data=bytearray(self.image());struct.pack_into('<I',data,offset,1)
   with self.assertRaises(ValueError):build.macho_info(data)
 def test_reject_stale_changed_or_failed_results(self):
  for field,value in (('return_code',1),('timed_out',True),('source_unchanged',False),
    ('cached_inputs_unchanged',False),('fresh_application_objects',9),('fresh_linked_binary',False),
    ('network_namespace_isolated',False),('input_mounts_readonly',False),('logical_spec_sha256','bad'),('compiler_sdk_version','18.0')):
   r=self.valid();r[field]=value
   with self.assertRaises(ValueError):build.assess(r)
 def test_owned_paths_cannot_escape(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)
   self.assertEqual(build.within(root/'owned',root),(root/'owned').resolve())
   with self.assertRaises(ValueError):build.within(root.parent/'elsewhere',root)
   with self.assertRaises(ValueError):build.within(root,root)
 def test_input_ledger_detects_changed_bytes_and_added_files(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'a').write_text('first')
   first=build.tree_identity(root);(root/'a').write_text('second')
   self.assertNotEqual(first,build.tree_identity(root))
   second=build.tree_identity(root);(root/'b').write_text('new')
   self.assertNotEqual(second,build.tree_identity(root))
 def test_dry_plan_never_executes(self):
  out=io.StringIO()
  with patch.object(build,'execute') as execute,contextlib.redirect_stdout(out):
   self.assertEqual(build.main([]),0)
  execute.assert_not_called()
  self.assertEqual(json.loads(out.getvalue())['ai_requests'],0)
 def test_published_two_build_qualification(self):
  evidence=json.loads((ROOT/'results/r3_native_build_qualification_20261113.json').read_text())
  failed=json.loads((ROOT/'results/r3_native_build_attempt1_failed_20261113.json').read_text())
  self.assertTrue(failed['timed_out']);self.assertFalse(failed['passed'])
  self.assertTrue(evidence['complete'])
  self.assertFalse(evidence['performance_comparison'] or evidence['independent_external_replication'])
  self.assertFalse(evidence['installed_or_executed_on_phone'] or evidence['energy_measured'] or evidence['ane_profiled'])
  self.assertEqual(len(evidence['jobs']),2)
  self.assertTrue(all(a['fresh_application_objects_in_link_list']==10 and a['no_old_application_objects'] for a in evidence['link_inputs_audit']))
  self.assertEqual(len({j['cached_input_tree_sha256'] for j in evidence['jobs']}),1)
  for job in evidence['jobs']:
   self.assertTrue(job['passed'] and build.assess(job))
   self.assertEqual(job['ai_requests'],0)
   self.assertFalse(job['identity_signing'] or job['phone_install'] or job['new_downloads'])
   self.assertLess(job['elapsed_s'],180)
 def test_protocol_and_runner_locked_before_execution(self):
  from datetime import datetime
  import hashlib
  raw=(ROOT/'results/r3_native_build_qualification_protocol_v2_20261113.json').read_bytes()
  plan=json.loads(raw)
  e=json.loads((ROOT/'results/r3_native_build_qualification_20261113.json').read_text())
  self.assertEqual(hashlib.sha256(raw).hexdigest(),e['protocol_sha256'])
  self.assertEqual(build.sha(ROOT/'client/r3_native_build.py'),plan['runner_sha256'])
  self.assertLess(datetime.fromisoformat(plan['created_utc']),datetime.fromisoformat(e['locked_utc']))
  self.assertLess(datetime.fromisoformat(e['locked_utc']),datetime.fromisoformat(e['started_utc']))
  previous=e['started_utc']
  for job in e['jobs']:
   self.assertEqual(job['runner_sha256'],plan['runner_sha256'])
   self.assertEqual(job['source_commit'],plan['source_commit'])
   self.assertLess(datetime.fromisoformat(previous),datetime.fromisoformat(job['completed_utc']))
   previous=job['completed_utc']
if __name__=='__main__':unittest.main()
