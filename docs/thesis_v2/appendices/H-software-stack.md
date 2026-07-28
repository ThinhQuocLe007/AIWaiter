# Appendix H. Software and Network Stack

Every software component the system runs, with the version each experiment in Chapter 5 was
carried out against. Versions are pinned exactly by `uv.lock` for the Python dependencies, so a
machine matching the hardware in §5.1.1 and §5.1.2 and the versions below reproduces the
measurements reported in that chapter. Referenced from §5.1.3.

| Component | Version | Role |
|-----------|---------|------|
| Operating system | Ubuntu 22.04 LTS | Server and robot |
| ROS 2 | Humble Hawksbill | Robot middleware, navigation and sensor drivers |
| Python | 3.10 | All server-side and robot-side Python code |
| uv | (lock file: `uv.lock`) | Python dependency management, exact version pinning |
| Ollama | 0.5.x | LLM serving on the server |
| PhoWhisper medium | via faster-whisper 1.0.x (CTranslate2 backend) | Vietnamese STT inference on the robot |
| Silero VAD | (bundled model, ~1.5 MB) | Voice activity detection on the robot |
| Piper TTS | (community Vietnamese voice, ~200 MB) | Speech synthesis on the robot |
| FastAPI | 0.115.x | Backend orchestrator REST and WebSocket server |
| LangGraph | 0.2.x | Agent graph execution engine |
| SentenceTransformers | 3.x | Embedding model loading and inference |
| FAISS | 1.8.x | Dense vector index for menu retrieval |
| Vue 3 | 3.5.x (Vite 6.x) | Three single-page web applications |
| SQLite | 3.x (system) | Business ledger and conversation checkpoints |

The server and the robot communicate over a local WiFi network with no internet dependency in
normal operation, and the three web applications connect to the server over the same network.
