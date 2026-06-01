import sys
import os
import uuid

# Add robot_ws/src/ai_waiter_core to Python path so we can import everything correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
core_src = os.path.join(project_root, "robot_ws/src/ai_waiter_core")
sys.path.insert(0, core_src)

from ai_waiter_core.agent.agent import get_agent_app
from langchain_core.messages import HumanMessage, AIMessage

def run_test_scenario():
    print("======================================================================")
    print("🔥 STARTING ADVANCED E2E MULTI-TURN ORDER WORKFLOW TEST SCENARIO")
    print("======================================================================\n")
    
    # 1. Initialize the LangGraph agent
    print("[INFO] Initializing LangGraph AI Waiter App...")
    app = get_agent_app()
    print("[SUCCESS] Application compiled successfully.\n")
    
    # 2. Setup session config
    thread_id = f"test_session_adv_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    table_id = "T_test_adv"
    
    # ----------------------------------------------------
    # TURN 1: Initial draft with multiple items & special requests
    # ----------------------------------------------------
    turn_1_input = "Cho bàn mình 1 tô phở bò đặc biệt nhiều hành, và 1 ly Cà phê sữa đá sài gòn ít đường nha"
    print(f"👉 TURN 1 [User]: \"{turn_1_input}\"")
    
    input_state = {
        "messages": [HumanMessage(content=turn_1_input)],
        "table_id": table_id
    }
    
    print("[INFO] Invoking Agent...")
    output_state = app.invoke(input_state, config=config)
    
    # Inspect Turn 1 output messages and state
    messages = output_state["messages"]
    print("\n--- TURN 1 INTERMEDIATE STATE ANALYSIS ---")
    
    tool_calls_t1 = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_t1.append(tc)
                
    print(f"Tool Calls Detected: {[tc['name'] for tc in tool_calls_t1]}")
    if tool_calls_t1:
        print(f"Tool Arguments: {tool_calls_t1[0]['args']}")
        
    print(f"Active Cart: {output_state.get('active_cart')}")
    print(f"Order Stage: {output_state.get('order_stage')}")
    print(f"AI Response: \"{messages[-1].content}\"")
    print("-------------------------------------------\n")
    
    # Asserts for Turn 1
    assert "sync_cart" in [tc["name"] for tc in tool_calls_t1], "ERROR: sync_cart should have been called in Turn 1!"
    assert output_state.get("order_stage") == "AWAITING_CONFIRMATION", f"ERROR: Expected order_stage 'AWAITING_CONFIRMATION', got '{output_state.get('order_stage')}'"
    print("✅ TURN 1 PASSED: Multiple items drafted, special requests extracted, sync_cart triggered, and stage shifted to AWAITING_CONFIRMATION!\n")
    
    # ----------------------------------------------------
    # TURN 2: Interrupted drafting - cancel one item, add another with quantity and special requests
    # ----------------------------------------------------
    turn_2_input = "À không, cho mình hủy ly Cà phê sữa đá sài gòn đi, lấy thay bằng 2 ly Sinh Tố Bơ Dừa không ngọt nha."
    print(f"👉 TURN 2 [User]: \"{turn_2_input}\"")
    
    input_state = {
        "messages": [HumanMessage(content=turn_2_input)],
        "table_id": table_id
    }
    
    print("[INFO] Invoking Agent...")
    output_state = app.invoke(input_state, config=config)
    
    # Inspect Turn 2 output messages and state
    messages = output_state["messages"]
    print("\n--- TURN 2 INTERMEDIATE STATE ANALYSIS ---")
    
    # Find tool calls only in Turn 2
    new_messages_t2 = []
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) and msg.content == turn_2_input:
            break
        new_messages_t2.append(msg)
    new_messages_t2.reverse()
    
    tool_calls_t2 = []
    for msg in new_messages_t2:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_t2.append(tc)
                
    print(f"Tool Calls Detected: {[tc['name'] for tc in tool_calls_t2]}")
    if tool_calls_t2:
        print(f"Tool Arguments: {tool_calls_t2[0]['args']}")
        
    print(f"Active Cart: {output_state.get('active_cart')}")
    print(f"Order Stage: {output_state.get('order_stage')}")
    print(f"AI Response: \"{messages[-1].content}\"")
    print("-------------------------------------------\n")
    
    # Asserts for Turn 2
    assert "sync_cart" in [tc["name"] for tc in tool_calls_t2], "ERROR: sync_cart should have been called in Turn 2 to update the modifications!"
    
    cart_items = output_state.get("active_cart", {}).get("items", [])
    item_names = [item["name"] for item in cart_items]
    
    # Verify the coffee is successfully cancelled/removed
    assert "Cà Phê Sữa Đá Sài Gòn" not in item_names, "ERROR: Cà Phê Sữa Đá Sài Gòn should have been removed!"
    
    # Verify the Avocado Coconut Smoothies are successfully added with correct quantity and requests
    smoothie_item = next((item for item in cart_items if item["name"] == "Sinh Tố Bơ Dừa"), None)
    assert smoothie_item is not None, "ERROR: Sinh Tố Bơ Dừa should be in the cart!"
    assert smoothie_item["quantity"] == 2, f"ERROR: Expected quantity 2 for Sinh Tố Bơ Dừa, got {smoothie_item['quantity']}!"
    assert "không ngọt" in smoothie_item["special_requests"].lower(), f"ERROR: Expected special request 'không ngọt', got '{smoothie_item['special_requests']}'"
    
    # Verify Phở Bò Đặc Biệt remains
    assert "Phở Bò Đặc Biệt" in item_names, "ERROR: Phở Bò Đặc Biệt should still remain in the cart!"
    
    print("✅ TURN 2 PASSED: Dynamic modifications verified! Item cancelled, new item added with quantity/requests, and total price updated successfully!\n")
    
    # ----------------------------------------------------
    # TURN 3: Final confirmation
    # ----------------------------------------------------
    turn_3_input = "Ok đúng rồi đó, đặt đơn luôn giùm mình nhé"
    print(f"👉 TURN 3 [User]: \"{turn_3_input}\"")
    
    input_state = {
        "messages": [HumanMessage(content=turn_3_input)],
        "table_id": table_id
    }
    
    print("[INFO] Invoking Agent...")
    output_state = app.invoke(input_state, config=config)
    
    # Inspect Turn 3 output messages and state
    messages = output_state["messages"]
    print("\n--- TURN 3 INTERMEDIATE STATE ANALYSIS ---")
    
    # Find tool calls only in Turn 3
    new_messages_t3 = []
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) and msg.content == turn_3_input:
            break
        new_messages_t3.append(msg)
    new_messages_t3.reverse()
    
    tool_calls_t3 = []
    for msg in new_messages_t3:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_t3.append(tc)
                
    print(f"Tool Calls Detected: {[tc['name'] for tc in tool_calls_t3]}")
    if tool_calls_t3:
        print(f"Tool Arguments: {tool_calls_t3[0]['args']}")
        
    print(f"Active Cart: {output_state.get('active_cart')}")
    print(f"Order Stage: {output_state.get('order_stage')}")
    print(f"AI Response: \"{messages[-1].content}\"")
    print("-------------------------------------------\n")
    
    # Asserts for Turn 3
    assert "confirm_order" in [tc["name"] for tc in tool_calls_t3], "ERROR: confirm_order should have been called in Turn 3!"
    assert output_state.get("order_stage") == "CONFIRMED", f"ERROR: Expected order_stage 'CONFIRMED', got '{output_state.get('order_stage')}'"
    print("✅ TURN 3 PASSED: Order confirmed in DB, confirm_order triggered, and stage shifted to CONFIRMED!\n")
    
    print("======================================================================")
    print("🎉 ALL ADVANCED TESTS PASSED SUCCESSFULLY!")
    print("======================================================================")

if __name__ == "__main__":
    run_test_scenario()
