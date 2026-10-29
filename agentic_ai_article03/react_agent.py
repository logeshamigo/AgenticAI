"""ReAct-style iterative model/tool execution with OpenAI Agents SDK."""
from agents import Agent, Runner, function_tool, MaxTurnsExceeded
from business import order_lookup, tracking_lookup

@function_tool
def get_order_status(order_id: str) -> dict:
    """Fetch an authorized order and its tracking identifier."""
    return order_lookup(order_id)

@function_tool
def get_carrier_tracking(tracking_id: str) -> dict:
    """Fetch tracking for an authorized shipment."""
    return tracking_lookup(tracking_id)

agent = Agent(
    name='Order Research Agent', model='gpt-4.1-mini',
    instructions='Investigate order questions using read-only tools. Never invent evidence or execute write operations. Explain missing evidence.',
    tools=[get_order_status, get_carrier_tracking],
)

def main():
    try:
        result = Runner.run_sync(agent, 'Investigate why order ORD-1042 is delayed and recommend next steps.', max_turns=6)
        print(result.final_output)
    except MaxTurnsExceeded:
        print('Stopped: maximum model turns reached')

if __name__ == '__main__':
    main()
