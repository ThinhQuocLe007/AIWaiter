## 5.1 System Under Test

Every experiment in this chapter ran on the hardware below. Nothing was measured in simulation or
on a different machine. The chassis and its two MC520P30 motors were purchased as a unit; the
sensor suite, the navigation software and the voice pipeline were added by the group.

**Table 5.1.** Server and robot hardware.

| Tier | Component | Specification |
|---|---|---|
| Server | GPU | NVIDIA GeForce RTX 3070 Laptop, 8 GB VRAM, CUDA 12.1 |
| Server | CPU / RAM | Intel Core i7 x86-64 / 32 GB |
| Server | Language model | Qwen2.5 14B Instruct at `q6_K`, served by Ollama, pinned in VRAM |
| Robot | Compute | NVIDIA Jetson Orin Nano, 8 GB unified memory, CUDA 12.6 |
| Robot | LiDAR | RPLiDAR A2M8, 360° 2D laser scanner, 8 Hz |
| Robot | Depth camera | Intel RealSense D435, RGB-D, 30 Hz |
| Robot | IMU | MPU6050, 6-axis gyroscope and accelerometer |
| Robot | Audio | USB condenser microphone 16 kHz mono, Bluetooth speaker |
| Robot | Display | 7-inch LCD touchscreen |

Both machines run Ubuntu 22.04 LTS and Python 3.10 with dependencies pinned by `uv.lock`; the full
version list is in Appendix H. The server runs the agent graph, the backend orchestrator and the
retrieval indices. The robot runs ROS 2 Humble for navigation and sensor drivers, and the voice
pipeline of §4.4. One model serves all three LLM roles in the agent, the tool-calling workers, the
query and result rewriters, and the response generator, and it is loaded once at startup and kept
resident. Results that depend only on the trained classifier, the deterministic validator or the
retrieval indices do not involve the language model at all, and are identified as such where they
appear.

The two machines communicate over local WiFi with no internet dependency in normal operation, and
the three web applications connect to the server over the same network. Only small structured
messages cross it, transcripts of roughly 100 bytes, pose coordinates and navigation goals, because
audio, video and LiDAR scans are processed on the robot and reduced to those messages first.

The Jetson's 8 GB of unified memory is the constraint behind that split. The Chapter 3 navigation
stack and the voice pipeline of §4.4 together consume nearly all of it, leaving no room for the
language model, which is measured in §4.3.1 and is why the model runs on the server.

A photograph of the assembled platform with labelled sensors is provided in Appendix F.
