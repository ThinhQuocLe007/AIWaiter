## 4.3 Software System Architecture

A restaurant runs as a loop: a guest is seated, orders, waits, is served, and pays. The
software in this chapter runs that loop with the customer speaking to the robot instead of to
a waiter, and its pieces do not all live in the same place.

The system runs on two computers and three browser apps. The robot carries an NVIDIA Jetson.
A central desktop server carries an x86 processor and one graphics card. The staff and
customers use three web apps: a tablet at each table, a kiosk at the entrance, and a
management panel in the kitchen. Everything talks over the restaurant's own WiFi, so the
system keeps working when the internet is down. Figure 4.1 shows the whole layout.

![Figure 4.1. System Architecture Overview](../images/Figure1.svg)

*Figure 4.1. System Architecture Overview: the three-tier layout (server, robot, staff
browsers) and the type of connection on each link. The inside of the agent and the search
index is left to later sections. (drawn by the group)*

### 4.3.1 Topology and Responsibilities

The work of the system divides into two kinds, and that divide decides what runs where. Some
work is bound to the robot's body and its senses, and it has to run on the robot. Other work
is bound to thought and to shared records, and it belongs on the server.

On the robot runs everything tied to its own hardware: reading the sensors and fusing them
into an estimate of where the robot is, holding the map, planning and following a path, and
recording and playing sound. Three things force this onto the robot, and none is about memory.
Each part is wired to a device that sits on the robot, the motors, the sensors, the microphone,
and the speaker. Driving the wheels and holding a position is a real-time loop that reads a
sensor and corrects the motors many times a second, and sending that loop out over WiFi and
back would add a delay that breaks it. And the raw data is heavy, a steady stream of camera
frames, laser scans, and audio, so it is cheaper to reduce it to a small result on the robot
than to ship it across the network.

On the server runs everything that is not tied to one robot's body: the language model and the
agent that reasons over the customer's request, the business records, and the menu with its
search. None of these belongs to a particular robot. They are common to every table and every
robot in the restaurant, so they live once, in one place, where they stay consistent. Table 4.1
sets out the whole division and the reason for each side.

*Table 4.1. Where each job runs, and the constraint that fixes its place.*

| Job | Runs on | Why it must be there |
|-----|---------|----------------------|
| Motor control and wheel odometry | Robot | Wired to the motors; needs real-time timing next to them |
| Sensing and localization (LiDAR, camera, IMU, map) | Robot | The sensors are on the robot; the raw data is heavy and reduced locally |
| Navigation, path planning, and obstacle avoidance | Robot | Closes a real-time loop with the sensors and motors |
| Voice capture and playback | Robot | The microphone and speaker are on the robot; keeps audio off the network |
| Language model and agent | Server | Too large for the robot's memory, and tied to no robot's body |
| Business records (tables, sessions, orders, payments) | Server | Shared state; one source of truth for every table and robot |
| Menu and its search | Server | Shared, updated in one place, used by every robot |

One job in the table could, in principle, run on either side: the language model. It is wired
to no sensor and closes no control loop, so nothing about the robot's hardware pins it in
place, and it would even be simpler to keep it on the robot, since then the request would
never leave the machine. What rules this out is memory, and the robot does not start empty. Before this chapter adds
anything, it already runs the navigation and localization built in Chapter 3, and that
software holds part of the 8 GB. Table 4.2 breaks down where the board's memory goes.

*Table 4.2. What the robot's 8 GB is already committed to before a language model is
considered. Figures are resident memory, not weights on disk.*

| Component | Approx. memory |
|-----------|---------------:|
| ROS 2 core and DDS middleware | ~0.2 GB |
| Sensor drivers (LiDAR, depth camera, IMU) | ~0.5 GB |
| Localization on the prebuilt map (RTAB-Map) | ~2.0 GB |
| Navigation (Nav2 planners, costmaps, behaviour trees) | ~0.7 GB |
| Odometry fusion (EKF) and ArUco docking | ~0.3 GB |
| **Navigation and localization together** | **~3.7 GB** |
| Voice pipeline (speech recognition, voice detection, speech synthesis) | ~3.7 GB |
| **Committed in total** | **~7.4 GB** |
| **Left of the 8 GB** | **~0.6 GB** |

The robot has to hear and speak on its own, so the voice pipeline claims nearly all of what
navigation and localization leave. A language model would have to fit into the ~0.6 GB that
remains, not into the whole 8 GB.

Table 4.3 shows what one would cost. The figures are the weights alone, obtained from the
parameter count and the number of bits each parameter is stored in; the memory a running model
holds is larger, because the attention cache for the conversation and the inference runtime sit
on top. Based on the survey of language models in Section 2.4.3 of Chapter 2, the smallest
class is the only one that would fit the free space on any reading, and it is also the class
that stops following a tool-calling protocol reliably across a multi-turn order.

*Table 4.3. Weights held by a language model, by size class and stored precision.*

| Model class | Weights at 4 bits | Weights at 6 bits | Follows a tool protocol over several turns |
|-------------|------------------:|------------------:|--------------------------------------------|
| 1 to 3 billion | ~0.8 to 1.7 GB | ~1.1 to 2.4 GB | Unreliable |
| 7 to 8 billion | ~4.0 to 4.5 GB | ~5.6 to 6.4 GB | Reliable |
| 13 to 14 billion | ~7.3 to 8.0 GB | ~10.4 to 11.5 GB | Reliable |

Even the smallest usable class needs several times the 0.6 GB that remains, and a model
compressed hard enough to fit would lose the accuracy the agent depends on. The free space is
not truly spare either: it is the headroom the navigation stack needs at its peak, when
costmaps rebuild or the localizer closes a loop, and a model that claimed it would starve the
work that must never stall. So the language model runs on the server, where it has room to be
as capable as the task needs.

Three more reasons support the same choice, and none of them depends on memory:

- **Speed.** Only small messages cross the WiFi, a line of text or a set of coordinates, never
  audio or video. A transcript is about a hundred bytes where the raw audio it replaces is
  about a hundred kilobytes, so the network step is tiny and adds almost no delay.
- **Safety of the data.** The robot stands out on the floor, where it can be knocked, damaged,
  or taken, so nothing lasting is kept on it. Every order, payment, session, and conversation
  lives on the server, and a robot that is lost or switched off carries no customer data with
  it and can be replaced at once.
- **Consistency across the fleet.** One model on one server serves every robot the same way,
  so their behaviour does not drift apart, and an improvement is installed once on the server
  rather than on each robot in turn.

The memory limit and these three reasons point the same way; a larger board would ease only the
first of them.

The server itself runs two programs. The agent turns a Vietnamese sentence into a checked
action, calling a language model that is served on the same machine by Ollama, which keeps the
model loaded in the graphics card so no request waits for it to start. The orchestrator keeps
the business consistent: it answers the web apps, pushes live updates to every screen, hands
delivery jobs to robots, and stores the tables, sessions, orders, and payments. Two small
databases sit behind it, one for the business records and one for the conversation history,
each a single file that needs no separate database server.

The two programs run as separate processes on purpose. The agent is slow: one reasoning step
takes seconds, and it stops while it runs. The orchestrator's own work, reading records and
updating screens, takes milliseconds. Keeping them apart means a slow reasoning step never
freezes the kitchen screen, and either program can be restarted without bringing down the
other. They pass messages to each other inside the one machine, which costs almost nothing.

### 4.3.2 Messages Between Components

The three web apps share one small library of communication and data code, so they always
agree with the server on formats. Two kinds of message travel between the apps and the server.
Commands and first page loads, such as placing an order or seating a party, use an ordinary
request-and-reply call: the app asks, the server answers. Live changes, such as a new order
appearing or a robot moving, are pushed the other way: the server sends them to the screens
that care, the moment they happen, instead of the screen asking again and again. Pushing is
what makes the system feel live. The kitchen sees an order the moment it is confirmed, and the
manager watches the robots move without refreshing. The robot keeps two open connections to
the server: one carries the command to start and stop listening, the other carries navigation
jobs out and position and battery reports back.

Two example flows show the whole system working together. The first is a spoken order. The
second is a delivery.

Figure 4.2 follows a spoken order, from the tablet's "Talk to AI" button through the robot's
microphone and transcription (about 800 ms) to the agent, and back one sentence at a time so
the robot can begin speaking before the reply is finished. Three things are worth noticing.
The recording, the transcription, and the speaking all happen on the robot, so no audio ever
crosses the WiFi. The check on the action sits between the model and the cart, so nothing
reaches the cart unchecked. The tablet only shows the conversation; it never controls the
microphone.

![Figure 4.2. Voice Ordering Sequence](../images/Figure7.svg)

*Figure 4.2. Voice Ordering Sequence: a spoken order travelling from the tablet, through the
server and the robot's voice pipeline, to the agent and back to the speaker. Recording,
transcription, and speech all happen on the robot; only text crosses the WiFi. (drawn by the
group)*

Figure 4.3 follows a delivery. A confirmed order is saved and pushed to the kitchen board,
where the staff move the card from Chờ Bếp (waiting) to Đang Làm (cooking) to Xong (done). Once
it is done, the server creates a delivery job, hands it to the nearest free robot with enough
battery, and links the table's voice to that robot on arrival, releasing both when the delivery
finishes. The path from the agent's decision to the robot's wheels runs entirely on pushed
events; nothing polls, and no person carries the order from screen to screen.

![Figure 4.3. Order-to-Delivery Sequence](../images/Figure11a.svg)

*Figure 4.3. Order-to-Delivery Sequence: one AI decision (confirm order) travelling through
the kitchen board, the delivery dispatcher, and the robot's navigation to a real delivery.
(drawn by the group)*

Each connection uses the kind of message that fits it, listed in Table 4.4. Commands and page
loads go over HTTP, where a reply is expected. Live updates are pushed over WebSocket. The one
two-way WebSocket to each robot carries jobs out and reports back on a single open connection.

*Table 4.4. Type of connection on each link, and why.*

| Link | Connection | Why |
|------|-----------|-----|
| Agent to language model | HTTP, same machine | Native protocol, no network, almost no delay |
| Agent and orchestrator | HTTP, same machine | Ask-and-answer for actions, fire-and-forget for voice events |
| Voice device to agent | HTTP request | Send the text, get the reply back; holds no state |
| Orchestrator to web apps | WebSocket | Live push; asking again and again would add 5–10 s of lag |
| Orchestrator and robot | WebSocket | Two-way: jobs out, position and status in, one open connection |
| Web apps to orchestrator | HTTP request | Create, read, update, and delete map cleanly onto HTTP |
