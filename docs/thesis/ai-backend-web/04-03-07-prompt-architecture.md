## 4.3.7 Prompt Architecture

> **Status:** draft
> **Cross-refs:** §4.1.4 (DP4 — no fine-tuning), all §4.3 subsections reference specific prompts
> **Source:** `src/agent_brain/agent/resources/system_prompts/` (7 MD files), `few_shots/` (5 JSON files), `skills/` (3 MD files)
> **Figures needed:** Table (per-stage model configuration matrix) — included in text

---

The system uses zero fine-tuning — all model adaptation is achieved through prompting. Off-the-shelf models (Qwen2.5 7B Instruct, AITeamVN/Vietnamese_Embedding, faster-whisper with PhoWhisper weights) are used without any weight modification. Domain adaptation — Vietnamese restaurant vocabulary, menu knowledge, ordering workflow, hospitality tone — is encoded entirely in the prompt files loaded at agent startup. The prompt architecture is therefore a first-class design element, not an implementation detail (DP4, §4.1.4).

### 4.3.7.1 Prompt File Inventory

Seven system prompts, five few-shot example sets, and three skill documents are loaded from the `src/agent_brain/agent/resources/` directory at agent startup (`prompt_utils.py`). All are stored as markdown or JSON files, editable without code changes — a menu swap or tone adjustment requires only editing prompt files and restarting the agent.

#### System Prompts (7 files)

Each LLM-calling node has its own system prompt defining its role, reasoning protocol, output format, and constraints:

| File | Used By | Lines | Content |
|------|---------|-------|---------|
| `router_agent.md` | SLM router | 83 | 4-step reasoning protocol: check context → identify primary intent → check sequential intents → produce JSON. Defines 5 intent categories with Vietnamese trigger keywords. Includes 10 inline examples as a markdown table. |
| `order_worker_agent.md` | Order worker | ~80 | Cart CRUD rules: when to add vs remove vs clear vs confirm. Vietnamese quantity patterns ("2 phần", "1 dĩa"). Modification handling ("ít cay", "thêm hành"). Multi-item extraction from compound utterances. |
| `search_agent.md` | Search worker | ~60 | Query rewriting instructions: translate conversational Vietnamese into concrete search keywords. "ĐÃ BIẾT" injection format for avoiding redundant queries. Non-food delegation triggers (restaurant info, hours, parking, complaints). |
| `payment_worker_agent.md` | Payment dispatch | ~20 | (Defensive — the payment_dispatch node is deterministic and does not call the LLM. Exists for completeness.) |
| `response_rewriter.md` | Response node (search, off-menu) | ~50 | Natural Vietnamese waiter persona: polite, warm, using "dạ", "ạ", "anh/chị". Tone guidelines: enthusiastic about food, apologetic about missing items, never robotic. |
| `chat_rewriter.md` | Response node (chat) | ~40 | Open-ended conversational waiter persona. Guidelines for handling small talk, complaints, out-of-domain questions. Memory grounding: use `curated_memory` to answer follow-up questions about previously discussed dishes. |
| `waiter_agent.md` | (shared, injected into multiple prompts) | ~30 | Core waiter identity: "Em là nhân viên phục vụ của quán Ốc Quậy." Restaurant metadata (hours, address). Service boundaries. |

**Language.** All system prompts are written in Vietnamese. This is an intentional design choice: prompting the model in Vietnamese produces more natural Vietnamese output than prompting in English and asking for Vietnamese output. The model's internal representations for Vietnamese are activated more strongly when the prompt itself is in Vietnamese.

#### Few-Shot Examples (5 files)

Static JSON files loaded at boot and injected into prompts at runtime. Each example is a `(human, ai)` message pair formatted via `FewShotChatMessagePromptTemplate` for KV-cache optimization — the static examples are placed before dynamic content, so their attention KV pairs are cached across turns.

| File | Used By | Examples | Coverage |
|------|---------|----------|----------|
| `router.json` | SLM router | 14 | Single-intent (ORDER, SEARCH, PAYMENT, CHAT, ORDER_CONFIRM), multi-intent (ORDER+PAYMENT, SEARCH+ORDER), teencode ("ad", "vs", "ck"), short affirmations ("ừ", "ok", "được") |
| `order_worker.json` | Order worker | 9 | `add_cart` (single item, multi item, with modifier, with quantity), `remove_cart`, `clear_cart`, `confirm_order`, `delegate` |
| `search_worker.json` | Search worker | 9 | Keyword search, attribute search ("món chay"), price-based search, recommendation request, restaurant info delegation, delegate on already-known items |
| `payment_worker.json` | Payment dispatch | 3 | `request_payment` with and without table_id, payment inquiry delegation |
| `utterances.json` | Semantic router (offline) | 192 | Per-intent centroid construction utterances (used only for centroid computation, not at runtime) |

**Few-shot design principle.** Examples are selected to cover failure modes observed in zero-shot testing, not random samples. The 14 router examples include specifically: (a) "ok" at IDLE vs "ok" at AWAITING_CONFIRMATION — to teach context-dependent routing; (b) teencode abbreviations — because they appear frequently in Vietnamese casual speech; (c) multi-intent compound sentences — because the SLM must learn to decompose them into ordered intent lists.

#### Skill Documents (3 files)

Markdown files defining behavioral rules, loaded alongside system prompts via `active_skills` parameters (`prompt_utils.py:60-79`):

| File | Content | Purpose |
|------|---------|---------|
| `hospitality.md` | Vietnamese restaurant service etiquette | Defines greeting patterns ("Dạ, em chào anh/chị ạ"), politeness levels (always use "dạ"/"ạ"), refusal phrasing ("Dạ, món đó không có, em xin lỗi ạ"), upselling guidelines |
| `menu_grounding.md` | Rules for menu-as-ground-truth | Enforces that the agent must never claim knowledge of dishes not on the menu; when uncertain, the agent must search the menu rather than inventing; price information must come from menu data, not LLM knowledge |
| `no_service_response.md` | Domain boundary definition | What the waiter should refuse to answer: inappropriate requests, unrelated questions (politics, other businesses), personal questions. Provides refusal templates: "Dạ, em chỉ biết về thực đơn và quán ạ." |

**Skill composition.** Skills are injected into prompts via the `build_system_prompt` function: the core prompt is concatenated with active skill content, separated by double newlines. Skills are model-agnostic — the same `hospitality.md` can be injected into the order worker, search worker, and response rewriter, ensuring consistent waiter persona across all LLM calls.

### 4.3.7.2 Dynamic Context Injection

Static prompts define behavior; dynamic context provides the specific situation the LLM must act on. Three forms of dynamic context are injected at runtime:

**Conversation history** (router, workers, response). The last 2–3 conversation turns are extracted and formatted as text:
- **Router:** Last 2 user-assistant pairs, formatted as `User: ...\nAI: ...` (`slm_router_node.py:67-80`). This enables context-dependent classification: "ok" at AWAITING_CONFIRMATION → ORDER_CONFIRM, but at IDLE → CHAT.
- **Workers:** Last 3 turns via `last_n_turns()` (`prompt_utils.py:7-34`), which preserves full turn spans including ToolMessages from validation retries. This ensures the LLM sees its own prior failed attempt plus validator feedback on retry.
- **Response (chat path):** Full conversation history, formatted as `Khách: ...\nEm: ...` pairs, enabling memory-grounded responses.

**Order stage** (router, workers). The current `order_stage` (`IDLE`, `DRAFTING`, `AWAITING_CONFIRMATION`, `CONFIRMED`) is injected as a plain string. For the router, it is accompanied by an explicit instruction (`slm_router_node.py:53-59`): "If stage is AWAITING_CONFIRMATION, a short affirmation is ORDER_CONFIRM, not CHAT."

**Validator feedback** (workers, on retry). When the validator rejects a tool call, the `feedback` string is injected into the worker's dynamic context block with the header "SYSTEM FEEDBACK (MANDATORY FIX)." The feedback includes the specific error and correction instruction, enabling the LLM to fix its output without re-reasoning from scratch.

**"ĐÃ BIẾT" context** (search worker). Items from prior search results and the current cart are injected as a list of already-known items. This prevents the LLM from re-searching topics already discussed, reducing redundant RAG queries.

### 4.3.7.3 KV-Cache Optimization

Ollama's prefix caching is exploited for latency reduction. The prompt sequence is ordered to maximize the static (cacheable) prefix:

```
[SystemMessage (static)]        ← cached KV
[FewShotMessage 1 (static)]     ← cached KV
[FewShotMessage 2 (static)]     ← cached KV
...
[FewShotMessage N (static)]     ← cached KV
[DynamicSuffixMessage]          ← NOT cached (changes per turn)
[ConversationHistory]           ← NOT cached (changes per turn)
[UserMessage]                   ← NOT cached (new utterance)
```

The `build_dynamic_suffix` function (`prompt_utils.py:106-114`) explicitly places dynamic content (table_id, cart state, validator feedback) at the **end** of the prompt sequence to preserve the static prefix. If dynamic content were interleaved with static prompt elements, the KV cache would be invalidated for all subsequent tokens, eliminating the latency benefit.

### 4.3.7.4 Per-Stage Model Configuration

All three LLM-calling nodes use the same Qwen2.5 7B Instruct model served by Ollama, but configured differently per stage:

| Stage | Node | Temperature | Key Configuration | Rationale |
|-------|------|-------------|-------------------|-----------|
| **Router (Tier 2)** | `slm_router_node` | 0.0 | `with_structured_output(IntentPrediction)` | Deterministic classification — same utterance always maps to same intents. Structured output forces valid JSON with controlled enum values. |
| **Worker (ORDER/SEARCH)** | `order_worker`, `search_worker` | 0.1 | `tool_choice="any"` | Slightly-above-zero temperature allows variant phrasings in tool arguments ("ít cay" vs "it cay") while keeping tool selection near-deterministic. Forced tool call prevents the LLM from producing text instead of tool calls. |
| **Response** | `response_node` | 0.3 | Free-form generation | Higher temperature enables varied Vietnamese phrasing for natural conversation. The LLM receives only verified structured data as context, so hallucination risk is minimized — higher temperature is safe. |

**Model sharing.** A single Ollama model instance serves all three stages. This is achieved by creating three `ChatOllama` objects pointing to the same model name (`qwen2.5:7b-instruct`) with different runtime parameters. Ollama's `keep_alive=-1` pins the model in GPU VRAM, so there is zero model-switching overhead between stages — the same loaded model handles routing, decision, and response.

**Warmup.** At agent startup (`server.py`), a warmup ping is sent to Ollama: a trivial prompt ("ping") is sent through the response LLM. This triggers Ollama to load the model into GPU VRAM before any customer request arrives. Without this warmup, the first customer utterance would experience 15–30 seconds of cold-start latency while the 7B model loads.

### 4.3.7.5 Prompt Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Vietnamese-first** | All system prompts, few-shot examples, and skill documents are written in Vietnamese. The model thinks in Vietnamese, not translated English. |
| **Explicit reasoning protocols** | Every LLM prompt includes numbered reasoning steps (router: 4 steps; workers: implicit in tool descriptions). The model is told *how* to think, not just *what* to output. |
| **Failure-driven example selection** | Few-shot examples are chosen to cover observed failure modes, not random utterances. Each example teaches a specific skill the model lacked in zero-shot testing. |
| **Separation of static and dynamic** | Static content (system prompts, few-shots) is positioned before dynamic content (conversation history, feedback) to maximize KV-cache reuse. |
| **Skill composition** | Behavioral rules (hospitality, menu grounding, domain boundaries) are isolated in separate skill files, composed into prompts via `build_system_prompt`. Changing the waiter's tone or boundaries requires editing one file, not seven. |
| **Menu exclusion from decision prompts** | The LLM workers (order, search) do not see the full menu. They only need to decide *which action to take* and extract *what the customer said* — menu validation happens in the deterministic validator, not the LLM. This keeps worker prompts compact (~200 tokens vs ~3000 with the menu). |
| **No fine-tuning** | All model adaptation is achieved through prompting. This eliminates the need for a labeled training dataset (which does not exist for Vietnamese restaurant ordering) and enables rapid iteration — a prompt change takes effect at the next agent restart without retraining. |
