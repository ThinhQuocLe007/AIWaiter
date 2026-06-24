# Testing Tracker — AI Waiter

> Single place to track what has been validated, on which target, and how.
> Detailed voice procedures live in [vad-mic-testing-guide.md](vad-mic-testing-guide.md);
> this file is the checklist + the web (ordering) test procedure.
> Updated: 2026-06-24 · Branch: `feat/payment-tool`.

Legend: ✅ done · 🔄 in progress · ⬜ todo · ⏸ deferred

---

## 1. Status at a glance

| Area | Component | How tested | Ubuntu (dev laptop) | Jetson Orin |
|---|---|---|---|---|
| **Voice** | Mic + VAD (segment speech) | `scripts/probe_vad.py [--mic]` | ✅ | ⬜ |
| **Voice** | STT — file → text | `scripts/probe_stt.py --audio f.wav` | 🔄 | ⬜ |
| **Voice** | STT — live mic → text | `scripts/probe_stt_live.py` | ⬜ | ⬜ (USB mic on device) |
| **Voice** | TTS (text → speech) | _no probe yet_ | ⬜ | ⬜ |
| **Web** | Ordering UI (customer_ui) — **production build** | §3 below (`make build` + `serve`) | ⬜ | ⬜ |
| **Web** | Backend API (orders/tables/payments) | §3.3 below (curl) | ⬜ | ⬜ |
| **Brain** | Embedding / Retrieval (RAG) | `evals/scripts/eval_retrieval.py` | ⏸ later | ⏸ later |
| **Brain** | Router / Workers / E2E agent | `evals/scripts/eval_*.py` (needs Ollama) | ⏸ later | ⏸ later |

---

## 2. Voice testing — two targets, two workflows

The split exists because **SSH does not forward microphone audio**: the mic must
be local to the process. See full details + troubleshooting in
[vad-mic-testing-guide.md](vad-mic-testing-guide.md) (§9 live mic, §10 Jetson).

### 2.1 Ubuntu laptop — live, real-time

You sit at the laptop, so its built-in mic is local → speak and watch text appear.

```bash
uv run python scripts/probe_stt_live.py     # mic → VAD → STT → text, Ctrl-C to stop
```

(No Ollama needed — this is just the perception path, not the agent.)

### 2.2 Jetson — record → scp → transcribe (SSH-only)

You reach the Jetson over SSH, so you cannot stream your laptop mic into it.
Record locally, copy the file, transcribe on the Jetson:

```bash
# on the laptop
arecord -d 20 -f S16_LE -r 16000 test.wav            # 20s, 16 kHz mono
scp test.wav jetson@<jetson-ip>:~/AI_Waiver/
# on the jetson (ssh)
uv run python scripts/probe_stt.py --audio test.wav  # watch tegrastats for RAM
```

This validates the STT model + **unified-memory footprint** on the real target.
It does **not** validate live on-device mic latency — for that, plug a USB mic
into the Jetson and run `probe_stt_live.py` in the SSH shell (the USB mic is local
to the Jetson process, so it works). Full table of what is / isn't covered: §10 of
the voice guide.

### 2.3 Still missing for voice

- [ ] **TTS** (`ai_waiter_core/output/tts_engine.py`) — text → speech, the output
  half of the pipeline. No standalone probe yet.
- [ ] **Full voice loop** (`ai_waiter_core/main.py`) — mic → VAD → STT → agent →
  TTS. Needs Ollama (`gemma4:e2b-it-qat`) running. Run after TTS is validated.

---

## 3. Web (ordering) testing — production mode

Scope: the **customer_ui** ordering tablet web + its **backend**, in **production
build** (not the `make frontend` dev server). Kiosk/Panel are out of scope here.

Production mode = the static build in `dist/` served by `vite preview` (`make
serve`), talking to the FastAPI backend. The dev-only Vite proxy does not apply to
preview, so a `preview.proxy` block was added to
[customer_ui/vite.config.ts](../src/frontends/customer_ui/vite.config.ts) to route
`/api` + `/ws` → FastAPI:8000 (same as dev). Without it the production build's API
calls 404.

### 3.1 Build + serve

```bash
make backend          # terminal 1 — FastAPI :8000 (seeds tables 1–6 + menu)
make build            # build customer_ui → src/frontends/customer_ui/dist/
make serve            # terminal 2 — serve dist/ on http://0.0.0.0:4173 (preview)
```

Open **http://localhost:4173** (or `http://<laptop-ip>:4173` from a tablet on the
same LAN — `host: true` is set).

### 3.2 Manual flow to verify (production build)

- [ ] Page loads, menu fetches (217 dishes) — no blank screen / fetch error.
- [ ] Browser devtools → Network: `/api/menu` returns **200** (proxy works).
- [ ] Add items to cart → cart total is correct.
- [ ] Confirm order → button shows "Đang gửi đơn…", then success.
- [ ] (cross-check) order appears on the Panel KDS, or via `GET /api/orders`.
- [ ] Service screen: if the table is being served with an open order, "Gọi món
  thêm" / "Thanh toán" both work.
- [ ] Payment: QR screen shows the right amount → "Đã thanh toán xong" →
  table flips to `DA_THANH_TOAN`.

### 3.3 Backend API smoke test (independent of UI)

```bash
curl -s localhost:8000/health
curl -s localhost:8000/menu | head -c 200          # raw menu json
curl -s localhost:8000/tables                       # tables 1–6
# seat → order → pay (adjust ids)
curl -s -X POST localhost:8000/seatings -H 'content-type: application/json' \
  -d '{"table_id":1,"party_size":2}'
curl -s -X POST localhost:8000/orders -H 'content-type: application/json' \
  -d '{"table_id":1,"items":[{"dish_id":1,"qty":1}]}'
curl -s -X POST localhost:8000/payments/1
```

Reset demo data between runs: `make reset` (backend must be running) or delete
`storage/db/orchestrator.db` and restart the backend.

### 3.4 Web notes

- [ ] After validating, decide on the real-deploy story: let **FastAPI serve the
  static `dist/`** (same origin → no proxy needed) instead of `vite preview`.
  Listed as a future idea in [PROGRESS.md](PROGRESS.md) §4.

---

## 4. Deferred — embedding / brain

Not testing now (user request). When resumed:
- Build the FAISS index + centroids first: `uv run python scripts/setup.py`.
- Retrieval quality: `uv run python evals/scripts/eval_retrieval.py`.
- Compare embedding models: `scripts/bench_embedding.sh`.
- Router / E2E: `evals/scripts/eval_router.py`, `eval_e2e.py` (need Ollama up).
