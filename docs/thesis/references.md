# References

> **Format:** IEEE. Entries are grouped by the chapter section that cites them and carry the
> section-scoped keys used in the drafts (`[2.1.1]`, `[2.1.2]`, …). Final sequential numbering
> (`[1]`, `[2]`, …) is assigned once all chapters are merged — see the note at the end of this file.
>
> **Status column:** `Verified` = bibliographic details confirmed against the source or its
> publisher on 22 July 2026. `Unverified` = placeholder; the citation key is used in the draft but
> the source has not yet been identified or confirmed. **No `Unverified` entry should survive into
> the submitted document.**
>
> **Before submission:** re-check every URL and `[Accessed]` date. Web sources for commercial
> products change without notice, and press releases are sometimes relocated to investor-relations
> archives.

---

## Chapter 2 — Related Work

### §2.1 Overview: Automation of the Restaurant Service Loop

**[2.1.1]** Bear Robotics, Inc., "Servi — autonomous serving robot," Bear Robotics. [Online].
Available: https://www.bearrobotics.ai. [Accessed: 22-Jul-2026]. *(Verified: company founded 2017,
Redwood City, CA; Servi introduced 2019.)*

**[2.1.2]** Pudu Robotics, "BellaBot — delivery and engagement robot for restaurants and retail,"
Shenzhen Pudu Technology Co., Ltd. [Online]. Available:
https://www.pudurobotics.com/en/products/bellabot. [Accessed: 22-Jul-2026]. *(Verified: company
founded 2016, Shenzhen; BellaBot debuted January 2019.)*

**[2.1.3]** KEENON Robotics Co., Ltd., "About KEENON," KEENON Robotics. [Online]. Available:
https://www.keenon.com/en/about/index.html. [Accessed: 22-Jul-2026]. *(Verified: company founded
2010; deployments in 60+ countries.)*

**[2.1.4]** *Unverified* — comparative survey of commercial restaurant service robot platforms.
A peer-reviewed survey is preferable here to a fourth vendor page; see note (a) below.

**[2.1.5]** Pudu Robotics, "With nearly 70,000 units shipped, Pudu Robotics leads global market as
China's No.1 service robot exporter," PR Newswire, 24-Aug-2023. [Online]. Available:
https://www.prnewswire.com/news-releases/with-nearly-70-000-units-shipped-pudu-robotics-leads-global-market-as-chinas-no1-service-robot-exporter-301950208.html.
[Accessed: 22-Jul-2026]. *(Verified — but see correction (i) below: this source reports ~70,000
cumulative units across all Pudu models, not 40,000 BellaBot units.)*

**[2.1.6]** M. Wolf, "Alibaba opens robot restaurant as automation expands around the globe," The
Spoon, 2018. [Online]. Available:
https://thespoon.tech/alibaba-opens-robot-restaurant-as-automation-expands-around-the-globe/.
[Accessed: 22-Jul-2026]. *(Verified: Robot.He, Hema store at the National Exhibition and Convention
Center, Shanghai, 2018; rail-mounted pod AGVs; ordering performed by the customer via QR code and
the Hema mobile app. Also the source for Figure 2.1 — see note (b) below.)*

**[2.1.7]** *Unverified* — supporting citation for the claim that commercial delivery robots do not
participate in the ordering conversation. See note (c) below: this may be better carried as the
author's synthesis of [2.1.1]–[2.1.6] than as a citation to a separate source.

**[2.1.8]** *Unverified* — survey or representative work on open ROS2 differential-drive service
platforms. Should be aligned with the sources cited in §2.2.5.

**[2.1.9]** *Unverified* — representative published system combining EKF-fused odometry, RTAB-Map
SLAM, Nav2 navigation, and fiducial-marker docking on a TWD platform. Should be aligned with the
sources cited in §2.2.1–§2.2.4.

**[2.1.10]** T. Bocklisch, J. Faulkner, N. Pawlowski, and A. Nichol, "Rasa: Open source language
understanding and dialogue management," presented at the NIPS Conversational AI Workshop, Long
Beach, CA, USA, Dec. 2017. [Online]. Available: https://arxiv.org/abs/1712.05181. *(Verified:
arXiv:1712.05181.)*

**[2.1.11]** *Unverified* — Google Cloud, "Dialogflow CX/ES documentation." A vendor documentation
page is acceptable here; the specific product edition cited should match the claim being made.

**[2.1.12]** *Unverified* — representative deployment study of task-oriented dialogue systems for
restaurant ordering in English, Chinese, Korean, or Japanese. The draft claims deployment across
these four languages; a source supporting that breadth is required.

**[2.1.13]** *Unverified* — Zalo AI (VNG Corporation) and VinAI Research. Two distinct
organizations are referenced in one citation key; they should be split into separate entries.

**[2.1.14]** *Unverified* — supporting citation for the architectural claim that a chatbot cannot
invoke a function, validate against a database, or dispatch a robot. See note (c) below.

**[2.1.15]** The Wendy's Company and Google Cloud, "Wendy's taps Google Cloud to revolutionize the
drive-thru experience with artificial intelligence," PR Newswire, 09-May-2023. [Online]. Available:
https://www.prnewswire.com/news-releases/wendys-taps-google-cloud-to-revolutionize-the-drive-thru-experience-with-artificial-intelligence-301819196.html.
[Accessed: 22-Jul-2026]. *(Verified: Wendy's FreshAI announced 9 May 2023; built on Google Cloud
generative AI and Vertex AI; first pilot June 2023, Columbus, OH.)*

**[2.1.16]** Domino's Pizza, Inc., "Domino's on quest for digital dominance using artificial
intelligence," PR Newswire, 2018. [Online]. Available:
https://www.prnewswire.com/news-releases/dominos-on-quest-for-digital-dominance-using-artificial-intelligence-300633827.html.
[Accessed: 22-Jul-2026]. *(Verified — but see correction (ii) below: DOM launched as a voice
ordering app in 2014; AI phone-order testing was announced April 2018, not 2019.)*

**[2.1.17]** *Unverified* — study of QR-code ordering adoption in restaurants during COVID-19. A
peer-reviewed hospitality-technology source is preferable to trade press for this claim.

### §2.2 Autonomous Mobile Robot

> **STATUS — ALL ENTRIES UNVERIFIED.** The §2.2 draft was written against these citation keys, but
> no entry below has been checked against the source. Each names the work the key is intended to
> point to; the author must confirm authors, title, venue, year, and pages before submission, and
> supply full bibliographic detail in IEEE format. Keys [2.2.32]–[2.2.34] have no candidate source
> identified at all and are the highest priority.

**[2.2.1]** *Unverified* — S. Thrun, W. Burgard, and D. Fox, *Probabilistic Robotics*. MIT Press, 2005.

**[2.2.2]** *Unverified* — J. Borenstein and L. Feng, "Measurement and correction of systematic odometry errors in mobile robots," *IEEE Trans. Robotics and Automation*, 1996.

**[2.2.3]** *Unverified* — R. Siegwart, I. R. Nourbakhsh, and D. Scaramuzza, *Introduction to Autonomous Mobile Robots*, 2nd ed. MIT Press, 2011. *(Cited for differential-drive forward kinematics.)*

**[2.2.4]** *Unverified* — InvenSense, "MPU-6000/MPU-6050 product specification," datasheet.

**[2.2.5]** *Unverified* — G. Welch and G. Bishop, "An introduction to the Kalman filter," Univ. North Carolina at Chapel Hill, tech. rep. *(Or an equivalent EKF reference.)*

**[2.2.6]** *Unverified* — T. Moore and D. Stouch, "A generalized extended Kalman filter implementation for the Robot Operating System," in *Proc. Int. Conf. Intelligent Autonomous Systems (IAS-13)*, 2014. *(The `robot_localization` package.)*

**[2.2.7]** *Unverified* — R. Mahony, T. Hamel, and J.-M. Pflimlin, "Nonlinear complementary filters on the special orthogonal group," *IEEE Trans. Automatic Control*, 2008.

**[2.2.8]** *Unverified* — S. J. Julier and J. K. Uhlmann, "Unscented filtering and nonlinear estimation," *Proc. IEEE*, 2004.

**[2.2.9]** *Unverified* — T. Qin, P. Li, and S. Shen, "VINS-Mono: A robust and versatile monocular visual-inertial state estimator," *IEEE Trans. Robotics*, 2018. *(Or an equivalent VIO reference.)*

**[2.2.10]** *Unverified* — H. Durrant-Whyte and T. Bailey, "Simultaneous localization and mapping: Part I," *IEEE Robotics and Automation Magazine*, 2006.

**[2.2.11]** *Unverified* — Slamtec, "RPLIDAR A2M8 360° laser range scanner," datasheet.

**[2.2.12]** *Unverified* — Intel Corporation, "Intel RealSense Depth Camera D435," product datasheet.

**[2.2.13]** *Unverified* — P. J. Besl and N. D. McKay, "A method for registration of 3-D shapes," *IEEE Trans. Pattern Analysis and Machine Intelligence*, 1992. *(ICP.)*

**[2.2.14]** *Unverified* — G. Grisetti, C. Stachniss, and W. Burgard, "Improved techniques for grid mapping with Rao-Blackwellized particle filters," *IEEE Trans. Robotics*, 2007. *(GMapping.)*

**[2.2.15]** *Unverified* — S. Kohlbrecher, O. von Stryk, J. Meyer, and U. Klingauf, "A flexible and scalable SLAM system with full 3D motion estimation," in *Proc. IEEE Int. Symp. Safety, Security and Rescue Robotics (SSRR)*, 2011. *(Hector SLAM.)*

**[2.2.16]** *Unverified* — W. Hess, D. Kohler, H. Rapp, and D. Andor, "Real-time loop closure in 2D LIDAR SLAM," in *Proc. IEEE ICRA*, 2016. *(Cartographer.)*

**[2.2.17]** *Unverified* — S. Macenski and I. Jambrecic, "SLAM Toolbox: SLAM for the dynamic world," *Journal of Open Source Software*, 2021.

**[2.2.18]** *Unverified* — M. Labbé and F. Michaud, "RTAB-Map as an open-source lidar and visual SLAM library for large-scale and long-term online operation," *Journal of Field Robotics*, 2019.

**[2.2.19]** *Unverified* — D. Gálvez-López and J. D. Tardós, "Bags of binary words for fast place recognition in image sequences," *IEEE Trans. Robotics*, 2012. *(DBoW2.)* **Note:** this key is also cited in §2.2.3 for operator-initiated goal selection in prior deployments — that citation is misplaced and must be repointed to [2.2.32]–[2.2.34] once those are identified.

**[2.2.20]** *Unverified* — R. Kümmerle, G. Grisetti, H. Strasdat, K. Konolige, and W. Burgard, "g2o: A general framework for graph optimization," in *Proc. IEEE ICRA*, 2011.

**[2.2.21]** *Unverified* — S. Macenski, F. Martín, R. White, and J. Ginés Clavero, "The Marathon 2: A navigation system," in *Proc. IEEE/RSJ IROS*, 2020. *(Nav2.)*

**[2.2.22]** *Unverified* — D. Fox, W. Burgard, and S. Thrun, "The dynamic window approach to collision avoidance," *IEEE Robotics and Automation Magazine*, 1997.

**[2.2.23]** *Unverified* — C. Rösmann et al., "Trajectory modification considering dynamic constraints of autonomous robots," in *Proc. ROBOTIK*, 2012. *(TEB.)*

**[2.2.24]** *Unverified* — S. Macenski, S. Moore, D. Lu, A. Merzlyakov, and M. Ferguson, "From the desks of ROS maintainers: A survey of modern and capable mobile robotics algorithms in the Robot Operating System 2," *Robotics and Autonomous Systems*, 2023. *(Regulated Pure Pursuit.)*

**[2.2.25]** *Unverified* — M. Colledanchise and P. Ögren, *Behavior Trees in Robotics and AI: An Introduction*. CRC Press, 2018.

**[2.2.26]** *Unverified* — D. Fox, "KLD-sampling: Adaptive particle filters," in *Advances in Neural Information Processing Systems*, 2001. *(AMCL.)*

**[2.2.27]** *Unverified* — S. Garrido-Jurado, R. Muñoz-Salinas, F. J. Madrid-Cuevas, and M. J. Marín-Jiménez, "Automatic generation and detection of highly reliable fiducial markers under occlusion," *Pattern Recognition*, 2014. *(ArUco.)*

**[2.2.28]** *Unverified* — E. Olson, "AprilTag: A robust and flexible visual fiducial system," in *Proc. IEEE ICRA*, 2011.

**[2.2.29]** *Unverified* — M. Fiala, "ARTag, a fiducial marker system using digital techniques," in *Proc. IEEE CVPR*, 2005.

**[2.2.30]** *Unverified* — B. Benligiray, C. Topal, and C. Akinlar, "STag: A stable fiducial marker system," *Image and Vision Computing*, 2019.

**[2.2.31]** *Unverified* — V. Lepetit, F. Moreno-Noguer, and P. Fua, "EPnP: An accurate O(n) solution to the PnP problem," *Int. Journal of Computer Vision*, 2009.

**[2.2.32]** *Unverified — NO CANDIDATE IDENTIFIED.* Academic ROS2 campus/cafeteria food delivery robot. Required to support Table 2.2f row 1 and the §2.2.5 interaction-gap claim.

**[2.2.33]** *Unverified — NO CANDIDATE IDENTIFIED.* Academic ROS2 hospital medication transport robot. Required to support Table 2.2f row 2.

**[2.2.34]** *Unverified — NO CANDIDATE IDENTIFIED.* Academic ROS2 office document delivery robot. Required to support Table 2.2f row 3.

### §2.3 Vietnamese Voice Understanding

> **STATUS — ALL ENTRIES UNVERIFIED.** As with §2.2, each entry names the work the key is intended to
> point to; authors, title, venue, year, and pages must be confirmed before submission.
>
> **Numeric claims requiring a source.** The §2.3 draft deliberately omits word-error-rate and MOS
> tables because published figures for these systems are not comparable cell to cell. The figures
> that *do* remain in the draft and still need attribution are: model footprints and VRAM at float16
> (Table 2.3b), engine footprints (Table 2.3c), and the 60–70 dB restaurant ambient-noise range
> [2.3.22]. Verify each against a primary source or a measurement of your own.

**[2.3.1]** *Unverified* — reference establishing the limits of energy-threshold voice activity detection under noise. A speech-processing textbook treatment is preferable to a web source.

**[2.3.2]** *Unverified* — Silero Team, "Silero VAD: pre-trained enterprise-grade voice activity detector," GitHub repository. *(Confirm footprint: the draft states ~2 MB, matching the deployed model; the earlier draft said ~1.5 MB.)*

**[2.3.3]** *Unverified* — WebRTC Project, "Voice activity detection module," WebRTC native code documentation.

**[2.3.4]** *Unverified* — H. Bredin et al., "pyannote.audio: neural building blocks for speaker diarization," in *Proc. IEEE ICASSP*, 2020.

**[2.3.5]** *Unverified* — NVIDIA Corporation, "NeMo voice activity detection," NVIDIA NeMo toolkit documentation.

**[2.3.6]** *Unverified* — A. Radford, J. W. Kim, T. Xu, G. Brockman, C. McLeavey, and I. Sutskever, "Robust speech recognition via large-scale weak supervision," in *Proc. ICML*, 2023. *(Whisper. Source for the 680,000-hour training figure and the four model sizes.)*

**[2.3.7]** *Unverified* — SYSTRAN, "faster-whisper: fast inference for Whisper using CTranslate2," GitHub repository; and the CTranslate2 engine documentation. **Key claim to verify:** that faster-whisper models are distributed pre-converted to CTranslate2 format and require no conversion step. This is the criterion on which §2.3.2 selects the multilingual model over PhoWhisper — if it is wrong, the selection argument fails.

**[2.3.8]** *Unverified* — T. Le, L. Nguyen, and D. Q. Nguyen, "PhoWhisper: automatic speech recognition for Vietnamese," 2024. **Three claims to verify:** (a) that PhoWhisper is distributed as Transformers-format checkpoints requiring conversion for CTranslate2 — same dependency as [2.3.7]; (b) that a `medium` size is among the released variants, since Table 2.3b names it specifically; (c) that the released sizes mirror the Whisper architecture exactly, which is what licenses the footprint-parity claim (769M parameters, ~1.5 GB converted, ~3 GB VRAM at fp16). Claim (c) is load-bearing: it is the basis for §2.3.2's statement that the Vietnamese advantage costs nothing in memory, and hence for §6.3 describing the substitution as low-cost.

**[2.3.9]** *Unverified* — VLSP (Vietnamese Language and Speech Processing) shared-task benchmark description for automatic speech recognition.

**[2.3.10]** *Unverified* — Google LLC, "Cloud Speech-to-Text — supported languages," product documentation.

**[2.3.11]** *Unverified* — Viettel Group, "Viettel AI speech-to-text," product documentation.

**[2.3.12]** *Unverified* — FPT Corporation, "FPT.AI speech-to-text," product documentation.

**[2.3.13]** *Unverified* — eSpeak NG contributors, "eSpeak NG text-to-speech," GitHub repository.

**[2.3.14]** *Unverified* — M. Hansen, "Piper: a fast, local neural text-to-speech system," GitHub repository. *(Vietnamese voice `vi_VN-vais1000-medium`, ~200 MB per the deployed system.)*

**[2.3.15]** *Unverified* — J. Kim, J. Kong, and J. Son, "Conditional variational autoencoder with adversarial learning for end-to-end text-to-speech," in *Proc. ICML*, 2021. *(VITS.)*

**[2.3.16]** *Unverified* — Coqui, "XTTS: open model for multilingual text-to-speech with voice cloning," model card and documentation. *(Confirm the ~4 GB GPU requirement.)*

**[2.3.17]** *Unverified* — Microsoft Corporation, "Azure AI Speech — neural text to speech," product documentation; accessed via the `edge-tts` client.

**[2.3.18]** *Unverified* — Google LLC, "Cloud Text-to-Speech — WaveNet voices," product documentation.

**[2.3.19]** *Unverified* — Vbee JSC, "Vbee text-to-speech," product documentation.

**[2.3.20]** *Unverified* — FPT Corporation, "FPT.AI text-to-speech," product documentation.

**[2.3.21]** *Unverified* — ITU-T Recommendation P.800, "Methods for subjective determination of transmission quality," 1996. *(Standard definition of Mean Opinion Score.)*

**[2.3.22]** *Unverified — NO CANDIDATE IDENTIFIED.* Source for restaurant ambient noise levels in the 60–70 dB range. This figure recurs throughout Chapters 1, 2, and 4 and currently has no attribution anywhere. Either cite an acoustics or hospitality-environment study, or replace it with a sound-level measurement taken in the deployment restaurant and report it as such.

### §2.4 Conversational AI Agent

> **STATUS — NOT YET WRITTEN.** §2.4 cites keys [2.4.1]–[2.4.61] and no entry exists for any of them.
> This is the largest reference debt in Chapter 2 and it sits under the chapter's most
> load-bearing section. The keys map to well-known works (Vaswani et al. on Transformers, Yao et al.
> on ReAct, LangGraph and AutoGen documentation, Liu et al. on lost-in-the-middle, Asai et al.,
> Gao et al., and so on) — but the mapping has not been written down, and until it is, the section
> cannot be checked by anyone but its author.
>
> **Two specific items, flagged during the 23-Jul revision:**
>
> **[2.4.24] — Berkeley Function Calling Leaderboard.** The draft previously quoted numeric BFCL
> scores per model (e.g. Qwen2.5 7B at "~68–82%"), which were internally inconsistent with the
> surrounding prose and unattributed to a leaderboard version. Numeric scores have been removed;
> the draft now reports only that the families are separated consistently and that the ordering is
> stable across revisions. **If numeric scores are reinstated, they must be quoted against one
> pinned BFCL version**, since scoring has changed across releases.
>
> **[2.4.61] — Vietnamese tokenization penalty.** *NO CANDIDATE IDENTIFIED.* The draft previously
> asserted that Vietnamese text consumes "approximately 20–30% more tokens than English
> equivalents," uncited, in two places (§2.4.3 and §2.4.6), with the context-budget argument
> resting on it. The figure has been removed and replaced with the qualitative claim that
> multilingual tokenizers segment Vietnamese into more tokens than English, the magnitude being
> tokenizer-specific and unreported for the surveyed models.
>
> **Recommended: replace this citation with your own measurement.** You have the deployed
> tokenizer and a 217-dish Vietnamese menu plus the system prompts in
> `src/agent_brain/agent/resources/`. Tokenizing that corpus against an English translation gives a
> figure that is *specific to this system's tokenizer and domain* — strictly better evidence than a
> general claim from the literature, and defensible because it is measured rather than cited.

---

### §2.5 Menu Knowledge Retrieval

> **STATUS — NOT YET WRITTEN.** No entries exist for the keys cited in §2.5.

---

### §2.6 Backend Orchestration & Fleet Management

> **STATUS — NOT YET WRITTEN.** No entries exist for the keys cited in §2.6.

---

### §2.7 Multi-Role Web Interfaces

> **STATUS — NOT YET WRITTEN.** No entries exist for the keys cited in §2.7.

---

### §2.8 Edge Computing Platform

> **STATUS — DRAFTED 23-Jul-2026, ALL ENTRIES UNVERIFIED.** Keys [2.8.1]–[2.8.18] below are
> placeholders naming the *kind* of source required. None has been confirmed against the actual
> document. Vendor datasheets ([2.8.1]–[2.8.5], [2.8.12]–[2.8.16]) are the priority: §2.8.4's
> comparison table is built on them and every quantitative cell in it is currently unverified.
>
> **Quantitative claims in §2.8.4 requiring datasheet confirmation before submission:**
> memory bandwidth per board; TOPS figures per accelerator; power envelopes; and all indicative
> prices, which are single-unit figures, volatile, and quoted without a date. Each must either
> acquire a dated vendor citation or be removed. The *relative ordering* of the bandwidth column
> carries the argument in §2.8.2 and is the most important thing to confirm.

**[2.8.1]** *Unverified* — NVIDIA Corporation, "NVIDIA Jetson Orin Nano Developer Kit," product data sheet / module data sheet. *(Source for: GPU and CPU configuration, 8 GB LPDDR5, unified memory architecture, power modes, memory bandwidth.)*

**[2.8.2]** *Unverified* — NVIDIA Corporation, "Jetson modules comparison," product family documentation. *(Source for: Table 2.8a and Table 2.8b Jetson rows — AGX Orin, Orin NX, Orin Nano, Xavier NX memory, bandwidth, TOPS, and pricing.)*

**[2.8.3]** *Unverified* — NVIDIA Corporation, "JetPack SDK documentation," including Linux for Tegra (L4T) release notes for the deployed version. *(Source for: Ubuntu 22.04 ARM64 base, CUDA version, ROS2 Humble native installation.)*

**[2.8.4]** *Unverified* — NVIDIA Corporation, CUDA / cuDNN / TensorRT developer documentation. *(Source for: the accelerated inference stack and TensorRT's role as an optimizing compiler.)*

**[2.8.5]** *Unverified* — USB Implementers Forum, USB 2.0 and USB 3.x specifications, or an equivalent survey of embedded sensor bus characteristics. *(Source for: Table 2.8c bus bandwidth characteristics.)*

**[2.8.6]** *Unverified* — A survey or representative deployment paper covering ROS2 SLAM and navigation on Jetson hardware. **No candidate identified.**

**[2.8.7]** *Unverified* — A representative paper reporting vision workloads (object detection, fiducial marker recognition) on Jetson in a robotics context. **No candidate identified.**

**[2.8.8]** *Unverified* — A paper or technical report measuring optimized speech recognition inference on Jetson-class hardware. **No candidate identified.** *(Supports the claim that real-time transcription on this board class is documented.)*

**[2.8.9]** *Unverified* — Supporting citation for the claim that combined navigation-plus-speech deployments report per-subsystem measurements in isolation. **No candidate identified.** *(This key supports a negative claim about the literature and is the hardest to source; consider rephrasing the claim as an observation about the surveyed set [2.8.6]–[2.8.8] rather than citing a source for an absence.)*

**[2.8.10]** *Unverified* — S. Williams, A. Waterman, and D. Patterson, "Roofline: An insightful visual performance model for multicore architectures," *Communications of the ACM*, 2009. *(Source for: arithmetic intensity and the memory-bound / compute-bound distinction underpinning §2.8.2.)*

**[2.8.11]** *Unverified* — R. Pope et al., "Efficiently scaling Transformer inference," in *Proc. MLSys*, 2023. *(Source for: autoregressive decoding being memory-bandwidth-bound. An alternative or additional citation on KV-cache-bound decoding may serve equally well.)*

**[2.8.12]** *Unverified* — Rockchip, "RK3588 technical reference manual" or product datasheet. *(Source for: NPU TOPS rating, supported precision, memory configuration.)*

**[2.8.13]** *Unverified* — Hailo Technologies, "Hailo-8 / Hailo-8L datasheet." *(Source for: TOPS rating and supported operator classes for the discrete-accelerator row of Table 2.8a.)*

**[2.8.14]** *Unverified* — Raspberry Pi Ltd, "Raspberry Pi 5 product brief." *(Source for: CPU, memory type and bandwidth, power envelope, absence of a neural accelerator.)*

**[2.8.15]** *Unverified* — Intel Corporation, "Intel Processor N100 product specifications." *(Source for: memory configuration and bandwidth, TDP, integrated graphics.)*

**[2.8.16]** *Unverified* — Vendor documentation for the NPU compilation toolchains referenced in §2.8.2 (Rockchip RKNN Toolkit and/or Hailo Dataflow Compiler). *(Source for: the operator support matrix and quantisation calibration requirements.)*

**[2.8.17]** *Unverified* — Reserved. *(Allocated for a citation supporting the INT8 quantisation accuracy-degradation claim for tonal languages in §2.8.2, should one be found. **No candidate identified** — the draft currently states this as a risk requiring empirical characterisation rather than as an established result, which is the defensible form if no source is located.)*

**[2.8.18]** *Unverified* — Reserved for the deployed Jetson Orin Nano firmware/JetPack version actually in use, to be recorded from the device. *(This one is confirmable directly: read it off the board.)*

**[2.8.19]** *Unverified* — B. Kehoe, S. Patil, P. Abbeel, and K. Goldberg, "A survey of research on cloud robotics and automation," *IEEE Trans. Automation Science and Engineering*, 2015. *(Source for: cloud robotics as the field treating delegation of robot computation to networked infrastructure — §2.8.2.)*

**[2.8.20]** *Unverified* — M. Waibel et al., "RoboEarth," *IEEE Robotics and Automation Magazine*, 2011. *(Source for: shared knowledge bases across robot fleets. An alternative early cloud-robotics system may substitute.)*

**[2.8.21]** *Unverified* — P. Mach and Z. Becvar, "Mobile edge computing: A survey on architecture and computation offloading," *IEEE Communications Surveys & Tutorials*, 2017. *(Source for: computation offloading decision criteria — latency, energy, bandwidth — in §2.8.2. This is the citation the gap statement argues against: it supplies resource-optimisation criteria, not functional ones.)*

**[2.8.22]** *Unverified* — Reserved. *(Allocated for a citation on the physical attack surface of unattended edge/IoT devices, supporting the data-residence consideration in §2.8.2. **No candidate identified.** The draft deliberately states this qualitatively and does not present a formal threat model; if no source is located, the paragraph stands as a design consideration rather than a literature-backed claim, which is the intended weight.)*

---

### §2.9 Summary

> No external citations; §2.9 is a traceability matrix over the preceding sections.

---

## Notes and Outstanding Corrections

### Corrections in the §2.1 draft — APPLIED 22-Jul-2026

**(i) Pudu deployment figure. — APPLIED.** The draft stated *"Pudu alone reported over 40,000 units
deployed across more than 600 cities as of 2023."* The 600-cities figure is supported (BellaBot,
600+ cities across 60 countries, as of June 2023). The 40,000-unit figure is not: the publisher
reports **nearly 70,000 cumulative units shipped across all Pudu models** as of August 2023. The
sentence also mixed a company-wide shipment total with a single-product deployment footprint. The
draft now reports the two figures as separate, correctly-attributed claims.
**Still outstanding: the same 40,000 claim appears in Chapter 1 §1.2 and has NOT yet been corrected there.**

**(ii) Product years are company founding years. — APPLIED.** The draft labelled the platforms
*"Bear Robotics Servi (USA, 2017), Pudu Bellabot (China, 2016), Keenon T-series (China, 2010)."* All
three years are **company founding dates**, not product launch dates. The parentheses now read as
manufacturer founding years, with Servi (2019) and BellaBot (January 2019) product launches stated
explicitly. The Keenon T-series launch year is still unstated — supply it if a source is found.

**(iii) Domino's date. — APPLIED.** The draft stated *"Domino's AI (USA, 2019)."* DOM launched as a
voice ordering application in 2014 (developed with Nuance Communications); AI handling of inbound
phone orders was announced in April 2018 and tested in 20 US stores. Both dates are now in the draft
and the unsupported 2019 has been removed.

**(iv) Robot.He reinforces the argument. — APPLIED.** At Robot.He, customers order by scanning a QR
code and using the Hema app, and human staff still greet, explain the system, take payment, and
cook. This is direct evidence for the section's thesis that the robot handles transport only. Now
stated in the track-based paragraph, cited to [2.1.6].

### Structural notes

**(a) Four citations, three vendors. — PARTIALLY APPLIED.** `[2.1.1]`–`[2.1.4]` was cited as a range
for three named platforms; the draft range is now reduced to `[2.1.1]`–`[2.1.3]`. `[2.1.4]` is
consequently no longer cited anywhere and remains an *Unverified* placeholder — either fill it with a
genuine comparative survey of commercial service-robot platforms (preferable to a fourth vendor page)
or delete the entry.

**(b) Figure 2.1 permissions. — OUTSTANDING.** Figure 2.1 reproduces a photograph of the Robot.He
installation. Confirm the licence of the specific image file before submission and give the
photographer/agency credit in the caption if required. Press-agency imagery (Xinhua, Alamy) of this
installation is generally **not** freely reusable.

**(c) Citations attached to the author's own analysis. — APPLIED.** `[2.1.7]` and `[2.1.14]` were
attached to analytical claims rather than to facts reported elsewhere — that commercial robots do not
join the ordering conversation, and that a chatbot cannot call a function or dispatch a robot. Both
keys have been removed; the preceding citations carry the evidence.
**Consequence: `[2.1.7]` and `[2.1.14]` are now uncited.** Re-purpose or delete them on merge.

### Numbering

Section-scoped keys (`[2.1.x]`, `[2.2.x]`, …) are a drafting convenience that keeps each section
independently editable. On merge, flatten to a single sequential IEEE list ordered by **first
appearance in the text**, and update every in-text key. Do not flatten until all chapters are
drafted — inserting one reference into an early section otherwise renumbers everything after it.
