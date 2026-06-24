# Building CTranslate2 from source on Jetson (for faster-whisper)

Target: Jetson Orin, JetPack 6.x, CUDA 12.6, Python 3.10, project venv managed by `uv`.

## Why we build from source

The prebuilt wheel from `pypi.jetson-ai-lab.dev` (or PyPI) is **only the Python
binding** (`ctranslate2._ext`). It does **not** ship the C++ runtime library
`libctranslate2.so.4`. Importing it fails with:

```
ImportError: libctranslate2.so.4: cannot open shared object file: No such file or directory
```

So we compile the C++ library ourselves, install it into `/usr/local`, then build
the Python binding against it.

> Note: `pyproject.toml` deliberately declares `faster-whisper` only for
> `platform_machine == 'x86_64'`. On Jetson (aarch64), `uv sync` does **not**
> install faster-whisper / ctranslate2 — we install them by hand (steps below).

---

## One-time prerequisites

```bash
nvcc --version          # expect CUDA 12.6
cmake --version         # need >= 3.18
sudo apt-get update && sudo apt-get install -y build-essential cmake git
ls /usr/lib/aarch64-linux-gnu/libcudnn.so*   # cuDNN should already exist on JetPack 6.x
```


---

## Step 1 — Build the C++ library

```bash
export CTRANSLATE_VERSION=4.6.0
export CTRANSLATE_BRANCH=v4.6.0
export CTRANSLATE_SOURCE=$HOME/CTranslate2

git clone --branch=${CTRANSLATE_BRANCH} --recursive \
    https://github.com/OpenNMT/CTranslate2.git ${CTRANSLATE_SOURCE}

mkdir -p ${CTRANSLATE_SOURCE}/build
cd ${CTRANSLATE_SOURCE}/build
install_dir=${CTRANSLATE_SOURCE}/build/install

cmake .. \
  -DWITH_CUDA=ON \
  -DWITH_CUDNN=ON \
  -DWITH_MKL=OFF \
  -DOPENMP_RUNTIME=COMP \
  -DCMAKE_INSTALL_PREFIX=$install_dir \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_ARCHITECTURES=87        # Orin = sm_87

make -j$(nproc)         
make install
```

`make` is incremental: if it gets Ctrl+C'd or OOM-killed, just rerun `make -j2`
and it resumes. Do **not** run `make clean` (that wipes progress).

## Step 2 — Install the C++ lib system-wide

```bash
sudo cp -r ${install_dir}/* /usr/local/
sudo ldconfig            # CRITICAL — refreshes the .so loader cache (the NVIDIA script omits this)
```

Verify:

```bash
ls -l /usr/local/lib/libctranslate2.so*
ldconfig -p | grep ctranslate2
```

Expected — the 3-level symlink chain + ldconfig entry:

```
libctranslate2.so       -> libctranslate2.so.4
libctranslate2.so.4     -> libctranslate2.so.4.6.0
libctranslate2.so.4.6.0  (real file, ~12MB)
libctranslate2.so.4 (libc6,AArch64) => /usr/local/lib/libctranslate2.so.4
```

The C++ lib is system-wide and shared by every venv — this is correct, leave it.

## Step 3 — Build the Python binding into the project venv

```bash
cd ~/ptd_workspace/AI_Waiver
uv sync                          # installs torch/etc; does NOT touch ctranslate2 on aarch64
source .venv/bin/activate

cd ~/CTranslate2/python
uv pip install -r install_requirements.txt          # pybind11, wheel
CTRANSLATE2_ROOT=/usr/local uv pip install . --no-build-isolation
```

- `CTRANSLATE2_ROOT=/usr/local` — points setup.py at the headers/lib from Step 2.
- `--no-build-isolation` — ctranslate2 uses a legacy `setup.py`; isolation hides the
  pybind11 we just installed, so disable it.

## Step 4 — Install faster-whisper (without re-pulling ctranslate2)

```bash
uv pip install faster-whisper --no-deps
uv pip install tokenizers huggingface-hub av onnxruntime
```

`--no-deps` stops faster-whisper from pulling a PyPI ctranslate2 that would
overwrite our hand-built one.

## Step 5 — Verify

```bash
cd ~          # IMPORTANT: NOT inside ~/CTranslate2/python (see gotcha below)
python -c "import ctranslate2; print(ctranslate2.__version__, ctranslate2.get_cuda_device_count())"
python -c "from faster_whisper import WhisperModel; print('OK')"
python -c "import ctranslate2; print(ctranslate2.__file__)"   # must point into .venv, not CTranslate2/python
```

Expected: `4.6.0 1` and `OK`.

---

## Gotchas (the ones that actually bit us)

1. **`uv sync` removes the hand-built packages.** Default `uv sync` is *exact* and
   uninstalls anything not in `uv.lock` — including ctranslate2 / faster-whisper.
   On Jetson always use:

   ```bash
   uv sync --inexact
   ```

   If you forget and they get wiped, just rerun Step 3 + Step 4.

2. **Never test `import ctranslate2` from `~/CTranslate2/python`.** That dir has a
   `ctranslate2/` source subfolder that shadows the installed package (cwd is first
   on `sys.path`). You get `module 'ctranslate2' has no attribute 'StorageView' /
   'get_cuda_device_count'` even though the install is fine. Just `cd ~` first.

3. **`ldconfig` is mandatory** after copying to `/usr/local`. Without it the loader
   still won't find `libctranslate2.so.4`.

4. **Limit `make -j`** on 8GB RAM. `make -j$(nproc)` (6 jobs) OOM-kills the CUDA
   compile. Use `-j2`, add swap.

5. **DNS errors** (`Name or service not known`) are network, not package, problems.
   Fix DNS first: `echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf`.

---

## Quick rebuild cheatsheet (when it breaks again)

If the C++ lib at `/usr/local/lib/libctranslate2.so.4` still exists, you only lost
the Python side (e.g. after `uv sync` wiped it):

```bash
cd ~/ptd_workspace/AI_Waiver && source .venv/bin/activate
cd ~/CTranslate2/python
CTRANSLATE2_ROOT=/usr/local uv pip install . --no-build-isolation
uv pip install faster-whisper --no-deps
uv pip install tokenizers huggingface-hub av onnxruntime
cd ~ && python -c "import ctranslate2; from faster_whisper import WhisperModel; print(ctranslate2.__version__, 'OK')"
```

If even the C++ lib is gone, start from Step 1.

---

## After a reboot — do I need to reinstall anything?

**No.** Everything is on disk and survives a reboot. Just activate the venv and run:

```bash
cd ~/ptd_workspace/AI_Waiver
source .venv/bin/activate
python scripts/probe_stt.py --audio test.wav
```

| Component | Location | Survives reboot? |
|-----------|----------|------------------|
| C++ lib `libctranslate2.so.4` | `/usr/local/lib` (ldconfig'd) | ✅ |
| Python binding `ctranslate2`  | `.venv/.../site-packages` | ✅ |
| `faster-whisper` + deps       | `.venv` | ✅ |
| Source `~/CTranslate2`        | `$HOME` | ✅ |

The only thing lost on reboot is the **swap file** (`swapon` is not persistent
unless added to `/etc/fstab`). Swap is only needed while compiling the C++ lib
(Step 1), not at runtime — so a normal reboot needs nothing. If you ever rebuild
the C++ lib after a reboot, re-enable swap first: `sudo swapon /swapfile` (or
recreate it as in the "Add swap" section if the file is gone).

Rule of thumb: **a reboot deletes nothing; only `uv sync` (without `--inexact`)
deletes the hand-built packages.**

---

## Recovery scenarios — which steps to rerun

Check what you still have, then pick the matching scenario:

```bash
ls /usr/local/lib/libctranslate2.so.4   # present -> C++ lib OK | "No such file" -> rebuild C++
ls ~/CTranslate2/python                  # present -> source OK
```

### Scenario 1 — same Jetson, repo re-cloned / `.venv` lost (C++ lib still present)

`~/CTranslate2` and `/usr/local/lib/libctranslate2.so.4` live **outside** the repo,
so re-cloning AI_Waiver does not touch them. You only need to rebuild the Python
side (~1–2 min, no CUDA recompile):

```bash
# (re)install the uv tool itself if it's gone
curl -LsSf https://astral.sh/uv/install.sh | sh

# clone + sync the project
cd ~/ptd_workspace
git clone <repo-url> AI_Waiver
cd AI_Waiver
uv sync
source .venv/bin/activate

# reinstall the Python binding against the existing C++ lib (no C++ rebuild)
cd ~/CTranslate2/python
CTRANSLATE2_ROOT=/usr/local uv pip install . --no-build-isolation
uv pip install faster-whisper --no-deps
uv pip install tokenizers huggingface-hub av onnxruntime

# verify
cd ~ && python -c "import ctranslate2; from faster_whisper import WhisperModel; print(ctranslate2.__version__,'OK')"
```

### Scenario 2 — fresh Jetson, or `/usr/local/lib/libctranslate2.so.4` missing

Start from **Step 1** (full C++ rebuild, ~30–40 min), then Steps 2–5.

### Running the app without triggering a sync

`uv run ...` does an implicit `uv sync` first, which can wipe the hand-built
packages. On Jetson, run via the activated venv, or pass `--no-sync`:

```bash
source .venv/bin/activate && python scripts/probe_stt.py --audio test.wav
# or
uv run --no-sync python scripts/probe_stt.py --audio test.wav
```
