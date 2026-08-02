MINISTRY OF EDUCATION AND TRAINING

HCMC UNIVERSITY OF TECHNOLOGY AND ENGINEERING

FACULTY OF MECHANICAL ENGINEERING

DEPARTMENT OF MECHATRONICS

----------------------------------


![image01.png](images/image01.png)


GRADUATION THESIS


SMART RESTAURANT ASSISTANT: LEVERAGING LARGE LANGUAGE MODELS FOR DINING INTERACTION AND AUTONOMOUS DELIVERY


| SUPERVISOR: | PhD. TRAN VU HOANG |
| --- | --- |
| STUDENT: | DINH DUC DUY - 22134001 |
|  | HUYNH THANH PHONG - 22134009 |
|  | LE QUOC THINH - 22134013 |
| CLASS: | 22134 |
| YEAR: | 2022 - 2026 |


MINISTRY OF EDUCATION AND TRAINING

HCMC UNIVERSITY OF TECHNOLOGY AND ENGINEERING

FACULTY OF MECHANICAL ENGINEERING

DEPARTMENT OF MECHATRONICS

----------------------------------


![image02.png](images/image02.png)


GRADUATION THESIS


SMART RESTAURANT ASSISTANT: LEVERAGING LARGE LANGUAGE MODELS FOR DINING INTERACTION AND AUTONOMOUS DELIVERY


| SUPERVISOR: | PhD. TRAN VU HOANG |
| --- | --- |
| STUDENT: | DINH DUC DUY - 22134001 |
|  | HUYNH THANH PHONG - 22134009 |
|  | LE QUOC THINH - 22134013 |
| CLASS: | 22134 |
| YEAR: | 2022 - 2026 |


| TRƯỜNG ĐẠI HỌC CÔNG NGHỆ KỸ THUẬT TP. HCM | CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập - Tự do – Hạnh phúc |
| --- | --- |
| KHOA CƠ KHÍ CHẾ TẠO MÁY | CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập - Tự do – Hạnh phúc |

NHIỆM VỤ ĐỒ ÁN TỐT NGHIỆP

Học kỳ II  / năm học 2025-2026

Giảng viên hướng dẫn: Trần Vũ Hoàng

Sinh viên thực hiện: Đinh Đức Duy	 MSSV: 22134001. Điện thoại: 0865208467

Sinh viên thực hiện: Huỳnh Thanh Phong	 MSSV: 22134009. Điện thoại: 0832338183

Sinh viên thực hiện: Lê Quốc Thịnh	 MSSV: 22134013. Điện thoại: 0365681517

Đề tài tốt nghiệp:

Mã số đề tài: 	28.

Tên đề tài: Smart Restaurant Assistant: Leveraging Large Language Models for Dining Interaction and Autonomous Delivery.

2. Các số liệu, tài liệu ban đầu:

- Mô hình robot di động truyền động vi sai 2 bánh chủ động (Differential Drive Robot), kết hợp bánh dẫn hướng (caster) để giữ thăng bằng.

- NVIDIA Jetson Orin, LiDAR 2D, Camera chiều sâu (RGB-D), STM32.

- Môi trường thử nghiệm: ROS2 + Gazebo.

3. Nội dung chính của đồ án:

- Nghiên cứu kiến trúc tích hợp giữa LLM và hệ điều hành robot (ROS 2).

- Phát triển module Hành động dựa trên ngôn ngữ.

- Tích hợp và kiểm nghiệm hệ thống trên môi trường mô phỏng và thực tế.

4. 	Các sản phẩm dự kiến

- Hệ thống gồm robot di động hai bánh tự hành có khả năng lập bản đồ, tránh vật cản và giao hàng, kết hợp với mô-đun tương tác với thực khách dựa trên mô hình ngôn ngữ lớn (LLM).

- Báo cáo thuyết minh.

5. 	Ngày giao đồ án: 2/2026

6. 	Ngày nộp đồ án: 7/2026

7. Ngôn ngữ trình bày: 	Bản báo cáo:		Tiếng Anh	þ	Tiếng Việt	¨

Trình bày bảo vệ: 	Tiếng Anh	þ	Tiếng Việt	¨


| TRƯỞNG KHOA | GIẢNG VIÊN HƯỚNG DẪN |
| --- | --- |
| (Ký, ghi rõ họ tên) | (Ký, ghi rõ họ tên) |


Được phép bảo vệ	……………………………………………

(GVHD ký, ghi rõ họ tên)


# STATEMENT OF COMMITMENT

- Project name: Smart Restaurant Assistant: Leveraging Large Language Models for Dining Interaction and Autonomous Delivery
- Advisor: PhD. Tran Vu Hoang
- Student: Dinh Duc Duy  MSSV: 22134001 Class 22134
- Address: Topazhome B1, Tang Nhon Phu, HCMC
- Phone: 0865208467
- Email: ducduy9304@gmail.com
- Student: MSSV: Class 22134
- Address:
- Phone:
- Email:
- Student: Class 22134
- Address:
- Phone:
- Email:
- Graduation thesis submission date: 30/07/2026
- Statement of commitment: "I hereby declare that this graduation thesis is my own research and work. I have not copied from any published article without citing the source. If there is any violation, I take full responsibility"


Ho Chi Minh City, 30th July 2026


# ACKNOWLEDGMENT

We want to thank our supervisor, PhD. Tran Vu Hoang for his precious direction, support, and encouragement throughout this study. His skill, knowledge, and constructive criticism have been essential in the direction and achievement of this thesis.

We want to give our sincere thanks to the lecturers of the Faculty of Mechanical Engineering, Ho Chi Minh City University of Technology and Education, for the knowledgeable and academic atmosphere where we  accomplished this work. The authors also wish to thank the professors and personnel who helped and guided them during their project.

We want to thank members of the research group for providing collaboration and shared resources, which greatly enhanced the quality of this work.

To our family and friends, I genuinely appreciate your support, love, and encouragement; without it, I could not have gone through this journey. Their faith in me has served as inspiration.

Lastly, I want to thank those who helped and participated in realizing this thesis, directly or indirectly.

Sincerely,

Dinh Duc Duy

Huynh Thanh Phong

Le Quoc Thinh


# ABSTRACT

Smart Restaurant Assistant: Leveraging Large Language Models for Dining Interaction and Autonomous Delivery

Restaurant service automation has advanced along two lines that do not meet. Delivery robots carry food between fixed points but take their destinations from a person, and conversational systems understand an order but cannot act on the physical world. A restaurant wanting both runs two systems with a member of staff between them.

This thesis presents an autonomous waiter that joins them. A customer speaks Vietnamese to a robot; a conversational agent turns the utterance into checked actions on live restaurant records; the kitchen display updates as the order is placed; and the robot navigates to the correct table and docks against a fiducial marker. Every component runs on the restaurant's own hardware with no cloud dependency.

The central design decision is that the language model proposes and deterministic code disposes. A trained classifier routes each utterance in 7.2 ms at 95.3 % accuracy, matching a 14-billion-parameter model prompted for the same task at a twenty-fourth of its latency. A rule-based validator inspects every tool argument against the menu before execution: with the validator bypassed, 32 dishes the kitchen cannot cook reached the cart across 41 scenarios; with it enabled, none did, in any run. The deterministic layers wrote nothing incorrect in thirty-five end-to-end runs, of which 29 completed a full ordering conversation. Median turn latency is 1.61 s. On the robot, graph SLAM with marker landmarks bounds pose error, and last-metre visual alignment reduces docking error from 47.8 cm to 1.6 cm at a cost of 1.1 s per delivery.

Where the system still fails, it fails in the language model's judgement rather than in the layers built to contain it.


# LIST OF FIGURES

Figure 1.1: A Commercial Restaurant Service Robot [11].	16
Figure 1.2: Screen-Mediated Ordering	17
Figure 1.3: Food Robotics Market Forecast: global market value from 2022 to 2034, with 2026 to 2034 shown as projection.[5]	19
Figure 2.1: Track-based food delivery: Alibaba Robot.	23
Figure 2.2: Top-view geometry of the two-wheel differential drive: reference point O, wheel track W, wheel speeds  and , and body-frame velocities , .	27
Figure 2.3: ROS2 publish/subscribe communication.	29
Figure 2.4: The navigation stack and its goal interface.	33
Figure 2.5: Pose estimation from a square fiducial marker.	34
Figure 2.6: Precision against recall for five voice activity detectors on a multi-domain validation set.	37
Figure 2.7: Function calling mechanism	44
Figure 2.8: Four agent architecture patterns: chain, loop, graph, and multi-agent	46
Figure 3.1: Block diagram of the robot's electronics with the Jetson Orin Nano at the center and three data links.	61
Figure 3.2: Block diagram of Encoder-IMU odometry fusion using EKF.	69
Figure 3.3: RTAB-Map SLAM data-flow architecture.	73
Figure 3.4: Effect of loop closure. The map before and after a loop closure is accepted	74
Figure 3.5: Localization and pose-correction flow.	76
Figure 3.6: Autonomous navigation architecture and motion planning framework.	81
Figure 4.1: System Architecture Overview: the three-tier layout and the type of connection	85
Figure 4.2: Edge Voice Pipeline: the three threads passing one utterance through two queues, with the barge-in path that lets the customer interrupt.	89
Figure 4.3: Agent StateGraph Topology	90
Figure 4.4. Intent Classification Pipeline	94
Figure 4.5: Validator Control Flow	100
Figure 4.6: Menu Name Resolution Cascade	101
Figure 4.7: Cart and Order Stage Machine	107
Figure 4.8: Hybrid Retrieval Pipeline	111
Figure 4.9: The three control layers	117
Figure 4.10: A task, and the robot state	119
Figure 4.11: The ordering screen at rest, waiting for a guest to touch it	120
Figure 4.12: The menu, with the voice prompt sitting above the dish grid	121
Figure 4.13: The entrance kiosk, showing the tables and how many are free	122
Figure 4.14: The management panel: the table overview, the robot board, the kitchen board, and the minimap docked at the lower right	123
Figure 5.1: Robot simulation on Gazebo and Rviz2	131
Figure 5.2: Aruco marker ID 1 for one table and ID 6 for Dock	132
Figure 5.3: Stockroom facility with polished ceramic tile flooring, three aisle-bounding storage crates, Dock station marked with ArUco 6, and Table 1 with ArUco 1	132
Figure 5.4: Overlaid odometry paths.	133
Figure 5.5: Runtime ROS 2 transform tree (TF tree)	135
Figure 5.6: Occupancy grid with Dock and Table 1	136
Figure 5.7:  Localized paths overlaid on restaurant map	136
Figure 5.8: Real-time dynamic obstacle avoidance sequence in the service lane	139
Figure 5.9: Retrieval Quality by Query Difficulty	151
Figure 5.10: Turn Latency by Intent Class	157
Figure 5.10: Share of turn latency by graph node	158

# LIST OF TABLES

Table 2.1: Type of interfaces with autonomous physical delivery	25
Table 2.2: 2D SLAM implementations available for ROS2.	30
Table 2.3: Localization against a prior map.	31
Table 2.4: Nav2 global planners and local controllers.	32
Table 2.5: Voice activity detection approaches.	37
Table 2.6: Speech-to-text options for Vietnamese.	40
Table 2.7: Text-to-speech engines with Vietnamese capability.	42
Table 2.8: Documented properties of the four agent architectures.	44
Table 2.9: Function-calling support and Vietnamese quality across model categories.	46
Table 2.10: Routing approaches against criteria in the routing literature.	47
Table 2.11: Where each validation approach intervenes.	48
Table 2.12: Vietnamese word segmentation tools.	50
Table 2.13: Dense embedding models with Vietnamese capability (representative).	51
Table 2.14: Backend framework families.	52
Table 2.15: Data stores for a single-venue deployment.	53
Table 2.16: Transport mechanisms for browser and device clients.	54
Table 2.17: SPA frameworks (selection-relevant properties).	55
Table 3.1: Robot platform specification.	57
Table 3.2: Extended Kalman Filter design settings.	67
Table 3.3: Covariance values, planar diagonal entries.	68
Table 3.4: RTAB-Map configuration for mapping.	70
Table 3.5: Costmap configuration.	77
Table 3.6: Global planner and local controller configuration.	80
Table 4.1: Memory budget on the Jetson after the navigation stack of Chapter 3.	86
Table 4.2: The nodes of the agent graph, in the order an utterance meets them.	91
Table 4.3: Layer composition of the intent classifier MLP.	93
Table 4.4. The five styles of the manual dataset.	95
Table 4.5. Training hyperparameters and methodology.	96
Table 4.6. What each agent receives and what it produces.	98
Table 4.7. What the validator checks before each tool, and what happens when a check fails.	103
Table 4.8. The five categories of state field, by lifecycle.	104
Table 4.9: The agent's seven tools, what each touches, and whether its effect outlives the session.	105
Table 4.10. The five response contexts, and what each carries into the reply stage.	108
Table 4.12. Where each retrieval lane succeeds, where it fails, and on what kind of query.	112
Table 4.13. Settings of the retrieval pipeline.	114
Table 5.1: Server specification	125
Table 5.2: Robot hardware components and specifications.	126
Table 5.3: Software stack specifications.	127
Table 5.4: Evaluation datasets	128
Table 5.5: Odometry return-to-start error.	133
Table 5.6: Mapping summary.	135
Table 5.7: Localization drift vs surveyed floorplan ground truth	135
Table 5.8: Delivery performance with visual alignment enabled.	137
Table 5.9: Without visual align (ENABLE_VISUAL_ALIGN = False).	138
Table 5.10: Traceability.	140
Table 5.11: Confusion matrix on the single-intent set (n = 149)	142
Table 5.12: Multi-intent detection.	143
Table 5.13: Accuracy and latency of the router arms	143
Table 5.14: Name resolution, suggestion and ambiguity detection by stage.	145
Table 5.15: Validator ablation (n = 41 scenarios per arm).	146
Table 5.16: Multi-intent execution and verbalisation	147
Table 5.17: Retrieval quality by mode	149
Table 5.18: Retrieval with the customer's words and with the rewritten query	150
Table 5.19: The eight queries the fused ranking returns nothing relevant for, by cause.	151
Table 5.20: The six conversations, the claim each exercises, and the outcome.	153
Table 5.21: Objectives against measured results.	159
Table 5.22: Failures by responsible component.	160

# LIST OF ABBREVIATION

AI		Artificial Intelligence

API		Application Programming Interface

BM25		Best Matching 25

CRAG	Corrective Retrieval Augmented Generation

DWB		Dynamic Window Approach

EKF		Extended Kalman Filter

FAISS	Facebook AI Similarity Search

GPU		Graphics Processing Unit

ICP		Iterative Closest Point

IMU		Inertial Measurement Unit

LiDAR	Light Detection and Ranging

LLM		Large Language Model

MLP		Multi-Layer Perceptron

Nav2		Navigation 2

PnP		Perspective-n-Point

ROS 2	Robot Operating System 2

RTAB-Map	Real-Time Appearance-Based Mapping

RAG		Retrieval-Augmented Generation

SLAM	Simultaneous Localization and Mapping

RGB-D	Red-Green-Blue + Depth

STT		Speech-to-Text

TTS		Text-to-Speech

VAD		Voice Activity Detection

WER		Word Error Rate

URDF	Unified Robot Description Format

