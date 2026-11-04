from memory_engine import MemoryStore, Candidate

store = MemoryStore()
store.write(Candidate('acme', 'revenue-q3', 'semantic', 'report_period',
                      'The approved report period is Q3 FY2026', 'approval-101', True))
store.write(Candidate('acme', 'revenue-q3', 'episodic', 'analysis-2026-10-10',
                      'On Oct 10, the analyst found a missing refund adjustment',
                      'audit-208', True))
store.save_checkpoint('acme', 'run-42', {'step': 'validate_revenue', 'approved': False})
print('Recalled:', [(m['kind'], m['key']) for m in
                    store.recall('acme', 'revenue-q3', 'Q3 report refund')])
print('Resume:', store.load_checkpoint('acme', 'run-42'))
store.close()
