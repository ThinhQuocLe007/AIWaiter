# Perception + Output Layer Refactor — Queues & Streaming

> Scope: introduce typed queue plumbing for the voice perception pipeline, refactor the streaming TTS path to consume the new queues, and prepare the graph layer for token-level streaming. Brain hardening (previous file) is done; this document supersedes that work.

## Context — Why Now

- The voice pipeline (`vad_silero.py` → `stt_phowhisper.py` → `agent.chat()` → `tts_engine.py`) was built 2026-06-13 but its **verification was deferred** (see `docs/logs/2026-06-13-0000-perception-streaming-output-layer.md:90-99`).
- Queues are **inline in `main.py:22-23`** with no central definition, no observability, and no type contracts. The third queue (`StreamingPlayer._queue`) is private to `tts_engine.py:53`.
- `graph.py:186` uses `app.invoke()` which blocks until **every node** finishes (router → worker → validator → tools → state_updater → response_node → END). The first audio byte arrives ~6-10s after the user stops speaking. `response_node.py:70` (`_response_llm.invoke`) is the bottleneck.
- `tts_engine.py:97 speak_streaming` claims "background-synthesize during playback" but actually **synthesizes serially** (sentence N+1 starts only after sentence N finishes playing). The log claim is false.
- The StreamingPlayer's `is_speaking()` check (`tts_engine.py:79`) polls every 4096 samples (~170ms) using a fragile heuristic (`vad_silero.py:54` `len(_current_utterance) > 3`).

## Goals

1. Centralize the cross-thread queues in **`perception/queues.py`** with typed payloads + drop counters
2. Add async queue plumbing in **`output/queues.py`** for streaming TTS (separate file from perception — different concurrency primitive: `asyncio.Queue` vs `queue.Queue`)
3. Refactor `vad_silero.py`, `stt_phowhisper.py`, `tts_engine.py`, `main.py` to consume the new queues
4. **(Deferred)** Add `chat_stream()` to `graph.py` for token-level streaming — user is collecting the streaming knowledge first

## Architecture Delta

```
                  CURRENT                                            NEW
                                                           
main.py:22-23                                              perception/queues.py
  speech_queue = queue.Queue(...)  ─────────────►           speech_queue, text_queue
  text_queue   = queue.Queue(...)                            (AudioChunk, Transcript)
                                                           
tts_engine.py:97                                             output/queues.py
  speak_streaming(                                          synth_queue, playback_queue
    synth S1 → play S1 →                                ◄── (SynthesisJob, AudioSegment)
    synth S2 → play S2 →                                    + barge_in_event
    synth S3 → play S3                                       (asyncio primitives)
  ) — serial pipeline

graph.py:186                                                graph.py (deferred)
  app.invoke(...)                                       ◄── app.astream_events(...) in chat_stream()
  blocks until graph END                                   yields tokens from response_node
  5-8s first-byte latency                                  target: <1s first-byte latency
```

---

## Phase A — `perception/queues.py` (tonight) 🟢

- [ ] **Create `perception/queues.py`** (~80 LOC)
  - [ ] `@dataclass(frozen=True, slots=True) AudioChunk(samples: bytes, timestamp: float, sample_rate: int=16000, duration_s: float=0.0)`
  - [ ] `@dataclass(frozen=True, slots=True) Transcript(text: str, timestamp: float, audio_duration_s: float|None=None)`
  - [ ] Module-level `speech_queue: queue.Queue[AudioChunk]` with `maxsize=10`
  - [ ] Module-level `text_queue: queue.Queue[Transcript]` with `maxsize=10`
  - [ ] `put_speech(chunk)` — non-blocking `put_nowait` with drop counter + `logger.warning` on drop
  - [ ] `put_transcript(t)` — non-blocking with drop counter
  - [ ] `get_transcript(timeout: float = 0.5) -> Optional[Transcript]` — returns `None` on `queue.Empty`
  - [ ] `queue_stats() -> dict` — `{speech_qsize, text_qsize, speech_drops, text_drops}`
  - [ ] `shutdown_all()` — drain both queues for graceful stop
  - [ ] Module-level docstring explaining the threading-model rationale (VAD/STT are CPU-bound daemon threads, not async coroutines)
- [ ] **Update `perception/__init__.py`** — re-export `AudioChunk`, `Transcript`, `speech_queue`, `text_queue`, `put_speech`, `put_transcript`, `get_transcript`, `queue_stats`, `shutdown_all`
- [ ] **Migrate `perception/vad_silero.py`**
  - [ ] Drop `speech_queue` from `__init__` (line 19)
  - [ ] Replace `self.speech_queue.put((audio, timestamp))` (line 81) with `queues.put_speech(AudioChunk(samples=audio, timestamp=timestamp, duration_s=len(audio)/SAMPLE_RATE))`
  - [ ] Keep `is_speaking()` for now (Phase A doesn't change the barge-in signal) — see Open Decision #2
- [ ] **Migrate `perception/stt_phowhisper.py`**
  - [ ] Drop `speech_queue` and `text_queue` from `__init__` (line 11)
  - [ ] Replace `audio, timestamp = self.speech_queue.get(timeout=0.5)` (line 42) with `chunk = queues.speech_queue.get(timeout=0.5); audio, timestamp = chunk.samples, chunk.timestamp`
  - [ ] Replace `self.text_queue.put((text, timestamp))` (line 45) with `queues.put_transcript(Transcript(text=text, timestamp=timestamp, audio_duration_s=chunk.duration_s))`
- [ ] **Migrate `main.py`**
  - [ ] Remove inline `speech_queue = queue.Queue(maxsize=10)` (line 22) and `text_queue = queue.Queue(maxsize=10)` (line 23)
  - [ ] Replace `text, timestamp = text_queue.get()` (line 52) with `transcript = queues.get_transcript(timeout=0.5); if transcript is None: continue`
  - [ ] Update `vad = SileroVAD()` (drop `speech_queue=` kwarg, line 25)
  - [ ] Update `stt = PhoWhisperSTT()` (drop `text_queue=` kwarg, line 26)
  - [ ] Add periodic `queues.queue_stats()` log every 30s (observability)
  - [ ] Update SIGINT/SIGTERM handler: call `queues.shutdown_all()` before stopping VAD/STT
- [ ] **Verify**
  - [ ] Feed `inputs/audio/recording_at_2025-10-20_*.wav` through VAD → STT (bypass PyAudio if no mic) — log transcripts
  - [ ] Confirm drop counters are 0 in quiet operation
  - [ ] SIGINT shutdown: all threads exit cleanly, no zombie processes
  - [ ] `python -c "from ai_waiter_core.perception.queues import speech_queue, text_queue; print('ok')"` works

---

## Phase B — `output/queues.py` + TTS refactor (tonight) 🟢

- [ ] **Create `output/queues.py`** (~100 LOC)
  - [ ] `@dataclass(frozen=True, slots=True) SynthesisJob(text: str, stage: str="IDLE", job_id: int=0)` — `job_id` is monotonic, for barge-in cancel correlation
  - [ ] `@dataclass(frozen=True, slots=True) AudioSegment(samples: np.ndarray, sample_rate: int=24000, job_id: int=0, is_final: bool=False)`
  - [ ] Module-level `synth_queue: asyncio.Queue[SynthesisJob]` with `maxsize=4`
  - [ ] Module-level `playback_queue: asyncio.Queue[AudioSegment]` with `maxsize=4`
  - [ ] Module-level `barge_in_event: asyncio.Event`
  - [ ] `async enqueue_synthesis(job) -> bool` — drop-oldest on overflow (latest text wins), returns True if accepted
  - [ ] `async enqueue_playback(seg)` — drop-oldest on overflow
  - [ ] `trigger_barge_in()` — **synchronous** setter, callable from VAD thread (`asyncio.Event.set()` is thread-safe in CPython)
  - [ ] `clear_barge_in()` — called by synth/player task after handling the interrupt
  - [ ] `async drain()` — clear synth + playback queues, clear `barge_in_event`
  - [ ] `output_stats() -> dict` — `{synth_qsize, playback_qsize, synth_drops, playback_drops, barge_in_set}`
  - [ ] Module-level docstring explaining: (a) why `asyncio.Queue` not `queue.Queue` — TTS/streaming are I/O-bound async coroutines, (b) why a separate file from `perception/queues.py` — different concurrency primitive
- [ ] **Create `output/sentence_splitter.py`** (~20 LOC) — extract `split_vietnamese_sentences` and `SENTENCE_BOUNDARY` regex from `tts_engine.py:25-33`. Single source of truth — to be shared with `graph.py chat_stream()` in Phase C.
- [ ] **Update `output/__init__.py`** — re-export the queue names + helpers + `split_vietnamese_sentences`
- [ ] **Refactor `output/tts_engine.py`**
  - [ ] **Keep** `StreamingPlayer` and its intra-thread `_queue` (sounddevice callback concern, stays private to the player)
  - [ ] **Keep** `synthesize(text, stage) -> np.ndarray` (unchanged)
  - [ ] **Keep** `warmup()` (unchanged)
  - [ ] **Add** `async synth_task()` — consumes `synth_queue`, calls `synthesize`, `await enqueue_playback(AudioSegment(...))`. Respects `barge_in_event` between jobs.
  - [ ] **Add** `async playback_task(player)` — consumes `playback_queue`, calls `player.play_sentence(seg.samples)`. Checks `barge_in_event` between segments. If set, calls `clear_barge_in()` and exits the current sentence early.
  - [ ] **Replace** `speak_streaming()` with two helpers:
    - `async enqueue_response(text, stage, job_id=0)` — splits text with `split_vietnamese_sentences`, enqueues each as a `SynthesisJob`. Returns the number of jobs enqueued.
    - `async await_playback_drain(timeout=None)` — waits until `playback_queue.empty()` AND no segment is currently playing. Used by main loop to know when the response is fully spoken.
  - [ ] Remove the old `speak_streaming` (replaced by the helpers above)
- [ ] **Migrate `main.py`**
  - [ ] Wrap the voice loop in a long-lived `asyncio.run()` (not per-turn `asyncio.run` like today)
  - [ ] At startup: spawn `asyncio.create_task(synth_task())` + `asyncio.create_task(playback_task(player))`
  - [ ] Main loop: `transcript = await queues.get_transcript_async(...)` (or use sync `get_transcript` in a thread)
  - [ ] **Wire barge-in**: when `vad.is_speaking()` flips to True (VAD thread), call `output_queues.trigger_barge_in()` from a polling task or via a `threading.Event` callback
  - [ ] SIGINT handler: `await output_queues.drain()`, cancel synth + playback tasks, `vad.stop()`, `stt.stop()`, `flush_traces()`
  - [ ] Periodic `output_queues.output_stats()` log every 30s
- [ ] **Verify**
  - [ ] Synthesize "Dạ, chào anh chị ạ" — first audio byte in <500ms, total ~1s
  - [ ] Drop counters 0 in quiet operation
  - [ ] Barge-in test: start TTS playback, simulate `trigger_barge_in()` mid-sentence — playback stops within 170ms (one sounddevice callback tick)
  - [ ] Graceful shutdown: SIGINT → all tasks cancel, no leaked threads
  - [ ] `python -c "from ai_waiter_core.output.queues import synth_queue, playback_queue, barge_in_event; print('ok')"` works

---

## Phase C — `graph.py chat_stream()` (DEFERRED — user learning streaming first) 🟡

> Status: user needs to learn about `langgraph.astream_events` and token-level streaming before implementing. Targeting **tomorrow**. This section is a scoping placeholder, not an actionable plan.

### Why this phase exists

`graph.py:186` uses `self.app.invoke(inputs, config)` which returns the final state after every node finishes. The user-facing text is generated by `response_node._response_llm.invoke(...)` which blocks until the full message is complete. With current latency budget of 5-8s LLM + 0.5s TTS, the user waits **~6-10s before hearing anything**.

### Three levels of streaming (for the user's learning)

1. **Node-level**: `app.stream(stream_mode="updates")` — yields one dict per node finish. Saves a few hundred ms. **Not worth the complexity.**
2. **Token-level (target)**: `app.astream_events(version="v2")` — yields LLM tokens as they're generated. **First audio byte in <1s.** This is the target.
3. **Parallel workers**: Multi-intent queries run search + order in parallel. Big win for "phở bò + món nào ngon?" but requires async coordination. **Defer to later.**

### Planned work (when user is ready)

- [ ] Add `async chat_stream(query, table_id, session_id) -> AsyncIterator[dict]` to `AIWaiterGraph` (~30 LOC)
  - [ ] Use `async for event in self.app.astream_events(inputs, config, version="v2")`
  - [ ] Filter for `event["event"] == "on_chat_model_stream"` AND `metadata["ls_model_name"] == settings.RESPONSE_MODEL`
  - [ ] Accumulate tokens, split on `SENTENCE_BOUNDARY` from `output/sentence_splitter.py` (shared with TTS)
  - [ ] Yield `{"phase": "working", "node": ...}` for non-response_node chain events (routing, tool execution)
  - [ ] Yield `{"phase": "speaking", "sentence": ...}` for each complete sentence
  - [ ] Yield `{"phase": "done", "response": ..., "session_id": ..., "final_stage": ...}` on completion
- [ ] Refactor `chat()` to call `asyncio.run(self._collect_stream(query, table_id, session_id))` — backward compat for tests + e2e eval
- [ ] Wire `main.py`: `async for phase in agent.chat_stream(...)` → `await enqueue_synthesis(SynthesisJob(text=phase["sentence"], stage=final_stage))`
- [ ] Verify: end-to-end pipeline `python main.py` → speak "Cho tôi một phở bò" → first audio byte in **<1s**

### Open questions for the user's research

1. `astream_events(version="v2")` — does the current `langgraph` pin in `requirements.txt` support this? If not, what's the version?
2. `metadata["ls_model_name"]` filter — is this the right key? Fallback: filter on `event["name"] == "response_node"`.
3. There are **3 LLM call paths** in the graph today (router, worker, response_node). `chat_stream()` must filter so we only stream response_node's tokens. How does the event metadata disambiguate them?
4. The `chat()` → `asyncio.run(self._collect_stream(...))` wrapper — does this break the existing `evals/scripts/eval_e2e.py` test harness? If so, what's the cheapest fix?

---

## Files Summary

| File | Action | Phase | Est. Lines | Status |
|---|---|---|---|---|
| `perception/queues.py` | CREATE | A | ~80 | 🟢 tonight |
| `perception/__init__.py` | EDIT (re-export) | A | ~10 | 🟢 tonight |
| `perception/vad_silero.py` | EDIT (remove queue arg, use module) | A | ~10 | 🟢 tonight |
| `perception/stt_phowhisper.py` | EDIT (remove queue args, use module) | A | ~10 | 🟢 tonight |
| `main.py` | EDIT (drop inline queues, add stats logging) | A | ~25 | 🟢 tonight |
| `output/queues.py` | CREATE | B | ~100 | 🟢 tonight |
| `output/sentence_splitter.py` | CREATE | B | ~20 | 🟢 tonight |
| `output/__init__.py` | EDIT (re-export) | B | ~10 | 🟢 tonight |
| `output/tts_engine.py` | EDIT (refactor to consume queues, add synth_task + playback_task) | B | ~80 | 🟢 tonight |
| `main.py` | EDIT (long-lived asyncio, synth+playback tasks, barge-in wiring) | B | ~50 | 🟢 tonight |
| `agent/graph.py` | EDIT (add `chat_stream`, refactor `chat` to wrap) | C | ~30 | 🟡 deferred |
| **Total tonight (A + B)** | | | **~395** | |
| **Total when C lands** | | | **~425** | |

## Implementation Order

```
Phase A (perception queues)     ← independent, do first
        ↓
Phase B (output queues + TTS)   ← depends on A (shares queue observability pattern)
        ↓
Phase C (graph streaming)       ← depends on B (uses output/sentence_splitter.py)
```

**Tonight: A → B in sequence. Phase C tomorrow after the user has collected the streaming knowledge.**

---

## Verification (Phase A + B)

- [ ] Feed `inputs/audio/recording_at_2025-10-20_*.wav` through VAD → STT, log transcripts
- [ ] Synthesize "Dạ, chào anh chị ạ" → first audio byte in <500ms
- [ ] Drop counters 0 in quiet operation
- [ ] Barge-in test: trigger mid-sentence, playback stops within 170ms
- [ ] Graceful shutdown via SIGINT — VAD, STT, synth task, playback task all exit cleanly
- [ ] No new lint or type errors
- [ ] Existing tests in `robot_ws/tests/` still pass: `test_agent.py`, `test_agent_ordering.py`, `test_order_flow.py`, `test_ordering_scenarios.py`
- [ ] `evals/scripts/eval_e2e.py` still runs (uses `chat()` which stays backward-compat)

## Open Decisions (review and confirm)

1. **Drop semantics on overflow** — `put_speech` and `put_transcript` use `put_nowait` with counter (drop on full). Alternative: blocking put (caller blocks, may stall VAD). **Recommend: drop-on-full for both.** Audio arrivals faster than STT drains → VAD buffer overflow is the lesser evil vs. blocking VAD and losing real-time detection.
2. **`is_speaking()` in VAD** — should it be derived from queue stats (`speech_queue.qsize() > 0`) or from a separate `threading.Event` `vad.speech_active` that's set on first detected speech and cleared on utterance flush? **Recommend: add `vad.speech_active` Event (Phase A stretch goal).** The current `len(_current_utterance) > 3` heuristic is fragile.
3. **Sentence splitter location** — `output/sentence_splitter.py` (recommended, shared with graph.py) or keep in `tts_engine.py` (back-edge: graph → output). **Recommend: extract.**
4. **Backward compat for `chat()`** — keep signature identical, route through `chat_stream()` internally. All existing tests + e2e eval should pass unchanged. **Recommend.**
5. **`StreamingPlayer._queue`** — stays private to `tts_engine.py` (intra-thread sounddevice callback feeder, not a cross-stage data pipe). Different concern from the new output queues. **Recommend: leave alone.**

## Out of Scope (deferred)

- Phase C (graph streaming) — user learning first, target tomorrow
- Multi-intent parallel worker execution (Level 3 streaming)
- Echo cancellation (mic-during-playback mute or `module-echo-cancel`)
- Token-level streaming inside worker/router LLMs (only `response_node` for now)
- Frontend integration (kiosk → FastAPI / WebSocket)
- ROS / MQTT bridges
- Critic node wiring
- BM25 indexing of `ingredients` + `description`
- Payment idempotency, bank creds in `.env`, webhook endpoint
- Tool-name-vs-intent validation in validator
- `chat()` resetting `search_context` and `loop_count` per turn
- `chat_worker_node.py` (does not exist)
