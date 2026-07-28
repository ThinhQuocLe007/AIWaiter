## 2.3 Vietnamese Voice Understanding

A restaurant robot's voice interaction system must process tonal Vietnamese speech accurately amidst severe acoustic noise (kitchen clatter, concurrent conversations) while sustaining a natural conversational rhythm. To achieve this, every component in the voice pipeline is evaluated against three non-negotiable systemic constraints:
- Connectivity: The system must operate fully on the edge. Relying on network round-trips turns temporary WiFi outages into total interface failures rather than mere degradations.
- Memory: The edge device provides a single memory pool. Any footprint claimed by the voice models is directly subtracted from the capacity available to the robot's running navigation stack and operating system.
- Latency Budget: Conversational latency is a zero-sum budget. From the mandatory trailing silence in voice activity detection to transcription and synthesis scaling, components compete for time. Any gain in accuracy must be weighed against the downstream latency it incurs

### 2.3.1 Voice Activity Detection

Voice activity detection (VAD) determines the boundaries of a spoken utterance within a continuous audio stream, specifically identifying when a customer starts and stops speaking. As the initial processing stage, its output—a trimmed audio segment containing exactly one utterance—feeds directly into the transcription model.  
The accuracy of this single stage dictates the upper bound of performance for everything that follows. If the detector terminates an utterance prematurely, the transcriber receives a truncated sentence, preventing the system from capturing the complete order. Conversely, if detection triggers falsely on background noise, all downstream components—transcription, intent classification, reasoning, and validation—will waste computational resources processing restaurant clatter as though it were a valid customer order.
To address audio segmentation, previous research and industrial applications generally fall into three categories:

- Energy Thresholding: The simplest approach classifies any audio frame whose root-mean-square (RMS) amplitude exceeds a fixed threshold as speech. While effective in quiet recording environments, this method fails in restaurant settings because the ambient noise floor regularly exceeds the amplitude of quiet speech. It provides no mechanism to separate speech from non-speech at comparable loudness; raising the threshold loses trailing syllables, while lowering it causes continuous false triggers
- Lightweight Neural Models (CPU-based): To overcome amplitude limitations, lightweight neural models classify frames based on learned spectral structures. WebRTC VAD (approximately 100 KB) applies a Gaussian mixture model; while extremely lightweight, its accuracy degrades significantly under noise. In contrast, Silero VAD (approximately 2 MB) emits a speech probability per frame and exposes a configurable decision threshold, handling noise much more effectively. A key advantage of both is that they execute in real time entirely on the CPU.
- Large Neural Models (GPU-based): At the state-of-the-art end of the spectrum, systems such as pyannote.audio (roughly 100 MB) and NVIDIA NeMo's VAD (roughly 200 MB) utilize large architectures for highly accurate frame-level discrimination. However, real-time operation for these models strictly requires GPU inference.


The following table summarizes the documented footprint, compute requirements, and noise discrimination capabilities of the surveyed approaches.
**Table 2.3a.** Voice activity detection approaches.

| Approach | Footprint | Inference | Discrimination under noise | GPU required | Documented evaluation context |
|---|---:|---|:---:|:---:|---|
| Energy threshold | n/a | Trivial | Poor; cannot separate speech from noise at similar amplitude | No | Quiet recording conditions [2.3.1] |
| WebRTC VAD | ~100 KB | CPU, real-time | Moderate | No | Telephony-quality speech [2.3.3] |
| Silero VAD | ~2 MB | CPU, real-time | Good; threshold configurable | No | Multilingual telephone and meeting audio [2.3.2] |
| pyannote.audio | ~100 MB | GPU | High | Yes | Meeting and diarization corpora [2.3.4] |
| NeMo VAD | ~200 MB | GPU | High | Yes | NVIDIA internal benchmarks [2.3.5] |


Rather than establishing a single optimal choice, the literature indicates that any detector's viability is governed by its hardware constraints and two primary behavioral parameters. Structurally, the choice depends on footprint and compute limitations; committing scarce edge GPU capacity to an always-on detector is difficult to justify if CPU-only alternatives are adequate. Behaviorally, the first parameter is the decision threshold on the per-frame speech probability, which trades the suppression of false triggers against the risk of clipping quiet onsets. The second is the fixed interval of observed silence used to declare an utterance finished. This silence interval elapses on every turn before transcription begins, strictly setting a floor on conversational latency that no downstream optimization can recover.

### 2.3.2 Speech-to-Text for Vietnamese
Speech-to-text (STT) converts the isolated audio segment into Vietnamese text and stands as the most consequential stage in the processing pipeline. Every downstream component—including the intent classifier, language model, and response generator—operates strictly on the text produced here, meaning no downstream system can recover information lost to transcription errors. Crucially for the Vietnamese language, a tonal diacritic error (e.g., transcribing cá [fish] as cà [eggplant]) does not manifest as a pipeline failure; instead, it propagates as a correctly processed order for an entirely wrong dish.
Current transcription systems suitable for this domain fall into three categories:
- Cloud-based Dedicated Services: Providers like Google Cloud STT, Viettel AI, and FPT.AI offer dedicated Vietnamese recognition trained on large corpora, achieving high accuracy on clean speech via server-grade infrastructure. However, their reliance on network round-trips introduces a strict structural limitation: it places conversational latency partly outside the system's control and turns temporary WiFi outages into total failures of the voice interface.  
- On-device Multilingual Models: The Whisper architecture (a Transformer encoder-decoder trained on 680,000 hours of web audio) is the dominant choice for edge deployment. While it handles Vietnamese competently, the language was not a primary optimization target. Its deployment viability is significantly enhanced by faster-whisper and the CTranslate2 inference engine, which apply operator fusion, memory-layout optimization, and integer quantization to reduce both latency and memory footprint, distributing the models ready to load.  - On-device Vietnamese-Targeted Models: PhoWhisper fine-tunes the Whisper architecture specifically on Vietnamese speech data. This targeting reportedly improves word error rates over the multilingual base, with gains notably concentrated in correcting tonal diacritics—directly addressing the critical failure mode mentioned above. Because it maintains its base architecture, it holds the exact same parameter count and decodes in the same time as multilingual Whisper, though it requires a one-time build step to convert its weights into the CTranslate2 format. 
The following table outlines the structural and deployment characteristics of the available options.
**Table 2.3b.** Speech-to-text options for Vietnamese. The disk figures are the weights alone, that is the parameter count at the stored precision, two bytes per parameter at float16. Runtime memory is larger, because the inference context and the working buffers sit on top of the weights, and the two are frequently conflated; a measured figure for the deployed configuration is given in §4.4. The English-only Whisper checkpoints are omitted as inapplicable to Vietnamese.

| Model / service | Parameters | Vietnamese | Distribution format | Disk | Offline |
|---|---:|---|---|---:|:---:|
| Whisper tiny | 39M | Multilingual, not targeted | CTranslate2, ready to load | ~75 MB | ✓ |
| Whisper base | 74M | Multilingual, not targeted | CTranslate2, ready to load | ~145 MB | ✓ |
| Whisper small | 244M | Multilingual, not targeted | CTranslate2, ready to load | ~485 MB | ✓ |
| Whisper medium | 769M | Multilingual, not targeted | CTranslate2, ready to load | ~1.5 GB | ✓ |
| Whisper large-v3 | 1.55B | Multilingual, not targeted | CTranslate2, ready to load | ~3 GB | ✓ |
| Whisper large-v3-turbo | 809M (large-v3 encoder, four-layer decoder) | Multilingual, not targeted | CTranslate2, ready to load | ~1.6 GB | ✓ |
| PhoWhisper medium | 769M (Whisper medium architecture) | Fine-tuned on Vietnamese | Transformers; conversion required for CTranslate2 | ~1.5 GB once converted (~3 GB as released, fp32) | ✓ |
| Google Cloud STT | n/a | Dedicated Vietnamese model | Hosted API | n/a | ✗ |
| Viettel AI STT | n/a | Dedicated Vietnamese model | Hosted API | n/a | ✗ |
| FPT.AI STT | n/a | Dedicated Vietnamese model | Hosted API | n/a | ✗ |

Word error rates are deliberately excluded from this comparison. Published accuracy figures for these models are derived from disjointed corpora recorded under different conditions—ranging from multilingual benchmarks to quiet, standard-pronunciation academic datasets like VLSP—making a single ranked accuracy column structurally invalid.  Ultimately, selecting an STT component requires evaluating connectivity constraints against hardware budgets. Cloud APIs offer accuracy but fail without a network, whereas edge models ensure reliability but consume a fixed memory budget. Within the edge models, the division between a targeted Vietnamese model (PhoWhisper) and its multilingual base (Whisper) is remarkably narrow: they share identical inference costs, parameter counts, and footprints. The primary difference lies strictly in their training distributions and a one-time build-step requirement, leaving it an open empirical question whether the fine-tuned model's theoretical accuracy advantage persists once the audio leaves the recording studio and enters a noisy dining room.


### 2.3.3 Text-to-Speech for Vietnamese

The final stage of the voice pipeline converts the agent's generated Vietnamese text into audible speech. Quality in this stage is evaluated along two axes: intelligibility (whether the customer can easily recover the words) and naturalness (whether the voice is appropriate for a service setting). For Vietnamese, a third, critical consideration applies because tone is lexical: a synthesizer that renders diacritics inaccurately does not merely sound unnatural; it fundamentally alters the meaning of the words being spoken
The available synthesis engines span a wide range of model complexities and deployment requirements:
- Formant Synthesis (Rule-based): At the lightest extreme, engines like eSpeak-NG model the vocal tract as a set of resonant frequencies and apply rules to shape them into phonemes. While the output is unmistakably mechanical and lacks natural prosody, it requires only 5 MB of footprint, runs effortlessly on any CPU, and its phoneme tables provide full coverage of the Vietnamese tonal system.
- Lightweight Neural Models (CPU-based): Systems like Piper occupy the middle ground, implementing the VITS architecture to convert text directly to a waveform in a single pass without an intermediate vocoder. The community-trained Vietnamese voice requires approximately 200 MB, synthesizes sentences on a CPU in roughly half a second, and renders tones correctly. It provides a fully intelligible, albeit audibly synthetic, output and is the only neural Vietnamese voice that fits an edge memory budget without demanding GPU capacity.
- Large Neural Models (GPU-based): Coqui's XTTS v2 represents the upper limit of on-device synthesis. It utilizes a large autoregressive model with a separate vocoder, supports Vietnamese, and offers voice cloning. However, its naturalness comes at a massive structural cost: roughly 4 GB of GPU memory, forcing it to compete directly with the transcription model and navigation stack.
- Hosted Cloud Services: Microsoft Azure (via edge-tts), Google Cloud TTS, vbee, and FPT.AI supply highly natural, regional-specific Vietnamese voices. While their naturalness exceeds any on-device option, they strictly require network connectivity for every sentence spoken.

The table below outlines the trade-offs in footprint and compute resources
**Table 2.3c.** Text-to-speech engines for Vietnamese.

| Engine | Synthesis approach | Footprint | Compute | Offline | Vietnamese voices |
|---|---|---:|---|:---:|---|
| eSpeak-NG | Formant, rule-based | ~5 MB | CPU | ✓ | Phoneme tables, full tonal coverage |
| Piper | VITS, single-stage neural | ~200 MB | CPU | ✓ | One community-trained voice |
| XTTS v2 | Autoregressive + vocoder | ~4 GB | GPU | ✓ | Multilingual, voice cloning |
| edge-tts (Azure) | Neural, hosted | n/a | Cloud | ✗ | Multiple, regional accents |
| Google Cloud TTS | WaveNet, hosted | n/a | Cloud | ✗ | WaveNet voices |
| vbee | Neural, hosted | n/a | Cloud | ✗ | Vietnamese-specific |
| FPT.AI TTS | Neural, hosted | n/a | Cloud | ✗ | Vietnamese-specific |

Conventional Mean Opinion Scores (MOS) for naturalness are deliberately omitted here. Published scores are derived from varying listener pools, different text materials, and distinct listening environments, rendering a ranked comparison mathematically invalid. Furthermore, under heavy restaurant noise, the gap between a moderately natural voice and a highly natural one compresses significantly, as raw intelligibility becomes the limiting factor. Ultimately, selecting a TTS engine requires discrete commitments rather than slight trade-offs: crossing the GPU line displaces critical robot navigation systems, while crossing the network line risks total system failure upon a WiFi outage.

### 2.3.4 Identified Literature Gaps 
Identified Literature GapsA review of the existing voice understanding pipeline reveals two fundamental gaps when transitioning from standard environments to a dining room setting:
Acoustic and Empirical Gaps: The literature supplies no definitive values for three critical system metrics: the VAD frame-level decision threshold, the silence interval that terminates an utterance, and the STT accuracy on restaurant-domain vocabulary. Existing evaluations strictly assume quiet conditions, read speech, or telephony, completely ignoring the defining acoustic challenge of a restaurant: intelligible conversation carrying from an adjacent table. These three parameters must therefore be treated as empirical quantities rather than preset configurations.  
Orchestration and Interaction Gaps: Traditional voice assistants assume a unified physical architecture where the microphone, speaker, user, and wake-word trigger occupy the same location. In contrast, a restaurant robot requires decoupled orchestration. Capture is armed deliberately via a customer tablet, routed through a server to a dynamically moving robot, and must remain completely interruptible (allowing cancellations, muting, or barging in). Because acoustic models are indifferent to how they are invoked, this complex orchestration layer has no existing counterpart in standard single-device voice assistant literature and must be custom-built. 