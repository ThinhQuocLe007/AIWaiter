# CHAPTER 1: INTRODUCTION


## Motivation
Service robots in restaurants have changed shape. The first deployments ran on fixed rails or magnetic tape laid into the floor, so the building had to be rebuilt around the robot. Current platforms localize themselves against a map they built and follow a route an operator can redraw in software. The direction is steady: less fixed infrastructure, more autonomy. But one thing has not changed. These robots navigate to a table, stop, and wait for a person to load or unload them. They do not speak, take an order, or answer a question. They are delivery vehicles, not waiters.

Figure 1.1: A Commercial Restaurant Service Robot [11].

Ordering has moved along a similar line. Paper menus gave way to QR codes and tablet applications, a shift the pandemic accelerated, and which is now ordinary in Vietnamese casual dining. Every step took away part of the conversation a customer used to have with a waiter and handed it to a screen. Speaking to the restaurant instead of tapping at it continues that line rather than departing from it.

Figure 1.2: Screen-Mediated Ordering

The third development is more recent. Large language models stopped being text generators and became controllers: given a set of tools, a model can choose which one to call and with what arguments, so its output is an action on a software system rather than a paragraph for a person to read. An ordering conversation is exactly that kind of task, and this capability is what makes an AI waiter buildable now rather than three years ago.

Inference has also moved closer to where it is used. Open-weight models small enough to serve on one commodity GPU, together with edge boards of the Jetson class, let a restaurant run speech recognition and language understanding on its own premises. The consequences are commercial as much as technical: no per-request cloud bill, no dependence on an external internet connection during service, and customer conversations that never leave the building.

These four lines point at the same system, and nobody has joined them. The robot that reaches the table does not talk to the customer, and the software that understands the customer cannot send a robot. A restaurant that wants both runs two independent systems and bridges them by hand, with a member of staff or a tablet in the middle. The robot can reach the table but cannot talk; the AI can talk but cannot reach the table. Joining them would give the conversation a physical presence, a waiter that listens, answers, and acts, at the table, not behind a screen.

This thesis proposes the joined system: an autonomous waiter robot that accepts spoken Vietnamese orders, processes them through a conversational AI agent, dispatches the order to the kitchen, and navigates to the correct table.

The work contributes in two primary areas. The first is autonomous navigation: a purchased two-wheel differential-drive platform is integrated with ROS 2, sensor fusion, SLAM, and Nav2 to navigate from the docking station to the table and dock against fiducial markers. The second is a conversational AI agent: informal spoken Vietnamese is classified, validated against the restaurant's menu, and converted into actions on live restaurant records. Supporting these are a voice processing pipeline (VAD, STT, TTS) deployed on the robot's edge hardware, and a real-time backend orchestrator that pushes order state, kitchen display and robot position to role-specific web interfaces over WebSocket.


## 1.2 Necessity of the Study
The case for the study rests on three conditions that hold at the same time: a structural labor shortage in food service, a market that is already buying service automation, and a set of component technologies that are individually mature but have not been composed.

The restaurant industry has faced a persistent and worsening labor shortage. In the United States, the restaurant workforce remained approximately 3.6% below pre-pandemic levels as of 2024, with quit rates in hospitality consistently outpacing all other sectors [1], [2]. In Vietnam, the food and beverage sector, valued at over 590 trillion VND in 2023 and forecast to grow at 9 to 10% annually [3], faces its own recruitment pressures. A 2024 survey of Vietnamese food and beverage enterprises found that 48% reported difficulty recruiting and retaining service staff, citing high turnover, wage pressure and a growing preference among younger workers for office-based employment over physical service roles [4]. These conditions create a structural need for automation able to absorb the high-frequency repetitive parts of table service taking orders, answering menu questions, and processing payment not to replace human workers but to cover the portion of the workload for which staff are increasingly unavailable.

Investment in food service automation has accelerated in step with that need. The global food robotics market was valued at 2.18 billion USD in 2024 and is projected to reach 11.78 billion USD by 2034 [5]. A major Chinese manufacturer reported more than 56,000 units deployed across over 600 cities as of the end of 2022 [6]. Vietnamese restaurants, especially in the fast-growing casual dining and hot-pot segments in Ho Chi Minh City, Hanoi and Da Nang, have begun operating service platforms imported from China and South Korea. Those deployments are uniformly non-interactive: the robot navigates to the table but the order was placed through a human waiter or a QR-code menu application. Interaction and navigation remain separate systems the disconnect described above, appearing in the Vietnamese market in operational form.

Figure 1.3: Food Robotics Market Forecast: global market value from 2022 to 2034, with 2026 to 2034 shown as projection.[5]

The third condition is technical. Every component an AI waiter needs already works on its own. Large language models achieve competitive performance on Vietnamese conversational benchmarks [7], [8]. Speech recognition models fine-tuned on Vietnamese reach word error rates below 15% under clean conditions [9]. ROS 2 navigation stacks reliably drive differential-drive platforms in mapped indoor environments [10]. Restaurant management software, covering point-of-sale, kitchen display and QR-code ordering, is a mature commercial category. What does not exist is a system in which these components operate as one pipeline: a customer speaks Vietnamese to a robot, the speech is transcribed, the intent is classified correctly despite informal wording, the agent takes validated actions on a backend, the kitchen display updates in real time, and a robot drives to the correct table. Each component was built for a different context: cloud chatbots for customer support, warehouse fleet managers for logistics, and academic navigation stacks for controlled laboratory environments.

The work is feasible at student scale because the mechanical layer is bought rather than built. The project uses a purchased two-wheel differential-drive platform whose chassis, motors, encoders, microcontroller and IMU are supplied as a unit, and the group's contribution begins at ROS 2 integration: adding the sensors, fusing them, building the navigation stack, and developing the entire AI, backend and web software layer. That boundary keeps the effort on system integration and AI capability rather than on mechanical engineering. The whole system runs on commodity hardware, an NVIDIA GPU for language model inference, an NVIDIA Jetson edge computer for on-robot voice processing, and ordinary web browsers for the client interfaces, which puts the architecture within reach of small and medium-sized restaurant operators.


## Objectives
The overall objective is to design, implement and evaluate an autonomous AI waiter system that takes Vietnamese orders in conversation, processes them through a conversational agent, dispatches orders to the kitchen, and navigates to the correct table using a two-wheel differential-drive robot. Eight specific objectives were set. Chapter 5 reports the measured results for each one, including those that could not be measured within the reporting period.

**Intent classification accuracy.** Classify Vietnamese restaurant utterances into the correct intent, ordering, menu search, payment or general conversation, with accuracy of at least 90% on cases held out from training.

**Routing without a language model in the loop.** Reach that accuracy with a trained classifier rather than with a language model, at a median latency at least an order of magnitude below language-model routing, so that deciding what a customer wants costs no perceptible time.

**Deterministic action validation.** Allow no item absent from the menu to reach the customer's cart, measured by comparing the system with the validator enabled against the same system as the validator bypassed.

**Knowledge retrieval quality.** Retrieve relevant dishes from the 234-entry menu in response to Vietnamese sensory descriptions rather than dish names, with recall at rank five of at least 0.70 and a relevant dish present in the top five results for at least 90% of queries.

**Agent ****turn**** latency.** Produce a reply within five seconds at the median, measured from the arrival of a transcript to the completion of the reply text.

**End-to-end ordering.** Complete full ordering scenarios, from a customer request through a confirmed order to the kitchen display, across conversations that include ambiguous dish names, items that are not on the menu, and changes of mind, with the cart and session state kept consistent throughout. At least 5 of the 7 scenarios must be completed correctly, and no run may produce an incorrect cart or an incorrect bill.

**Map-based navigation.** Build a map of the restaurant from LiDAR and RGB-D data using RTAB-Map, and drive from the docking station to the correct table with a success rate of at least 90%.

**ArUco precision docking**. Re-localize against a wall-mounted ArUco marker on final approach and perform closed-loop visual docking to achieve a final arrival pose error within 10 cm in position (lateral offset) and 8 degrees in heading orientation relative to the target station.

Two clarifications belong to this list. First, Objectives 1 to 6 were evaluated on typed Vietnamese text rather than on speech, so the accuracy figures reported in Chapter 5 describe typed input and do not include speech-recognition error. The voice pipeline (VAD, STT, TTS) uses pre-trained models Silero VAD, PhoWhisper, and Piper whose accuracy is documented in their respective publications. This thesis evaluates the pipeline's end-to-end latency (Section 5.4.7); recognition accuracy is not re-benchmarked, and Section 6.3 records this scope as a limitation. Second, multi-intent verbalization completeness was measured to evaluate how reliably the system communicates all executed intents to the customer, with the expectation of achieving a high completeness rate.


## 1.4 Research Scope
**In scope**. The system is designed for an indoor, flat-floor restaurant environment with a two-dimensional, pre-mapped layout consisting of a kitchen area and six dining tables connected by a dedicated service lane. This scenario was evaluated in simulation. Physical validation on the real robot was carried out separately in a warehouse environment using cardboard boxes as static obstacles, to demonstrate the robot's obstacle avoidance and navigation capability independently of the restaurant layout. The lane is physically separated from the customers, so the robot does not navigate through dining areas and does not perform pedestrian avoidance. Navigation is autonomous within the service lane, and arrival at a table triggers a precision docking step using ArUco fiducial markers. The customer interacts with the system through spoken Vietnamese, processed by a voice pipeline running on the robot's edge computer. The AI agent, the knowledge retrieval system and the backend orchestrator run on a local server with a self-hosted large language model. Three web interfaces, a customer ordering tablet, a guest check-in kiosk and a combined kitchen and fleet management panel, provide the operational frontend. All components communicate over local WiFi with no cloud dependency in normal operation.

**Out of scope.** The robot platform is purchased, so the mechanical design, the chassis, the motors, and the low-level motor control firmware are not part of this work. Physical transport of food and drink is not addressed. The contribution begins at ROS 2 integration.The system supports Vietnamese speech only. The language model is prompted, not fine-tuned. Only one restaurant environment is mapped in simulation, and only one physical environment is used for validation. Multi-floor operations, elevator integration and dynamic obstacle handling for pedestrians in the lane are not addressed.

**Known limitations.** The platform is non-holonomic: it cannot move laterally and corrects heading by rotating in place. The consumer-grade MPU6050 IMU has bounded yaw accuracy, and the drift it accumulates over distance is corrected by the ArUco markers at the tables but not during transit. The Intel RealSense D435 depth camera and ArUco detection are both sensitive to lighting conditions. All components communicate over WiFi, and network latency and occasional packet loss are managed by reconnection logic rather than eliminated.


## 1.5 Report Structure
The structure of this report is organized as follows.

- Chapter 1: Introduces the project
- Chapter 2: Surveys prior work in the areas the system draws on and identifies the gap each area leaves open.
- Chapter 3: Presents the robot control and navigation system.
- Chapter 4: Presents the AI agent, backend orchestrator, and web interfaces.
- Chapter 5: Reports the experimental evaluation of each component against the objectives set in section 1.3.
- Chapter 6: Concludes with the contributions, limitations, and future work.
