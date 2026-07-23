## 2.8 Edge Computing Platform

> *The computer aboard the robot determines what can run there, and by exclusion what must run elsewhere. This section describes the workload such a robot carries, surveys how prior work has divided robot computation between the vehicle and off-board infrastructure, examines the classes of embedded accelerator that can host whatever remains on the vehicle, and describes the NVIDIA Jetson Orin Nano — its position within its product family, the software stack that makes GPU-accelerated inference available on an embedded board, and the interfaces through which sensors reach it. The property that matters most for the architecture is not compute throughput but the memory model, and the section closes on what the published deployments do and do not tell us about running two demanding workloads on one such board.*
>
> **Section type: [MIXED].** §2.8.3–§2.8.5 are a [USE] survey of off-the-shelf boards ending in a comparison table, from which §4.9 selects. §2.8.2 is a [BUILD] survey: the placement of computation between vehicle and infrastructure is a design question, and it ends in a gap statement that §4.4.1 answers.
>
> **Cross-refs:** §2.2 (navigation stack), §2.3 (voice pipeline components and their footprints), §2.6 (fleet orchestration), §3.3 (robot hardware setup — wiring and component specifications), §4.4 (edge/server workload split), §5.4.4 (edge performance measurement)
> **Citations:** [2.8.1]–[2.8.22]; final numbering assigned when all Ch.2 references are merged. Bibliographic entries for this section are pending — see `references.md`.
> **Figures and tables:** keyed section-scoped (`Table 2.8a`, …). Flatten to sequential chapter numbering on merge.

---

The edge computer differs from the other components surveyed in this chapter in one respect worth stating plainly: it was purchased before the software that runs on it was written, and no comparative procurement study preceded that purchase. The survey of boards below is therefore not a record of a selection process but its converse — a check, performed after the fact, of which classes of board can host the workload that remains on the vehicle, and which cannot.

That workload is not itself a given. How much computation a mobile robot carries, and how much it delegates to infrastructure it can reach over a network, is a design decision with its own literature and its own trade-offs, and it is logically prior to the choice of board: what the vehicle must compute determines what the vehicle must compute *with*. This section therefore proceeds in that order — the workload, its placement, and only then the hardware.

---

### 2.8.1 The Workload Aboard a Service Robot

A robot of the class considered here carries two families of computation, established independently elsewhere in this chapter.

The first is perception and motion (§2.2): a graph-based SLAM system operating on RGB-D input, a navigation stack maintaining costmaps and planning continuously, an extended Kalman filter fusing wheel odometry with inertial measurement, and fiducial marker detection on the camera stream. These are predominantly CPU-bound and run as a set of concurrent middleware processes. They are also hard-real-time in the practical sense: a planner that stalls is a robot that does not stop when it should.

The second is speech (§2.3): a voice activity detector, a speech recognition model in the Whisper family, and a speech synthesiser. Of these the recogniser dominates the resource footprint, and the size at which it is deployed is not incidental. The smaller members of the family reduce memory and latency at a cost in word error rate that falls disproportionately on tonal diacritics (§2.3) — the dimension on which a Vietnamese ordering system is least able to absorb degradation. At the *medium* size the recogniser is approximately 769M parameters, some 1.5 GB of weights in half precision.

A third family — the language model that interprets the transcribed utterance and decides what to do about it — is larger than either, and whether it belongs on the vehicle at all is the subject of §2.8.2.

Between them these workloads demand four things of whatever host runs them, and the four are worth naming because they discriminate sharply between hardware classes that a headline specification would rank as similar.

**A general-purpose accelerator rather than a fixed-function one.** The recogniser is an encoder-decoder Transformer executed autoregressively with beam search, and the runtimes that execute it efficiently (§2.3) reach the accelerator through a general-purpose compute API. A board whose acceleration is available only through a vendor-specific neural network compiler does not run this workload; it runs a different workload that would first have to be built.

**Memory bandwidth adequate for autoregressive decoding**, which — as §2.8.3 develops — is the performance characteristic that governs this workload, and is not the same thing as arithmetic throughput.

**Half-precision execution without mandatory quantisation.** A platform that requires reduction to 8-bit integer precision in order to use its accelerator at all introduces an accuracy risk concentrated, again, on tonal distinctions.

**A vendor-supported ROS2 distribution on the host architecture.** The navigation stack is a set of middleware packages distributed for a particular Ubuntu release. Cross-compilation or source builds of the full stack are possible but constitute a maintenance burden disproportionate to the rest of the work.

To these a non-computational constraint applies: the board must draw a current the robot's battery system can supply alongside motors and sensors, and must physically mount within the chassis.

These are characteristics of the workload, not requirements of this system; the system's requirements are stated in §4.1, and the selection they drive is made in §4.9.

---

### 2.8.2 Placement of Computation: Onboard, Offboard, and the Split

Deciding what a mobile robot computes for itself is a long-standing design question, and the literature that treats it directly is *cloud robotics* — the study of robots that delegate computation, storage, or knowledge to infrastructure reachable over a network [2.8.19]. The motivating observation is that a vehicle is a poor place to put computation: it is power-limited, thermally limited, mass-limited, and expensive to upgrade, while a server subject to none of those limits can be reached in milliseconds over a local network. Early systems in this line explored shared knowledge bases from which many robots draw and to which each contributes [2.8.20], and the same reasoning appears in mobile edge computing, where the question is posed as one of computation offloading: which tasks to execute locally, which to ship to an edge server, and on what criterion to decide [2.8.21].

Three positions on this spectrum appear in deployed robotics.

**Fully onboard.** The vehicle computes everything and depends on no infrastructure. This is the position of most autonomous navigation research, and its advantages are self-evident: no network dependence, no infrastructure to provision, and a failure mode confined to the vehicle. Its cost is that the vehicle's compute envelope bounds the system's capability permanently, and that every capability upgrade is a hardware upgrade replicated across the fleet.

**Fully offboard.** The vehicle streams sensor data to infrastructure and receives commands in return. This maximises available capability and minimises vehicle cost, and it is the position taken by voice assistant products, which transmit audio to a service and return synthesised speech. Its cost is a hard dependence on the network for basic function: a connectivity failure does not degrade the system, it stops it. For a robot whose motion control is on the far side of that link, the failure is also a safety matter.

**Split.** The vehicle retains what must not fail and what must not wait; infrastructure hosts what is too large to carry. This is the position the offloading literature generally recommends, and the criteria it offers for drawing the line are latency, energy, and bandwidth [2.8.21] — a task is offloaded when transmitting its input costs less than computing it locally.

Those criteria are the ones the literature optimises, and they are not the only ones that bear on where the line falls in a commercial service deployment. Three further considerations appear in practice and are treated only incidentally in that literature.

The first is **data residence**. A service robot is a physically exposed device operating unattended in a space open to the public; it can be interfered with, damaged, or removed in a way that a server in a back office cannot. Whatever business data resides on the vehicle — menus, prices, order history, payment state, conversation transcripts — shares that exposure. Placing the authoritative copy of such data on infrastructure and leaving the vehicle with only transient working state changes what a compromised vehicle is worth, and it does so independently of how much compute the vehicle happens to have.

The second is **fleet consistency**. When several vehicles serve one establishment, any state replicated across them can diverge: a menu updated on three robots and not the fourth is a pricing error with a customer at the end of it. Centralising the authoritative state removes the class of fault rather than managing it (§2.6).

The third is **update surface**. Capability that lives on infrastructure is revised in one place; capability that lives on vehicles is revised once per vehicle, under whatever access and downtime constraints a working restaurant imposes.

What these three share is that none of them is a function of the vehicle's compute capacity. A split motivated by them alone would remain the correct design on a vehicle with abundant memory — which is the property that distinguishes an architectural decision from a workaround, and which the offloading literature's latency-and-energy framing does not capture, because it treats placement as an optimisation to be re-evaluated whenever the hardware changes rather than as a boundary with reasons of its own.

**→ Gap.** The offloading literature supplies criteria for splitting robot computation and the cloud robotics literature supplies architectures for doing so, but both frame the decision as a resource optimisation: offload what is expensive to compute locally, retain what is expensive to transmit. What neither characterises is a split drawn on functional grounds — a boundary placed so that the vehicle holds no authoritative state and no business data at all, retaining only the perception and motion it cannot safely delegate and the transcription that must survive a network outage, with every consequence of that boundary for resilience, fleet consistency, and the value of a compromised vehicle following from the placement rather than from the hardware. The placement adopted here, and the reasoning that fixes each component on one side of the line, is set out in §4.4.1.

---

### 2.8.3 Accelerator Classes: GPU, NPU, and the TOPS Metric

Embedded boards marketed for artificial intelligence workloads are commonly compared by a single headline figure — operations per second, quoted in TOPS — and on that figure several boards costing considerably less than a Jetson appear competitive or superior. The comparison does not survive contact with this particular workload, and the reason is instructive enough to state carefully, because it is the question an examiner familiar with embedded platforms is most likely to raise.

TOPS is a measure of dense integer arithmetic throughput, and it is quoted from benchmarks dominated by convolution: many arithmetic operations performed on each byte fetched from memory. Under that access pattern the arithmetic unit is the bottleneck and its throughput predicts performance. Autoregressive Transformer decoding has the opposite character. Each decoding step reads the model's weights and the accumulated key-value cache and performs comparatively little arithmetic on what it reads; its arithmetic intensity is close to unity, placing it firmly on the memory-bound side of the roofline [2.8.10]. The step is repeated once per output token. Performance is therefore governed by how fast the accelerator can stream memory, not by how many operations it could perform on data already resident [2.8.11] — and TOPS, which measures the latter, predicts the former only loosely. This is why memory bandwidth, and not TOPS, is the figure to compare: between two boards, the one with the higher memory bandwidth is the better predictor of decoding latency, largely irrespective of which quotes the larger TOPS figure.

Three further properties separate fixed-function neural accelerators from general-purpose GPUs on this workload.

The first is the supported operator set. Neural processing units of the class found on embedded system-on-chip designs and on discrete inference accelerators [2.8.12]–[2.8.13] are built around statically shaped integer convolutional networks. Autoregressive decoding requires dynamic sequence lengths, a key-value cache that grows during execution, and — in this system — beam search maintaining several hypotheses concurrently (§4.4.2). Encoder-decoder speech recognition under beam search is not a supported execution path in the production toolchains for these accelerators, and where community ports exist they typically execute the encoder on the accelerator and fall back to the CPU for the decoder, which is the part that dominates the latency.

The second is precision. Most fixed-function accelerators of this class execute 8-bit integer arithmetic and offer no half-precision fallback, so using them is not optional quantisation but mandatory quantisation. For a recogniser whose discriminative signal in Vietnamese lies substantially in tonal diacritics, mandatory reduction to 8-bit precision represents an accuracy risk that would have to be characterised empirically before it could be accepted — a measurement absent from the published record for this language.

The third is the toolchain. Reaching a vendor accelerator requires compiling the model through a vendor-specific graph compiler, each with its own operator support matrix and its own quantisation calibration procedure. Where a general-purpose GPU executes an unmodified upstream inference runtime, a neural processing unit requires a port. The cost is not the compilation itself but the ongoing coupling: every model change re-enters the compiler, and every unsupported operator becomes an engineering problem rather than a configuration one.

The consequence is that the property this application requires of its accelerator is not throughput. It is that the accelerator be programmable through a general-purpose compute API, expose sufficient memory bandwidth, and execute half precision natively — three properties that the accelerator classes offering the best TOPS-per-unit-cost for convolutional vision do not possess, and that a small general-purpose GPU possesses without qualification.

---

### 2.8.4 The Jetson Orin Nano — Hardware and Software Stack

The Jetson Orin Nano Developer Kit is a single-board computer built for embedded inference and robotics. It carries a 1024-core Ampere-architecture GPU with 32 tensor cores, a six-core Arm Cortex-A78AE CPU, and 8 GB of LPDDR5 memory, within a power envelope configurable between roughly 7 and 15 watts [2.8.1]. Physically it is small enough to mount in a robot's electronics bay, and at its default sustained power mode it draws a current a modest battery system can supply alongside motors and sensors.

Of these specifications the memory is the consequential one, and not because 8 GB is a particular quantity. The Orin Nano uses a *unified* memory architecture: CPU and GPU address one physical pool rather than each having its own [2.8.1]. There is no separate system RAM and video RAM between which work can be balanced. The operating system, the middleware, every sensor driver, every neural network, and every buffer allocated by any of them draw from the same 8 GB. Exceeding it does not degrade performance gracefully in the manner of a system that can page to disk; the kernel's out-of-memory killer terminates whichever process holds the largest allocation. On a robot, the processes holding large allocations are the ones performing perception and motion, so the failure mode of over-committing memory is not slowness but a robot that stops controlling itself. The question of what runs on this board is consequently a question of what fits, simultaneously, in one shared 8 GB — and it admits no partial answers.

The software distribution is JetPack, which bundles an operating system with the GPU stack [2.8.3]. The operating system, Linux for Tegra, is Ubuntu built for ARM64 and presents an ordinary Ubuntu environment — standard package management, a system Python, standard POSIX interfaces — so ROS2 distributions targeting that Ubuntu release install from their usual repositories without cross-compilation, which is what the middleware stack requires of its host. Above it sit CUDA, providing the GPU programming interface and allocation against the unified pool; cuDNN, supplying the accelerated primitives that neural network layers are built from; and TensorRT, an optimizing compiler that rewrites a trained network into a tuned execution plan [2.8.4].

The third of these warrants a qualification, because its presence in the stack is often taken to imply its use. TensorRT is available on this platform and is the conventional route to optimized inference on it, but the speech recogniser deployed in this system does not pass through it: the inference runtime selected in §2.3 performs its own operator fusion and quantisation and addresses the GPU through CUDA directly (§4.4.2). Two considerations support leaving it there. The recogniser's architecture is one for which that runtime already provides tuned kernels, so the marginal gain from a second optimizing pass is small; and TensorRT's larger benefit on this class of board accrues to language model inference, which in this architecture does not occur on the board at all. Compiling the recogniser to a TensorRT engine remains an available optimization and is noted as such (§6.3) rather than claimed as one performed.

What the stack provides — and what the general-purpose-accelerator characteristic of §2.8.1 demands — is that an inference runtime written for desktop GPUs executes on this board without modification.

---

### 2.8.5 Platform Comparison

The boards below span the classes of embedded computer that could plausibly host this workload. They are compared against the workload characteristics set out in §2.8.1, on the placement established in §2.8.2 — that is, as hosts for perception, motion, and speech, but not for the language model.

**Table 2.8a** — Candidate platform classes against the workload characteristics of §2.8.1 [2.8.1]–[2.8.2], [2.8.12]–[2.8.16]. *All quantitative cells are* **Unverified** *pending vendor datasheet confirmation; prices are indicative single-unit figures in USD and are volatile.*

| Platform | Accelerator | Memory bandwidth | Half precision | ASR runtime path | ROS2 Humble arm64/x86 | Power | Indicative cost |
|---|---|---|---|---|---|---|---|
| Raspberry Pi 5 (8/16 GB) | None (no NN accelerator) | ~17 GB/s | CPU only | CPU, 8-bit integer | Source build / community | ~5–12 W | ~80–120 |
| Pi 5 + discrete NN accelerator | Fixed-function, ~13–26 TOPS | ~17 GB/s (host) | No | Unsupported for encoder-decoder ASR | As above | ~10–17 W | ~150–230 |
| RK3588 SBC (8–32 GB) | Fixed-function NPU, ~6 TOPS | ~30–50 GB/s | No | Vendor compiler; community ports, CPU decoder | Community | ~8–15 W | ~150–190 |
| Intel N100 mini-PC (16 GB) | Integrated graphics, no NPU | ~38 GB/s | Limited | CPU, 8-bit integer (mature) | Native x86 | ~15–25 W | ~150–180 |
| **Jetson Orin Nano (8 GB)** | **General-purpose GPU, CUDA** | **~68–102 GB/s** | **Native** | **Unmodified upstream runtime, CUDA** | **Vendor (JetPack)** | **~7–15 W** | **~250** |
| Jetson Orin NX (8/16 GB) | General-purpose GPU, CUDA | ~102 GB/s | Native | As above | Vendor (JetPack) | ~10–25 W | ~800–900 + carrier |
| Jetson AGX Orin (32/64 GB) | General-purpose GPU, CUDA | ~205 GB/s | Native | As above | Vendor (JetPack) | ~15–60 W | ~2,000 |

Three observations follow, and the third is the one that matters architecturally.

The boards without a general-purpose accelerator cannot host the recogniser at all. This is not a statement about their capability — the Raspberry Pi 5 and the RK3588 platforms are capable computers, and the latter's neural processing unit is genuinely useful for the convolutional vision workloads it was designed for. It is a statement about the workload: the speech recogniser as deployed cannot reach those accelerators, and reaching them would mean replacing the recognition stack rather than porting it.

The x86 mini-PC class is the closest competitor and is not dismissed here. The inference runtime used in this system has mature, well-optimized integer CPU kernels, and on a board of this class the recogniser would run — more slowly, but plausibly within an interactive budget for short utterances. Its disadvantages are narrower than the preceding paragraph's: no accelerator remains available for concurrent vision work, the middleware and the recogniser contend for the same few cores, and the power and mounting arrangements suit a desk better than a chassis. Whether that margin is decisive is an empirical question this chapter does not settle, and §5.4.4 measures only the platform actually deployed. The honest position is that the mini-PC class is a viable alternative for a voice-only edge node and a weaker one for a node that must also perceive.

The Jetson boards above the Orin Nano satisfy every characteristic and offer one capability besides: at 16 GB and above, the unified pool is large enough to host a quantised language model alongside perception. It is worth being precise about what that capability would and would not change. It would remove the *memory* argument for placing the language model off the vehicle. It would leave untouched the three considerations of §2.8.2 that do not depend on vehicle capacity — data residence, fleet consistency, and update surface — each of which continues to favour infrastructure on a board of any size. The placement adopted here is therefore not a concession extracted by an 8 GB ceiling, and a larger board would not have reversed it; the ceiling and the design agree, which is a weaker claim than the ceiling causing the design but a considerably more robust one. What the smaller board does determine is that the agreement is not optional, and that the architecture's resilience to a network outage (§4.4.1) had to be engineered rather than assumed.

**Table 2.8b** — Position of the Orin Nano within the Jetson family [2.8.1]–[2.8.2].

| Board | Unified memory | Generation | Relevance to a robot that need not host a language model locally |
|---|---:|---|---|
| Jetson AGX Orin | 32 GB | Ampere, current | Sufficient to co-host a 7B-parameter model with perception; priced for industrial deployment |
| Jetson Orin NX | 8–16 GB | Ampere, current | Intermediate; the 16 GB variant relaxes but does not remove the shared-pool constraint |
| **Jetson Orin Nano** | **8 GB** | **Ampere, current** | **GPU adequate for real-time speech inference; memory adequate for perception and voice but not for a language model alongside them** |
| Jetson Xavier NX | 8 GB | Volta, superseded | Widely used in earlier academic robotics; discontinued |

A note on cost at scale, since the figures above are single-unit prices and the deployment they describe is not. A restaurant fleet amortises one server across many robots, so the quantity that governs deployment cost is the per-robot bill of materials, not the total. An architecture that keeps the language model on shared infrastructure therefore lowers cost per robot as the fleet grows, and makes the *smallest* board satisfying the workload the correct choice at scale rather than a compromise accepted at prototype scale. The same reasoning, pressed one step further, would ask why speech recognition remains on the vehicle at all rather than joining the language model on the server; that boundary is argued on grounds of network dependence, aggregate audio bandwidth, and audio locality in §4.4.1, not on grounds of cost.

---

### 2.8.6 Sensor Interfaces

Sensors reach the board over standard buses, and the specifications of the individual devices belong with the platform description in §3.3 rather than here. What is worth recording at this level is the aggregate: several devices reporting concurrently at different rates over a small number of controllers.

**Table 2.8c** — Sensor classes and their interface characteristics on this class of board [2.8.5].

| Sensor class | Bus | Typical report rate | Data volume | Consumed by |
|---|---|---|---|---|
| 2D laser scanner | USB 2.0 (serial) | Several Hz | Low — one scan per revolution | Mapping, localization, obstacle costmaps |
| RGB-D camera | USB 3.0 | Tens of Hz | High — colour and depth frames | Visual place recognition, marker detection |
| Inertial measurement unit | I²C to microcontroller, serial to board | Hundreds of Hz | Very low | Odometry fusion |
| Microphone | USB audio | Continuous at audio sample rate | Low | Speech detection and transcription |
| Audio output | USB, analogue, or Bluetooth | Continuous during playback | Low | Speech synthesis |

The depth camera dominates this table: it is the only device whose bandwidth requires the faster bus, and it is the reason USB 3.0 is a requirement of the platform rather than a convenience. Beyond bandwidth, the aggregate raises a scheduling question rather than a capacity one — several drivers servicing devices at rates differing by two orders of magnitude, on a CPU also running middleware, inference, and control.

---

### 2.8.7 Prior Work on Jetson in Robotics

Jetson boards are widely used in academic and research robotics, and the individual workloads are well documented. Published deployments cover simultaneous localization and mapping, autonomous navigation, sensor fusion, and vision tasks including object detection and fiducial marker recognition, with performance figures reported across ROS2 distributions and Jetson generations [2.8.6]–[2.8.7]. Speech workloads are likewise documented, with optimized inference runtimes reported to achieve real-time transcription on this class of board [2.8.8]. The platform's suitability for either category of work, taken by itself, is not in question.

What the literature reports less often is the two categories running together. Published robotics deployments describe robots that navigate; published speech deployments describe assistants that listen. Where both appear in one system, the reported measurements are typically of each subsystem in isolation, because that is how each was developed and benchmarked [2.8.9]. This leaves the interaction uncharacterised, and on a unified-memory board the interaction is precisely where the risk lies: two workloads that each fit comfortably alone may not fit together, and the manner in which they fail to fit is abrupt rather than gradual.

---

Two properties of this platform bear on everything built above it, and they pull in opposite directions.

The first is that the board is genuinely capable, and capable in the specific respects this workload requires rather than in the respects its marketing emphasises. Its GPU executes transformer inference at speeds adequate for interactive use, its memory bandwidth suits a decoding workload that arithmetic throughput would not predict, its CPU carries a full middleware stack and its drivers, and its software distribution is mature enough that neither the robotics stack nor the inference runtimes require modification to run on it. Of the platform classes surveyed in §2.8.5, it is the least expensive that exhibits all four characteristics of §2.8.1. Nothing in the published record suggests that any individual workload this application requires is beyond it.

The second is that its memory is a single indivisible resource, and the published record says almost nothing about how workloads share it. Each of the deployments surveyed above measured one thing: a navigation stack, or a vision pipeline, or a speech model. The question that a robot conducting a conversation while navigating actually poses — what the combined resident footprint is when perception, middleware, and speech inference are live simultaneously, and how close that total sits to the ceiling above which the kernel begins terminating processes — is not one those deployments were constructed to answer. It is not a difficult measurement. It is simply absent, and because the consequence of getting it wrong is a robot that stops rather than a robot that slows down, it is a measurement that has to be made rather than estimated. It is made in §5.4.4.
