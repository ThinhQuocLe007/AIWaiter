import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

from dotenv import load_dotenv
load_dotenv()

from src.agent_brain.agent import AIWaiterGraph
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

agent = AIWaiterGraph()

# Test multi-turn conversation
queries = [
    "Cho mình 2 phần Ốc Hương xốt trứng muối",
    "Đúng rồi, xác nhận đặt luôn",
]

table_id = "T_test_confirm"
session_id = None

for query in queries:
    print(f"\n[USER]: {query}")
    print("-" * 50)

    result = agent.chat(query, table_id=table_id, session_id=session_id)
    session_id = result['session_id']

    print(f"[AGENT]: {result['response']}")
    print(f"[STAGE]: {result['final_stage']}")

# Get full state
config = {"configurable": {"thread_id": session_id}}
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
