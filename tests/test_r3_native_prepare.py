from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'client'))
import r3_native_prepare as prepare
class NativePrepareTests(unittest.TestCase):
 def test_repository_cannot_be_native_workspace(self):
  with self.assertRaises(ValueError):prepare.prepare(ROOT/'private-job')
 def test_existing_manifest_is_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);f=root/'study-job.json';f.write_bytes(b'protected-existing')
   with self.assertRaises(ValueError):prepare.prepare(root)
   self.assertEqual(f.read_bytes(),b'protected-existing')
if __name__=='__main__':unittest.main()
