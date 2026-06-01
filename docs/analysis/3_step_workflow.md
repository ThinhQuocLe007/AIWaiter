# AI Waiter: Multi-Agent Architecture & 3-Step Verification Workflow

This document summarizes the decentralized SLM (Small Language Model) architecture designed for the AI Waiter, ensuring zero-hallucination ordering and strict state machine enforcement.

## 1. Core Architectural Paradigm

Instead of relying on a slow, monolithic LLM to handle all tasks, the system uses a **Decentralized Multi-Agent Graph** (via LangGraph).

- **The Blackboard (`AgentState`)**: The central source of truth. Contains the chat transcript (`messages`), session context (`table_id`), extracted routing data (`current_intent`), temporary RAG data (`search_context`), and the active state machine (`active_cart`, `order_stage`).
- **The Router (`slm_router_node`)**: A lightweight traffic cop that determines user intent and passes execution to a specialist worker.
- **The Specialists (`nodes/*_worker_node.py`)**: Tiny, lightning-fast SLMs (e.g., 3B parameters) given hyper-focused prompts. The `order_worker` handles orders, the `menu_worker` handles search, etc.

---

## 2. The 3-Step Verification Workflow (Order State Machine)

To prevent the LLM from skipping steps or hallucinating orders, the ordering process is physically locked behind a strict 3-step state machine governed by the `order_stage` variable.

> [!IMPORTANT]
> **The Golden Rule:** The LLM *never* directly edits the `order_stage`. The stage is strictly transitioned by Python Tools and Validator Nodes.

### Step 1: DRAFTING (Iterative Assembly)
- **Trigger**: User orders an item (e.g., *"Cho 1 phở bò"*).
- **Process**:
  1. The `order_worker` reads the `MENU_NAMES` injected into its System Prompt and drafts a structured `OrderItem`.
  2. The worker calls the `sync_cart` tool.
  3. The `sync_cart` tool updates the `active_cart` and hardcodes `state["order_stage"] = "DRAFTING"`.
- **LLM Behavior**: Because the stage is `DRAFTING`, a Dynamic Prompt forces the LLM to simply acknowledge the item and ask: *"Anh/chị có gọi thêm gì không?"* (Would you like anything else?). It is blocked from confirming.

### Step 2: AWAITING_CONFIRMATION (The Guardrails)
- **Trigger**: The graph routes the drafted cart through the Safety Layer before the LLM can speak again.
- **Process**:
  1. **Deterministic Validator (Python)**: Uses `difflib` to fuzzy-match the drafted item against the real DB. If it's a typo, Python auto-corrects it. If it's a total mismatch (e.g., "Pizza"), Python rejects it and loops back to the LLM to ask the user to clarify.
  2. **Critic Node (QA LLM)**: Checks the cart for logic and tone. It rejects impossible requests (e.g., *"Pho without noodles"*).
  3. If both pass, the graph promotes the state to `AWAITING_CONFIRMATION`.
- **LLM Behavior**: The dynamic prompt now instructs the LLM: *"Summarize the cart and explicitly ask for confirmation."* The `confirm_order` tool is finally unlocked for use.

### Step 3: CONFIRMED (Execution)
- **Trigger**: User explicitly agrees (e.g., *"Ok, chốt đi"*).
- **Process**: 
  1. The `order_worker` calls the newly unlocked `confirm_order` tool.
  2. The tool saves the verified cart to `order.db` and hardcodes `state["order_stage"] = "CONFIRMED"`.
- **LLM Behavior**: The LLM notifies the user that the kitchen has received the order.

---

## 3. Key Engineering Solutions

1. **Solving the Single-Intent Bottleneck**: By extracting `current_intent` and supporting a `"COMPLEX"` intent (or list of intents), the system can seamlessly handle multi-part queries (e.g., *"1 Pho and what is the wifi?"*) through worker handoffs.
2. **Solving Context Bloat**: RAG search results are saved to `state["search_context"]` instead of polluting the `messages` history. This preserves the SLM's memory window.
3. **Bi-Directional Frontend Sync**: The `AgentState` can accept data from an external iPad (`frontend_context`) and the agent can call tools to push URL changes back to the iPad, creating a true Co-pilot experience.
