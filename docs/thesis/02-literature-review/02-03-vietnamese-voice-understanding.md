## 2.3 Vietnamese Voice Understanding

> *Vietnamese speech recognition, voice activity detection, and speech synthesis exist as standalone research areas. This section surveys each component: how it works, what existing methods exist, and what prior evaluations have been conducted. For each component, a comparison table is presented; the selection from these tables occurs in §4.4. The edge hardware that hosts these components is surveyed in §2.8.*
>
> **Cross-refs:** §2.1 (overview — commercial robot voice limitations), §4.1 (AI system requirements), §4.4 (voice pipeline — proposed architecture), §5.4 (voice pipeline experiments)
> **Citations:** [2.3.1]–[2.3.25]; final numbering assigned when all Ch.2 references are merged.

---

A restaurant voice interaction follows a physical path: the customer speaks into a microphone mounted on the robot, the captured audio is processed on the robot's edge computer, and a spoken reply is produced through the robot's speaker. This path must complete in under 5 seconds from end-of-speech to start-of-reply to maintain conversational flow. It must operate under restaurant acoustic conditions — ambient noise at 60–70 dB from concurrent conversations, kitchen sounds, plate clatter, and chair movement. It must process Vietnamese, a tonal language where a single diacritic error changes word meaning entirely. And it must do all of this on edge hardware that is simultaneously running the robot's navigation stack.

This section surveys each component of the voice pipeline — voice activity detection, speech-to-text, and text-to-speech. For each component, the section surveys available technology options, identifies the selection criteria imposed by the restaurant deployment context (offline operation, VRAM budget, under-5-second latency, Vietnamese language support), and presents comparison tables. No component was built from scratch: VAD, STT, and TTS are used as off-the-shelf models. The design contribution in this domain is the integration of these components into a threaded pipeline on resource-constrained edge hardware.

---

### 2.3.1 Voice Activity Detection

Voice activity detection determines the boundaries of a spoken utterance in a continuous audio stream — when did the customer start speaking, and when did they stop? This is the first processing stage in the voice pipeline. Its output, a trimmed audio segment containing exactly one utterance, feeds directly into the STT model. If VAD cuts off speech prematurely, the STT model transcribes a truncated sentence, and the agent never sees the full order. If VAD triggers on background noise, the entire downstream pipeline — transcription, intent classification, LLM reasoning, validator checks — processes restaurant clatter as if it were an order. The accuracy of this single stage sets an upper bound on everything that follows.

The simplest approach to VAD is energy thresholding: any audio frame whose root-mean-square amplitude exceeds a fixed threshold is classified as speech. This method works in quiet recording studios, where silence has near-zero amplitude and speech rises clearly above it. In a restaurant, the ambient noise floor at 60–70 dB — plate clinks, chair scrapes, kitchen clatter, concurrent conversations — regularly exceeds the amplitude of quiet speech. Raising the threshold to reject noise causes the system to miss trailing syllables; lowering it produces continuous false triggers from background sounds. Energy-based VAD has no mechanism to distinguish speech from non-speech sounds of similar loudness, making it fundamentally unsuitable for restaurant deployment [2.3.1].

Lightweight neural models address this limitation by classifying audio frames based on learned spectral patterns rather than raw energy. Silero VAD, a language-agnostic model occupying approximately 1.5 MB, is the dominant open-source choice for edge deployment [2.3.2]. It processes each frame on CPU in real time, outputs a speech probability between 0 and 1, and exposes a configurable sensitivity threshold that allows operators to trade recall (detecting quiet speech) against precision (rejecting background noise). WebRTC VAD, at approximately 100 KB, uses a Gaussian Mixture Model trained on telephony speech — it is the lightest option but trades accuracy for size, performing noticeably worse than Silero under noisy conditions [2.3.3]. Both run on CPU without GPU dependency, leaving GPU memory available for the STT model and the ROS2 navigation stack. Figure 2.6 compares the precision-recall performance of Silero VAD, WebRTC VAD, and the energy-threshold baseline on Vietnamese speech samples, demonstrating Silero's advantage across the operating range.

At the high-accuracy end of the spectrum, deep learning VAD systems such as pyannote.audio and NVIDIA NeMo VAD use larger neural architectures to achieve state-of-the-art frame-level speech discrimination [2.3.4]. These models require GPU inference for real-time performance, an architecture inherently at odds with edge deployment where GPU memory is a constrained shared resource — the STT model, robot navigation processes, and the VAD unit would compete for the same memory pool. For a service robot that must run its entire software stack on a single embedded computer, an always-on GPU-dependent VAD is difficult to justify when CPU-only alternatives provide adequate accuracy at a fraction of the resource cost. The computation constraints that govern edge hardware selection are analyzed in §2.8.

| Model | Size | Inference | Accuracy (noisy) | Edge-Suitable | Notes |
|-------|------|-----------|-------------------|:---:|-------|
| Energy threshold | N/A | N/A | Poor | Yes | Cannot discriminate speech from noise at similar amplitude |
| Silero VAD | ~1.5 MB | CPU, real-time | Good | Yes | Language-agnostic; configurable sensitivity; dominant open-source model |
| WebRTC VAD | ~100 KB | CPU, real-time | Moderate | Yes | Gaussian Mixture Model; lighter but less accurate in noise |
| pyannote VAD | ~100 MB | GPU | High | No | Requires GPU; unsuitable for always-on edge process |
| NeMo VAD | ~200 MB | GPU | High | No | NVIDIA NeMo framework; GPU-dependent |

Prior work has evaluated Silero VAD on multilingual telephone speech and meeting recordings in quiet or moderately noisy conditions. WebRTC VAD has been tested on telephony-quality speech. Neither has been benchmarked on Vietnamese speech corpora or under restaurant noise profiles. The available evaluation data covers general-domain speech; Vietnamese-specific VAD performance in restaurant acoustic conditions — with concurrent conversations, impulse noise from dropped utensils, and sustained broadband kitchen noise — is not characterized in existing benchmarks. The sensitivity threshold calibration for restaurant deployment remains an open operational question.

---

### 2.3.2 Speech-to-Text for Vietnamese

Speech-to-text converts the audio segment isolated by VAD into Vietnamese text. It is the single most impactful stage in the voice pipeline: every downstream component — the intent classifier, the agent's LLM, the validator, and the response generator — operates on the text that the STT model produces.

The dominant on-device architecture for multilingual STT is OpenAI's Whisper, a Transformer-based encoder-decoder trained on 680,000 hours of web-scraped speech spanning 99 languages [2.3.5]. Whisper processes raw audio through a convolutional front-end, encodes it into a latent representation via the encoder stack, and decodes it autoregressively into text tokens — with the decoder conditioned on both the audio encoding and previously generated tokens. Vietnamese was included in the training data but was not a primary target language; the model handles Vietnamese partially but is not optimized for it. Whisper scales across four sizes — tiny (39M parameters), base (74M), medium (769M), and large-v3 (1.55B) — offering a spectrum of accuracy against computational cost. Larger models produce lower word error rates but require proportionally more VRAM and inference time, with large-v3 consuming approximately 3 GB of GPU memory at FP16 precision [2.3.6].

A significant advance in deployment efficiency came with faster-whisper [2.3.7], a reimplementation of Whisper using the CTranslate2 inference engine. CTranslate2 applies operator fusion, memory layout optimization, and 8-bit integer quantization to reduce latency by approximately 4× compared to the standard Whisper implementation while cutting VRAM usage by roughly half. With faster-whisper, the medium-sized model — previously requiring over 3 GB — becomes deployable at approximately 1.5 GB, fitting within the memory budget of a single-board edge computer.

PhoWhisper [2.3.8] addresses Vietnamese specifically by fine-tuning the Whisper model on Vietnamese speech data. The fine-tuning achieves an estimated 5–10% word error rate improvement over the base multilingual Whisper, with the largest gains concentrated in tonal diacritics — Vietnamese has six tones where a single diacritic mark changes word meaning ("cá" is fish, "cà" is eggplant). PhoWhisper preserves compatibility with faster-whisper's CTranslate2 backend, meaning the latency and memory benefits of optimized inference carry over to the Vietnamese-enhanced variant.

On the cloud side, dedicated Vietnamese STT services — Google Cloud Speech-to-Text, Viettel AI STT, and FPT.AI STT — operate on server-grade infrastructure with models trained on large Vietnamese speech corpora, achieving estimated word error rates of 5–8% on clean speech [2.3.9]–[2.3.11]. These services benefit from continuous model updates and access to substantially larger training datasets. Their trade-off is architectural: every utterance requires a network round-trip to a remote data center. In a deployment scenario where internet connectivity is unreliable, cloud STT introduces a single point of failure — a WiFi outage renders the entire voice pipeline inoperable.

| Model / Service | Vietnamese Optimization | Edge Deployable | Offline | Latency (3s utterance) | VRAM | Est. WER (clean VN) |
|-----------------|:---:|:---:|:---:|:---:|:---:|:---:|
| Whisper tiny | No (multilingual) | Yes | Yes | ~300ms | ~0.5 GB | 25–35% |
| Whisper base | No (multilingual) | Yes | Yes | ~400ms | ~0.8 GB | 20–30% |
| Whisper medium | No (multilingual) | Yes | Yes | ~800ms | ~1.5 GB | 15–20% |
| PhoWhisper (medium via faster-whisper) | Yes (fine-tuned VN) | Yes | Yes | ~800ms | ~1.5 GB | 10–15% |
| Whisper large-v3 | No (multilingual) | Borderline | Yes | ~1.5s | ~3 GB | 10–15% |
| Google Cloud STT | Yes (dedicated model) | No | No | ~200ms + RTT | 0 (cloud) | 5–8% |
| Viettel AI STT | Yes (dedicated model) | No | No | ~200ms + RTT | 0 (cloud) | 5–8% |
| FPT.AI STT | Yes (dedicated model) | No | No | ~200ms + RTT | 0 (cloud) | 5–8% |

PhoWhisper has been evaluated on the VLSP (Vietnamese Language and Speech Processing) benchmark and related academic corpora [2.3.12], consisting of read speech in quiet recording conditions with standard pronunciation. These evaluations confirm the 5–10% improvement over base Whisper on clean Vietnamese speech.

---

### 2.3.3 Text-to-Speech for Vietnamese

The final stage of the voice pipeline converts the agent's Vietnamese text response into audible speech. TTS engines for Vietnamese fall along a clear spectrum, from lightweight formant-based synthesizers that run on any CPU to neural models requiring dedicated GPU memory to cloud services with studio-quality output.

At the lightest extreme, eSpeak-NG [2.3.13] is a formant synthesizer — rather than learning from recorded speech, it generates audio by modeling the human vocal tract as a set of resonant frequencies and applying rules to shape them into phonemes. The result is unmistakably robotic: a flat, mechanical voice with correct vowel and consonant placement but no natural prosody. Its advantage is size — approximately 5 MB and entirely CPU-bound, eSpeak can produce Vietnamese speech on a microcontroller. Formant synthesis has been deployed in screen readers and accessibility tools for decades, and its Vietnamese phoneme tables cover the language's full tonal system, though without the smooth transitions of neural speech.

Piper TTS [2.3.14] occupies the middle of the spectrum. It uses the VITS (Variational Inference with adversarial learning for end-to-end Text-to-Speech) architecture, where a single neural network converts text directly to waveform in one forward pass — no intermediate spectrogram, no separate vocoder. The single community-trained Vietnamese voice model is approximately 200 MB and runs on CPU, producing one sentence of speech in approximately 500ms. The output is clearly synthetic but intelligible, with correct tone production for Vietnamese diacritics. It is the only neural Vietnamese TTS option that operates within the memory budget of a single-board edge computer without GPU offloading.

At the heavy end of on-device neural TTS, Coqui's XTTS v2 [2.3.15] uses a 1.87-billion-parameter autoregressive model with a separately trained vocoder. It supports Vietnamese as part of its multilingual training and offers voice cloning from a short reference clip. The quality approaches cloud neural voices — natural prosody, smooth tonal transitions, speaker-adaptive output. The cost is VRAM: inference requires approximately 4 GB of GPU memory, making it demanding for deployment on a shared-resource edge device where the STT model and robot navigation also need GPU access. XTTS represents the quality ceiling for on-device Vietnamese TTS but at a resource cost that constrains its use in concurrent-workload scenarios.

The remaining Vietnamese TTS options are cloud services. Microsoft Azure Neural TTS, accessed through the open-source edge-tts client, offers multiple Vietnamese voices with Northern and Southern accents and both male and female speakers [2.3.16]. Google Cloud TTS provides WaveNet voices with the highest reported naturalness scores [2.3.17]. Two Vietnamese providers — vbee and FPT.AI — offer TTS APIs trained specifically on Vietnamese speech with local-market voice profiles [2.3.18]. All four produce speech substantially more natural than any on-device option. All four require an active internet connection for every sentence.

| Engine | Approach | Offline | Edge Deployable | Latency (per sentence) | VRAM | Naturalness | Vietnamese Voices |
|--------|----------|:---:|:---:|:---:|:---:|:---:|:---:|
| eSpeak-NG | Formant | Yes | Yes (CPU) | ~50ms | ~5 MB | Very Low | Phoneme tables |
| Piper TTS | VITS (neural, single-stage) | Yes | Yes (CPU) | ~500ms | ~200 MB | Moderate | 1 community-trained |
| XTTS v2 | Autoregressive + vocoder | Yes | Borderline | ~2s | ~4 GB GPU | High | Multilingual + voice cloning |
| edge-tts (Azure) | Neural (cloud) | No | No (cloud) | ~300ms + RTT | 0 (cloud) | High | Multiple neural |
| Google Cloud TTS | WaveNet (cloud) | No | No (cloud) | ~200ms + RTT | 0 (cloud) | Very High | WaveNet voices |
| vbee TTS | Neural (cloud) | No | No (cloud) | ~300ms + RTT | 0 (cloud) | High | Vietnamese-specific |
| FPT.AI TTS | Neural (cloud) | No | No (cloud) | ~300ms + RTT | 0 (cloud) | High | Vietnamese-specific |

TTS quality is measured through Mean Opinion Score (MOS), where human listeners rate speech samples on a 1–5 naturalness scale. In published evaluations on general-domain Vietnamese text, cloud neural voices achieve MOS scores of 4.0–4.5, XTTS approaches 3.5–4.0, Piper's Vietnamese voice is estimated at 2.5–3.5, and eSpeak typically scores below 2.0 [2.3.14]–[2.3.15]. A score below 2.0 means the voice is robotic but words are identifiable; 2.5–3.5 means clearly synthetic but fully intelligible; above 4.0 approaches human-like naturalness.

---

### → Overall Gap for §2.3

Three individually mature voice components — VAD, STT, and TTS — are available for Vietnamese, each with off-the-shelf models that satisfy the deployment constraints: Silero VAD provides CPU-only, language-agnostic frame-level speech detection configurable via a sensitivity threshold; PhoWhisper via faster-whisper achieves Vietnamese-optimized transcription at approximately 800ms per utterance within approximately 1.5 GB of VRAM; Piper TTS provides CPU-based Vietnamese speech synthesis at approximately 500ms per sentence within approximately 200 MB of RAM.

What has not been demonstrated is their integration into a single pipeline on resource-constrained edge hardware that is simultaneously running the robot's navigation stack. Four specific integration gaps exist:

1. **Concurrent workload characterization.** No prior work has characterized the combined memory footprint of ROS2 navigation processes and Vietnamese voice pipeline processes co-residing on the same Jetson Orin Nano with 8 GB of unified memory — the practical constraint that determines whether the edge/server split is necessary and where the split boundary must be drawn.

2. **Restaurant noise robustness.** VAD and STT have been evaluated on clean Vietnamese speech in quiet conditions. No evaluation exists for Vietnamese VAD and STT under restaurant noise profiles — sustained ambient noise at 60–70 dB, impulse noise from dropped utensils, concurrent conversations at adjacent tables — where false VAD triggers waste processing time and STT errors propagate through the entire conversational pipeline.

3. **Command-driven voice capture.** Prior voice assistants use always-on wake-word detection; the restaurant context requires push-to-talk gating where voice capture is armed by a tablet button press, routed through a backend voice bridge to a specific robot's microphone based on dynamic table-to-robot binding, and supports cancel, mute, and barge-in — a multi-actor orchestration pattern not present in single-device voice assistants.

4. **Barge-in for Vietnamese dialogue.** Barge-in — where the customer's speech interrupts in-progress TTS playback — requires VAD to operate during TTS output and detect speech onset over the speaker's own audio. This capability has been demonstrated for English dialogue systems but not for Vietnamese restaurant interactions where tonal diacritics in the TTS output create a different spectral profile than English speech.

These gaps motivate the edge voice pipeline architecture in §4.4 and the deployment topology analysis in §4.9.
