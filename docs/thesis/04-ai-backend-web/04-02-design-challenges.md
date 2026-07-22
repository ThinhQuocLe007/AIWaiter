## 4.2 Design Challenges

> **Status:** draft
> **Cross-refs:** §2.3–§2.7 (needs and gaps), §4.1 (requirements), §4.3 (architecture solutions)
> **Figures needed:** none

---

The six needs identified in Chapter 2 translate into six concrete design challenges that the AI, backend, and web system must solve. Each challenge follows from a specific gap in prior work. The proposed solutions in §4.3–§4.9 address these challenges directly; the experiments in Chapter 5 validate that they are met.

---

### C5 — The Vietnamese Informality Frontier

**Source:** Need 3 (§2.4) — informal Vietnamese speech to correct, validated actions.

Vietnamese restaurant speech presents four linguistic phenomena that break conventional intent classification approaches:

1. **Teencode and informal vocabulary.** Common texting abbreviations — "ck" (chuyển khoản), "z" (vậy), "ad" (anh/chị), "nhiêu" (bao nhiêu), "hông" (không) — are absent from formal training corpora. Traditional NLU pipelines (Rasa, Dialogflow) and lightweight classifiers (fastText, SetFit) treat these as out-of-vocabulary tokens and fail to classify.

2. **Context-dependent ambiguity.** The same utterance has different intents at different conversation stages. "ok em" at order confirmation → ORDER; "ok em" at greeting → CHAT. The utterance text alone carries zero signal — the classifier must incorporate conversation state to disambiguate.

3. **Multi-intent compounding.** Vietnamese naturally combines actions: "Cho 2 Ốc Hương rồi tính tiền luôn" (Give me 2 Ốc Hương then the bill) = ORDER + PAYMENT. Single-label classifiers force a single choice, losing the secondary intent.

4. **Domain vocabulary.** Dish names ("Ốc Hương Xốt Trứng Muối") are out-of-distribution for general-domain embedding models. The classifier must either be trained on or exposed to restaurant-specific vocabulary.

**The trade-off.** LLM-based routing (few-shot prompting with Qwen2.5 7B) handles all four challenges simultaneously — the LLM understands teencode, reads conversation context from the prompt, identifies multiple intents, and handles domain vocabulary through its general knowledge. But it does so at ~1.8 seconds per classification, with non-deterministic output (same input can produce different classifications). Trained ML classifiers are fast (~0.17ms) and deterministic but brittle — they operate on text alone, blind to conversation state.

**What the system must achieve.** Accuracy ≥ 90% on all four challenge categories, latency under 1ms, and deterministic output — three properties that prior approaches trade against each other. This challenge motivates the MLP classifier with context features (§4.5.2), which adds conversation state (order_stage, cart, search context) as 10-dimensional input features alongside the 768-dimensional sentence embedding.

---

### C6 — VRAM Is Zero-Sum on the Edge

**Source:** Need 2 (§2.3) — Vietnamese voice on the edge.

The Jetson Orin Nano has 8 GB of unified LPDDR5 memory shared among all processes: ROS2 navigation, sensor drivers, voice processing, and — if co-located — the LLM itself. The VRAM budget decomposes as:

| Consumer | Approximate VRAM |
|----------|-----------------|
| ROS2 navigation (costmaps, TF, Nav2) | ~500 MB |
| Sensor drivers (LiDAR, D435, IMU) | ~200 MB |
| Silero VAD | <10 MB |
| faster-whisper medium (float16) | ~1.5 GB |
| Piper TTS (Vietnamese voice) | ~200 MB |
| **Subtotal (edge pipeline)** | **~2.5 GB** |
| Qwen2.5 7B (float16) | **~6–8 GB** |
| **Total with co-located LLM** | **~9–10 GB** |

The LLM alone would consume 75–100% of the Jetson's memory, leaving insufficient headroom for ROS2 navigation and the operating system. 4-bit quantization could reduce the LLM to ~4 GB, but at significant quality degradation — particularly for Vietnamese, which is underrepresented in training data and thus more sensitive to quantization artifacts.

**The constraint.** The LLM cannot run on the Jetson. It must run on a separate server with a dedicated GPU. The voice pipeline (VAD + STT + TTS) must remain on the Jetson because the microphone and speaker are physically attached. The system must split compute between edge and server without introducing unacceptable network latency in the voice interaction loop.

**Why not cloud STT?** Cloud speech services (Google Cloud, Viettel AI, FPT.AI) circumvent the Jetson VRAM constraint by offloading STT computation. However, they require internet connectivity — a restaurant WiFi failure would break the entire voice pipeline at its most vulnerable point (the STT model is the only heavy-inference component on the Jetson that cannot be downscaled without accuracy loss). Local STT survives WiFi drops: the audio never leaves the Jetson; only the text transcript (a few bytes) is sent to the server when connectivity recovers.

**What the system must achieve.** A clean edge/server split where latency-critical operations (VAD, STT, TTS) run locally on the Jetson within the 2.5 GB VRAM budget, the LLM runs on a server GPU, and the total round-trip time from speech end to reply start stays under 5 seconds (NFR2). This challenge motivates the edge/server split architecture in §4.4.1.

---

### C7 — The LLM Is a Probabilistic Component in a Deterministic System

**Source:** Need 3 (§2.4) — post-generation validation gap.

The conversational agent's core intelligence comes from a large language model (Qwen2.5 7B), which is inherently probabilistic. Given the same input, the LLM may produce different outputs. In a chatbot, this is acceptable — a slightly different rephrasing of a recommendation is fine. In a transactional restaurant agent, the stakes are higher:

- A hallucinated dish name ("Pizza Hải Sản") reaching `add_cart` → wrong food appears in the customer's bill.
- A hallucinated quantity (999) reaching `confirm_order` → impossible order created.
- An invalid state transition (confirming an empty cart) → inconsistent backend state.

These are not hypothetical failures. They are expected behavior from any LLM at temperature > 0. The constraint is not to prevent hallucination — that would require fine-tuning, which the system explicitly avoids (prompt-based adaptation only, DP4). The constraint is to **detect and block** hallucination before any LLM output reaches external systems — on every single LLM call, without human review.

**Existing mitigations are insufficient.** Constrained decoding enforces valid JSON schema but cannot validate semantic correctness — `{"name": "Pizza Hải Sản"}` is valid JSON. RAG reduces hallucination probability by providing relevant context but does not eliminate it — the LLM may still ignore the context. Human-in-the-loop eliminates risk but defeats autonomous operation.

**What the system must achieve.** A deterministic validation layer that sits between every LLM tool call and its execution, checking: (a) dish names against the 217-item menu, (b) quantities against reasonable bounds, (c) state transitions against the cart state machine, (d) ambiguous names that require clarification. The layer must reject invalid calls with corrective feedback, loop back to the LLM for retry (max 3 attempts), and trigger a circuit breaker with apology if retries are exhausted. This challenge motivates the deterministic validator in §4.5.4.

---

### C8 — Sensory Queries Don't Match Menu Structure

**Source:** Need 4 (§2.5) — bridging Vietnamese food descriptions to menu knowledge.

Customers describe what they want in experiential terms: "món gì ấm bụng cho ngày lạnh?" (what's warm and filling for a cold day?), "có món nào ăn cay cay không?" (anything spicy?). Restaurant menus are structured by dish name, category, and price — not by the feeling a dish produces. The word "ấm" (warm) does not appear in any menu entry. The word "cay" (spicy) appears only as part of compound dish names, not as a standalone searchable attribute.

Standard RAG — embed the user's query, retrieve the most similar document chunks, generate an answer grounded in those chunks — assumes that the query and the documents share vocabulary. For "Ốc Hương giá bao nhiêu?", the string "Ốc Hương" appears in multiple menu entries → retrieval succeeds. For "món gì ấm bụng?", zero lexical overlap with any dish → the embedding vector for this query is closer to general-domain sentences about comfort than to any food item → retrieval fails.

**Why BM25+FAISS hybrid retrieval alone isn't enough.** BM25 handles exact keyword matches ("Ốc Hương", "Lẩu Thái") well. FAISS handles semantic similarity ("món cay" → dishes tagged with "cay" in metadata). But neither bridges the full sensory gap — BM25 finds nothing for "ấm bụng" because those words don't appear; FAISS may retrieve vaguely related dishes (anything with "nước" or "canh") but cannot distinguish which ones are actually "ấm bụng" from those that just happen to share embedding space with warmth-related concepts.

**What the system must achieve.** A closed-loop pipeline where: (a) an LLM actively rewrites the customer's vague sensory query into concrete Vietnamese search terms before retrieval ("ấm bụng" → "lẩu, súp, cháo, món nước nóng"), reasoning about Vietnamese culinary categories; (b) the rewritten query drives both BM25 keyword search and FAISS semantic retrieval via RRF fusion; (c) after retrieval, an LLM evaluates which results match the original sensory intent and rephrases them in natural Vietnamese, detecting empty results and responding appropriately rather than hallucinating. This challenge motivates the closed-loop knowledge retrieval pipeline in §4.6.

---

### C9 — The Backend Is a State Machine the AI Drives

**Source:** Need 5 (§2.6) — coordinating AI decisions with restaurant operations. Also Need 6 (§2.7) — multi-role web interfaces.

A restaurant has multiple operational roles: customers ordering at tablets, kitchen staff managing orders, a manager monitoring the floor, and robots delivering food. Each role sees a different subset of the system state, and all must be synchronized in real time. The AI agent — not a human operator — is the primary driver of state changes: the agent creates orders (→ kitchen panel must update), modifies cart state (→ customer tablet must update), and dispatches robots (→ fleet dashboard must update).

**The polling problem.** Traditional restaurant systems (POS, KDS) use REST polling — clients refresh every 5–10 seconds. A new order created by the AI agent sits invisible on the kitchen display for 0–10 seconds until the next poll. For a voice interaction where the customer says "Cho 2 Ốc Hương" and expects to see the cart update immediately on the tablet, a 5-second delay breaks the conversational flow.

**The single-machine constraint.** The entire system must run on one server machine (DP1 — centralized brain). This means one FastAPI process handles all REST endpoints, WebSocket connections (4+ client types, multiple instances each), SQLite writes (orders, payments, sessions), and real-time event broadcasting — without cloud infrastructure for load distribution.

**The SQLite concurrency constraint.** SQLite uses file-level write locks. If robot heartbeats (4+ Hz per robot) wrote directly to the database, they would contend with order and payment transactions — write requests queue behind the lock holder. At restaurant scale (dozens of orders per hour, not thousands per second), this is not a throughput problem but a contention problem at the wrong moment: a payment transaction should not be delayed by a heartbeat write.

**What the system must achieve.** Role-based WebSocket push (not polling) for all real-time updates — events are delivered within ~50ms of occurrence. RAM-only storage for high-frequency telemetry (robot pose, battery) to avoid SQLite write contention. Session-scoped state enforced through guarded transitions (seating → ordering → payment → release), not arbitrary CRUD. Single-server deployment with no cloud dependency. This challenge motivates the backend orchestrator architecture in §4.7 and the fleet management design in §4.7.4.

---

### C10 — Robot-Table Voice Binding Must Survive Disconnection

**Source:** Need 5 (§2.6.2) — dynamic robot-table voice binding gap.

Robots are table-agnostic — any robot can serve any table. When a customer presses "Talk to AI" on the tablet at table 3, the system must know which robot's microphone to activate. But the robot at table 3 may have moved to deliver food to table 5, or its WiFi may have dropped, or it may have been reassigned to a higher-priority task.

**The binding lifecycle problem.** The binding is not static — it is established when a robot physically arrives at a table and released when the robot departs. The binding must survive: (a) WiFi disconnection — the robot's WebSocket drops but the task is reassigned to another robot; the new robot must rebind to the same table without the customer needing to press a button again; (b) concurrent tables — two customers at different tables both press "Talk to AI" simultaneously; the system must route each command to the robot currently at that table, without cross-talk; (c) rapid rebinding — a robot completes a delivery at table 3, immediately receives a call task for table 3, and re-binds; the customer's microphone activation must route to the correct robot within milliseconds.

**The watchdog requirement.** A hung robot (process running but not responding, OS-level hang) can maintain an open WebSocket while producing no heartbeats. Without liveness monitoring, the dispatcher would continue assigning tasks to a zombie robot while the customer waits. The watchdog must detect silence, mark the robot offline, release its table binding, and requeue its tasks — within a bounded timeout that does not leave the customer waiting indefinitely.

**What the system must achieve.** Dynamic bind/unbind of `table_id → robot_id` on robot arrival/departure. Watchdog with 30-second heartbeat timeout for zombie detection. Automatic task requeue and voice rebind on disconnection. The customer should not perceive which robot is listening — the system abstracts over individual robots. This challenge motivates the voice bridge and fleet watchdog in §4.7.4.
