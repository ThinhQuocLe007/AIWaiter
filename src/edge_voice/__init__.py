"""AI Waiter — edge voice device.

Runs on the **Jetson** (or any machine with a microphone + speaker).
Hosts the voice pipeline: Silero VAD → PhoWhisper STT → text-only POST to
the agent (``POST /chat`` on the server) → edge-tts reply.

Voice-specific code (VAD / STT / TTS / queues) lives in ``perception/`` and
``output/``. The voice loop entry point is ``main.py``.

Shared infra (env / settings / logger / tracing) lives in
``src/agent_brain/config`` and ``src/agent_brain/utils`` — the voice device
imports those from the brain package, so the two roles share one source of
truth for configuration and logging.
"""
