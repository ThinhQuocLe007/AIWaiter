## 4.8 Web Interfaces

> **Status:** draft
> **Cross-refs:** §4.3.2 for the deployment split, §4.4 for the voice pipeline, §4.7.3 for the WebSocket event stream, §4.7.4 for dispatch
> **Source:** `src/frontends/customer_ui/`, `kiosk/`, `panel/`, `shared/`
> **Figures:** Fig 4.20–4.26, produced by `scripts/thesis_screenshots.py` into `docs/thesis/images/ui/`. Figure numbers are provisional — renumber once Chapter 4's figures are settled.

---

Three web applications sit on top of the orchestrator, one for each role in the restaurant: the
screen a guest orders on, the kiosk that seats them, and the panel the staff work from. All three
are built with Vue and TypeScript and reach the backend the same way. They load their initial state
over REST and then receive every later change over the WebSocket described in §4.7.3. None of them
keeps important state of its own. The orchestrator is the single source, and each screen is a view
onto it, which is why two panels open side by side never disagree and why a screen that has been
closed all afternoon is correct the moment it opens.

The three share one small client library rather than three copies of the same code: the REST
wrapper, the WebSocket client with its reconnection logic, and the TypeScript types describing
every record and every event. The types are the part that matters most. A screen that reads a field
the backend no longer sends fails when the project is built rather than in front of a guest.

Their production builds are static files, which is what makes the deployment as simple as it is.
Nothing on a client device needs Node, a build step, or a development server; opening a URL is the
whole of it. The server builds all three and serves them from one origin — the ordering screen at
the root, the kiosk and the panel each under their own path — so every device in the restaurant is
a browser pointed at the same machine. That includes the robot: the Jetson runs no web tooling of
its own, it opens Chromium in kiosk mode at the server's address and displays what comes back
(§4.3.2). Being served from the same origin as the API is also what removes cross-origin
configuration from the deployment entirely.

The sections below say what each application is for. The screenshots carry the visual detail.

### 4.8.1 The Guest's Ordering Screen

The ordering screen runs on the touchscreen mounted on the robot, so a guest orders on the machine
that drove to their table rather than on a tablet left there. It is drawn for that display and no
other: the whole application is laid out on a fixed 1024×600 stage that is scaled to whatever
viewport it lands in, so the robot's screen is the design target and every other screen is a
rescaled copy of it. It is organised as a short sequence of screens: a welcome, a choice of what to
do, the menu, a confirmation, and payment.

Which screen a guest first sees is decided by the state of their table rather than by the guest. A
party that has just been seated and has ordered nothing gets the welcome screen (Fig 4.20). A table
already dining goes straight to the choice between ordering more and paying, because that is the
only thing a party in the middle of a meal wants from it. The screen asks the backend for its
table's state to make that decision, so it holds true after every return to the start, including
when a robot arrives at a table partway through a visit.

![Ordering screen — welcome](../images/ui/ordering-welcome.png)

**Figure 4.20:** The ordering screen on the robot's display, for a table that has been seated and
has not ordered yet.

From the menu the guest browses by category, opens a dish for its detail and photograph, changes
quantities, and places the order (Fig 4.21). What is placed is a list of dishes and quantities. The
amount is computed by the orchestrator from the stored prices, so a stale or tampered screen cannot
set what a party pays.

![Ordering screen — menu](../images/ui/ordering-menu.png)

**Figure 4.21:** Browsing the menu. Categories down the side, dishes with photographs and prices in
the body, search across the whole menu in the bar, and the cart carried in the corner.

The screen also mirrors the spoken conversation (Fig 4.22). As the guest talks, it shows what was
heard and the reply that came back, and it follows along when the agent opens the menu or the
payment page, so a guest who orders entirely by voice still sees the same screens move under them.
The cart on the screen and the cart the agent is building are held as one in both directions: a
dish added by voice appears in the cart, and a quantity changed by hand is pushed back into the
agent's state, so the next spoken turn does not overwrite it with a stale copy.

![Ordering screen — voice mirror](../images/ui/ordering-voice.png)

**Figure 4.22:** The conversation sheet. The guest's words and the agent's reply, with the dishes
the agent just added shown as cards the guest can also tap.

One boundary inside this screen is worth naming because it is easy to assume otherwise. The browser
never touches the microphone. The talk button signals the robot, and the recording, the
transcription, and the speech all happen in the voice pipeline on the same board (§4.4). The screen
is a viewer of the conversation, not a participant in it, which is why muting the robot or
cancelling a turn are requests sent to the robot rather than actions taken in the page.

The visit ends on the payment screen (Fig 4.23), which shows the session's running total — every
confirmed order, not just the last one — and a QR code to pay against. Confirming payment closes
the session at the orchestrator, which is what clears the cart and returns the screen to the start
for the next party.

![Ordering screen — payment](../images/ui/ordering-payment.png)

**Figure 4.23:** The payment screen: the session total computed by the orchestrator, with the QR
code and the confirmation the guest taps when they have paid.

### 4.8.2 Entrance Kiosk

The kiosk stands at the entrance, outside the dining area, and does a single job: booking a table. A
guest arriving at the restaurant uses it without waiting for anyone. It shows the tables as a grid
(Fig 4.24), each marked free, dining, or waiting to be cleared, with a count of how many are open.
The guest taps a free table, sets the party size against the table's capacity, and confirms
(Fig 4.25). That opens the session, marks the table as occupied, and sends a robot to meet the
party at it. A closing screen confirms the table is ready and tells the guest to order on the
screen at the table, then returns to the grid for the next arrival.

Two guests can reach for the same table at the same moment, and the kiosk is written for that: the
seating request is refused by the orchestrator if the table was taken in between, and the kiosk
says so and reloads the grid rather than pretending the booking succeeded.

![Kiosk — table grid](../images/ui/kiosk-grid.png)

**Figure 4.24:** The kiosk's table grid, with free tables tappable and occupied ones dimmed.

![Kiosk — party size](../images/ui/kiosk-seating.png)

**Figure 4.25:** Choosing the party size for the selected table, capped at that table's capacity.

### 4.8.3 Management Panel

The management panel is the staff view of the whole floor, carried rather than mounted so it can be
read anywhere in the restaurant, and it has four parts on one screen (Fig 4.26).

The table overview lists each table with its party size, how long since it was seated, its running
total, and where its order stands with the kitchen. Two actions sit beside each row: call a robot to
the table, and close out a table that has paid, which frees it and clears any work still queued for
it.

The kitchen board is the display the kitchen works from. Orders appear as cards in three columns,
waiting, cooking, and done, and a card is moved along as the food progresses. What the board
carries is the kitchen's own progress, not a dispatch: the robot takes the order and brings the
guest to the point of ordering, while the staff carry the dishes out, so marking a card done
publishes the change to every panel and nothing else (§4.7.4). The two moments that do put a robot
on the road are a party being seated at the kiosk and a guest pressing the call button at their
table.

The robot board shows each robot with what it is doing right now, described in the words the staff
would use rather than in states from the database: on its way to table three, serving table one,
returning to the dock, or disconnected. A robot that has never connected since the system started is
shown as such rather than as idle, so nobody sends work to a machine that is switched off.

The minimap draws the robots on the restaurant's actual SLAM map and moves them as they travel. It
is the point where the web layer meets the navigation layer with nothing in between: the backdrop is
the same map the robot localises against in Chapter 3, and the positions on it come straight from
the robots' telemetry, projected into the map frame the robot itself uses. It sits as a small
draggable overlay above the rest of the panel, so the manager can put it wherever it does not cover
what they are reading.

A connection indicator in the header reports whether the panel's own WebSocket is live. It is a
small thing, but it is the difference between a quiet floor and a screen that has silently stopped
updating, and on a screen that is watched rather than clicked, that distinction is worth showing.

![Management panel](../images/ui/panel-overview.png)

**Figure 4.26:** The management panel during service: table overview, robot board, the kitchen's
three columns, and the minimap floating over them with the robots on the SLAM map.

### 4.8.4 Reproducing the Figures

The screenshots above are captured from the running system rather than mocked up. The server builds
and serves the three applications (`make build`, `make backend`), a robot client is attached so the
robot board and the minimap have something to draw (`make mockrobot`, or a real robot), and
`scripts/thesis_screenshots.py --seed` stages a service — three parties seated, one order in each
kitchen column, one spoken turn mirrored to the table — then drives a headless browser through the
screens and writes the figures into `docs/thesis/images/ui/`. Running it without `--seed` captures
whatever the system is actually doing at that moment.
