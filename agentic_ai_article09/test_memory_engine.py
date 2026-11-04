import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from memory_engine import Candidate, MemoryStore

class MemoryEngineTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.base = dict(tenant='acme', subject='q3', kind='semantic',
                         key='period', content='Q3 FY2026', source_id='approval', verified=True)
    def tearDown(self):
        self.store.close()
    def test_verified_write_and_recall(self):
        self.store.write(Candidate(**self.base))
        self.assertEqual(len(self.store.recall('acme','q3','Q3')), 1)
    def test_reject_unverified(self):
        with self.assertRaises(PermissionError):
            self.store.write(Candidate(**{**self.base,'verified':False}))
    def test_cross_tenant_isolation(self):
        self.store.write(Candidate(**self.base))
        self.assertEqual(self.store.recall('other','q3','Q3'), [])
    def test_cross_subject_isolation(self):
        self.store.write(Candidate(**self.base))
        self.assertEqual(self.store.recall('acme','other','Q3'), [])
    def test_supersession(self):
        self.store.write(Candidate(**self.base))
        self.store.write(Candidate(**{**self.base,'content':'Q4 FY2026'}))
        result = self.store.recall('acme','q3','period')
        self.assertEqual([m['content'] for m in result], ['Q4 FY2026'])
    def test_revoke(self):
        ident = self.store.write(Candidate(**self.base))
        self.assertTrue(self.store.revoke('acme','q3',ident))
        self.assertEqual(self.store.recall('acme','q3','period'), [])
    def test_revoke_other_tenant_denied(self):
        ident = self.store.write(Candidate(**self.base))
        self.assertFalse(self.store.revoke('other','q3',ident))
    def test_expired_at_write_rejected(self):
        expired=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):
            self.store.write(Candidate(**{**self.base,'expires_at':expired}))
    def test_ttl_excluded_at_read(self):
        future=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        ident=self.store.write(Candidate(**{**self.base,'expires_at':future}))
        with self.store.db:
            self.store.db.execute('UPDATE memory SET expires_at=? WHERE id=?',
               ((datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),ident))
        self.assertEqual(self.store.recall('acme','q3','period'), [])
    def test_no_query_returns_active(self):
        self.store.write(Candidate(**self.base))
        self.assertEqual(len(self.store.recall('acme','q3')), 1)
    def test_unrelated_query_excluded(self):
        self.store.write(Candidate(**self.base))
        self.assertEqual(self.store.recall('acme','q3','unrelated'), [])
    def test_checkpoint_resume(self):
        self.store.save_checkpoint('acme','r1',{'step':2})
        self.assertEqual(self.store.load_checkpoint('acme','r1'), {'step':2})
    def test_checkpoint_isolation(self):
        self.store.save_checkpoint('acme','r1',{'step':2})
        self.assertIsNone(self.store.load_checkpoint('other','r1'))
    def test_checkpoint_update(self):
        self.store.save_checkpoint('acme','r1',{'step':1})
        self.store.save_checkpoint('acme','r1',{'step':2})
        self.assertEqual(self.store.load_checkpoint('acme','r1'), {'step':2})
    def test_invalid_kind(self):
        with self.assertRaises(ValueError):
            self.store.write(Candidate(**{**self.base,'kind':'procedural'}))
    def test_limit_validation(self):
        with self.assertRaises(ValueError):
            self.store.recall('acme','q3',limit=0)

    # --- regression tests added in v2 ---
    def test_future_expiry_with_negative_offset_is_recalled(self):
        future=(datetime.now(timezone.utc)+timedelta(hours=1)).astimezone(timezone(timedelta(hours=-10)))
        self.store.write(Candidate(**{**self.base,'expires_at':future.isoformat()}))
        self.assertEqual(len(self.store.recall('acme','q3','period')), 1)
    def test_past_expiry_with_positive_offset_rejected(self):
        past=(datetime.now(timezone.utc)-timedelta(hours=1)).astimezone(timezone(timedelta(hours=14)))
        with self.assertRaises(ValueError):
            self.store.write(Candidate(**{**self.base,'expires_at':past.isoformat()}))
    def test_naive_expiry_rejected_with_value_error(self):
        with self.assertRaises(ValueError):
            self.store.write(Candidate(**{**self.base,'expires_at':'2030-01-01T00:00:00'}))
    def test_z_suffix_expiry_accepted(self):
        self.store.write(Candidate(**{**self.base,'expires_at':'2030-01-01T00:00:00Z'}))
        self.assertEqual(len(self.store.recall('acme','q3','period')), 1)
    def test_garbage_expiry_rejected(self):
        with self.assertRaises(ValueError):
            self.store.write(Candidate(**{**self.base,'expires_at':'tomorrow'}))
    def test_string_verified_flag_rejected(self):
        with self.assertRaises(PermissionError):
            self.store.write(Candidate(**{**self.base,'verified':'false'}))
    def test_whitespace_content_rejected(self):
        with self.assertRaises(ValueError):
            self.store.write(Candidate(**{**self.base,'content':'   '}))
    def test_unique_active_semantic_key_enforced_by_database(self):
        self.store.write(Candidate(**self.base))
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store.db:
                self.store.db.execute("""INSERT INTO memory(tenant,subject,kind,key,content,
                    source_id,recorded_at) VALUES('acme','q3','semantic','period','x','s','t')""")
    def test_latest_semantic_write_wins_regardless_of_source(self):
        # Documents a demo limit: supersession is by recency, not authority.
        self.store.write(Candidate(**{**self.base,'content':'USD','source_id':'policy'}))
        self.store.write(Candidate(**{**self.base,'content':'EUR','source_id':'chat'}))
        self.assertEqual([m['content'] for m in self.store.recall('acme','q3','period')], ['EUR'])
    def test_episodic_entries_with_same_key_are_both_kept(self):
        ep={**self.base,'kind':'episodic','key':'event'}
        self.store.write(Candidate(**{**ep,'content':'first event'}))
        self.store.write(Candidate(**{**ep,'content':'second event'}))
        self.assertEqual(len(self.store.recall('acme','q3','event')), 2)

if __name__ == '__main__': unittest.main()
