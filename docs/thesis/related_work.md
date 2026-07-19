CHAPTER 2: RELATED WORK & THEORETICAL FOUNDATIONS
2.1 Service Robots in the Restaurant Industry
- What is a service robot — autonomous systems that perform tasks in human environments
- Why restaurants: labor shortage, service consistency, contactless demand post-pandemic
- Current landscape: commercial robots exist (Servi, Bellabot, Keenon) — they navigate and carry trays, interaction is via touchscreen
- The missing dimension: they don't understand natural language, especially not Vietnamese
- Opportunity: combine autonomous navigation with conversational AI for a complete waiter experience
- This chapter builds the knowledge foundation for such a system, layer by layer
2.2 Mobile Robot Fundamentals
- 2.2.1 Classification of mobile robots: wheeled, legged, aerial — why wheeled for indoor flat floors
- 2.2.2 Drive mechanisms: differential drive, Ackermann steering, omnidirectional — how each works, diagrams, where each is used
- 2.2.3 Holonomic vs non-holonomic: definition, mathematical constraint (V_y = 0 for TWD), why it matters for motion planning
- 2.2.4 TWD kinematic model: wheel velocities V_A, V_B, forward kinematics V_x = (V_A+V_B)/2, V_ω = (V_B−V_A)/W, track width W, turning radius R, Euler pose integration, non-holonomic constraint
- 2.2.5 Indoor autonomous navigation pipeline: Perception → Localization → Mapping → Planning → Control
2.3 Sensors for Indoor Mobile Robots
- 2.3.1 Sensor categories: proprioceptive (encoders, IMU) vs exteroceptive (LiDAR, camera)
- 2.3.2 2D LiDAR: time-of-flight laser scanning, 360° planar measurement, range, angular resolution, scan data structure
- 2.3.3 RGB-D camera: active stereo depth sensing, depth map + RGB image, field of view, structured light vs stereo
- 2.3.4 IMU: 3-axis accelerometer + 3-axis gyroscope, raw readings, bias, drift characteristics
- 2.3.5 Wheel encoders: incremental encoder (Hall effect), pulses per revolution (PPR), quadrature decoding (N = P·4·G), distance traveled per tick
2.4 Odometry and Sensor Fusion
- 2.4.1 What is odometry: estimating pose from motion sensors — wheel odometry, inertial odometry, visual odometry, laser odometry
- 2.4.2 The drift problem: why every odometry source accumulates unbounded error over time. Wheel slip, IMU bias integration, rounding
- 2.4.3 Why fuse sensors: different sensors have different error profiles. Encoder: good short-term motion, drifts from slip. IMU: good fast turns, heading drifts from integration. Each compensates the other's weakness
- 2.4.4 Kalman filter concept: state estimate + uncertainty. Predict step (motion model) → Update step (sensor measurement). Covariance matrices encode trust in each source
- 2.4.5 Extended Kalman Filter: why the basic KF fails for non-linear robot motion. Local linearization via Jacobians. Predict/update still works after approximation
2.5 ROS2 and Autonomous Navigation
- 2.5.1 Why a robotics middleware: multiple sensors, multiple algorithms, concurrent execution, need structured communication
- 2.5.2 ROS2 fundamentals: Nodes (independent programs), topics (publish/subscribe), services (request/reply), actions (long-running goals with feedback), DDS transport layer
- 2.5.3 TF and URDF: coordinate frame tree (map→odom→base_footprint→base_link→sensor_links), robot model description, why spatial transforms matter
- 2.5.4 SLAM (Simultaneous Localization and Mapping): the chicken-and-egg problem. Front end (sensor processing, feature extraction, scan matching via ICP). Back end (graph optimization). Filter-based vs graph-based SLAM. Loop closure: detecting revisits, correcting accumulated drift
- 2.5.5 RTAB-Map: graph-based SLAM. LiDAR provides geometric constraints (ICP scan matching). RGB-D camera provides visual appearance for loop closure (bag-of-words place recognition). Memory management for real-time operation. Output: 2D occupancy grid map
- 2.5.6 Nav2 navigation: costmaps (global + local) with inflation layers. Global planner (A* or Dijkstra on global costmap). Local controller (pure pursuit — lookahead point, non-holonomic constraint enforced). Behavior tree for recovery
- 2.5.7 Gazebo simulation: physics engine, sensor plugins (LiDAR, camera, IMU, differential drive) producing ROS2-compatible messages. Why sim-first-then-real
2.6 Large Language Models for Conversational AI
- 2.6.1 Transformer architecture: self-attention mechanism (Attention(Q,K,V) = softmax(QK^T/√d_k)V), multi-head attention, residual connections, layer normalization, feed-forward sub-layers. Why this design parallelizes on GPUs and captures long-range dependencies
- 2.6.2 Autoregressive generation: next-token prediction, probability distribution over vocabulary, temperature parameter T controlling randomness (T→0: deterministic, T>0: varied). Why low temperature for decision tasks, slightly higher for natural conversation
- 2.6.3 SLM vs LLM: model size vs capability vs latency trade-off. Small models for narrow classification tasks, large models for generation. Local serving via Ollama — quantized models, persistent GPU memory, single API
- 2.6.4 Prompt engineering: zero-shot vs few-shot (in-context learning). Structured output — JSON schema, constrained decoding, turning an LLM into a program-callable component. Prefix caching — static prompt prefix reused across turns, reducing latency
2.7 Intent Routing and Retrieval-Augmented Generation
- 2.7.1 Intent routing: why classify user input before processing — different intents need different subsystems. Semantic router — sentence embeddings, per-intent centroid vectors, cosine similarity. Softmax with temperature T — converts similarities to probabilities. Gap gating — winner must have sufficient probability margin above runner-up, else defer to fallback. Two-tier approach: fast semantic path (~15ms) for confident cases, LLM fallback for ambiguous ones
- 2.7.2 Retrieval-Augmented Generation: the hallucination problem — LLM knowledge frozen at training, cannot know a restaurant's specific menu. RAG pipeline: Index (offline) → Retrieve (online, top-k) → Generate (LLM grounds answer in retrieved documents)
- 2.7.3 Dense vs sparse retrieval: Dense (FAISS, SentenceTransformer embeddings): captures semantic similarity ("something sour and spicy" → spicy dishes). Sparse (BM25, TF-IDF): captures exact keyword matches (dish names, ingredient terms). Hybrid approach — run both in parallel, fuse with Reciprocal Rank Fusion: score(d) = Σ 1/(k + rank_d). Needs only ranks, not comparable scores
- 2.7.4 Vietnamese language considerations: Vietnamese is tonal (6 tones), monosyllabic but with compound words ("bún bò Huế" is one lexical unit). Tokenization via underthesea for BM25. Vietnamese embedding models — AITeamVN/BGE-M3 (1024-dim), PhoBERT variants
- 2.7.5 LLM agents and LangGraph: From single prompt to agent loop: observe → decide → act → repeat. Tool calling (function calling) — describe operations as typed functions, model outputs structured invocation. LangGraph StateGraph — shared typed state flowing through nodes (LLM calls, tool execution, deterministic code), conditional edges for branching and bounded loops, checkpointer for conversation memory across turns. Why decompose into a graph — testable per node, bounded failure modes, deterministic validation interleaved between LLM calls
2.8 Speech Processing for Voice Interaction
- 2.8.1 The voice pipeline: Microphone → VAD → STT → (dialogue agent from 2.6–2.7) → TTS → Speaker
- 2.8.2 Voice Activity Detection: neural frame-level speech probability classification (Silero VAD family). Endpointing rules — silence duration threshold, maximum utterance length. Why energy-thresholding is insufficient in noisy environments
- 2.8.3 Speech-to-Text: encoder-decoder Transformer architecture. Whisper family — pretrained on 680k hours of multilingual audio. faster-whisper — optimized inference (CTranslate2). Vietnamese variant (PhoWhisper) — fine-tuned for tonal accuracy. Beam search decoding (beam_size). Challenges — ambient noise, regional accents, unusual dish names cause transcription errors
- 2.8.4 Text-to-Speech: neural TTS — learns prosody and pronunciation from recorded speech. Vietnamese voices — cloud options (vbee, FPT.AI, edge-tts) vs edge options (Piper TTS). Trade-offs — latency, quality, offline capability
- 2.8.5 Vietnamese speech challenges: 6 tones (ngang, huyền, sắc, nặng, hỏi, ngã), complex diacritics often misrecognized, monosyllabic structure requires accurate tone disambiguation, teencode and informal speech common in restaurant settings
2.9 Supporting Technologies
- 2.9.1 Web frontends: Single-page applications (SPA) with reactive frameworks (Vue.js, Vite). Component-based architecture — reusable UI elements, declarative data binding, automatic re-render on state change
- 2.9.2 Backend API: FastAPI — high-performance async Python framework, automatic request validation from type hints (Pydantic), auto-generated OpenAPI documentation. REST — stateless resource-oriented API design. WebSocket — persistent full-duplex channel for real-time push (robot telemetry, order status, voice events)
- 2.9.3 Data storage: SQLite — embedded relational database, serverless, single-file, ACID transactions. Suitable for single-server moderate-volume deployment
- 2.9.4 Model serving: Ollama — local LLM runtime, quantized open-weight models, persistent GPU memory (keep_alive), single local API for multiple models

===========================================================================
