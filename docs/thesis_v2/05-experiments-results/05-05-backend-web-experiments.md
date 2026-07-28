## 5.5 Backend and Web Infrastructure Checks

The backend orchestrator and the three web interfaces are not evaluated as contributions. They exist so
the agent has somewhere to write and the restaurant has somewhere to read, and the question here is
narrower than the ones §5.4 answers: whether that infrastructure stays out of the way.

**API responsiveness.** All twelve endpoints were exercised with one hundred samples each against the live
orchestrator. Eleven answer within 4 ms at the 99th percentile, and write endpoints are as fast as read
endpoints, which is expected for SQLite at a working set of a few dozen rows. `POST /orders` is the
exception, at 0.7 ms at the median and 9.0 ms at the 99th, a tail thirteen times its typical case where
every other endpoint stays within a factor of two; the likely cause is SQLite's write lock serialising the
one endpoint on the critical path of order creation. The absolute figure is small, but it is the one place
in the backend where a queue can form. Read against the agent's median turn latency in §5.4.6, the backend
contributes roughly one twentieth of one percent of a conversational turn, so whatever limits this
system's responsiveness it is not the orchestrator.

**Fleet task lifecycle.** One full lifecycle was driven with a mock robot connected over WebSocket. The
robot moved through `offline`, `idle` on connect, `busy` on task creation, `returning` on `task_done` and
`idle` again on `at_dock`, while the task advanced from PENDING to ASSIGNED to DONE. The robot's status is
derived from the messages it sends rather than assumed from the task state, so a robot that accepts a task
and then goes quiet does not continue to appear busy. This is the only measurement in the chapter that
touches the coupling §2.2.5 identified as the central navigation gap, where a navigation goal originates
in a business event rather than in an operator's choice of waypoint. It establishes that such a goal
reaches the robot and that the round trip completes, and nothing about physical execution.

**Multi-role convergence.** Four roles observe the restaurant at once: the kiosk seats guests, the agent
creates orders, the panel monitors the floor, and the tablet shows one party its own order. Driving a
seating through the kiosk path and an order creation through the agent path, then querying each role's own
endpoint, every role reflects the change within a single request and response cycle. The table moves from
`TRONG` (free) to `DANG_PHUC_VU` (being served) once and is read by three different consumers from the
same records, so there is no synchronisation step between roles that could lag or fail.

Four further measurements were designed and not taken, and §5.6.3 records what they leave open.
