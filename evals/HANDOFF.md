# Cascade recording + evaluation — handoff

This packet covers the one experiment that cannot run on an 8 GB laptop, because it needs
Whisper-medium and the voice stack resident at the same time. Everything else in Chapter 5
runs on the author's machine.

**What it measures.** Every other AI experiment in the thesis feeds the agent clean typed
text. This one runs real speech through the actual pipeline and reports how much routing
accuracy survives. If the answer is "most of it", the thesis has its strongest single result;
if not, that is a finding worth having before the defence rather than after.

You need: a quiet room, 3 people, a microphone, and about 40 minutes each. Then one command.

---

## Step 1 — Record

Open [`evals/data/cascade/manifest.json`](data/cascade/manifest.json). It lists **60 Vietnamese
utterances**. Each is read by **3 speakers**, so 180 recordings total.

**Read the line exactly as written.** The `text` field is the ground-truth transcript that
word error rate is computed against — paraphrasing, adding "à", or fixing what sounds odd all
register as recogniser errors and corrupt the result.

Audio requirements:

| Setting | Value |
|---|---|
| Format | WAV, 16-bit PCM |
| Sample rate | 16 000 Hz |
| Channels | mono |
| Room | quiet — **do not** add background noise yourself |

Filenames must match the `files` field exactly:

```
CAS-001_spk1.wav   CAS-001_spk2.wav   CAS-001_spk3.wav
CAS-002_spk1.wav   ...
```

Put them all in one flat directory. Speaker 1 must be the same person for every `_spk1` file.

> **Record clean only.** Noise is mixed in digitally afterwards at 20 dB, 10 dB and 0 dB SNR.
> That is why 180 recordings become 720 evaluation items without anyone recording four times.
> Recording in a noisy room instead destroys the clean reference and the whole noise axis with it.

## Step 2 — Get a noise file

One WAV of restaurant ambience — dishes, chatter, background music — at least 60 seconds,
16 kHz mono. A real recording from a busy restaurant is ideal. Save it anywhere and pass the
path in step 3.

Without it the script still runs, but scores the `clean` condition only, which loses the part
of the experiment that says something about a real dining room.

## Step 3 — Check before running

Validates every file path in one second, without loading any model:

```bash
PYTHONPATH=. uv run python evals/scripts/eval_cascade.py \
    --audio-dir /path/to/recordings --check
```

Fix anything it reports. It names the missing files.

## Step 4 — Run

```bash
PYTHONPATH=. uv run python evals/scripts/eval_cascade.py \
    --audio-dir /path/to/recordings \
    --noise /path/to/restaurant_noise.wav
```

Roughly 20–40 minutes on a Jetson Orin Nano, less on a desktop GPU. Add `--device cpu` if no
CUDA is available; it will be much slower but produces identical numbers.

## Step 5 — Send back

One file: `evals/results/cascade_<timestamp>.json`. It contains every transcript and every
per-item score, so nothing has to be re-run to build the thesis tables.

---

## What you should see

```
| Condition | n   | WER   | CER  | Dish sub. | Acc (ref) | Acc (ASR) | Delta  |
|-----------|-----|-------|------|-----------|-----------|-----------|--------|
| clean     | 180 | ...   | ...  | ...       | ...       | ...       | ...    |
| 20db      | 180 | ...   | ...  | ...       | ...       | ...       | ...    |
```

`Delta` is the headline: routing accuracy on reference text minus routing accuracy on what the
recogniser actually produced. WER describes the recogniser; delta describes the system.

A large `Dish sub.` with a small `Delta` is itself an interesting result — it would mean intent
survives dish-name corruption, which pushes the failure downstream into the validator's name
resolution rather than the router.

---

## Second job, if you have the Jetson (optional)

Chapter 2 argues the LLM belongs on the server rather than on the robot. That argument is
currently prose with no measurement behind it. On the Orin Nano, with ROS 2 and the voice
stack already running:

```bash
ollama pull qwen2.5:7b-instruct
ollama run qwen2.5:7b-instruct "Xin chào, quán có món gì ngon?" --verbose
```

Report: tokens/sec, time to first token, peak memory (`tegrastats`), and whether it OOMs at
all. Any of those outcomes validates the placement decision — including, especially, a crash.

---

## Notes

- Nothing here needs the orchestrator, the database, the web UIs, or a robot.
- The manifest is generated deterministically (`seed 20260723`). Re-running
  `build_cascade_manifest.py` reproduces the identical 60 utterances, so recordings stay valid.
- If a speaker misreads a line, just re-record that one file and overwrite it.
