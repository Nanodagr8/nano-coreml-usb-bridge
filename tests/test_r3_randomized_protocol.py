from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'client'))
import hashlib,itertools,json,random,unittest
from unittest.mock import patch
import r3_randomized_mixed_workload as b

class RegisteredProtocolTests(unittest.TestCase):
    def test_seed_recreates_registered_orders(self):
        orders=list(itertools.permutations(b.PROTOCOL['ai_targets']))
        random.Random(b.PROTOCOL['public_order_seed']).shuffle(orders)
        self.assertEqual(orders,[tuple(x) for x in b.PROTOCOL['condition_orders']])
        sequence=['baseline']
        for order in orders:
            sequence.extend(order)
            sequence.append('baseline')
        self.assertEqual(b.balanced_plan(b.PROTOCOL['targets'],6),sequence)
    def test_plan_bytes_match_locked_hash(self):
        self.assertEqual(hashlib.sha256(b.PLAN_BYTES).hexdigest(),
            '2212fcadb78d8e2631026ff40bd75a1354fb95d30f75b9054fa7192398b19b3a')
    def test_invalid_registered_orders_rejected(self):
        bad=dict(b.PROTOCOL)
        bad['condition_orders']=[b.PROTOCOL['condition_orders'][0]]*6
        with patch.object(b,'PROTOCOL',bad):
            with self.assertRaises(ValueError):
                b.balanced_plan(b.PROTOCOL['targets'],6)

    def test_modified_protocol_refused_at_import(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('changed_registered_fixture',b.__file__)
        module=importlib.util.module_from_spec(spec)
        with patch.object(Path,'read_bytes',return_value=b'{}'):
            with self.assertRaisesRegex(RuntimeError,'RegisteredProtocolChanged'):
                spec.loader.exec_module(module)

if __name__=='__main__':
    unittest.main()
