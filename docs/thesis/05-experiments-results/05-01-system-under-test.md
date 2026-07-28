## 5.1 System Under Test

This section describes the hardware, the robot platform, and the software stack that every
experiment in this chapter was run on. Nothing was measured in simulation or on a different
machine. The physical robot is introduced here because its sensors, its compute board and its
8 GB memory ceiling shape several of the architectural decisions evaluated in §5.4 and §5.5,
and because the system is a waiter robot, not only a software pipeline: the hardware is part
of what was built.

### 5.1.1 Server Hardware

The server is a single x86-64 laptop that runs the LLM, the conversational agent, the backend
orchestrator and the menu retrieval indices. It is the central machine in the three-tier
topology described in §4.3.

| Component | Specification |
|-----------|--------------|
| GPU | NVIDIA GeForce RTX 3070 Laptop GPU, 8 GB VRAM, CUDA 12.1 |
| CPU | Intel Core i7 (x86_64) |
| RAM | 32 GB |
| Storage | 1 TB NVMe SSD |
| Operating system | Ubuntu 22.04 LTS |

The language model is Qwen2.5 14B Instruct, served by Ollama with `keep_alive = -1` so the model
is loaded once at startup and stays pinned in VRAM for the lifetime of the server process. A
warmup ping at agent startup ensures the model is loaded before the first customer utterance
arrives. The same model serves all three LLM roles in the agent: the tool-calling workers, the
query and result rewriters, and the response generator. The selection of this model class
follows from the survey of Vietnamese-capable LLMs in §2.4.3.

The evaluation reported in this chapter was carried out on the deployment configuration,
`qwen2.5:14b-instruct-q6_K` serving the tool-calling workers, the rewriters and the response
generator. Results that depend only on the trained classifier, the deterministic validator or
the retrieval indices do not involve the language model at all, and are identified as such where
they appear.

### 5.1.2 Robot Platform

The robot is a purchased two-wheel differential-drive chassis carrying the sensors, the compute
board and the peripherals that make it a waiter. The mechanical platform (chassis, two
MC520P30 DC motors with encoders, an STM32 microcontroller and an MPU6050 IMU) was bought as
a unit. The research contribution begins at ROS 2 integration: the sensor suite, the
navigation software and the voice pipeline were added by the group.

| Component | Specification | Role |
|-----------|--------------|------|
| Compute | NVIDIA Jetson Orin Nano, 8 GB unified memory, CUDA 12.6 | Runs ROS 2, navigation stack and voice pipeline |
| LiDAR | RPLiDAR A2M8, 360° 2D laser scanner, 8 Hz | SLAM and obstacle avoidance |
| Depth camera | Intel RealSense D435, RGB-D, 30 Hz | Loop closure (RTAB-Map) and ArUco docking |
| IMU | MPU6050 (6-axis gyroscope + accelerometer) | Angular rate for EKF sensor fusion |
| Microphone | USB condenser microphone, 16 kHz mono | Voice capture |
| Speaker | Bluetooth speaker | Voice reply playback |
| Display | 7-inch LCD touchscreen, HDMI + USB touch | Customer-facing tablet interface |
| Motors | 2 × MC520P30 DC motors with encoders (P = 1024 pulses/rev, G = 30:1) | Differential-drive locomotion |
| Battery | 12 V Li-ion pack | Powers all onboard electronics |

The Jetson's unified memory is shared by the CPU and GPU, and the
operating system kills processes that exceed it. Before this chapter's work begins, the
navigation and localisation stack built in Chapter 3 already holds approximately 3.7 GB: ROS 2
middleware (~0.2 GB), sensor drivers (~0.5 GB), RTAB-Map localisation (~2.0 GB), Nav2
planners and costmaps (~0.7 GB), and EKF odometry fusion (~0.3 GB). The voice pipeline
described in §4.4 takes a further ~3.7 GB, filling nearly all of the remainder. The
consequence, that the LLM cannot run on the robot, is validated in §4.3.1 with measured
resident-memory figures; the navigation experiments in §5.3 test whether the Chapter 3 stack
performs correctly within this budget, and the latency experiments in §5.4.6 confirm that the
server-side LLM placement adds no unacceptable delay.

A photograph of the assembled robot platform with labelled sensors is provided in Appendix F.

### 5.1.3 Software & Network Stack

Every software component and its version are pinned so that any experiment in this chapter can
be reproduced on a machine with the same specification.

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

The server and the robot communicate over a local WiFi network with no
internet dependency in normal operation. The three web applications (the customer tablet, the
entrance kiosk and the management panel) connect to the server over the same WiFi. Only small
structured messages cross the network: text transcripts (~100 bytes), pose coordinates and
navigation goals. Audio, video and LiDAR scans are processed on the robot and reduced to these
messages before transmission. The architecture and the protocol choices are described in full
in §4.3.
