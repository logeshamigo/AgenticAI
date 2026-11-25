"""Article 16: controlled model-driven architecture comparison.
Requires OPENAI_API_KEY and an available chat-completions-compatible model.
"""
import argparse, csv, json, os, random, re, time, urllib.request, urllib.error, datetime
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

DOCS = [
 {'id':'D01','title':'Q3 churn draft — superseded','date':'2026-07-08','status':'superseded','text':'Preliminary draft: churn increased 14%. This is an unvalidated early estimate, superseded after cohort reconciliation.'},
 {'id':'D02','title':'Q3 promotional discounts','date':'2026-10-09','status':'current','text':'Q3 net revenue declined chiefly due to deeper promotional discounts and adverse pricing mix, including expanded promotional tiers.'},
 {'id':'D03','title':'Q3 regional sales summary','date':'2026-10-10','status':'current','text':'Lower realized prices and a shift toward discounted product tiers contributed to Q3 revenue decline.'},
 {'id':'D04','title':'Validated Q3 cohort reconciliation','date':'2026-10-17','status':'authoritative','text':'Final reconciled cohort audit: Q3 customer churn stayed flat versus Q2. Prior claim of 14% churn increase in preliminary draft is incorrect. Main revenue decline driver was discounting and pricing mix. This record supersedes D01.'},
 {'id':'D05','title':'Q3 board deck draft','date':'2026-08-01','status':'superseded','text':'An early slide repeated the preliminary churn rise; not reconciled against final cohort analysis.'},
 {'id':'D06','title':'Pricing change log','date':'2026-10-11','status':'current','text':'Sales offered expanded discounts during Q3; realized average selling price declined after promotions.'},
 {'id':'D07','title':'Cohort methodology notes','date':'2026-10-16','status':'current','text':'Use reconciled active-customer denominator; early cohort extracts can exaggerate churn. Seek final cohort reconciliation.'},
]
BY_ID = {d['id']:d for d in DOCS}
GOLD = {'required':'D04','drivers':{'discounting','pricing mix'},'churn':'flat'}
INSTRUCTION = '''You are investigating Q3 revenue decline in a fictional organization. Evidence is accessible ONLY through SEARCH and READ actions. You have NOT been given the decisive reconciliation record. Never assume a draft is current. Choose one JSON action: {"action":"search","query":"..."} OR {"action":"read","id":"D01"} OR {"action":"final","churn":"flat|increased|unknown","drivers":["discounting","pricing mix"],"citations":["Dxx"],"conclusion":"..."}. A citation must refer to a document you have read. Do not invent sources. Search returns titles plus short excerpts. Analyze contradiction, recency and authority. No real business data is used.'''

def search(query, seed):
    words = set(re.findall(r'[a-z0-9]+',query.lower())) - {'the','and','for','why','q3','show','find'}
    scored=[]
    for d in DOCS:
        title=d['title'].lower(); text=d['text'].lower()
        score=sum(3*(w in title)+1*(w in text) for w in words)
        scored.append((score,random.Random(seed+int(d['id'][1:])).random(),d))
    scored.sort(key=lambda x:(-x[0],x[1]))
    return [{'id':d['id'],'title':d['title'],'date':d['date'],'excerpt':d['text'][:90]} for _,_,d in scored[:3]]

class ProviderRequestError(Exception):
    """Contains a truncated provider error body; never includes API credentials."""


def request_parameters(model_name, max_tokens):
    """Use Chat Completions parameters appropriate to the named model family.

    Model-specific compatibility should still be validated with a live provider call.
    """
    reasoning = model_name.startswith(('o1', 'o3', 'o4', 'gpt-5', 'gpt-6'))
    params = {'max_completion_tokens' if reasoning else 'max_tokens': max_tokens}
    if not reasoning:
        params['temperature'] = 0
    return params


class Model:
    def __init__(self, name):
        self.name = name
        self.total_tokens = 0
        self.model_calls = 0

    def ask(self, prompt, max_tokens):
        body = {'model': self.name,
                'messages': [{'role': 'system', 'content': INSTRUCTION},
                             {'role': 'user', 'content': prompt}],
                'response_format': {'type': 'json_object'}}
        body.update(request_parameters(self.name, max_tokens))
        req = urllib.request.Request(
            'https://api.openai.com/v1/chat/completions',
            data=json.dumps(body).encode(),
            headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY'],
                     'Content-Type': 'application/json'})
        self.model_calls += 1
        try:
            with urllib.request.urlopen(req, timeout=90) as res:
                data = json.load(res)
        except urllib.error.HTTPError as exc:
            error_body = exc.read(4096).decode('utf-8', errors='replace')
            raise ProviderRequestError(f'HTTP {exc.code}: {error_body}') from exc
        usage = data.get('usage') or {}
        self.total_tokens += usage.get('total_tokens', 0) or 0
        output = data['choices'][0]['message']['content']
        return json.loads(output)


def score_final(final, reads, failure):
    """Deterministic, conservative fixture grading; not a full semantic judge."""
    unique = set(reads)
    if not isinstance(final, dict):
        final = {}
    cites = final.get('citations') or []
    citation_shape_ok = isinstance(cites, list) and all(isinstance(x, str) for x in cites)
    # Empty citations have 0 citation accuracy, but an abstention without
    # citations can remain policy-compliant if no other violation occurs.
    valid_citations = bool(not failure and citation_shape_ok and cites and set(cites).issubset(unique))
    citations_policy_ok = bool(citation_shape_ok and set(cites).issubset(unique)) if citation_shape_ok else False
    churn_correct = str(final.get('churn', '')).strip().lower() == 'flat'
    drivers = final.get('drivers')
    drivers_ok = isinstance(drivers, list) and all(isinstance(x, str) for x in drivers)
    normalized = {re.sub(r'\s+', ' ', v.strip().lower()) for v in drivers} if drivers_ok else set()
    driver_correct = {'discounting', 'pricing mix'}.issubset(normalized)
    discovered = 'D04' in unique
    correct = bool(not failure and discovered and valid_citations and churn_correct and driver_correct and 'D04' in cites)
    return {
        'correct': int(correct), 'decisive_discovered': int(discovered),
        'valid_citations': int(valid_citations), 'accurate_churn': int(churn_correct),
        'accurate_driver': int(driver_correct),
        # This is citation/budget proxy only; no live access policy is enforced.
        'policy_compliant': int(not failure and citations_policy_ok),
    }

def role_for(architecture, step):
    if architecture=='single': return 'Generalist investigator (single evolving context)'
    if architecture=='workflow': return ['Retrieve initial evidence','Check churn','Check pricing','Check time validity','Resolve conflicts','Verify provenance'][step]
    return ['Churn specialist','Churn specialist','Pricing specialist','Pricing specialist','Evidence auditor','Evidence auditor'][step]

def run_trial(architecture,seed,model_name,max_tokens=6000):
    model=Model(model_name); started=time.monotonic(); seen=[]; reads=[]; actions=[]; context=[]; failure=''; final={}
    # Six research decisions plus one final decision, the same cap for all three approaches.
    for step in range(6):
        remaining=max_tokens-model.total_tokens
        if remaining<350: failure='token_budget'; break
        role=role_for(architecture,step)
        # In the supervisor case, only the prior ACTION history is sliced.
        # Every role still sees the complete text of all documents read so far.
        if architecture=='supervisor':
            local=context[step//2*2:]
        else: local=context
        prompt=f'Role: {role}\nStep {step+1}/6. Allowed total SEARCH/READ operations: 6.\nShared document reads: {json.dumps([BY_ID[x] for x in dict.fromkeys(reads)])}\nLocal prior actions: {json.dumps(local)}\nChoose the next SEARCH or READ action, returning JSON only. You may not finalize yet.'
        try: act=model.ask(prompt,min(500,max(180,remaining//3)))
        except Exception as e: failure='provider_error:'+type(e).__name__+':'+str(e)[:600]; break
        if not isinstance(act, dict):
            failure='invalid_model_action'; break
        action=act.get('action')
        if action=='search':
            result=search(str(act.get('query','')),seed); seen.extend(x['id'] for x in result)
        elif action=='read' and isinstance(act.get('id'), str) and act['id'] in BY_ID:
            docid=act['id']; result=BY_ID[docid]; reads.append(docid)
        else:
            result={'error':'Invalid research action; search or read required'}
        row={'role':role,'action':act,'tool_result':result}; actions.append(row); context.append(row)
    if not failure:
        remaining=max_tokens-model.total_tokens
        if remaining<350: failure='token_budget'
        else:
            prompt=f'FINAL synthesis role: {"supervisor" if architecture=="supervisor" else "investigator"}.\nDocuments read: {json.dumps([BY_ID[x] for x in dict.fromkeys(reads)])}\nReturn ONLY final JSON with churn, drivers (a list of exact driver names), citations, and conclusion. Do not cite unread evidence. If decisive proof is not found, say unknown. No further tools.'
            try: final=model.ask(prompt,min(650,max(250,remaining//2)))
            except Exception as e: failure='provider_error:'+type(e).__name__+':'+str(e)[:600]
    scores = score_final(final, reads, failure)
    unique = set(reads)
    stale = sum(1 for x in reads if BY_ID[x]['status'] == 'superseded')
    return {'architecture': architecture, 'seed': seed, 'model': model_name,
            **scores,
            'unique_relevant_evidence': len({x for x in unique if BY_ID[x]['status'] in ('current', 'authoritative')}),
            'duplicate_reads': len(reads)-len(unique), 'stale_reads': stale,
            'tool_calls': len(actions), 'model_calls': getattr(model, 'model_calls', len(actions)+(0 if failure else 1)),
            'tokens': model.total_tokens,
            'latency_seconds': round(time.monotonic()-started, 2),
            'failure': failure, 'final': final, 'trace': actions}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--trials',type=int,default=5);p.add_argument('--model',default=os.getenv('EVAL_MODEL','gpt-4.1-mini'));p.add_argument('--max-tokens',type=int,default=6000);p.add_argument('--output',default='results');args=p.parse_args()
    if not os.getenv('OPENAI_API_KEY'): p.error('Set OPENAI_API_KEY; this tool performs real provider calls and does not fabricate benchmark results.')
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True); rows=[]
    # Each invocation starts a fresh, internally consistent dataset.
    (out/'trials.jsonl').write_text('')
    (out/'summary.csv').write_text('')
    for seed in range(args.trials):
        order=['single','workflow','supervisor'];random.Random(seed).shuffle(order)
        for arch in order:
            r=run_trial(arch,seed,args.model,args.max_tokens);rows.append(r)
            with (out/'trials.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
            # Persist an incremental CSV after every trial so crashes or interrupts
            # do not discard all completed trial summaries.
            keys=['architecture','seed','model','correct','decisive_discovered','valid_citations','accurate_churn','accurate_driver','unique_relevant_evidence','duplicate_reads','stale_reads','tool_calls','model_calls','tokens','latency_seconds','policy_compliant','failure']
            with (out/'summary.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows([{k:item[k] for k in keys} for item in rows])
            print(arch,seed,'correct=',r['correct'],'tokens=',r['tokens'],'failure=',r['failure'],flush=True)
    print('Actual measurements written to',out)
if __name__=='__main__':main()
