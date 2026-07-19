"""AI Waiter — edge voice device.

Runs on the **Jetson** (or any machine with a microphone + speaker).
Hosts the voice pipeline: Silero VAD → PhoWhisper STT → text-only POST to
the agent (``POST /chat`` on the server) → edge-tts reply.

Voice-specific code (VAD / STT / TTS / queues) lives in ``perception/`` and
``output/``. The voice loop entry point is ``main.py``.

Dependency rule: this package must import NOTHING that lives in ``--extra server``.
The Jetson installs only ``--extra voice``, so anything reaching into the brain's LLM
stack (langsmith / langchain / langgraph) breaks the robot at import time. Settings are
still shared — ``src/agent_brain/config`` is pure pydantic-settings, which sits in the
base deps — but logging is local (``log.py``) precisely to avoid dragging
``src/agent_brain/utils`` (and its tracing imports) along.
"""
