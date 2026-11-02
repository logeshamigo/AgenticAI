"""Run from the extracted directory: python demo.py"""
from traditional_rag import collect_traditional
from agentic_rag import collect_agentic, requirement_state
AUTH = frozenset({'acme'})

def main():
    fixed = collect_traditional('acme', authorized_tenants=AUTH)
    adaptive = collect_agentic('acme', authorized_tenants=AUTH)
    print('Question: Why did total revenue fall from FY2025-Q2 to FY2026-Q2?')
    print('Traditional searched: revenue -> churn')
    print('Traditional sources:', [d.id for d in fixed])
    print('Traditional coverage complete:', requirement_state(fixed)[0])
    print('Agentic searched:', ' -> '.join(adaptive.searched))
    print('Agentic sources:', [d.id for d in adaptive.documents])
    print('Agentic status:', adaptive.status)
    print('Agentic calls:', adaptive.calls)
    print('Interpretation: synthetic attribution figures, not independent proof of causation.')
    limited = collect_agentic('acme', authorized_tenants=AUTH, max_calls=2)
    print('Agentic max_calls=2 status:', limited.status)

if __name__ == '__main__':
    main()
