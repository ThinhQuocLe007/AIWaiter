# ABSTRACT

**Smart Restaurant Assistant: Leveraging Large Language Models for Dining Interaction and Autonomous Delivery**

Restaurant service automation has advanced along two lines that do not meet. Service robots navigate autonomously but do not interact, and conversational systems understand an order but cannot act on the physical world. A restaurant wanting both runs two systems with a member of staff between them.

This thesis presents an autonomous waiter that joins them. A customer speaks Vietnamese to a robot; a conversational agent turns the utterance into checked actions on live restaurant records; the kitchen display updates as the order is placed; and the robot navigates to the correct table and docks against a fiducial marker. Every component runs on the restaurant's own hardware with no cloud dependency.

The central design decision is that the language model proposes and deterministic code disposes. A trained classifier routes each utterance in 9.0 ms at 92.9 % accuracy on 225 held-out utterances, matching a 14-billion-parameter model prompted for the same task at a twenty-fourth of its latency. A rule-based validator inspects every tool argument against the menu before execution: with the validator bypassed, 32 dishes the kitchen cannot cook reached the cart across 41 scenarios; with it enabled, none did, in any run. The deterministic layers wrote nothing incorrect in 35 end-to-end runs, of which 29 completed a full ordering conversation. Median turn latency is 1.61 s. On the robot, graph SLAM with marker landmarks bounds pose error, and last-meter visual alignment reduces docking error from 47.8 cm to 1.6 cm at a cost of 1.1 s per run.

Where the system still fails, it fails in the language model's judgement rather than in the layers built to contain it.

