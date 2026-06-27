import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

from dotenv import load_dotenv
load_dotenv()

from src.agent_brain.agent import AIWaiterGraph
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

agent = AIWaiterGraph()

query = "Cho mình 2 phần Ốc Hương xốt trứng muối"
table_id = "T_test"

print(f"\n[USER]: {query}")
print("-" * 50)

result = agent.chat(query, table_id=table_id)

print(f"\n[AGENT RESPONSE]: {result['response']}")
print(f"[FINAL STAGE]: {result['final_stage']}")
print(f"[STATUS]: {result['status']}")

# Get full state to inspect tool calls
config = {"configurable": {"thread_id": result['session_id']}}
state = agent.app.get_state(config)

print("\n" + "=" * 50)
print("MESSAGE HISTORY:")
print("=" * 50)

for i, msg in enumerate(state.values.get('messages', [])):
    msg_type = type(msg).__name__
    if isinstance(msg, AIMessage):
        tool_calls = getattr(msg, 'tool_calls', None)
        print(f"\n[{i}] {msg_type}:")
        print(f"  Content: {msg.content[:100] if msg.content else '(empty)'}")
        if tool_calls:
            print(f"  Tool Calls: {tool_calls}")
    elif isinstance(msg, ToolMessage):
        print(f"\n[{i}] {msg_type}:")
        print(f"  Name: {msg.name}")
        print(f"  Content: {msg.content[:200]}")
    elif isinstance(msg, HumanMessage):
        print(f"\n[{i}] {msg_type}: {msg.content}")
    else:
        print(f"\n[{i}] {msg_type}: {msg}")

print("\n" + "=" * 50)
print("STATE KEYS:")
print("=" * 50)
print(f"  order_stage: {state.values.get('order_stage')}")
print(f"  active_cart: {state.values.get('active_cart')}")
print(f"  current_intents: {state.values.get('current_intents')}")
