import unittest
from demo import run
class Tests(unittest.TestCase):
    def setUp(self):
        self.good=run('validated'); self.bad=run('stale')
    def test_validated(self): self.assertTrue(self.good[-1]['attributes']['validated'])
    def test_stale(self): self.assertFalse(self.bad[-1]['attributes']['validated'])
    def test_completion(self): self.assertEqual(self.bad[-1]['status'],'ok')
    def test_retry(self): self.assertEqual([s['status'] for s in self.bad if s['name']=='retrieve'],['ok','error','ok'])
    def test_unique(self): self.assertEqual(self.bad[-2]['attributes']['unique_evidence'],1)
    def test_parent(self): self.assertTrue(all(s['parent_id']==self.good[-1]['span_id'] for s in self.good[:-1]))
    def test_trace(self): self.assertEqual(len({s['trace_id'] for s in self.bad}),1)
    def test_distinct(self): self.assertNotEqual(self.good[-1]['trace_id'],self.bad[-1]['trace_id'])
    def test_duration(self): self.assertTrue(all(s['duration_ms']>=0 for s in self.bad))
    def test_root(self): self.assertIsNone(self.good[-1]['parent_id'])
    def test_no_payload(self): self.assertNotIn('simulated',str(self.bad))
    def test_unknown(self):
        with self.assertRaises(ValueError): run('other')
if __name__=='__main__': unittest.main()
