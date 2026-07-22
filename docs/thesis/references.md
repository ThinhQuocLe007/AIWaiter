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

### §2.1 Overview: The Integrated AI Waiter Problem

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

---

## Notes and Outstanding Corrections

### Corrections required in the §2.1 draft

**(i) Pudu deployment figure.** The draft states *"Pudu alone reported over 40,000 units deployed
across more than 600 cities as of 2023."* The 600-cities figure is supported (BellaBot, 600+ cities
across 60 countries, as of June 2023). The 40,000-unit figure is not: the publisher reports **nearly
70,000 cumulative units shipped across all Pudu models** as of August 2023. The two halves of the
sentence also mix a company-wide shipment total with a single-product deployment footprint. The same
claim appears in Chapter 1 §1.2 and must be corrected in both places.

**(ii) Product years are company founding years.** The draft labels the platforms *"Bear Robotics
Servi (USA, 2017), Pudu Bellabot (China, 2016), Keenon T-series (China, 2010)."* All three years are
**company founding dates**, not product launch dates. Servi was introduced in 2019, BellaBot debuted
in January 2019, and Keenon was founded in 2010 with the T-series released later. Either relabel the
parentheses as founding years of the manufacturer or substitute the correct product-launch years.

**(iii) Domino's date.** The draft states *"Domino's AI (USA, 2019)."* DOM launched as a voice
ordering application in 2014 (developed with Nuance Communications); AI handling of inbound phone
orders was announced in April 2018 and tested in 20 US stores. 2019 is not supported.

**(iv) Robot.He reinforces the argument.** Verification surfaced a detail that strengthens the
draft: at Robot.He, customers order by scanning a QR code and using the Hema app, and human staff
still greet, explain the system, take payment, and cook. This is direct evidence for the section's
thesis that the robot handles transport only and does not participate in ordering — worth one
sentence in the track-based paragraph.

### Structural notes

**(a) Four citations, three vendors.** `[2.1.1]`–`[2.1.4]` is cited as a range for three named
platforms. Either reduce the range to `[2.1.1]`–`[2.1.3]` or identify a genuine fourth source; a
comparative survey would carry more weight than a fourth vendor page.

**(b) Figure 2.1 permissions.** Figure 2.1 reproduces a photograph of the Robot.He installation.
Confirm the licence of the specific image file before submission and give the photographer/agency
credit in the caption if required. Press-agency imagery (Xinhua, Alamy) of this installation is
generally **not** freely reusable.

**(c) Citations attached to the author's own analysis.** `[2.1.7]` and `[2.1.14]` are attached to
analytical claims rather than to facts reported elsewhere — that commercial robots do not join the
ordering conversation, and that a chatbot cannot call a function or dispatch a robot. These are
conclusions the section draws from the evidence already cited. Attaching a citation to them invites
a reviewer to check a source that does not say what the sentence says. Consider removing both keys
and letting the preceding citations carry the evidence.

### Numbering

Section-scoped keys (`[2.1.x]`, `[2.2.x]`, …) are a drafting convenience that keeps each section
independently editable. On merge, flatten to a single sequential IEEE list ordered by **first
appearance in the text**, and update every in-text key. Do not flatten until all chapters are
drafted — inserting one reference into an early section otherwise renumbers everything after it.
