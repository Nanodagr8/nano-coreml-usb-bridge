from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import unittest
import r3_burst_workload as b

class PlacementChecks(unittest.TestCase):
    def api(self,vram=0,digest=None):
        return {'models':[{'name':b.r3.MODEL,'digest':digest or b.r3.MODEL_DIGEST,'size':1000,'size_vram':vram}]}
    def cli(self,processor):
        return b.r3.MODEL+' id 1 GB '+processor+' 4096 forever'
    def test_cpu(self):
        self.assertTrue(b.validate_placement(self.api(),self.cli('100% CPU'),'windows_cpu')['placement_check_passed'])
    def test_gpu(self):
        self.assertTrue(b.validate_placement(self.api(900),self.cli('100% GPU'),'windows_gpu_candidate')['placement_check_passed'])
    def test_reject_partial_or_wrong_processor(self):
        for processor in ('50%/50% CPU/GPU','100% CPU'):
            with self.assertRaises(ValueError):
                b.validate_placement(self.api(900),self.cli(processor),'windows_gpu_candidate')
    def test_reject_conflicting_vram(self):
        with self.assertRaises(ValueError):
            b.validate_placement(self.api(900),self.cli('100% CPU'),'windows_cpu')
    def test_reject_missing_duplicate_wrong_model(self):
        for api in ({'models':[]},{'models':self.api()['models']*2},self.api(digest='wrong')):
            with self.assertRaises(ValueError):
                b.validate_placement(api,self.cli('100% CPU'),'windows_cpu')
if __name__=='__main__':
    unittest.main()
