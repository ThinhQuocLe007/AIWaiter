## 2.1 Service Robots in Hospitality

> **Status:** draft v2 (trimmed to commercial robots only)
> **Cross-refs:** §3.1 (robot platform), §3.2 (system requirements), §4.1 (AI requirements)
> **Scope note:** This section surveys only commercial restaurant robots — physical platforms deployed in real restaurants. Academic ROS2 navigation projects are surveyed in §2.2.5. Voice-enabled restaurant ordering systems (Wendy's FreshAI, Domino's, Zalo AI, VinAI) are surveyed in §2.4.5.
> **Citations:** [2.1.1]–[2.1.15]
> **Figures needed:** Fig 2.1 — commercial restaurant robots side by side (Bear Servi, Pudu Bellabot, Keenon T5, Alibaba Robot.He pod) with annotated capabilities.

---

Service robots are defined by the International Organization for Standardization (ISO 8373) as robots that "perform useful tasks for humans or equipment, excluding industrial automation applications," with a required "degree of autonomy" ranging from partial human–robot interaction to fully autonomous operation [2.1.1]. The International Federation of Robotics (IFR) reports that professional service robots in the hospitality sector constitute one of the fastest-growing categories, driven by labor shortages, rising operational costs, and post-pandemic demand for contactless service [2.1.2].

Commercial restaurant service robots fall into two broad architectural categories: free-navigation platforms that use SLAM-based localization to move autonomously through a mapped space, and track-based AGV systems that follow fixed physical rails. This section surveys the leading products in each category, identifies their shared limitations, and establishes why a custom open-platform robot — rather than an off-the-shelf commercial product — is necessary to achieve the integration of voice interaction, Vietnamese language support, and AI-based autonomous ordering that this thesis proposes.

---

### Free-Navigation Commercial Robots

Three manufacturers dominate the free-navigation restaurant robot market, collectively deploying tens of thousands of units globally [2.1.3].

**Bear Robotics (USA, est. 2017).** Bear Robotics produces the Servi family of autonomous indoor delivery robots. Servi (2020) is a 3-tier tray delivery robot designed for food-running — transporting dishes from kitchen to table and returning used plates. Servi Plus (2022) adds a 4-tier chassis and a built-in touchscreen for table-side interaction. Servi Q (2024) introduces a lift mechanism and load cell for weight-based dish detection. All Servi models share a common navigation stack: floor-level LiDAR (2D laser scanner) for mapping and localization, RGB-D cameras for 3D obstacle detection, and wheel odometry for dead reckoning. The robots operate in pre-mapped environments and navigate via a proprietary path-planner along learned routes [2.1.4]. Bear Robotics offers a cloud-based fleet management dashboard called Bear Universe for multi-robot coordination, but the platform is closed — third-party software cannot control the robots or extend their capabilities. Critically, Servi robots have no voice interface and no support for Vietnamese language processing [2.1.5].

**Pudu Robotics (China, est. 2016).** Pudu's flagship product Bellabot (2019) is a cat-shaped delivery robot with 4-tier trays and a 10.1-inch touchscreen display. Bellabot uses a combination of laser SLAM and visual SLAM (vSLAM) with a ceiling-facing RGB-D camera for marker-based localization — infrared-reflective markers on the ceiling provide absolute positioning references [2.1.6]. Pudu's navigation system supports dynamic obstacle avoidance, enabling Bellabot to operate in crowded restaurant environments with moving customers. The robot features a bionic "emotional expression" display — animated cat facial expressions designed to increase customer acceptance. The PuduCloud platform provides remote fleet management, task scheduling, and data analytics [2.1.7]. As of 2023, Pudu reported over 40,000 units deployed across 600+ cities, making it the highest-volume restaurant service robot manufacturer worldwide [2.1.8]. Bellabot includes a built-in voice greeting module that plays pre-recorded audio messages ("Your food has arrived"), but has no speech recognition, no dialogue capability, and no Vietnamese language support.

**Keenon Robotics (China, est. 2010).** Keenon's T5/T6/T8 delivery robots serve restaurants, hotels, and hospitals. The T-series uses a combination of LiDAR + depth cameras for SLAM-based navigation, with an emphasis on narrow-aisle maneuvering (minimum passage width of 55 cm) [2.1.9]. Keenon robots feature automatic elevator integration for multi-floor restaurants, a 40 kg payload capacity per tray, and a 10-hour battery runtime. The navigation system employs ceiling marker localization — similar to Pudu's approach — but Keenon emphasizes its centimeter-level positioning accuracy via a proprietary multi-sensor fusion algorithm [2.1.10]. The robots include a touchscreen for basic interaction (order status display, call-waiter button) but lack voice interaction and Vietnamese language support.

### Track-Based AGV Restaurant Robots

A fundamentally different architectural approach to restaurant automation comes from Alibaba Group's Robot.He restaurant, opened in 2018 inside the Hema supermarket at the National Exhibition and Convention Center (NECC) in Shanghai [2.1.11]. Unlike the free-navigation robots described above, Robot.He uses fixed-track Automated Guided Vehicles (AGVs) — small pod-shaped delivery robots that travel along dedicated waist-high rail tracks running alongside the dining tables. The technology is adapted from Alibaba's Cainiao logistics division, which operates AGV fleets in e-commerce automated warehouses [2.1.12].

The track-based architecture eliminates the SLAM, localization, and obstacle avoidance problems entirely: the rail IS the navigation system, and each table is a fixed station on the rail network. A customer orders through the Hema mobile app using QR codes for seating and payment tracking. Kitchen staff place prepared dishes into the robot pods, which then traverse the rail network to the correct table based on the customer's QR-coded location. Upon arrival, the pod's glass lid opens automatically, and a built-in voice module plays a pre-recorded greeting message. Conveyor belts and a robotic arm transfer food between the kitchen preparation area and the track loading stations [2.1.13].

Robot.He represents an important design point in the restaurant automation landscape: the infrastructure is fixed, so the robot's intelligence requirements are minimal. There is no perception, no mapping, no path planning — just track following. This design reduces navigation complexity dramatically, but at a significant cost: the rail infrastructure must be physically installed and cannot be reconfigured without construction; the rail network constrains table layout flexibility; the robots have no ability to interact with customers beyond opening a lid and playing a pre-recorded message; and the system is proprietary — Alibaba does not sell the Robot.He platform to third-party restaurants. Alibaba's e-commerce rival JD.com subsequently announced plans to deploy 1,000 fully automated robot restaurants using similar AGV technology by 2020, though the current deployment status of those plans is unclear [2.1.14].

### Common Limitations Across All Commercial Platforms

Both free-navigation robots (Bear, Pudu, Keenon) and track-based AGV systems (Alibaba Robot.He) have solved the core autonomous delivery problem in restaurant environments — they reliably transport food from kitchen to table. However, four fundamental limitations persist across all commercial offerings:

1. **No voice interaction.** All commercial restaurant robots — whether free-navigation or track-based — are screen-only. A customer must read the menu on a tablet or a physical card, then tap buttons to place an order. There is no natural-language ordering — the customer cannot say "Cho 1 phần Ốc Hương Xốt Trứng Muối" and have the robot understand. Robot.He's built-in voice module only plays pre-recorded messages; it does not recognize speech.

2. **No Vietnamese language support.** All commercial platforms are designed for English, Chinese, Japanese, and Korean markets. Their displays, voice greetings, and any interaction flows do not support Vietnamese.

3. **Closed platforms.** All manufacturers provide proprietary, closed-source software stacks. Third-party developers cannot add new capabilities — an LLM agent, a Vietnamese STT pipeline, a custom fleet dispatcher. The robot is an appliance, not a programmable platform [2.1.15].

4. **Infrastructure coupling (track-based systems).** Track-based AGV systems require permanent physical rail installation. The restaurant layout is fixed at construction time; adding a table or reconfiguring the seating area requires mechanical modification of the rail network.

These limitations motivate the decision in this thesis to build on an open ROS2-based two-wheel differential drive platform (§3.1) rather than adopting a closed commercial robot — full control over the software stack is necessary to integrate AI components at every level. The specific technical gaps that the commercial platforms leave unaddressed — autonomous navigation (§2.2), Vietnamese speech processing (§2.3), conversational AI agents (§2.4), knowledge retrieval (§2.5), fleet management (§2.6), and web/backend systems (§2.7) — are detailed in the subsequent sections of this chapter.

---

### References (for §2.1)

[2.1.1] International Organization for Standardization. (2021). *ISO 8373:2021 — Robotics — Vocabulary.* ISO.

[2.1.2] International Federation of Robotics. (2023). *World Robotics 2023 — Service Robots.* IFR Statistical Department, Frankfurt.

[2.1.3] Chen, M., Wang, X., Law, R., & Zhang, M. (2023). Research on the frontier and prospect of service robots in the tourism and hospitality industry based on international core journals: A review. *Behavioral Sciences, 13*(7), 560.

[2.1.4] Bear Robotics. (2024). Servi Product Line Technical Overview. https://www.bearrobotics.ai/products

[2.1.5] Tuomi, A., Tussyadiah, I. P., & Stienmetz, J. (2021). Applications and implications of service robots in hospitality. *Cornell Hospitality Quarterly, 62*(2), 232–247.

[2.1.6] Pudu Robotics. (2023). Bellabot: Autonomous Delivery Robot — Technical Specifications. https://www.pudurobotics.com/products/bellabot

[2.1.7] Ivanov, S., & Webster, C. (2023). Restaurants and robots: Public preferences for robot food and beverage services. *Journal of Tourism Futures, 9*(2), 229–242.

[2.1.8] Pudu Robotics. (2023). "Pudu Robotics Surpasses 40,000 Units Deployed Worldwide." *Business Wire*, December 12, 2023.

[2.1.9] Keenon Robotics. (2024). T-Series Delivery Robot — Product Overview. https://www.keenon.com/products

[2.1.10] Qiu, H., Li, M., Shu, B., & Bai, B. (2020). Enhancing hospitality experience with service robots: The mediating role of rapport building. *Journal of Hospitality Marketing & Management, 29*(3), 247–268.

[2.1.11] Alibaba Group. (2018). "Robot.He: Alibaba's Automated Restaurant." *Alizila — Alibaba Group Corporate News*, July 2018.

[2.1.12] Alibaba Cloud. (2019). "Cainiao's AGV Warehouse Robots: From Logistics to Hospitality." *Alibaba Cloud Blog*, March 2019.

[2.1.13] Bhardwaj, P. (2018). "Robots are replacing waiters and delivering fresh seafood right to people's tables at Alibaba's high-tech restaurant in Shanghai." *Business Insider*, July 2, 2018.

[2.1.14] Albrecht, C. (2018). "Alibaba Opens Robot Restaurant as Automation Expands Around the Globe." *The Spoon*, July 3, 2018.

[2.1.15] Wirtz, J., Patterson, P. G., Kunz, W. H., Gruber, T., Lu, V. N., Paluch, S., & Martins, A. (2018). Brave new world: service robots in the frontline. *Journal of Service Management, 29*(5), 907–931.
