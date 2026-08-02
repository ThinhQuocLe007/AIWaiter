# CHAPTER 2: RELATED WORK


## 2.1 Overview: Automation of the Restaurant Service Loop
From greeting to payment, a restaurant service interaction is a closed-loop business process with three components: the customer conversation (taking orders, answering menu questions, confirming selections), the backend transaction (creating order records, updating kitchen displays, computing bills), and the physical service at the table, where a machine or a member of staff has to be at the right table at the right time. Automation has addressed each component independently.


### 2.1.1 Service Robots in the Restaurant Industry
Commercial service robots for food delivery generally fall into two architectural categories: free-navigation platforms (e.g., Bear Robotics, Pudu, Keenon) and track-based systems (e.g., Alibaba Hema Robot [13]) [6], [11], [12]. Free-navigation robots utilize SLAM-based mapping via LiDAR and RGB-D cameras to plan collision-free paths, whereas track-based AGVs follow deterministic physical rails for sub-centimeter precision. While both architectures achieve reliable autonomous physical delivery, their operational scope remains severely limited. They function as closed appliances requiring human intervention for loading and destination selection via touchscreens. Crucially, their proprietary software stacks prevent third-party integration, making it impossible to couple them with external Large Language Model (LLM) agents, custom fleet dispatchers, or native Vietnamese conversational pipelines.

Figure 2.1: Track-based food delivery: Alibaba Hema Robot [13].

To address the limitations of closed commercial architectures, a second line of research utilizes general-purpose mobile platforms running the Robot Operating System (ROS 2) [14]. These open platforms, typically differential-drive or mecanum chassis equipped with similar spatial sensors, allow full modification of sensor drivers, RTAB-Map SLAM algorithms, and the Nav2 navigation stack [15]. While this architectural openness theoretically permits an external system to manage interaction and business logic alongside navigation, current published implementations have not bridged this gap. Existing ROS 2 platforms still rely on navigation goals set manually by human operators rather than being dynamically driven by an autonomous conversational agent (Section 2.2).


### 2.1.2 Conversational Ordering Systems
Conversational ordering has evolved through three generations, yet each retains critical limitations:

**Task-oriented dialogue frameworks (Rasa**** [49]****, Dialogflow):** Capable of producing structured API calls but rely on rigid intents and schemas that fail to capture informal, open-ended Vietnamese queries.

**Vietnamese LLM chatbots (Zalo AI, VinAI):** Demonstrate strong open-domain capabilities but act merely as text generators. They lack the architectural capacity to trigger system changes (e.g., adding items to a cart or dispatching a robot).

**Voice ordering systems (Wendy's FreshAI, Domino's DOM):** Commercially viable and capable of pushing orders to point-of-sale (POS) systems, but they remain stateless, English-only, and completely detached from autonomous physical presence at the table.

Running alongside these technologies is traditional restaurant management software (POS, Kitchen Display Systems, QR applications).  These operate in isolated silos, and without a shared real-time state,, an external AI agent cannot orchestrate a multi-role workflow across the customer, the kitchen, and the robot fleet.


### 2.1.3 Restaurant Management Software
A separate layer of operational software runs alongside all three generations of conversational technology and is largely independent of them. It records what was ordered and tells the kitchen to cook it. Point-of-sale systems track orders and payments. Kitchen display systems show order tickets for cooking staff. QR-code ordering applications let customers browse menus and place orders from their phones, a model that proliferated during COVID-19 [16]. These systems share a common architecture: each covers one role (POS, kitchen, customer) and operates independently. A kitchen display learns about a new order on its next poll cycle, typically every 5 to 10 seconds. The customer ordering app does not know the kitchen's queue depth. The robot does not know the customer just paid. There is no shared real-time state across roles, and no external AI agent can drive the multi-role workflow through API calls.


### 2.1.4 The Integration Gap
As summarized in Table 2.1, no existing category covers more than two of the three service-loop components. Most notably, none successfully integrates a conversational interface with a robot that autonomously places itself at the customer's table.

Table 2.1: Type of interfaces with autonomous physical delivery


| Category | Conversation | Transaction | Presence at table | Language reach | Deployment model |
| --- | --- | --- | --- | --- | --- |
| Free-navigation robots | Absent | Absent | Full | N/A | Cloud |
| Track-based AGV | Absent | Absent | Full | N/A | Closed stack |
| Task-oriented dialogue frameworks | Partial | Full | Absent | Retrainable | cloud |
| Vietnamese LLM chatbots | Full | Absent | Absent | Native Vietnamese | Cloud |
| LLM voice ordering | Partial | Full | Absent | English only, as deployed | Vendor cloud |
| Restaurant software | Absent | Full | Absent | Localizable | Varies by vendor |

The "Partial" coverage observed in existing conversational systems highlights distinct functional limitations. Task-oriented dialogue frameworks are constrained by predefined schemas (intents and slots), rendering them brittle and prone to failure when faced with unanticipated utterances. Conversely, LLM voice ordering handles open-ended speech but operates statelessly, lacking multi-turn memory or persistent session states, and currently lacks robust Vietnamese language support.

Bridging this integration gap requires more than incremental improvements to isolated systems. A unified architecture must translate open-ended conversations into validated actions against live business records, which subsequently dispatch a robot to the customer's table. To achieve a fully synchronized, real-time service loop, the proposed system must address five core operational requirements, detailed in the subsequent sections:

**Dynamic goal navigation (****Section ****2.2):** The robot's destination must be selected at runtime by the system itself, from live restaurant state such as a seating event or a call button, rather than chosen for each trip by a human operator at a console.

**Vietnamese voice on the edge (****Section ****2.3):** Executing robust speech detection, recognition, and synthesis locally on the robot's hardware under high-noise restaurant conditions.

**Informal speech to validated actions (****Section ****2.4):** Transforming colloquial, teencode-heavy Vietnamese utterances into precise tool calls that are validated against an authoritative database before execution.

**Vague descriptions to relevant items (****Section ****2.5):** Mapping subjective customer requests (e.g., taste, sensation, or dining occasion) to specific menu items indexed by name, category, and price.

**Service events to synchronized operations (****Section ****2.6):** Unifying the customer tablet, kitchen display system, manager dashboard, and robot fleet into a single real-time state, accessible and mutable by the autonomous agent, floor staff, and kitchen personnel.


## 2.2 Autonomous Mobile Robot

### 2.2.1 Kinematic Model of the Two-Wheel Differential Drive Robot
The capabilities surveyed in this section all act on the robot through one model, which ties the two-wheel speeds to the motion of the body. A two-wheel differential-drive platform carries two independently driven wheels on a common axle, with one or more free casters for support, and moves only from the difference between the two wheel speeds: equal speeds send it straight, unequal speeds bend it onto a curve, and equal but opposite speeds spin it in place about the axle midpoint, the reference point O at which the model expresses the robot's motion [17].

A two-wheel differential drive cannot move sideways. In the body frame the lateral velocity is always zero (), the non-holonomic constraint that planning and control in later sections must respect. With wheel track , the inverse model maps a commanded body velocity  to left and right wheel speeds,

which the base controller applies. The forward model recovers body velocity from measured wheel speeds and is the basis of wheel odometry:

Together with , these describe the robot's planar motion completely; the geometric derivation (turning radius, arc lengths) is standard [17] and is not restated here. Integrating the body velocities over time yields the pose that wheel odometry accumulates. The next subsection turns that forward model into a measured estimate and examines the drift it accumulates.

Figure 2.2: Top-view geometry of the two-wheel differential drive: reference point O, wheel track W, wheel speeds  and , and body-frame velocities , .


### 2.2.2 Odometry and Sensor Fusion
For a mobile robot to navigate autonomously, it must continuously estimate its pose. This process is known as odometry: the robot starts from a known pose and incrementally estimates its motion from onboard sensors. Because the estimate uses only the robot's own motion, without an external reference, odometry is a form of dead reckoning [17].

Odometry can be derived from several sensing modalities (wheel encoders, IMU integration, visual or visual-inertial tracking, or consecutive LiDAR scan matching), each with different accuracy, cost, and drift characteristics [17]. This work uses wheel odometry as the primary source of translational motion because the robot operates on a flat indoor floor where encoders provide reliable short-term distance measurements.

The principal limitation is drift. Each measurement error becomes part of the estimate and propagates over time; for wheel odometry the main sources are wheel slip, imperfect geometry, and encoder quantization [17]. The estimate therefore diverges gradually during long-distance operation.

A standard remedy is sensor fusion of complementary modalities. Wheel encoders give accurate short-term translation but are blind to slip; an IMU measures rotation independently of wheel-ground contact and captures rapid turns well, yet integrating the gyroscope alone causes heading to drift [18]. Combining the two compensates each sensor's weakness with the other's strength.

The Extended Kalman Filter (EKF) is the widely used algorithm for this fusion. It recursively estimates the robot state by alternating a prediction step, which propagates the state through a motion model, and an update step, which corrects that prediction with incoming measurements according to their uncertainties. Unlike the linear Kalman filter, the EKF handles the nonlinear kinematics of mobile robots by linearizing the motion and measurement models around the current estimate [18]. The predict-update recursion is standard in the literature and is not restated here; what matters for selection is that the filter maintains an explicit covariance, runs at moderate cost on planar motion, and is available as a ready-made ROS 2 component.

Among common alternatives (encoder-only dead reckoning, a complementary filter, the unscented Kalman filter (UKF), and visual-inertial odometry), none removes drift entirely; they differ in how fast it accumulates and what they cost to slow it down [17]. Cost matters more than raw accuracy in this stack, because the SLAM map bounds drift over a service cycle (Section 2.2.4) and the fiducial marker bounds it again at the final approach (Section 2.2.6). On that criterion the complementary filter lacks an explicit uncertainty model; visual-inertial odometry needs a GPU that competes with other onboard workloads; and the UKF costs more than the EKF for little benefit when motion is nearly linear, as it is for a differential-drive robot on a flat floor. The EKF therefore strikes the practical balance.

The ROS 2 robot_localization package provides configurable EKF and UKF nodes, including a two_d_mode that constrains the state to planar motion [19]. In a typical differential-drive setup, wheel-encoder velocities and IMU angular velocity are fused; absolute IMU yaw is normally excluded when no magnetometer is available, because the integrated gyroscope heading drifts independently of the filter and would degrade the estimate. The node publishes filtered odometry and the odom → base_footprint transform that mapping, localization, and navigation all read. How the filter is instantiated on the robot of this thesis (state vector, sensor selection, and covariances) is set out in Section 3.3.


### 2.2.3 Robot Operating System (ROS 2)
The kinematic model, odometry, and filter of the previous subsections are useful only once they run together with the SLAM package, planner, controller, and marker detector surveyed below, which are separate programs that must exchange data continuously. ROS 2 is the robotics middleware that makes this composition practical: despite the name it is not an operating system, but a framework of communication tools and conventions that let independent programs cooperate as one robot [14].

Each program is a *node*. Nodes do not call each other directly; they communicate through topics (named publish/subscribe channels), services (request/reply), and actions (long-running goals that report progress and can be cancelled, the interface Nav2 exposes in Section 2.2.5). Underneath sits Data Distribution Service, which handles discovery and message delivery without the single central master of first-generation ROS. Spatial relationships are standardized by the TF transform tree and a URDF description of the robot's links, joints, and sensor mounts, so a point measured in one frame can be expressed in any other, exactly what fusing LiDAR, camera, and odometry requires [14].

ROS 2 rather than ROS1 is the standard choice for new work of this kind: Data Distribution Service removes a central point of failure, and the ecosystem of ready-made packages, from sensor drivers to SLAM and navigation, removes most of the code that would otherwise be written from scratch. Every navigation component surveyed below is distributed as a ROS 2 package, which is why the survey treats them as off-the-shelf parts to be selected and configured rather than reimplemented.

Figure 2.3: ROS 2 publish/subscribe communication.


### 2.2.4 SLAM, Map Building, and Localization
Simultaneous Localization and Mapping address a circular dependency: localizing requires a map, and building a map requires knowing where the robot is [20]. Modern systems separate a front end, which processes sensor data and aligns consecutive observations, from a back end, which optimizes a graph of poses subject to constraints and detects loop closures, revisits that redistribute accumulated drift across the trajectory. Graph-based SLAM is the standard formulation; the weighted least-squares objective and its MAP interpretation under Gaussian noise are well established [20] and are not restated here. Appearance-based loop closure typically treats place recognition as a Bayes filter over past locations, accepting a match only past a confidence threshold so that a single mistaken resemblance in a repetitive room does not corrupt the graph [20].

A 2D LiDAR such as the RPLiDAR A2M8 produces planar range scans that scan matching (commonly ICP) aligns into an occupancy grid [20]. Mapping is illumination-insensitive and geometrically accurate in the scan plane, but scan matching becomes ill-conditioned wherever geometry repeats, such as long corridors or a dining room of regularly spaced tables. An RGB-D camera such as the Intel RealSense D435 contributes place recognition rather than geometry: visual bag-of-words can recognize a previously visited location from appearance alone, even when local geometry is ambiguous [20], [21].

Five SLAM implementations are available for ROS 2. GMapping applies a Rao-Blackwellized particle filter to 2D laser data with no explicit loop closure. Hector SLAM scan-matches without odometry but likewise lack loop closure and drifts in featureless environments. Cartographer introduced submap-based graph SLAM with branch-and-bound loop-closure search, though its ROS 2 maintenance has lagged. SLAM Toolbox is the ROS 2 tier-one 2D solution, with pose-graph optimization via Ceres and loop closure by scan correlation [22]. RTAB-Map fuses LiDAR and RGB-D, detects loop closures through visual bag-of-words as well as laser proximity, and bounds real-time cost through a working-memory / long-term-memory partition [15].

Table 2.2: 2D SLAM implementations available for ROS 2.


| System | Sensors | Loop-closure cue | Behavior in repetitive geometry |
| --- | --- | --- | --- |
| GMapping | 2D LiDAR | None explicit | Degrades; no mechanism to correct a mistaken revisit |
| Hector SLAM | 2D LiDAR (no odometry required) | None | Drifts without bound in featureless corridors |
| Cartographer | 2D/3D LiDAR (+ IMU) | Branch-and-bound scan matching | Better than correlation alone, still geometry-only |
| SLAM Toolbox | 2D LiDAR | Scan correlation | Ambiguous where scans repeat at distinct locations |
| RTAB-Map | 2D LiDAR + RGB-D | Visual bag-of-words + LiDAR proximity | Appearance resolves locations that geometry cannot |

Once a map exists, operation shifts to localizing within it. Adaptive Monte Carlo Localization (AMCL) maintains a particle distribution over poses weighted by laser-scan agreement and is the long-standing ROS default [18]; in symmetric geometry the particle cloud can converge confidently on the wrong hypothesis. RTAB-Map's localization mode instead holds the stored graph fixed and relocalizes with the same visual and geometric matching used during mapping, permitting global recovery from an arbitrary starting pose.

Table 2.3: Localization against a prior map.


| Approach | Sensors | Behavior in symmetric geometry | Recovery when lost |
| --- | --- | --- | --- |
| AMCL | 2D LiDAR | Prone to confident false convergence where scans repeat | Global particle redistribution |
| RTAB-Map localization mode | 2D LiDAR + RGB-D | Visual appearance separates geometrically identical places | Global visual relocalization |

A dining room is close to the worst case for purely geometric place recognition: repeating table clusters, long featureless walls, and a service lane with the same profile at many points. On metric mapping accuracy the five systems are broadly comparable; they divide on whether a system carries a non-geometric place cue and whether it can recover after losing track without a person supplying an initial pose. RTAB-Map is the only entry that satisfies both. It fuses RGB-D, laser, and wheel-inertial odometry into a pose graph, closes loops by appearance and proximity, publishes the map-to-odom transform Nav2 reads, and keeps loop-closure search within a bounded working memory as the map grows [15]. How this stack is configured for the restaurant map of this thesis is set out in Chapter 3.


### 2.2.5 Autonomous Navigation
With a map and a pose within it, the navigation stack must convert a goal pose into wheel velocities. Navigation2 is the standard ROS 2 framework for this and decomposes the problem into a global planner, a local controller, a costmap layer, and a behavior tree that orchestrates the lifecycle and its recoveries [10].

The global planner searches the static costmap for a path minimizing length and obstacle proximity. NavFn (Dijkstra/A*) is fast and produces paths without kinematic feasibility constraints, which is acceptable for a differential-drive robot that can rotate in place. The Smac family adds kinematically feasible planners for car-like platforms; the extra cost is repaid only when the platform cannot turn in place. The local controller then emits velocity commands: DWB samples candidate velocity pairs and scores them with weighted critics [23]; TEB optimizes a timed trajectory at higher tuning cost; Regulated Pure Pursuit follows the path geometrically with few parameters.

Table 2.4: Nav2 global planners and local controllers.


| Component | Method | Suits non-holonomic TWD | Tuning burden |
| --- | --- | --- | --- |
| NavFn (global) | Dijkstra / A* on potential field | ✓ (rotation in place available) | Low |
| Smac Hybrid-A* / State Lattice | Kinematically feasible search | Unnecessary (no turning-radius constraint) | Moderate-High |
| DWB (local) | Velocity sampling with weighted critics | ✓ | Moderate (critic weights) |
| TEB (local) | Time-parameterized trajectory optimization | ✓, but over-specified | High |
| Regulated Pure Pursuit (local) | Geometric path following, curvature-regulated | ✓ | Low |

Because a differential-drive platform can rotate in place, a holonomic global planner is sufficient, and the controller needs only sample  pairs. Nav2's behaviour tree sequences recoveries (clearing rotation, larger in-place rotation, replan) and finally aborts with a status [10]. What should happen after that abort is left entirely outside the navigation system.

Figure 2.4: The navigation stack and its goal interface.

What the surveyed work does not provide is the interface above the stack. In every academic deployment reviewed, the goal is operator-initiated: a human selects a waypoint, or a hard-coded sequence steps through a fixed tour [14]. Reported success rates above 90% describe execution quality, not goal origin. Coupling Nav2 to a non-human source raises requirements that operator-driven navigation never encounters asynchronous goals from business events, preemption of in-flight goals, business context that must survive the round trip, and failures surfaced as recoverable task state. None of the surveyed work connects Nav2 to a goal source with these properties; the coupling proposed in Section 3.6 is designed to satisfy them.


### 2.2.6 Fiducial Marker Docking
Localization against a SLAM map carries residual error of several centimeters even under good conditions. For most of a run this does not matter; it matters at the final approach, where a lateral offset means the robot does not square up to the table. A fiducial marker, a visual pattern of known geometry and known position, provides an absolute local reference at that point.

A square fiducial encodes an integer ID in a binary grid. Detection and Perspective-n-Point pose estimation from the four corners are standard [24] and are not restated here. Among marker families, ArUco ships inside OpenCV with established ROS 2 wrappers [25]; AprilTag improves long-range and oblique detection at higher cost; ARTag is largely superseded [24]; STag stabilizes oblique views with a smaller ecosystem [24]; ChArUco offers sub-pixel accuracy but needs a physically larger target than a table-mounted marker allows. Published comparisons emphasize range, steep incidence, and false-positive resistance, margins a near-frontal one-meter docking approach never exercises. Selection therefore falls to availability and integration cost: ArUco needs no extra detector package, and its offline dictionaries fix the identifier space for a small set of tables. The docking design in Section 3.5 adopts ArUco on this basis.

Figure 2.5: Pose estimation from a square fiducial marker.

Prior work treats each marker as a geometric target, a pose to reach. In a restaurant, each table carries its own marker, so the decoded ID is also a reference to a business entity: table, seated session, and outstanding order. A pose correction alone does not tell the robot which seated session and open order belong to the party now in front of it. Making that check possible requires resolving marker → table → session → order at docking time. Among the systems surveyed here, none binds fiducial markers to business entities in this way; the docking design in Section 3.5 does so.


## 2.3 Vietnamese Voice Understanding
A restaurant voice interaction follows a physical path: the customer speaks into a microphone mounted on the robot, the captured audio is processed on the robot's edge computer, and a spoken reply comes out of the robot's speaker. That path has to be completed quickly enough to sustain conversational rhythm, and it has to do so under restaurant acoustic conditions, where concurrent conversations, kitchen sounds, plate clatter, and chair movement are present throughout service. The language it processes is Vietnamese, in which a single diacritic changes a word's meaning entirely. The hardware it runs on is simultaneously running the robot's navigation stack.

Three properties of that setting bear on every component surveyed below, and none of them belongs to the components themselves. The first is connectivity. A component that requires a network round-trip per utterance behaves differently in a building with intermittent WiFi than one that does not, since a temporary outage becomes a total loss of the voice interface rather than a degradation of it. The second is memory. The edge device provides a single pool shared between the voice pipeline, the navigation stack, and the operating system, so every model's footprint is subtracted from a fixed total rather than drawn from a dedicated allocation. The third is latency, the least obvious of the three, because it does not belong to any single component either.

The latency budget is a sum, and the components compete for it. An utterance is not complete until the detector has observed enough trailing silence to declare it finished, and that silence window is dead time in every turn, paid before transcription begins. Transcription then scales with model size, synthesis scales with sentence length, and the language model sits between them. Because the customer experiences the total, the useful question for each component is not only how accurate it is, but how much of the budget it consumes and what the accuracy gained costs the components downstream. The rest of this section sets out the available options for each component and the properties that determine that trade-off.


### 2.3.1 Voice Activity Detection
Voice activity detection determines the boundaries of a spoken utterance in a continuous audio stream: when the customer started speaking, and when they stopped. It is the first processing stage, and its output, a trimmed segment containing exactly one utterance, feeds directly into the transcription model. If detection ends with an utterance prematurely, the transcriber receives a truncated sentence, and the agent never sees the complete order. If detection triggers background noise, everything downstream (transcription, intent classification, reasoning, validation) processes restaurant clatter as though it were an order. The accuracy of this one stage therefore bounds everything that follows.

The simplest approach classifies any audio frame whose root-mean-square amplitude exceeds a fixed threshold as speech. This works in a quiet recording environment, where silence sits near zero amplitude and speech rises clearly above it. In a restaurant it does not, because the ambient noise floor regularly exceeds the amplitude of quiet speech and no threshold separates the two. Raising the threshold loses trailing syllables; lowering it produces continuous false triggers. Energy thresholding has no mechanism for distinguishing speech from non-speech at comparable loudness, which makes it unsuitable here regardless of tuning [26].

Lightweight neural models address this by classifying frames on learned spectral structure rather than amplitude. Silero VAD is a compact model of roughly 2 MB that processes frames on CPU in real time, emits speech probability per frame, and exposes a configurable decision threshold [27]. WebRTC VAD, roughly 100 KB, applies a Gaussian mixture model trained on telephony speech; it is the lighter of the two and correspondingly less accurate under noise, by the margin Figure 2.6 shows. Both run without GPU involvement, which matters because GPU memory on the edge device is committed to transcription and to the navigation stack.

Figure 2.6: Precision against recall for five voice activity detectors on a multi-domain validation set.

At the accurate end of the range, systems such as pyannote.audio and NVIDIA NeMo's VAD use substantially larger architectures for state-of-the-art frame-level discrimination, and both expect GPU inference for real-time operation. On a device where the transcription model and the navigation stack already contend for a shared memory pool, committing further GPU capacity to an always-on detector is hard to justify while CPU-only alternatives remain adequate.

Table 2.5: Voice activity detection approaches.


| Approach | Footprint | Inference | Discrimination under noise | GPU required |
| --- | --- | --- | --- | --- |
| Energy threshold | n/a | Trivial | Poor; cannot separate speech from noise at similar amplitude | No |
| WebRTC VAD | ~100 KB | CPU, real-time | Moderate | No |
| Silero VAD | ~2 MB | CPU, real-time | Good; threshold configurable | No |
| pyannote.audio | ~100 MB | GPU | High | Yes |
| NeMo VAD | ~200 MB | GPU | High | Yes |

Two parameters govern the behavior of any detector in this class, and they are where the accuracy and latency constraints meet. The first is the decision threshold on the per-frame speech probability, which trades two failure modes against one another: set high, it suppresses false triggers from impulse noise at the cost of clipping quiet onsets; set low, it captures hesitant speech at the cost of admitting noise to the transcriber. The second follows from the fact that any system segmenting continuous audio into discrete utterances has to decide when an utterance has ended, and the conventional criterion is a fixed interval of observed silence. That interval sets a floor on turn latency independent of every other component in the pipeline. It elapses on every turn, before transcription begins, and no downstream optimization recovers it. Shortening it returns control to the speaker sooner and truncates anyone who pauses mid-sentence. Neither parameter has a value that is correct in the abstract; both are properties of the room and of the people speaking in it.

The published record supplies neither value. Silero VAD has been evaluated on multilingual telephone and meeting audio and WebRTC VAD on telephony speech, and the hardest restaurant condition appears in neither: intelligible conversation at an adjacent table, which is exactly what a speech detector is built to respond to. What the literature does establish concerns the approaches rather than their settings, namely which of them run without a GPU, what each cost in memory, and whether the decision threshold is exposed for tuning at all.


### 2.3.2 Speech-to-Text for Vietnamese
Speech-to-text converts the segment isolated by the detector into Vietnamese text. It is the most consequential stage in the pipeline. Every component downstream (the intent classifier, the agent's language model, the validator, the response generator) operates on the text this stage produces, and none can recover information that transcription destroyed. A tone error that turns *cá* (fish) into *cà* (eggplant) does not present as an error downstream at all; it presents as a correctly processed order for the wrong dish.

The dominant architecture for on-device multilingual transcription is Whisper, a Transformer encoder-decoder trained on approximately 680,000 hours of multilingual web audio [28]. Audio passes through a convolutional front end, is encoded into a latent representation, and is decoded autoregressively into text conditioned on both the audio encoding and the tokens generated so far. Vietnamese is present in the training distribution but was not a primary target, so the model handles it competently without being optimized for it. The family is released in five sizes, tiny (39M parameters), base (74M), small (244M), medium (769M), and large (1.55B, currently at revision v3), which trade accuracy against memory and inference time. Two further variants exist. The English-only checkpoints, released from tiny.en through medium.en, are more accurate than their multilingual counterparts on English and unsuitable for Vietnamese. The large-v3-turbo checkpoint (809M) keeps the full large-v3 encoder and reduces the decoder from thirty-two layers to four, which cuts decoding time substantially at a small accuracy cost that varies by language and is not reported for Vietnamese.

The deployment characteristics of this family changed substantially with faster-whisper, a reimplementation built on the CTranslate2 inference engine [29]. CTranslate2 applies operator fusion, memory-layout optimization, and integer quantization to reduce both latency and memory footprint relative to reference implementation. Two consequences matter for edge deployment. The first is that a model size which would otherwise exceed the available budget becomes viable. The second is that the models are distributed *already converted* to the CTranslate2 format, so deploying one requires no weight-conversion step.

PhoWhisper [9] fine-tunes Whisper on Vietnamese speech data and reports improved word error rate over the multilingual base on Vietnamese benchmarks, with the gains concentrated in tonal diacritics. That is the error this subsection opened on, the one that does not surface as a transcription failure but as a correct-looking order for a different dish, and it is also the dimension on which a broadly multilingual model is weakest for this language. PhoWhisper is released across the same size range as its base, from tiny to large, so the choice of size remains open independently of the choice of language targeting; the medium checkpoint is tabulated below as the representative case.

What that Vietnamese targeting costs is the property worth recording. A fine-tune preserves the architecture and parameter count of its base, so PhoWhisper at a given size holds exactly the weights the multilingual model holds at the same size and decodes at the same time. The gain is therefore free at runtime. It is paid for once, at build time: PhoWhisper is distributed as Transformers-format checkpoints, so running it under CTranslate2 means converting the weights and maintaining the converted artefact locally, where a multilingual checkpoint is retrieved in its final form and loaded unattended.

Cloud services occupy a different position entirely. Google Cloud Speech-to-Text, Viettel AI, and FPT.AI all provide dedicated Vietnamese recognition trained on large Vietnamese corpora and running on server-grade infrastructure [31] and their accuracy on clean Vietnamese speech exceeds what any edge-deployable model achieves. Their limitation is structural rather than acoustic: every utterance requires a network round-trip, which places conversational latency partly outside the system's control and turns a WiFi outage into a total failure of the voice interface.

Table 2.6: Speech-to-text options for Vietnamese.


| Model/service | Parameters | Vietnamese | Distribution format | Disk | Offline |
| --- | --- | --- | --- | --- | --- |
| Whisper base | 74M | Multilingual, not targeted | CTranslate2, ready to load | ~145 MB | ✓ |
| Whisper small | 244M | Multilingual, not targeted | CTranslate2, ready to load | ~485 MB | ✓ |
| Whisper medium | 769M | Multilingual, not targeted | CTranslate2, ready to load | ~1.5 GB | ✓ |
| Whisper large-v3 | 1.55B | Multilingual, not targeted | CTranslate2, ready to load | ~3 GB | ✓ |
| PhoWhisper medium | 769M (Whisper medium architecture) | Fine-tuned on Vietnamese | Transformers; conversion required for CTranslate2 | ~1.5 GB once converted (~3 GB as released, fp32) | ✓ |
| Google Cloud STT | n/a | Dedicated Vietnamese model | Hosted API | n/a | ✗ |
| Viettel AI STT | n/a | Dedicated Vietnamese model | Hosted API | n/a | ✗ |
| FPT.AI STT | n/a | Dedicated Vietnamese model | Hosted API | n/a | ✗ |

Word error rates are deliberately omitted from the table. Published figures for these systems come from different corpora recorded under different conditions and are not comparable cell to cell. The Whisper family's rates are reported against multilingual benchmarks [28] and PhoWhisper's against Vietnamese academic corpora including VLSP [9], [30], which consist of read speech recorded in quiet conditions with standard pronunciation. A single ranked accuracy column would imply a comparability that the underlying evaluations do not support.

Of the properties the table reports, the one separating the Vietnamese-specialized model from its multilingual base is narrower than it first appears. The two are identical in architecture, parameter count, footprint, and inference cost, and differ only in what they were trained on and in a one-time build step. Whether the fine-tune keeps its advantage once the audio leaves the recording studio is not something any entry in the table establishes.


### 2.3.3 Text-to-Speech for Vietnamese
The final stage converts the agent's Vietnamese text into audible speech. Quality here is judged on two axes that do not always move together: intelligibility, meaning the customer recovers the words, and naturalness, meaning the voice is appropriate to a service setting. Vietnamese adds a third consideration, since tone is lexical. A synthesizer that renders diacritics inaccurately does not merely sound unnatural; it says something else.

The available engines span a wide range of model complexity. At the lightest extreme, eSpeak-NG is a formant synthesizer: rather than learning from recorded speech, it models the vocal tract as a set of resonant frequencies and applies rules to shape them into phonemes. The result is unmistakably mechanical, flat and without natural prosody, but it is approximately 5 MB, runs on any CPU, and its Vietnamese phoneme tables cover the full tonal system. Formant synthesis has served screen readers and accessibility tooling for decades and remains the floor of the range.

Piper occupies the middle of that range [32]. It implements the VITS architecture, in which a single network converts text directly to a waveform in one pass, with no intermediate spectrogram and no separate vocoder [33]. The community-trained Vietnamese voice is roughly 200 MB and synthesizes a sentence on CPU in the region of half a second. Its output is audibly synthetic but fully intelligible, with tones rendered correctly, and it is the only neural Vietnamese voice that fits an edge memory budget without requiring GPU capacity.

At the upper end of on-device synthesis, Coqui's XTTS v2 uses a large autoregressive model with a separate vocoder, supports Vietnamese within its multilingual training, and offers voice cloning from a short reference clip. Its naturalness approaches that of cloud neural voices. Its cost is roughly 4 GB of GPU memory, the largest claim any voice component could make on a device already allocating memory to transcription and to navigation, and it competes directly with the transcription model selected in Section 2.3.2.

The remaining options are hosted services. Microsoft Azure Neural TTS, reachable through the open-source edge-tts client, provides multiple Vietnamese voices covering Northern and Southern accents and both speaker genders. Google Cloud TTS offers WaveNet voices with the highest reported naturalness. Two Vietnamese providers, vbee and FPT.AI, supply voices trained specifically for the local market. All four are more natural than any on-device option, and all four require connectivity for every sentence spoken.

Table 2.7: Text-to-speech engines with Vietnamese capability.


| Engine | Synthesis approach | Footprint | Compute | Offline | Vietnamese voices |
| --- | --- | --- | --- | --- | --- |
| eSpeak-NG | Formant, rule-based | ~5 MB | CPU | ✓ | Phoneme tables, full tonal coverage |
| Piper | VITS, single-stage neural | ~200 MB | CPU | ✓ | One community-trained voice |
| XTTS v2 | Autoregressive + vocoder | ~4 GB | GPU | ✓ | Multilingual, voice cloning |
| edge-tts (Azure) | Neural, hosted | n/a | Cloud | ✗ | Multiple, regional accents |
| Google Cloud TTS | WaveNet, hosted | n/a | Cloud | ✗ | WaveNet voices |
| vbee | Neural, hosted | n/a | Cloud | ✗ | Vietnamese-specific |
| FPT.AI TTS | Neural, hosted | n/a | Cloud | ✗ | Vietnamese-specific |

Synthesis quality is conventionally assessed by Mean Opinion Score, in which listeners rate samples on a five-point naturalness scale [34], and reported scores place cloud neural voices above on-device neural synthesis and both well above formant methods. Specific values are not reproduced here: the published scores come from separate studies using different listener pools, different text material, and in most cases languages other than Vietnamese, so listing them in one ranked column would invite precisely the comparison those studies cannot support. All of them were also conducted in quiet listening conditions, and under restaurant noise the gap between a moderately natural voice and a highly natural one may compress considerably, since intelligibility rather than naturalness becomes the limiting factor.

What the record does document unambiguously is two divisions, and both fall in the same place: whether synthesis requires a network, and whether it requires GPU capacity. The two on-device neural options sit on opposite sides of the GPU line, and every hosted service sits on the far side of the network line. The three orders of magnitude of footprint in Table 2.7 are therefore not a continuum of small trade-offs but a set of discrete commitments about where synthesis runs and what it displaces.

Three numbers decide how this pipeline behaves in a dining room, and the literature supplies none of them: the frame-level decision threshold, the silence interval that terminates an utterance, and the transcription accuracy attainable on restaurant-domain vocabulary. Every evaluation cited above was conducted on read speech, telephony, or recorded meetings, in quiet or acoustically controlled conditions. The one acoustic condition that defines the deployment, intelligible conversation carried from the next table, appears in none of them. The three are therefore empirical quantities rather than settings to be looked up, and they remain open in this work.

A second gap is not acoustic at all. Voice assistants in the surveyed literature are single-device systems: one microphone, one speaker, one user, activated by a wake word and listening continuously thereafter. The arrangement required here differs in kind. Capture is armed deliberately, by a customer pressing a control on a tablet that is not the device holding the microphone. The command is routed through a server to whichever robot is currently serving that table, a binding that changes as robots move between tables. And the resulting turn has to remain interruptible throughout, by a customer who cancels it, mutes the reply, or simply begins speaking over it. None of this is a property of the detection, transcription, or synthesis models, which are indifferent to how they are invoked. It is a property of the orchestration around them, and it has no counterpart in single-device voice assistants, whose activation model assumes that the microphone, the speaker, the control surface, and the user occupy the same place.


## 2.4 Conversational AI Agent

### 2.4.1 From General-Purpose LLM to Task-Oriented Agent
Large language models (LLMs) are text-in-text-out systems: they cannot modify databases or command external devices directly. Early bridges used brittle post-hoc parsing (regex, keyword matching) over free-text outputs; any unanticipated phrasing broke the pipeline. Function calling resolved this by making structured JSON invocation a native capability: the LLM receives a typed tool schema, emits an invocation object, and the framework executes it and feeds the result back [35].

Figure 2.7: Function calling mechanism

Function calling provides the mechanism for action. It does not guarantee correctness. An LLM can invoke the right tool with hallucinated arguments, call tools in an invalid sequence, or produce parameter values that violate domain constraints. Whether tool invocations are safe in a transactional domain, where an error has material consequences, is settled by the layers around the LLM: the orchestration architecture, the routing mechanism, the validation gates, the memory system, and the planning logic. The subsections that follow survey each of them.


### 2.4.2 Agent Architectures: The Orchestration Layer
The architecture around the LLM decides when tools may run, what happens between calls, and what is guaranteed about termination and correctness. Four patterns dominate the literature [37]-[40].

A *chain* hard-codes a fixed linear sequence of steps. Control flow is auditable and termination is fixed, but a routing error early in the chain is unrecoverable and open-ended natural language makes failure-mode enumeration combinatorial [36]. An *autonomous loop* (ReAct and extensions such as AutoGPT) lets the LLM choose the next action from observed state [37]. Flexibility comes at the cost of structural guarantees: termination depends on the model, and nothing enforces valid tool sequences or argument checks before execution [37]. A *graph* (LangGraph) encodes the state machine in topology: conditional edges, checkpointed state, and circuit breakers give branching with structural termination [38]. *Multi-agent* systems (AutoGen, CrewAI, CAMEL) specialize prompts and tools across agents, but coordination is itself LLM-mediated, attention dilutes as agent count grows, and ownership of process correctness is diffused [39], [40].

Table 2.8: Documented properties of the four agent architectures.


| Property | Chain | Loop (ReAct) | Graph (LangGraph) | Multi-agent |
| --- | --- | --- | --- | --- |
| Termination condition | Fixed length | LLM decides | Graph topology | Emergent |
| Deterministic step between proposal and execution | ✗ | ✗ | Available | ✗ |
| Tool ordering fixed by | Developer | LLM at run time | Topology + state | Inter-agent negotiation |
| Adaptation to unanticipated utterances | ✗ | ✓ | ✓ | ✓ |
| Coordination overhead | None | None | None | LLM-mediated per handoff |

The four differ on where governance resides: developer, LLM, topology, or nowhere in particular. None has been evaluated on task-oriented dialogue in which every proposed action is inspected before it executes [37], [38], [39].

Tool *selection* accuracy is well characterized by the tool-learning literature [41], [42]. *Compositional* correctness (whether a sequence of calls produces the intended final state) is not. Sequential, parallel, and conditional composition are documented; only conditional composition requires a deterministic component between two LLM-proposed calls. Benchmarks typically measure per-call accuracy, which can score both calls in an invalid sequence as correct while the shared business state is wrong [43].

Figure 2.8: Four agent architecture patterns: chain, loop, graph, and multi-agent


### 2.4.3 Large Language Models: The Reasoning Component
Vietnamese-capable LLMs fall into three groups that trade language quality against tool-calling support and deployment constraints:

Vietnamese-native models (e.g. PhoGPT): strong fluency and polite registers, but no native function-calling API, which forces a return to brittle text parsing (Section 2.4.1).

Open-weight multilingual models (e.g. Qwen2.5 [44], Llama 3, Gemma 2): documented tool calling and self-hosted deployment; Vietnamese quality is functional but occasionally stilted.

Commercial APIs (e.g. GPT-4o [45], Claude 3.5 Sonnet): strongest joint fluency and tool use, but cloud-dependent and per-token costly.

Table 2.9: Function-calling support and Vietnamese quality across model categories.


| Category | Representative models | Open weights | Tool calling | Vietnamese quality |
| --- | --- | --- | --- | --- |
| Vietnamese-native | PhoGPT 7B, ViSoBERT [46] | ✓ | ✗ | Excellent |
| Open-weight multilingual | Qwen2.5, Llama 3, Gemma 2 | ✓ | ✓ | Moderate to good |
| Commercial API | GPT-4o, Claude 3.5, | ✗ | ✓ | Excellent |

Two further constraints matter for this domain. Attention favors prompt boundaries ("lost in the middle"), and multilingual tokenizers over-segment Vietnamese diacritics and compounds, so a Vietnamese conversation consumes more of the context budget than an English equivalent [47]. Quantization for edge serving can further degrade underrepresented languages [48]. Critically, function-calling benchmarks (BFCL) are English-only, while Vietnamese Natural Language Understanding (NLU) benchmarks measure text generation rather than structured actions. Joint performance on domain tool calling in Vietnamese is unmeasured.


### 2.4.4 Intent Classification: The Routing Layer
Before a tool runs, the system must route the utterance to the right subsystem. Five approaches trade speed against flexibility [52]:

Rule-based and lightweight classifiers: fast and deterministic, but fail on teencode and context-dependent turns.

Semantic centroids: handle new vocabulary, but not multi-intent blends.

State-augmented classifiers: require dialogue-state corpora that do not exist for Vietnamese.

LLM routing: handles teencode, context, and multi-intent turns, at second-scale latency with non-deterministic sampling.

LLM decomposition for a fast downstream classifier: untested on Vietnamese segmentation ambiguities.

Table 2.10: Routing approaches against criteria in the routing literature.


| Approach | Informal language | Context-aware | Multi-intent | Inference cost | Deterministic |
| --- | --- | --- | --- | --- | --- |
| Rule/SVM (Rasa, Dialogflow) | ✗ | ✗ | ✗ | Milliseconds | ✓ |
| Lightweight (fastText, SetFit [51]) | Partial | ✗ | ✗ | Milliseconds | ✓ |
| Semantic centroid | ✗ | ✗ | ✗ | Milliseconds | ✓ |
| LLM-based | ✓ | ✓ | ✓ | Seconds | ✗ |
| State-augmented classifier | Depends | ✓ | ✗ | Milliseconds | ✓ |

Published evaluations, including standard intent-classification benchmarks with out-of-scope coverage [71], fix one approach for a whole test set. None varies the router per utterance within a session, and none evaluates Vietnamese task-oriented speech where compound dish names, diacritics, and teencode stress every method at once.


### 2.4.5 Action Validation: The Safety Layer
Correct routing does not guarantee correct arguments. The literature addresses argument-level errors at different stages: constrained decoding [53] enforces schema syntax but not factual existence; RAG grounding [54] lowers hallucination probability without enforcement; self-correction [55] and human-in-the-loop achieve semantic accuracy at the cost of autonomy.

Table 2.11: Where each validation approach intervenes.


| Approach | Syntax | Semantic | Autonomous | Operates at |
| --- | --- | --- | --- | --- |
| Constrained decoding | ✓ | ✗ | ✓ | Generation |
| RAG grounding | ✗ | Partial | ✓ | Generation |
| Human-in-the-loop | ✓ | ✓ | ✗ | Post-generation |

A propose-and-verify pattern (probabilistic proposal, deterministic oracle) is documented in code generation and clinical decision support, but largely uncharacterized for conversational agents whose oracle would be the domain's own operational records. The interval between a fully formed tool call and its execution is occupied by no autonomous mechanism in the surveyed work.


### 2.4.6 Memory and State Management in Conversational Agents
Transactional dialogue needs history across turns. Four strategies are standard: sliding window, periodic summarization, vector retrieval, and hybrids [56], [57]. All compete for the same context budget already strained by Vietnamese tokenization (Section 2.4.3). Conversation text and application state (cart, stage, confirmed items) do not tolerate the same treatment: lossy summary preserves dialogue flow but destroys billable structure. Serialization tools exist (e.g. LangGraph checkpointers) [38], yet the memory literature does not evaluate retaining the two kinds of content under different policies.


### 2.4.7 Identified Literature Gaps
Three absences follow from studying and evaluating these components separately.

**Joint measurement (****Section ****2.4.3).** Function-calling accuracy and Vietnamese language quality are required together; no published benchmark reports both for the same model on the same task.

**Unoccupied interval in the action path (****Section ****2.4.5).** Validation happens during generation or through a human. Propose-and-verify against domain records is not characterized for conversational agents, though graph architectures supply primitives that could host it.

**Treatment of state (****Section ****2.4.6).** Memory research measures retention of conversation text, not deterministic transactional records.

What the surveyed work does not report is a system that addresses all three together, for Vietnamese or any other language.


## 2.5 Menu Knowledge Retrieval (RAG)

### 2.5.1 The Knowledge Problem and Standard RAG
Large language models hallucinate when queried about proprietary data such as a restaurant menu. Retrieval-Augmented Generation (RAG) mitigates this by fetching relevant documents into the prompt before generation [54]. The literature describes Naive, Advanced, and Modular RAG generations that progressively decouple pipeline stages [58]. Modular RAG makes components swappable but supplies no active coordination: nothing decides whether a module's output is adequate or whether retrieval has failed.

All three share a fragile assumption: that query and documents occupy the same vocabulary and vector space. When the user's need is expressed in terms absent from the corpus (query-document vocabulary mismatch), upgrading an encoder or chunker cannot close the gap [58]. The root is architectural. Standard RAG is one-way (query → retrieve → generate): the LLM sits at the end, receives whatever retrieval returns, and has no mechanism to register that the results are unusable or to reformulate before generation.


### 2.5.2 Representing Vietnamese Text for Retrieval
Dense embeddings and sparse term weighting both depend on word segmentation. Vietnamese places spaces between syllables, not words, so a compound such as "bún bò Huế" is three tokens naming one dish. Without segmentation, dense models embed fragments and sparse indexes match individual syllables across unrelated dishes [59]. Reported segmenter accuracies cover formal written Vietnamese; domain proper nouns (essentially an entire menu) are unevaluated.

Table 2.12: Vietnamese word segmentation tools.


| Tool | Method | Accuracy (VLSP 2013) | Deployment | Documented limitations |
| --- | --- | --- | --- | --- |
| underthesea | CRF | ~97% | Pure Python | Informal / proper nouns unbenchmarked |
| VnCoreNLP | RNN + CRF | ~98%+ | Java process | Runtime overhead |
| pyvi | Dictionary + regex | Lower | Pure Python | Weak on ambiguous compounds |

Dense encoders split into Vietnamese-native bi-encoders (PhoBERT-based; stronger on Vietnamese STS, retrieval-specific results unreported) [60], [61] and multilingual models (strong on MIRACL/MTEB; diacritic and compound handling only partially tuned) [62]. Neither category is characterized on menu-like corpora: short, structurally uniform documents dominated by proper nouns. The sparse alternative is BM25 [63], strong at exact lexical match but unable to bridge a vocabulary gap; for Vietnamese its behavior is decided upstream by the segmenter. At menu scale (a few hundred documents), FAISS exact search and a standard inverted index suffice [63], [64].

Table 2.13: Dense embedding models with Vietnamese capability (representative).


| Model | Vietnamese-native | Diacritic-aware | Documented limitation |
| --- | --- | --- | --- |
| vietnamese-bi-encoder / SimCSE-PhoBERT family | ✓ | ✓ | Retrieval-specific benchmarks unreported |
| bge-m3 / multilingual-e5-large | ✗ | Partial | Menu-scale / proper-noun corpora uncharacterized |
| paraphrase-multilingual-MiniLM | ✗ | Weak | Reduced dimension; BPE strips diacritics |


### 2.5.3 Result Fusion
Dense and sparse retrievers produce incommensurable scores. Standard fusion methods (Reciprocal Rank Fusion, linear combination after normalization, Condorcet voting) are well documented [65]. RRF needs no score calibration and transfers across domains; linear combination can exploit magnitude when α is tuned per collection; Condorcet adds cost without a clear two-retriever advantage over RRF. The mechanisms are not restated here.


### 2.5.4 Beyond Retrieve-then-Generate: Rewriting, Evaluation, Context
Extensions attach to edges of the one-way pipeline: pre-retrieval rewriting (Hypothetical Document Embeddings, Step-Back) [66], [67], post-retrieval evaluation or correction (Self-RAG, CRAG) [68], [69], and multi-turn search memory (dialogue state tracking, MemoryBank, LongMem) [70]. Each has been evaluated as an English point solution. Rewriting is open-loop: the model never sees whether the rewrite helped. Post-retrieval correction, where it exists, typically takes a fixed fallback rather than a strategy chosen from what came back. Multi-turn memory persists in context without feeding a failure signal back into retrieval. None has been evaluated where relevance depends on sensory or culinary metadata rather than factual concordance, and none closes a loop from retrieval output back to retrieval input.


### 2.5.5 Identified Literature Gaps
Modular RAG made stages independent and swappable, which also omitted coordination: good and poor module outputs present the same interface. The extensions of Section 2.5.4 attach to the pipeline's edges but do not close it. What is missing is a component that reads a stage's output and decides what happens next. Vocabulary mismatch (Section 2.5.1) gives that absence its concrete form: bridging a sensory query to a corpus indexed by dish name requires domain knowledge held by the LLM, which standard RAG places last and consults never.


## 2.6 Web System: Backend, Data Storage, and Real-Time Interfaces

### 2.6.1 Backend Framework and API Layer
A backend must serve short request/response traffic and long-lived connections that push state and accept device reports. Frameworks differ mainly in concurrency models (synchronous WSGI worker pools vs asynchronous event loops such as Asynchronous Server Gateway Interface / Node.js) and in whether input is validated at the boundary before a handler runs [72]. Splitting persistent connections into a second process forces a broker and a second view of state [72].

Table 2.14: Backend framework families.


| Framework | Concurrency | Boundary validation | Fit note |
| --- | --- | --- | --- |
| FastAPI | WebSocket in-process | Pydantic / OpenAPI | Single process for REST + push |
| Flask | WSGI pool | Manual | Long-lived connections occupy workers |
| Django REST | WSGI (+ Channels) | Serializers | Heavy; second runtime for WebSocket |
| Express / NestJS | Event loop | Optional / decorators | Different language from speech/agent stack |

For this deployment, an asynchronous single-process stack fits: robots stream pose over WebSocket while the same process writes orders and payments. FastAPI combines that model with declarative schema checks, which matter when an LLM agent submits writes without a form UI in front of the API. OpenAPI / JSON Schema are documented as client and contract tooling [72]; when an agent selects operations from the same description, field wording becomes behavioral, a use noted in Section 2.4.1 but not linked from the web literature.


### 2.6.2 Data Storage
Transaction volumes at single-venue scale are low: tens of seating, orders, and payments an hour, written by one application process. At that volume the database literature treats the choice as a question of operational cost and concurrency semantics rather than of throughput [72].

Table 2.15: Data stores for a single-venue deployment.


| Store | Approach | Advantages | Limitations |
| --- | --- | --- | --- |
| SQLite | Embedded in the application process, one file on disk | Nothing to install, secure, or keep running; no network hop; relational constraints enforced by DDL; WAL mode lets readers proceed during a write | One writer at a time; no access from another machine; limited concurrent write throughput |
| PostgreSQL | Separate service reached over a network protocol | Many concurrent writers with row-level locking; richer constraint and index types; access from other machines | A service to install, secure, back up, and keep running; a network hop on every query; unused capacity at this transaction rate |
| MongoDB | Separate service, document-oriented | Schema can change without migration; suits heterogeneous or nested records | No enforced schema, so lifecycle rules move into application code; joints across collections are awkward; same administrative cost as a server database |

Restaurant records are strongly relational, and their value lies in a lifecycle being enforced. A visit runs as a sequence in which a party is seated, orders accumulate, a bill is settled, and the table is released, and which step is permissible next depends on the current position [72]. Where staff drive those transitions, the constraints are carried by the workflow rather than by the schema: nobody settles a bill for a table with no one sitting at it, and the software need not prevent it. Commercial platforms implement these lifecycles internally and expose them through the interfaces staff use, not as operations a program can invoke [72]. What enforcement becomes necessary when the entity driving the transitions is not a person and cannot be relied on to observe an implicit workflow, does not arise in systems built on the assumption that it always is one.

For a restaurant service system SQLite is the option whose limitations do not bind.The single-writer restriction costs nothing where one backend process performs every write, the absence of remote access costs nothing where the database and the application are the same program, and the write throughput ceiling sits several orders of magnitude above tens of transactions an hour. What it removes is the whole administrative surface of a database service, which is the recurring cost in a venue with no operations staff. A document store would be the poorest fit, because the schema is exactly the part worth keeping once an agent is among the writers.


### 2.6.3 Real-Time Transport
Table 2.16: Transport mechanisms for browser and device clients.


| Mechanism | Approach | Advantages | Limitations |
| --- | --- | --- | --- |
| Polling | Client re-requests state on a fixed interval | Trivial to implement; no new endpoint needed; each request is independent, so recovery is automatic | Mean staleness half the interval; request volume fixed by client count and interval, not by change rate; server cannot initiate |
| WebSocket | One upgraded connection, persistent and bidirectional | Updates arrive on change; client can report as well as receive; one connection both ways | One open connection per client; a dropped socket does not re-establish itself, so reconnection is the application's job; an open socket is no evidence that the peer is working |
| Server-sent events | Server-to-client stream over a held-open HTTP response | Lighter than a WebSocket; auto-reconnects in the browser; resumes from the last event received | One direction only, so a client that must also send needs a second channel; limited concurrent connections per origin on HTTP/1.1 |

Polling degrades predictably, and kitchen display systems have conventionally run on it at intervals of several seconds, which the sources treat as unobjectionable for a screen a cook consults periodically (Section 2.1.3). Those characterizations are written against human tolerance for staleness. None of them reports what interval is appropriate when what waits on the state is a machine.

For a restaurant service system, the two persistent mechanisms are complementary rather than competing, and which one fits depends on the client. Robots have to report position and task progress as well as receive assignments, and a browser panel showing a live map benefits from the same channel, so a WebSocket is the mechanism that suits shared operational state. An agent's spoken reply is a different shape of traffic: it is produced progressively, flows one way to one tablet, and gains nothing from a return path, which is the case server-sent events were designed for. Polling remains adequate for anything a person merely glances at, and its cost is that it stops being adequate the moment a machine is the one waiting.

Two further properties are documented as mechanisms and left open as content. Routing events to subsets of clients by declared role is a standard publish-and-subscribe arrangement and is not itself difficult [72]; the event vocabularies are application-specific, and where commercial restaurant platforms implement one internally, they do not publish it (Section 2.1.3). The second is that an open connection is not evidence of a working peer. A process that has crashed closes its socket and is easily detected. A process that has hung holds the socket open, satisfies any check made at the transport layer, and reports nothing. Liveness therefore has to be established at the application layer, by requiring positive evidence at intervals and treating silence beyond a tolerance as failure [72]. The sources give the mechanism but no general value for tolerance, since what it should be depends on what the system does once failure is declared.


### 2.6.4 Frontend Stack
Role-specific interfaces over shared state are typically single-page applications. Vue 3, React, and Angular dominate [73]. Vietnamese rendering does not distinguish them. Runtime cost does: one UI runs on the robot's board beside navigation and speech (section 3.2.1), updating on WebSocket pose streams. Vue's dependency tracking re-renders only affected components; React reconciles a virtual DOM on state change; Angular walks a change-detection tree. On a CPU shared with control loops, that difference is capacity taken from motion. Ecosystem size and framework ceremony favor large teams; they do not repay themselves on small role UIs.

Table 2.17: SPA frameworks (selection-relevant properties).


| Framework | Update model | Relative runtime cost on frequent updates |
| --- | --- | --- |
| Vue 3 | Proxy dependency tracking | Lowest of the three |
| React | Virtual DOM reconciliation | Higher per update |
| Angular | Tree change detection | Highest structure/runtime overhead |

Supporting choices follow established practice: data-dense component libraries for operations screens, Vite for fast native-ESM development and tree-shaken production builds, and multiple role apps over one backend with shared types and role-scoped subscriptions [73].

