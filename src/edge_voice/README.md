# AI Waiter — Edge Voice Device

The voice pipeline for the AI Waiter robot. Runs on the **Jetson** (or any
machine with a working microphone + speaker). Command-driven: it idles, and when
the tablet pushes a "talk to AI" button the device captures one utterance,
POSTs the text to the agent (`POST /chat` on the server), and speaks the reply
back via TTS.

The mic + STT + TTS live on the device — the **tablet has no microphone** in
production (no HTTPS requirement, no sandbox limitations). The tablet is a
**mirror** of the live conversation, fed by the backend's `role=customer` WebSocket.

## Role split
- **Voice (this package)** — Silero VAD + PhoWhisper STT + edge-tts +
  WebSocket device client. Runs on the Jetson.
- **Brain** — see `../agent_brain/` → LLM, RAG, agent. Runs on the server.
  Receives the transcribed text and decides the reply.
- **Orchestrator** — see `../server_orchestrator/` → FastAPI backend, the
  only writer to `orchestrator.db`. Routes the voice device ↔ tablet ↔ robot.

## Layout
```
src/edge_voice/
├── main.py                      # voice device entry: mic → VAD → STT → POST /chat → TTS
├── config/                      # (placeholder; voice device uses src/agent_brain/config)
├── output/                      # TTS (edge-tts)
│   └── tts_engine.py
├── perception/                  # mic capture + VAD + STT + cross-thread queues
│   ├── queues.py                # speech_queue + text_queue (cross-thread)
│   ├── stt_phowhisper.py        # PhoWhisper
│   └── vad_silero.py            # Silero VAD
├── rewriter/                    # (placeholder; planned utterance rewriter)
└── utils/                       # (placeholder; voice-side logger if needed)
```

## Shared infra
The voice device **does not** have its own config / utils. It imports the brain
package's `src/agent_brain.config` (settings) and `src/agent_brain.utils`
(logger, tracing) so the two roles share one source of truth for env loading and
logging. The empty `config/` / `utils/` / `rewriter/` dirs are placeholders for
future voice-specific code (e.g. a voice-specific logger prefix, an utterance
rewriter pipeline).

## Install

```bash
# from the repo root (Jetson or any voice-capable machine)
uv sync --extra voice               # torch GPU auto-pulled for aarch64 from the Jetson index
# x86 dev machine doing both:
uv sync --extra server --extra voice --extra cu12
```

On Jetson, `faster-whisper` / CTranslate2 is **hand-built** — see
[`../../docs/jetson-ctranslate2-build.md`](../../docs/jetson-ctranslate2-build.md).
The `voice` extra does not pull `faster-whisper` on aarch64.

## Run

```bash
# from the repo root
uv run python src/edge_voice/main.py
# or: make voice
```

`.env` (copied from `.env.template`) must point `AGENT_URL` and `ORCHESTRATOR_URL`
at the server over the network.

## Features
- **Silero VAD** — voice-activity detection, CPU, in its own thread.
- **PhoWhisper STT** — Vietnamese speech recognition (faster-whisper /
  CTranslate2 backend on x86; hand-built on Jetson).
- **edge-tts** — cloud TTS for the agent's reply (Piper offline is a TODO).
- **Resampling** — polyphase scipy resample, native mic rate → 16 kHz.
- **Cross-thread queues** — `speech_queue` (VAD → STT) and `text_queue`
  (STT → main loop).
- **WebSocket voice device** — `role=voice-device&robot_id=<id>` to the backend.
  Idles for `start_listening` commands; binds to a table dynamically (the
  dispatcher sets `table → robot` when the robot arrives at the table).
- **Listen-on-command** — one utterance per `start_listening` command; POSTs
  the text to the agent with the `table_id` tag; the agent mirrors the turn
  back to the tablet via the orchestrator's voice bridge.
