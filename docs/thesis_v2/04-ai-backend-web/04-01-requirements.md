## 4.1 AI System Requirements

Chapter 1 set the objective of an autonomous waiter that takes spoken Vietnamese orders,
understands them through a conversational agent, sends them to the kitchen, and delivers
the food to the correct table. Chapter 3 delivered a robot that can navigate autonomously
and dock at tables, but it does not yet understand what a customer says, decide what to
do about it, or know where to go. To close that gap, the system described in this chapter
must:

- **Capture, transcribe, and synthesize Vietnamese speech entirely on the robot**, running
  VAD, STT, and TTS on the Jetson while the LLM runs on a central server. Only text
  transcripts cross the network. The speech pipeline must handle tonal diacritics,
  compound words, and restaurant background noise.

- **Understand informal spoken Vietnamese and map it to the correct action.** The agent
  must classify utterances into ordering, searching, paying, or chatting (handling teencode
  abbreviations, context-dependent short affirmations, and multi-intent turns), then decide
  which tool to invoke and keep the cart consistent when the customer switches between voice
  and touch on the tablet.

- **Let customers find dishes by taste, dietary type, price, or occasion**, not only by
  dish name. The retrieval pipeline must bridge the gap between experiential language
  ("trời lạnh ăn gì ấm bụng") and a menu organized by name and category. When no dish
  matches, it must return nothing rather than fabricate.

- **Push every business event to the right screen in real time.** A confirmed order must
  appear on the kitchen board instantly. A robot's position must update live on the
  minimap. The session lifecycle (seating, orders, payment, table release) must be
  enforced across all components, with six tables served concurrently in strict isolation.

- **Dispatch the right robot to the right table at the right time.** The fleet manager
  must assign each navigation task to the nearest idle robot with sufficient battery, track
  position and battery from live telemetry, bind a table's voice channel to whichever robot
  is physically there, and recover transparently when a robot disconnects, requeueing its
  tasks without the customer noticing.

- **Provide three role-specific web interfaces**: a customer tablet for menu browsing
  and voice mirroring, an entrance kiosk for check-in, and a management panel with a
  kitchen order board, fleet status, and live minimap. All three share a common TypeScript
  client and receive updates through WebSocket push rather than polling.

- **Run entirely on the restaurant's own hardware** with no cloud dependency in normal
  operation. Voice interaction must stay under five seconds from end of speech to start
  of reply. Every LLM decision must pass through a deterministic safety gate before
  affecting state. Conversation state must clear completely when a session ends, and no
  single component failure may bring down the system.
