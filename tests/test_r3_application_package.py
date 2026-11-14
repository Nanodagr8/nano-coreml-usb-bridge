from pathlib import Path
import contextlib,hashlib,io,json,random,itertools,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import r3_application_study as app
import r3_swift_prepare as prep
class ApplicationPackageTests(unittest.TestCase):
 def result(self):
  return {'passed':True,'exit_code':0,'source_unchanged':True,'source_count':10,'elapsed_s':4,
   'job_manifest_sha256':app.MANIFEST,'logical_spec_sha256':app.PROTOCOL['logical_spec_sha256']}
 def answers(self):
  return [{'task_label':task,'passed_exact_answer':True,'finish_offset_from_launch_s':2} for task in app.TASKS]
 def test_valid_and_late_overlap(self):
  self.assertIsNone(app.assess(self.result(),self.answers(),True))
  answers=self.answers();answers[-1]['finish_offset_from_launch_s']=3.9
  self.assertEqual(app.assess(self.result(),answers,True),'conservative_overlap_gate_failed')
 def test_reject_source_and_logical_change(self):
  r=self.result();r['source_unchanged']=False
  self.assertEqual(app.assess(r,self.answers(),True),'compiler_validation_failure')
  r=self.result();r['logical_spec_sha256']='different'
  self.assertEqual(app.assess(r,self.answers(),True),'logical_workload_mismatch')
 def test_reject_quality_and_partial_burst(self):
  self.assertEqual(app.assess(self.result(),[],True),'incomplete_ai_burst')
  a=self.answers();a[0]['passed_exact_answer']=False
  self.assertEqual(app.assess(self.result(),a,True),'ai_quality_failure')
 def test_dry_plan_never_starts_job_or_phone(self):
  with patch.object(app.subprocess,'Popen') as process,patch.object(app,'NanoUSBClient') as phone,contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(app.main([]),0)
  process.assert_not_called();phone.assert_not_called()
 def test_registered_seed_and_positions(self):
  targets=['windows_cpu','windows_gpu_candidate','iphone_usb_coreml']
  orders=list(itertools.permutations(targets))
  random.Random(app.PROTOCOL['public_order_seed']).shuffle(orders)
  self.assertEqual(orders,[tuple(x) for x in app.PROTOCOL['condition_orders']])
  self.assertEqual(len(app.ORDER),25)
  for position in range(3):
   self.assertTrue(all(sum(order[position]==target for order in orders)==2 for target in targets))
 def test_private_config_required(self):
  with patch.dict(app.os.environ,{'NANO_SWIFT_STUDY_CONFIG':''}):
   with self.assertRaises(ValueError): app.configure()
 def test_canonical_spec_hash_survives_formatting(self):
  spec=prep.load_spec()
  self.assertEqual(prep.canonical_sha(spec),prep.canonical_sha(json.loads(json.dumps(spec,indent=4))))
  self.assertEqual(prep.canonical_sha(spec),app.PROTOCOL['logical_spec_sha256'])
 def test_spec_contains_no_machine_paths(self):
  text=json.dumps(prep.load_spec()).lower()
  for marker in ('/var/lib/','/mnt/c/','c:\\users','kevin','bearer'):
   self.assertNotIn(marker,text)
 def test_argv_substitution_is_exact_and_requires_absolute_paths(self):
  spec={'argv_template':['{compiler}','-typecheck','{workspace}/Sources/A.swift']}
  paths={key:'/existing/'+key for key in ('compiler','dependency_modules','yyjson_module_map',
    'yyjson_headers','swift_resource_dir','toolset_bin','sdk','platform_swift_lib')}
  result=prep.expected_argv(spec,paths,'/private/job')
  self.assertEqual(result,['/existing/compiler','-typecheck','/private/job/Sources/A.swift'])
  paths['compiler']='relative'
  with self.assertRaises(ValueError): prep.expected_argv(spec,paths,'/private/job')
 def test_new_private_workspace_required(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError): prep.materialize({'workspace':d})
if __name__=='__main__':
 unittest.main()
