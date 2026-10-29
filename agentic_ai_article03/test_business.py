import unittest
from business import order_lookup, tracking_lookup

class Tests(unittest.TestCase):
    def test_order(self): self.assertEqual(order_lookup('ORD-1042')['tracking_id'], 'TRK-88')
    def test_denied_order(self): self.assertEqual(order_lookup('ORD-9999')['error'],'not_authorized')
    def test_tracking(self): self.assertIn('delayed',tracking_lookup('TRK-88')['status'])
    def test_denied_tracking(self): self.assertEqual(tracking_lookup('TRK-00')['error'],'not_authorized')

if __name__ == '__main__': unittest.main()
