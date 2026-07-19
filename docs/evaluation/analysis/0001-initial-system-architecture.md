# ADR 0001: Initial System Architecture

## Context
The AI Waiter project requires a robust architecture to handle voice interaction, autonomous navigation via ROS 2, and complex order management.

## Decision
We implemented a 4-layer orchestration architecture:
1.  **Perception Layer**: Silero VAD + Pho-Whisper STT for Vietnamese speech.
2.  **Orchestration Layer**: LLM Agent with shared chat history.
3.  **Action Layer**: Tools for RAG (Menu Search), Ordering, and Payments.
4.  **Output Layer**: TTS and WebSocket-based iPad UI.

## Consequences
- **Pros**: Modular, supports complex Vietnamese natural language, integrates with hardware.
- **Cons**: High latency for simple commands if always routed through the LLM.

## References
- [Original Overview](file:///home/lequocthinh/Desktop/KNOWLEDGE_HUB/MY%20DOCUMENT/AI%20ARCHITECTURE/AI_WAITER/overview.md)
