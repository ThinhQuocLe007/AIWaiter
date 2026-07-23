## 2.8 Edge Computing Platform

> *The computer aboard the robot determines what can run there, and by exclusion what must run elsewhere. This section describes the NVIDIA Jetson Orin Nano — its position within its product family, the software stack that makes GPU-accelerated inference available on an embedded board, and the interfaces through which sensors reach it — and surveys what prior robotics work has established about the platform. The property that matters most for the architecture is not compute throughput but the memory model, and the section closes on what the published deployments do and do not tell us about running two demanding workloads on one such board.*
>
> **Cross-refs:** §2.2 (navigation stack), §2.3 (voice pipeline components and their footprints), §3.3 (robot hardware setup — wiring and component specifications), §4.4 (edge/server workload split), §5.4.4 (edge performance measurement)
> **Citations:** [2.8.1]–[2.8.9]; final numbering assigned when all Ch.2 references are merged. Bibliographic entries for this section are pending — see `references.md`.
> **Figures and tables:** keyed section-scoped (`Table 2.8a`, …). Flatten to sequential chapter numbering on merge.

---

Unlike the components surveyed elsewhere in this chapter, the edge computer is not selected from a field of comparable alternatives on grounds this thesis contributes. It is a purchased board, chosen before the software was written, and the survey below is therefore concerned less with why this board rather than another than with what the board makes possible and what it forecloses. Its constraints propagate into every subsequent architectural decision, and stating them precisely is a prerequisite for the analysis in Chapter 4.

---

### 2.8.1 The Jetson Orin Nano — Hardware and Software Stack

The Jetson Orin Nano Developer Kit is a single-board computer built for embedded inference and robotics. It carries a 1024-core Ampere-architecture GPU with 32 tensor cores, a six-core Arm Cortex-A78AE CPU, and 8 GB of LPDDR5 memory, within a power envelope configurable between roughly 7 and 15 watts [2.8.1]. Physically it is small enough to mount in a robot's electronics bay, and at its default sustained power mode it draws a current a modest battery system can supply alongside motors and sensors.

Of these specifications the memory is the consequential one, and not because 8 GB is a particular quantity. The Orin Nano uses a *unified* memory architecture: CPU and GPU address one physical pool rather than each having its own [2.8.1]. There is no separate system RAM and video RAM between which work can be balanced. The operating system, the middleware, every sensor driver, every neural network, and every buffer allocated by any of them draw from the same 8 GB. Exceeding it does not degrade performance gracefully in the manner of a system that can page to disk; the kernel's out-of-memory killer terminates whichever process holds the largest allocation. On a robot, the processes holding large allocations are the ones performing perception and motion, so the failure mode of over-committing memory is not slowness but a robot that stops controlling itself. The question of what runs on this board is consequently a question of what fits, simultaneously, in one shared 8 GB — and it admits no partial answers.

The board sits in a family whose members differ mainly along that axis.

**Table 2.8a** — Position of the Orin Nano within the Jetson family [2.8.1]–[2.8.2].

| Board | Unified memory | Generation | Relevance to a robot that need not host a language model locally |
|---|---:|---|---|
| Jetson AGX Orin | 32 GB | Ampere, current | Sufficient to co-host a 7B-parameter model with perception; priced for industrial deployment |
| Jetson Orin NX | 8–16 GB | Ampere, current | Intermediate; the 16 GB variant relaxes but does not remove the shared-pool constraint |
| **Jetson Orin Nano** | **8 GB** | **Ampere, current** | **GPU adequate for real-time speech inference; memory adequate for perception and voice but not for a language model alongside them** |
| Jetson Xavier NX | 8 GB | Volta, superseded | Widely used in earlier academic robotics; discontinued |

The software distribution is JetPack, which bundles an operating system with the GPU stack [2.8.3]. The operating system, Linux for Tegra, is Ubuntu built for ARM64 and presents an ordinary Ubuntu environment — standard package management, a system Python, standard POSIX interfaces — so ROS2 distributions targeting that Ubuntu release install from their usual repositories without cross-compilation. Above it sit CUDA, providing the GPU programming interface and allocation against the unified pool; cuDNN, supplying the accelerated primitives that neural network layers are built from; and TensorRT, an optimizing compiler that rewrites a trained network into a tuned execution plan [2.8.4]. Inference runtimes reach the GPU through these libraries rather than addressing it directly, which is what allows a runtime written for desktop GPUs to execute on this board without modification.

---

### 2.8.2 Sensor Interfaces

Sensors reach the board over standard buses, and the specifications of the individual devices belong with the platform description in §3.3 rather than here. What is worth recording at this level is the aggregate: several devices reporting concurrently at different rates over a small number of controllers.

**Table 2.8b** — Sensor classes and their interface characteristics on this class of board [2.8.5].

| Sensor class | Bus | Typical report rate | Data volume | Consumed by |
|---|---|---|---|---|
| 2D laser scanner | USB 2.0 (serial) | Several Hz | Low — one scan per revolution | Mapping, localization, obstacle costmaps |
| RGB-D camera | USB 3.0 | Tens of Hz | High — colour and depth frames | Visual place recognition, marker detection |
| Inertial measurement unit | I²C to microcontroller, serial to board | Hundreds of Hz | Very low | Odometry fusion |
| Microphone | USB audio | Continuous at audio sample rate | Low | Speech detection and transcription |
| Audio output | USB, analogue, or Bluetooth | Continuous during playback | Low | Speech synthesis |

The depth camera dominates this table: it is the only device whose bandwidth requires the faster bus, and it is the reason USB 3.0 is a requirement of the platform rather than a convenience. Beyond bandwidth, the aggregate raises a scheduling question rather than a capacity one — several drivers servicing devices at rates differing by two orders of magnitude, on a CPU also running middleware, inference, and control.

---

### 2.8.3 Prior Work on Jetson in Robotics

Jetson boards are widely used in academic and research robotics, and the individual workloads are well documented. Published deployments cover simultaneous localization and mapping, autonomous navigation, sensor fusion, and vision tasks including object detection and fiducial marker recognition, with performance figures reported across ROS2 distributions and Jetson generations [2.8.6]–[2.8.7]. Speech workloads are likewise documented, with optimized inference runtimes reported to achieve real-time transcription on this class of board [2.8.8]. The platform's suitability for either category of work, taken by itself, is not in question.

What the literature reports less often is the two categories running together. Published robotics deployments describe robots that navigate; published speech deployments describe assistants that listen. Where both appear in one system, the reported measurements are typically of each subsystem in isolation, because that is how each was developed and benchmarked [2.8.9]. This leaves the interaction uncharacterised, and on a unified-memory board the interaction is precisely where the risk lies: two workloads that each fit comfortably alone may not fit together, and the manner in which they fail to fit is abrupt rather than gradual.

---

Two properties of this platform bear on everything built above it, and they pull in opposite directions.

The first is that the board is genuinely capable. Its GPU executes transformer inference at speeds adequate for interactive use, its CPU carries a full middleware stack and its drivers, and its software distribution is mature enough that neither the robotics stack nor the inference runtimes require modification to run on it. Nothing in the published record suggests that any individual workload this application requires is beyond it.

The second is that its memory is a single indivisible resource, and the published record says almost nothing about how workloads share it. Each of the deployments surveyed above measured one thing: a navigation stack, or a vision pipeline, or a speech model. The question that a robot conducting a conversation while navigating actually poses — what the combined resident footprint is when perception, middleware, and speech inference are live simultaneously, and how close that total sits to the ceiling above which the kernel begins terminating processes — is not one those deployments were constructed to answer. It is not a difficult measurement. It is simply absent, and because the consequence of getting it wrong is a robot that stops rather than a robot that slows down, it is a measurement that has to be made rather than estimated.
