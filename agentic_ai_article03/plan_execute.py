"""LLM creates structured, allowlisted plan; application executes with validation."""
from typing import Literal
from pydantic import BaseModel, Field
from agents import Agent, Runner
from business import order_lookup, tracking_lookup

class Plan(BaseModel):
    steps: list[Literal['lookup_order', 'lookup_tracking']] = Field(min_length=1, max_length=2)

planner = Agent(
    name='Order Investigation Planner', model='gpt-4.1-mini', output_type=Plan,
    instructions=('Create a minimal plan for investigating an order delay. '
                  'Only use lookup_order and lookup_tracking, in dependency order; '
                  'return no additional operations.'),
)

def execute_plan(plan: Plan, order_id: str) -> dict:
    evidence = {}
    for step in plan.steps:
        if step == 'lookup_order':
            evidence['order'] = order_lookup(order_id)
            if 'error' in evidence['order']:
                break
        elif step == 'lookup_tracking':
            order = evidence.get('order', {})
            if 'tracking_id' not in order:
                evidence['error'] = 'tracking_requires_authorized_order'
                break
            evidence['tracking'] = tracking_lookup(order['tracking_id'])
            if 'error' in evidence['tracking']:
                break
    return evidence

def main():
    output = Runner.run_sync(planner, 'Plan an investigation of delayed order ORD-1042.', max_turns=2)
    plan = output.final_output
    if not isinstance(plan, Plan):
        raise TypeError('Planner did not return a validated Plan')
    print('Plan:', plan.model_dump())
    print('Evidence:', execute_plan(plan, 'ORD-1042'))

if __name__ == '__main__':
    main()
