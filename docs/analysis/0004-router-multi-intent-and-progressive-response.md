# 0004: Router Multi-Intent and Progressive Response

This document outlines the architectural plan and step-by-step implementation guide to refactor the AI Waiter Core Routing and Response system. The changes are structured into two independent development phases.

---

### Phase 1: Multi-Intent SLM Router (SLM Refactoring) - [COMPLETE] ✅
*Goal: Remove the `COMPLEX` intent category and train the SLM fallback to output a structured, ordered list of core intents (e.g., `["MENU", "ORDER"]`).*

### Step 1.1: Schema Modifications - [COMPLETE]
*   **File**: [routing.py](file:///home/lequocthinh/Desktop/KNOWLEDGE_HUB/CODE/AI_Waiter/robot_ws/src/ai_waiter_core/ai_waiter_core/schemas/routing.py)
    *   Removed `"COMPLEX"` from the `IntentType` literal.
    *   Refactored `IntentPrediction` Pydantic model to return a list of intents: `intents: List[IntentType]`.
*   **File**: [state.py](file:///home/lequocthinh/Desktop/KNOWLEDGE_HUB/CODE/AI_Waiter/robot_ws/src/ai_waiter_core/ai_waiter_core/agent/state.py)
    *   Changed `current_intent` from a single string to a list `current_intents` in `AgentState`.

### Step 1.2: System Prompt & Few-Shots Refactoring - [COMPLETE]
*   **File**: [router_agent.md](file:///home/lequocthinh/Desktop/KNOWLEDGE_HUB/CODE/AI_Waiter/robot_ws/src/ai_waiter_core/ai_waiter_core/agent/resources/system_prompts/router_agent.md)
    *   Added rules for sequential Vietnamese multi-intent mapping.
*   **File**: [router.json](file:///home/lequocthinh/Desktop/KNOWLEDGE_HUB/CODE/AI_Waiter/robot_ws/src/ai_waiter_core/ai_waiter_core/agent/resources/few_shots/router.json)
    *   Loaded 12 highly diverse balanced multi-intent few-shots.

### Step 1.3: Hybrid Router Node Refactoring - [COMPLETE]
*   **File**: [hybrid_router_node.py](file:///home/lequocthinh/Desktop/KNOWLEDGE_HUB/CODE/AI_Waiter/robot_ws/src/ai_waiter_core/ai_waiter_core/agent/nodes/hybrid_router_node.py)
    *   Refactored cosine similarity fast-tracking (using `HYBRID_CONFIDENCE_THRESHOLD = 0.85`).
    *   Resolved nested `"metadata"` dictionary legacy keys to enable the **15ms semantic fast-path**.
    *   Added order-preserving deduplication for consecutive intents.

### Step 1.4: Evaluation Suite Modification - [COMPLETE]
*   **File**: [router_eval.json](file:///home/lequocthinh/Desktop/KNOWLEDGE_HUB/CODE/AI_Waiter/evals/data/router/router_eval.json)
    *   Updated the 15 complex cases to expect exact target intent lists.
*   **File**: [eval_router.py](file:///home/lequocthinh/Desktop/KNOWLEDGE_HUB/CODE/AI_Waiter/evals/scripts/eval_router.py)
    *   Added warm-up logic to eliminate cold-start load time bias.
    *   *Result*: Achieved **91.25% accuracy** and a **1.12s warm average latency** over 80 benchmark cases!

---

## Phase 2: Progressive Response & Streaming Loop (LangGraph Refactoring) - [IN PROGRESS] ⏳
*Goal: Modify the LangGraph workflow to execute intents sequentially in a single turn, providing progressive notification updates to the customer to minimize perceived latency.*

### 🚀 Key Optimizations and Architectural Patterns Added:

1.  **Ollama KV Prompt Caching (Prefill Optimization)**:
    *   *Concept*: Ollama caches the key-value representation of the large system prompt and few-shots in memory.
    *   *Execution*: For subsequent turns in the same conversation session, prefill time is reduced to **0ms**. The SLM's processing latency will drop from 2.0s to **300ms–500ms** in live production runs.
2.  **Instant Dispatcher Acknowledgment (Zero Perceived Latency)**:
    *   *Concept*: Immediately notify the customer about what the system understood and how it plans to execute the tasks.
    *   *Execution*: When the router identifies multiple intents (e.g., `["MENU", "ORDER"]`), a specialized notification is streamed back immediately (~100ms) before the worker chains execute.
    *   *Message Template*: *"Dạ, em đã nhận được các yêu cầu về **[Xem thông tin món ăn]** và **[Đặt món]**. Em xin phép xử lý từng việc cho mình ngay đây ạ..."*

### Step 2.1: Graph Transition Restructuring
*   **File**: [graph.py](file:///home/lequocthinh/Desktop/KNOWLEDGE_HUB/CODE/AI_Waiter/robot_ws/src/ai_waiter_core/ai_waiter_core/agent/graph.py)
    *   Modify `route_to_worker` conditional edge function to act as a popping stack router:
        ```python
        def route_to_worker(state: AgentState) -> Literal["order_worker", "menu_worker", "payment_worker", "chat_worker", "end"]:
            intents = state.get("current_intents", [])
            if not intents:
                return "end"
            # Return the first intent in the list
            next_intent = intents[0]
            if next_intent == "ORDER":
                return "order_worker"
            elif next_intent == "MENU":
                return "menu_worker"
            ...
        ```
    *   Update worker node transitions to loop back to the popping router edge instead of transitioning directly to `END`.

### Step 2.2: Instant Dispatcher Acknowledgment Node
*   **File**: [new] `dispatcher_acknowledgment_node.py`
    *   Create a fast edge node that runs immediately after the Hybrid Router.
    *   If `len(state["current_intents"]) > 1`, compile a friendly sequential outline of tasks and stream it to the client.

### Step 2.3: Worker Progressive Output Messaging
*   **Files**: 
    *   `robot_ws/src/ai_waiter_core/ai_waiter_core/agent/nodes/menu_worker_node.py`
    *   `robot_ws/src/ai_waiter_core/ai_waiter_core/agent/nodes/chat_worker_node.py`
    *   `robot_ws/src/ai_waiter_core/ai_waiter_core/agent/nodes/payment_worker_node.py`
*   **Logic**:
    *   Before executing its response chain, each worker pops its corresponding intent from `state["current_intents"]`.
    *   If there are further intents remaining in the stack (e.g. `["ORDER"]` is left after `MENU`), the worker appends a progressive notification to its message (e.g., *"Dạ, để em tiến hành lên đơn các món chay cho anh/chị nhé... ⏳"*).
    *   This provides a neat, sequential narrative.

### Step 2.4: Verification of Streaming
*   Create a verification script `scratch/verify_streaming.py` that executes a multi-intent query using `app.stream()` and captures/prints the output of each node transition to confirm progressive updates.ogressive updates.
