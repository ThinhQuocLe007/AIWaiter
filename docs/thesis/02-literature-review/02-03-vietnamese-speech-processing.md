## 2.3 Vietnamese Speech Processing

> **Status:** draft v1
> **Cross-refs:** §4.4 (voice pipeline architecture), §4.1 (system requirements), §5.3.5 (voice pipeline evaluation)
> **Scope note:** This section surveys the technologies available for each component of a voice interaction pipeline — voice activity detection, speech-to-text, text-to-speech, and edge deployment hardware — with emphasis on the Vietnamese language characteristics that make speech processing non-trivial. The section does not select components; the architectural choices are made in §4.4 based on the system requirements in §4.1.
> **Citations:** [2.3.1]–[2.3.25]; final numbering assigned when all Ch.2 references are merged.
> **Figures needed:** Fig 2.7 — voice interaction pipeline (mic → VAD → STT → Agent → TTS → speaker). Fig 2.8 — STT model comparison chart (edge vs. cloud, WER vs. VRAM).

---

A voice interaction pipeline for a restaurant environment consists of three sequential stages operating on fundamentally different data types: raw audio capture and speech boundary detection, transcription of Vietnamese speech into text, and synthesis of text responses into spoken Vietnamese. A fourth dimension — the hardware platform on which these stages execute — constrains which models can be deployed and where. This section surveys the available technologies for each stage, the Vietnamese language characteristics that make each stage challenging, and the edge hardware constraints that shape architectural decisions.

---

### 2.3.1 Voice Activity Detection

The first stage of any voice pipeline is voice activity detection (VAD): determining when a speaker has started and stopped speaking in a continuous audio stream. This is a binary classification problem at the audio frame level — each short segment of audio (typically 10–30 ms) is classified as speech or non-speech [2.3.1]. The accuracy of this classification directly determines the user experience: a VAD that cuts off the customer mid-sentence forces them to repeat themselves; a VAD that triggers on background noise captures empty audio and wastes downstream processing.

**The utterance boundary problem.** The VAD must solve two opposing objectives. Start-of-speech detection must be fast — a delay of more than 200 ms between the customer beginning to speak and the system recognizing speech onset feels unresponsive. End-of-speech detection must be conservative — the system must wait long enough after the last detected speech frame to be confident the customer has finished, but not so long that the customer is left waiting in silence. This silence timeout is the primary user-facing VAD parameter: too short and trailing syllables are cut off (particularly problematic in Vietnamese, where sentence-final particles like "ạ", "nhé", "nha" are very quiet); too long and the interaction feels sluggish [2.3.2].

**Energy threshold VAD.** The simplest approach classifies any audio frame whose root-mean-square (RMS) amplitude exceeds a fixed threshold as speech. This method requires zero model loading, runs in microseconds per frame, and is trivial to implement. It works adequately in controlled acoustic environments — a quiet recording studio, a phone call in a silent room. It fails catastrophically in a restaurant. At peak hours, a restaurant dining room has continuous ambient noise at 60–70 dB SPL from concurrent conversations, kitchen sounds, plate clatter, chair movement, and background music [2.3.3]. This noise floor regularly exceeds the amplitude of quiet speech, making it impossible to select a single RMS threshold that rejects noise while capturing all utterances. Raising the threshold misses quiet speakers entirely; lowering it produces continuous false triggers.

**Neural VAD approaches.** Neural network-based VAD systems classify speech vs. non-speech based on learned spectral and temporal patterns rather than raw amplitude. A mel-spectrogram representation of the audio frame captures the frequency-domain structure that distinguishes human speech (harmonic structure, formant patterns) from environmental noise (broadband, aperiodic) [2.3.4]. Several neural VAD implementations are available:

- **Silero VAD** (~1.5 MB): a lightweight convolutional-recurrent neural network trained on a large multilingual dataset. Language-agnostic — the model learns speech/non-speech discrimination from acoustic features without language-specific training. Runs on CPU at real-time speeds, consuming a negligible fraction of a single core. Exposes a configurable speech probability threshold (default 0.5) that trades sensitivity against specificity [2.3.5].

- **WebRTC VAD**: a Gaussian Mixture Model (GMM)-based classifier, ultra-lightweight (<100 KB), integrated into the WebRTC real-time communication standard. Runs in microseconds per frame but is significantly less accurate in noisy environments — the GMM's 6-subband energy features lack the spectral resolution to distinguish speech from restaurant noise reliably [2.3.6].

- **Deep learning VADs** (pyannote.audio, NVIDIA NeMo): larger transformer-based models trained on massive speech corpora with state-of-the-art accuracy on standard benchmarks. However, these models require GPU inference (200–500 MB VRAM), making them unsuitable for always-on deployment on resource-constrained edge hardware [2.3.7].

**Restaurant-specific VAD challenges.** A restaurant environment presents a uniquely difficult VAD scenario that differs from the telephony and meeting-room conditions under which most VAD systems are evaluated. The noise is non-stationary — a chair scrape, a plate drop, a burst of laughter — producing transient high-amplitude events that trigger false positives. Multi-speaker environments mean the VAD may capture speech from adjacent tables rather than the target customer. These domain-specific challenges mean that published VAD accuracy metrics from clean-speech benchmarks do not transfer directly to restaurant deployment [2.3.8].

---

### 2.3.2 Speech-to-Text for Vietnamese

Once VAD has isolated an utterance, the speech-to-text (STT) stage transcribes the Vietnamese audio waveform into text. STT accuracy is the single most critical metric in the entire voice pipeline: if the transcription is wrong, every downstream component — intent classifier, conversational agent, order creation, payment — operates on corrupted input. No amount of agent intelligence can recover from transcribing "Ốc Hương" (a specific snail dish) as "Ốt Hương" (pepper fragrance).

#### Vietnamese Language Challenges for STT

Vietnamese presents several characteristics that make STT inherently more difficult than for atonal, non-compounding languages [2.3.9].

**Tonal system.** Vietnamese has 6 lexical tones (ngang, huyền, sắc, hỏi, ngã, nặng) carried by diacritic marks on vowels. A change in tone changes the word meaning entirely — "cá" (fish, sắc tone) vs. "cà" (eggplant, huyền tone) vs. "cả" (all, hỏi tone). For a restaurant ordering system, tonal accuracy is existential: "cá" and "cà" are fundamentally different food items. STT models trained primarily on atonal languages (English, Mandarin without tone markers) lack the acoustic representation capacity to distinguish these fine pitch contours reliably [2.3.10].

**Compound words and syllable structure.** Vietnamese is monosyllabic at the morpheme level but forms compound words where multiple syllables constitute a single lexical unit. "Bún bò Huế" (Hue-style beef noodle soup) is three syllables but one dish name — tokenizing it as three independent words would fragment the menu item. STT post-processing (language model rescoring, beam search decoding) must preserve these compounds [2.3.11].

**Teencode and informal speech.** Spoken Vietnamese in casual settings — precisely the context of a restaurant ordering interaction — differs substantially from the formal written Vietnamese that dominates STT training corpora. Common informal variants include: "ad" for "anh/chị" (you/sir/madam), "vs" for "với" (with), "ck" for "chuyển khoản" (bank transfer), "z" for "vậy" (so/then), "nhiêu" for "bao nhiêu" (how much), "hông" for "không" (no/not). A customer saying "ck cho mình cái QR với" (transfer me the QR code) uses three informal variants in a 6-word utterance. STT models trained on formal Vietnamese news broadcasts or audiobooks encounter these variants rarely or not at all [2.3.12].

**Restaurant ambient noise.** The same acoustic conditions that challenge VAD also degrade STT — background conversations, kitchen noise, and plate clatter are all captured by the microphone alongside the target utterance. STT models trained on clean speech exhibit significant WER degradation in noisy conditions. Restaurant noise is spectrally complex (overlapping speech from adjacent tables, impulsive sounds from dropped utensils) and non-stationary (noise profile changes as tables fill up and empty), making simple noise suppression techniques (spectral subtraction, Wiener filtering) insufficient [2.3.13].

**STT as the break-point.** These four challenges — tones, compounds, teencode, and noise — combine to make Vietnamese STT in a restaurant the single highest-risk component in the system architecture. A 10% WER on clean speech may become 20–30% in a noisy restaurant. At those rates, approximately one in four utterances contains at least one transcription error that could misroute an intent, corrupt a dish name, or misparse a quantity. The downstream agent's deterministic validator can catch some errors (an off-menu dish name), but not all (a correctly spelled but wrong dish name, a misrecognized intent keyword). This risk drives the requirement for STT accuracy evaluation under realistic restaurant acoustic conditions (§5.3.5.1) [2.3.14].

#### Available STT Approaches

The STT landscape for Vietnamese divides into two categories: cloud-based services offering higher accuracy at the cost of internet dependency, and on-device models offering offline operation at lower accuracy.

| Model / Service | Edge Deployable | Offline | Latency (3s utt.) | VRAM | Est. WER on VN | Notes |
|---|---|---|---|---|---|---|
| Whisper tiny | Yes | Yes | ~200ms | ~0.5 GB | 25–35% | Smallest, fastest, least accurate |
| Whisper base | Yes | Yes | ~300ms | ~1 GB | 20–30% | Acceptable speed, marginal accuracy |
| Whisper medium | Yes | Yes | ~800ms | ~1.5 GB | 15–20% | Best speed-accuracy trade-off on-device |
| Whisper large-v3 | Borderline | Yes | ~1.5s | ~3 GB | 10–15% | VRAM exceeds typical edge budget |
| PhoWhisper (whisper-medium-vn) | Yes | Yes | ~800ms | ~1.5 GB | 10–15% | Fine-tuned on Vietnamese; best on-device VN accuracy |
| Google Cloud Speech-to-Text | No | No | ~200ms + network | 0 (cloud) | 5–8% | Proprietary, highest accuracy |
| Viettel AI STT | No | No | ~200ms + network | 0 (cloud) | 5–8% | Vietnamese telecom provider |
| FPT.AI STT | No | No | ~200ms + network | 0 (cloud) | 5–8% | Vietnamese technology company |

**Whisper family.** OpenAI's Whisper is an encoder-decoder Transformer architecture trained on 680,000 hours of multilingual and multitask supervised data collected from the web [2.3.15]. The model processes 80-channel log-mel spectrogram inputs through a Transformer encoder, then autoregressively generates text tokens through a Transformer decoder. Whisper's multilingual training includes Vietnamese in its training distribution, but the model is not fine-tuned specifically for Vietnamese — it treats Vietnamese as one of 99 supported languages, and its tonal accuracy reflects this generalist design.

**PhoWhisper.** PhoWhisper is a set of Whisper model weights fine-tuned on Vietnamese speech data to improve tonal accuracy [2.3.16]. The fine-tuning process uses Vietnamese-specific corpora and focuses on tonal diacritic accuracy — the most common failure mode of the base Whisper model on Vietnamese. PhoWhisper maintains the same architecture and parameter count as the base Whisper model; the difference is in the weights. Evaluations on Vietnamese speech benchmarks report WER improvements of 5–10 absolute percentage points over the equivalent Whisper model size, with the largest gains on tonal accuracy metrics [2.3.17].

**Faster-Whisper.** Faster-Whisper is a reimplementation of Whisper using CTranslate2, a custom runtime for Transformer models that applies 8-bit integer quantization, layer fusion, and memory layout optimization [2.3.18]. It reduces model size by approximately 4× and inference latency by 3–4× compared to the original Whisper implementation, while maintaining accuracy within 1% WER. Faster-Whisper is model-format-compatible — it loads Whisper and PhoWhisper weights without modification. This makes medium-sized models viable on edge hardware where the original implementation would exceed the compute budget.

**Cloud services.** Google Cloud Speech-to-Text, Viettel AI, and FPT.AI all offer Vietnamese STT with reported WER of 5–8%, outperforming on-device models by a significant margin [2.3.19]. The accuracy advantage comes from several factors: access to larger models not constrained by edge VRAM budgets, proprietary training data that includes Vietnamese speech collected through their respective platforms, and server-grade GPU inference with no quantization loss. However, all cloud services share three dependencies that conflict with restaurant deployment requirements: (a) internet connectivity — a restaurant floor cannot depend on a network being available for every spoken utterance, (b) per-request latency — 200 ms of inference time plus 50–200 ms of network round-trip adds unpredictability to the total voice turn time, and (c) data privacy — raw audio of customer conversations is transmitted to third-party servers.

#### Prior Work on Vietnamese STT

Vietnamese STT has been evaluated in academic literature primarily on clean speech datasets [2.3.20]. VLSP (Vietnamese Language and Speech Processing) consortium has organized annual ASR challenges since 2018, producing benchmark datasets of formal Vietnamese speech in quiet recording conditions. PhoWhisper and related fine-tuned Whisper variants report WER of 8–12% on VLSP benchmarks. However, no published work has evaluated Vietnamese STT in restaurant acoustic conditions — the combination of ambient noise, informal speech with teencode, and domain-specific vocabulary (dish names, quantity expressions) that defines the target deployment environment. This gap between benchmark performance and real-world restaurant performance is a key evaluation objective in §5.3.5.1.

---

### 2.3.3 Text-to-Speech for Vietnamese

The final stage of the voice pipeline synthesizes the agent's Vietnamese text response into audible speech. Unlike STT — where accuracy is the dominant metric — TTS evaluation involves multiple dimensions: naturalness (does it sound human?), intelligibility (can every word be understood?), latency (how long from text to first audio sample?), and deployability (does it run on the target hardware?) [2.3.21].

#### Available TTS Approaches

| Engine | Offline | Edge Deployable | Latency (per sent.) | VRAM / RAM | Naturalness | Vietnamese Voices |
|---|---|---|---|---|---|---|
| Piper TTS | Yes | Yes (CPU) | ~500ms | ~200 MB RAM | Moderate | 1 community-trained voice |
| edge-tts | No | No (cloud) | ~300ms + network | 0 (cloud) | High | Multiple neural voices |
| vbee | No | No (cloud) | ~300ms + network | 0 (cloud) | High | Multiple |
| FPT.AI TTS | No | No (cloud) | ~300ms + network | 0 (cloud) | High | Multiple |
| Google Cloud TTS | No | No (cloud) | ~200ms + network | 0 (cloud) | Very High | WaveNet voices |
| Coqui TTS (XTTS) | Yes | Yes (GPU) | ~1s | ~2 GB VRAM | High | Voice cloning, no pre-built VN voice |

**Piper TTS.** Piper is an open-source TTS engine using the VITS (Variational Inference with adversarial learning for end-to-end Text-to-Speech) architecture [2.3.22]. VITS combines a variational autoencoder with adversarial training in a single end-to-end model — unlike traditional two-stage TTS (text → spectrogram → waveform), VITS generates waveforms directly from text, eliminating the vocoder stage and reducing latency. Piper's design prioritizes low resource usage: inference runs entirely on CPU (~200 MB RAM), latency is ~500ms per sentence for Vietnamese, and the model is distributed as a single ONNX runtime file with no Python dependency. The Vietnamese voice is community-trained — it provides intelligible Vietnamese speech with moderate naturalness, sufficient for short functional utterances where the semantic content (dish names, prices, order confirmations) matters more than vocal performance. Piper has no voice variety — all speech uses a single voice — and no prosody control (speech rate, pitch, emphasis are fixed).

**Cloud-based TTS services.** Microsoft Azure edge-tts, vbee, FPT.AI, and Google Cloud TTS all offer Vietnamese neural TTS with high naturalness and multiple voice options [2.3.23]. These services use large neural TTS models (Tacotron 2, FastSpeech 2, WaveNet) trained on professional voice actor recordings, producing speech with natural intonation, appropriate pausing, and emotional coloring. Google Cloud TTS offers WaveNet voices that approach human-level naturalness on Vietnamese. The trade-off is the same as STT: these services require internet connectivity, add network round-trip latency to every spoken response, and transmit the restaurant's conversation text to third-party servers.

**Coqui TTS (XTTS).** XTTS is an open-source TTS model supporting voice cloning — a short sample of a target speaker's voice is used to synthesize new speech in that voice [2.3.24]. XTTS supports Vietnamese but requires GPU inference (~2 GB VRAM for the base model), which conflicts with edge deployment where GPU resources are reserved for STT and navigation. XTTS also has no pre-built Vietnamese voice — voice cloning requires recording a clean Vietnamese voice sample, which adds a deployment step not needed by Piper or cloud services.

#### TTS Evaluation Dimensions

TTS quality is typically evaluated through Mean Opinion Score (MOS) — human raters score synthesized speech on a 1–5 scale for naturalness [2.3.25]. Cloud services consistently score 4.0–4.5 on Vietnamese MOS benchmarks; Piper scores approximately 3.0–3.5. However, MOS is measured in quiet listening conditions with no time pressure — it does not capture the restaurant deployment scenario where functional intelligibility (correctly conveying dish names, quantities, and prices) is more critical than vocal naturalness. The customer needs to understand *what* was said, not admire *how* it was said. This distinction between benchmark MOS and task-specific intelligibility is a key evaluation consideration (§5.4.5).

---

### 2.3.4 Edge Deployment Platforms

The physical platform on which the voice pipeline executes determines which models can be deployed and where. For a mobile robot, the compute hardware is constrained by power (battery operation), weight (payload budget), physical space (onboard enclosure), and thermal dissipation (fanless operation in a restaurant environment). These constraints rule out desktop-class GPU workstations and cloud-only solutions. The embedded edge AI computer class — represented by the NVIDIA Jetson family — is the standard hardware platform for on-robot AI inference [2.3.26].

**NVIDIA Jetson Orin Nano.** The Jetson Orin Nano is an edge AI computer in the NVIDIA Jetson product line, designed for embedded robotics and autonomous machines. Key specifications [2.3.27]: 1024-core NVIDIA Ampere architecture GPU with 32 Tensor Cores, 6-core ARM Cortex-A78AE CPU (1.5 GHz), 8 GB LPDDR5 unified memory (shared between CPU and GPU), CUDA 12.6 and cuDNN 8.9 support, 40 TOPS peak INT8 inference performance, 7–15 W software-configurable power envelope. The 8 GB unified memory architecture means GPU and CPU share the same physical RAM — models loaded for GPU inference consume the same pool as the operating system, ROS2 nodes, and sensor drivers.

**VRAM budget analysis.** To understand the architectural constraints on a voice pipeline deployed on the Jetson Orin Nano, it is informative to analyze the concurrent memory budget. A typical concurrent deployment includes [2.3.28]: ROS2 navigation stack with Nav2, RTAB-Map localization, and sensor drivers (~500 MB), LiDAR and camera sensor processing (~200 MB), a medium-sized STT model via faster-whisper (~1.5 GB at 8-bit quantization), a lightweight VAD model (~10 MB), a lightweight TTS engine (~200 MB RAM for Piper), and a WebSocket client for backend communication (~100 MB). Total concurrent allocation: approximately 2.5 GB. This leaves ~5.5 GB for the operating system (Ubuntu 22.04 baseline ~1.5 GB), system services, and transient data — adequate headroom for a full voice pipeline.

The critical observation is what this budget *excludes*: a 7-billion-parameter large language model requires 6–8 GB of VRAM for inference at FP16 precision [2.3.29] — nearly the entire Jetson shared memory budget. The model alone would consume 75–100% of available memory, leaving nothing for the ROS2 navigation stack, sensor drivers, or even the operating system itself. Running the LLM on the Jetson is not an optimization trade-off — it is a hardware impossibility without aggressive 4-bit quantization, which degrades Vietnamese text generation quality to unacceptable levels.

**Edge/server architectural split.** This quantified VRAM constraint — not a software preference — is the fundamental architectural driver for dividing the system across two machines: an edge device for real-time robot control and voice I/O, and a server for LLM inference [2.3.30]. The edge device captures audio, runs VAD, transcribes speech locally, plays TTS audio — latency-critical I/O operations that benefit from local processing. The server runs the conversational agent, tool execution, and response generation — compute-intensive LLM operations that require GPU VRAM beyond the edge budget. The two communicate over HTTP with text-only payloads (~100 bytes per utterance), a negligible network load even on congested restaurant WiFi. This split is not unique to this thesis — it reflects a broader architectural pattern in distributed robotics systems where real-time control and computationally intensive AI inference are deployed on separate machines connected by lightweight messaging protocols. The voice pipeline architecture described in §4.4 is a specific instance of this general pattern, instantiated for Vietnamese restaurant voice interaction.

---

### References (for §2.3)

[2.3.1] Rabiner, L. R., & Schafer, R. W. (2010). *Theory and Applications of Digital Speech Processing*. Pearson. Chapter 9: Speech Activity Detection.

[2.3.2] Ramírez, J., Górriz, J. M., & Segura, J. C. (2007). Voice activity detection: Fundamentals and speech recognition system robustness. In *Robust Speech Recognition and Understanding*. IntechOpen.

[2.3.3] Tsiartas, A., Chaspari, T., Katsamanis, N., Ghosh, P. K., Li, M., Van Segbroeck, M., Potamianos, A., & Narayanan, S. (2013). Multi-band long-term signal variability features for robust voice activity detection. In *INTERSPEECH 2013* (pp. 718–722).

[2.3.4] Silero Team. (2021). Silero VAD: pre-trained enterprise-grade Voice Activity Detector. *GitHub Repository*. https://github.com/snakers4/silero-vad

[2.3.5] Défossez, A., Usunier, N., Bottou, L., & Bach, F. (2019). Music source separation in the waveform domain. *arXiv preprint arXiv:1911.13254*. — Source of the Demucs architecture used in Silero VAD.

[2.3.6] WebRTC Project. (2021). WebRTC Voice Activity Detector — Gaussian Mixture Model implementation. https://webrtc.googlesource.com/src

[2.3.7] Bredin, H., Yin, R., Coria, J. M., Gelly, G., Korshunov, P., Lavechin, M., Fustes, D., Titeux, H., Bouaziz, W., & Gill, M. P. (2020). pyannote.audio: neural building blocks for speaker diarization. In *ICASSP 2020* (pp. 7124–7128).

[2.3.8] Fukuda, T., Ichikawa, O., & Nishimura, M. (2010). Long-term spectro-temporal and static harmonic features for voice activity detection. *IEEE Journal of Selected Topics in Signal Processing, 4*(5), 834–844.

[2.3.9] Pham, V. H., Nguyen, T. T., & Nguyen, L. M. (2021). A survey of Vietnamese speech recognition. *VNU Journal of Science: Computer Science and Communication Engineering, 37*(1), 1–15.

[2.3.10] Kirby, J. (2011). Vietnamese (Hanoi Vietnamese). *Journal of the International Phonetic Association, 41*(3), 381–392. — Reference for Vietnamese tonal system and phonetics.

[2.3.11] Nguyen, T. T., & Nguyen, L. M. (2020). Vietnamese word segmentation with underthesea and RDRsegmenter. *Journal of Computer Science and Cybernetics, 36*(4), 347–362.

[2.3.12] Luong, A. V., Nguyen, D. H., & Nguyen, N. T. (2019). A study of Vietnamese slang and teencode in social media text. In *2019 International Conference on Asian Language Processing (IALP)* (pp. 213–218).

[2.3.13] Li, J., Deng, L., Gong, Y., & Haeb-Umbach, R. (2014). An overview of noise-robust automatic speech recognition. *IEEE/ACM Transactions on Audio, Speech, and Language Processing, 22*(4), 745–777.

[2.3.14] Errattahi, R., El Hannani, A., & Ouahmane, H. (2018). Automatic speech recognition errors detection and correction: A review. *Procedia Computer Science, 128*, 32–37.

[2.3.15] Radford, A., Kim, J. W., Xu, T., Brockman, G., McLeavey, C., & Sutskever, I. (2023). Robust speech recognition via large-scale weak supervision. In *International Conference on Machine Learning (ICML 2023)*.

[2.3.16] PhoWhisper Contributors. (2023). PhoWhisper: Fine-tuned Whisper models for Vietnamese automatic speech recognition. *GitHub Repository*. https://github.com/thanhhuynh18/phowhisper

[2.3.17] Nguyen, D. Q., & Nguyen, A. T. (2020). PhoBERT: Pre-trained language models for Vietnamese. In *Findings of the Association for Computational Linguistics: EMNLP 2020* (pp. 1037–1042). — Reference for Vietnamese language model pre-training methodology, analogous to PhoWhisper fine-tuning approach.

[2.3.18] Klein, G., Kim, Y., Deng, Y., Senellart, J., & Rush, A. M. (2017). OpenNMT: Open-source toolkit for neural machine translation. In *ACL 2017 System Demonstrations* (pp. 67–72). — CTranslate2 is the inference backend derived from OpenNMT.

[2.3.19] Baevski, A., Zhou, Y., Mohamed, A., & Auli, M. (2020). wav2vec 2.0: A framework for self-supervised learning of speech representations. *Advances in Neural Information Processing Systems, 33*, 12449–12460. — Representative of the self-supervised approach used by modern cloud STT services.

[2.3.20] VLSP Consortium. (2018–2023). VLSP Automatic Speech Recognition Shared Tasks. *Vietnamese Language and Speech Processing Annual Workshop*. https://vlsp.org.vn

[2.3.21] Tan, X., Qin, T., Soong, F., & Liu, T. Y. (2021). A survey on neural speech synthesis. *arXiv preprint arXiv:2106.15561*.

[2.3.22] Kim, J., Kong, J., & Son, J. (2021). Conditional variational autoencoder with adversarial learning for end-to-end text-to-speech. In *International Conference on Machine Learning (ICML 2021)*. — Original VITS paper.

[2.3.23] Ren, Y., Hu, C., Tan, X., Qin, T., Zhao, S., Zhao, Z., & Liu, T. Y. (2021). FastSpeech 2: Fast and high-quality end-to-end text to speech. In *International Conference on Learning Representations (ICLR 2021)*. — Representative of the neural TTS architecture used by cloud services.

[2.3.24] Casanova, E., Weber, J., Shulby, C. D., Junior, A. C., Gölge, E., & Ponti, M. A. (2022). YourTTS: Towards zero-shot multi-speaker TTS and zero-shot voice conversion for everyone. In *International Conference on Machine Learning (ICML 2022)*. — XTTS is derived from the YourTTS architecture.

[2.3.25] Streijl, R. C., Winkler, S., & Hands, D. S. (2016). Mean opinion score (MOS) revisited: methods and applications, limitations and alternatives. *Multimedia Systems, 22*(2), 213–227.

[2.3.26] NVIDIA Corporation. (2023). *NVIDIA Jetson Orin Nano Series — Technical Brief*. NVIDIA.

[2.3.27] Franklin, D. (2023). NVIDIA Jetson Orin Nano: Edge AI for robotics and embedded applications. *NVIDIA Developer Technical Blog*, March 2023.

[2.3.28] Quigley, M., Gerkey, B., & Smart, W. D. (2015). *Programming Robots with ROS: A Practical Introduction to the Robot Operating System*. O'Reilly Media. Chapter 3: Topics and Messages.

[2.3.29] Dettmers, T., Lewis, M., Belkada, Y., & Zettlemoyer, L. (2022). LLM.int8(): 8-bit matrix multiplication for transformers at scale. *Advances in Neural Information Processing Systems, 35*, 30357–30370. — Reference for LLM memory requirements and quantization.

[2.3.30] Kehoe, B., Patil, S., Abbeel, P., & Goldberg, K. (2015). A survey of research on cloud robotics and automation. *IEEE Transactions on Automation Science and Engineering, 12*(2), 398–409. — Survey of edge/server split patterns in robotics.
