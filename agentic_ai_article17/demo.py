import json
from contextlib import contextmanager
from time import perf_counter_ns
from uuid import uuid4
from pathlib import Path

class Trace:
    def __init__(self):
        self.id = uuid4().hex
        self.stack = []
        self.spans = []
    @contextmanager
    def span(self, name, **attrs):
        s = dict(trace_id=self.id, span_id=uuid4().hex[:16], parent_id=self.stack[-1] if self.stack else None, name=name, attributes=attrs, status='ok')
        start = perf_counter_ns()
        self.stack.append(s['span_id'])
        try:
            yield attrs
        except Exception as exc:
            s['status'] = 'error'
            attrs['error_type'] = type(exc).__name__
            raise
        finally:
            self.stack.pop()
            s['duration_ms'] = (perf_counter_ns()-start)/1e6
            self.spans.append(s)

def run(scenario):
    if scenario not in ('validated','stale'):
        raise ValueError('unknown scenario')
    t = Trace()
    evidence = []
    with t.span('agent.run', scenario=scenario) as root:
        for attempt in (1,2,3):
            try:
                with t.span('retrieve', attempt=attempt) as a:
                    if scenario == 'stale' and attempt == 2:
                        raise TimeoutError('simulated')
                    doc = 'D04' if scenario == 'validated' and attempt == 2 else 'D01'
                    evidence.append(doc)
                    a['source_id'] = doc
                    a['source_version'] = 'current' if doc == 'D04' else 'stale'
            except TimeoutError:
                continue
            if 'D04' in evidence:
                break
        with t.span('validate') as a:
            valid = 'D04' in evidence
            a.update(validated=valid, unique_evidence=len(set(evidence)))
        root.update(validated=valid, termination='completed')
    return t.spans

if __name__ == '__main__':
    rows = run('validated') + run('stale')
    Path('traces.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    for r in rows:
        print(json.dumps(r))
