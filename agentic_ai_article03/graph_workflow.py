"""Explicit graph with authorized tools and conditional transition."""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from business import order_lookup, tracking_lookup

class State(TypedDict, total=False):
    order_id: str
    order: dict
    tracking: dict
    outcome: str

def fetch_order(state: State) -> dict:
    return {'order': order_lookup(state['order_id'])}

def route(state: State) -> str:
    return 'tracking' if 'tracking_id' in state['order'] else 'finish'

def fetch_tracking(state: State) -> dict:
    return {'tracking': tracking_lookup(state['order']['tracking_id'])}

def finish(state: State) -> dict:
    if 'error' in state.get('order', {}):
        outcome = 'Cannot access order'
    elif 'error' in state.get('tracking', {}):
        outcome = 'Tracking unavailable'
    else:
        outcome = state.get('tracking', {}).get('status', 'No tracking information')
    return {'outcome': outcome}

builder = StateGraph(State)
builder.add_node('order', fetch_order)
builder.add_node('tracking', fetch_tracking)
builder.add_node('finish', finish)
builder.add_edge(START, 'order')
builder.add_conditional_edges('order', route, {'tracking':'tracking', 'finish':'finish'})
builder.add_edge('tracking', 'finish')
builder.add_edge('finish', END)
graph = builder.compile()

if __name__ == '__main__':
    print(graph.invoke({'order_id':'ORD-1042'}))
