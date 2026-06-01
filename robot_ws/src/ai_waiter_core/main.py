import os
from dotenv import load_dotenv
from ai_waiter_core.agent import AIWaiterGraph
from ai_waiter_core.utils import flush_traces, log_struct

# 1. Load environment variables (including LangSmith keys)
load_dotenv()

def main():
    log_struct("Starting AI Waiter Test Session")
    
    # 2. Initialize the Agent Graph
    agent = AIWaiterGraph()
    
    # 3. Simulate a conversation
    table_id = "Table_01"
    session_id = None # Let it generate a new UUID v7
    
    queries = [
        "Menu có món gì ngon không em?",
        "Cho anh 2 Phở Bò và 1 Coca nhé",
        "Thôi đổi thành 3 Phở Bò đi",
        "Xác nhận đặt hàng cho anh",
        "Tính tiền cho anh luôn"
    ]
    
    for query in queries:
        print(f"\n[USER]: {query}")
        
        # 4. Chat with the agent
        result = agent.chat(query, table_id=table_id, session_id=session_id)
        
        # Capture the session_id from the first turn to keep the thread linked
        if session_id is None:
            session_id = result["session_id"]
            print(f"[SYSTEM]: Started new session: {session_id}")
            
        print(f"[AGENT]: {result['response']}")
        print(f"--- (Trace sent to LangSmith) ---")

    # 5. Flush traces before exiting
    log_struct("Session complete. Flushing traces...")
    flush_traces()
    print("\nTest complete. You can now check your results at https://smith.langchain.com")

if __name__ == "__main__":
    main()
