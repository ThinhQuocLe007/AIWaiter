## 4.2 Design Challenges

The requirements of §4.1 are each familiar on their own, but meeting them together, in Vietnamese, on modest on-premises hardware, and with no human in the loop, raises six difficulties that shape the rest of this chapter. Each is stated here as the problem to be solved; the sections that follow present the design that answers it.

- Informal Vietnamese is hard to classify reliably. Customers speak in abbreviations and slang, reuse the same short word for different intents depending on the context, combine several requests in a single turn, and name dishes the model has rarely seen. No single classification approach handles all of these at once, yet the routing must still be accurate, fast enough to add no perceptible delay, and deterministic.

- Memory on the robot is a fixed budget shared by everything. The robot's onboard computer has 8 GB of memory shared between navigation, the sensors, and the voice pipeline, which together leave too little for a capable language model. The model must therefore run elsewhere, and the work must be divided between the robot and a server without letting the network round trip erode the voice response time.

- The language model is a probabilistic component inside a system that must behave deterministically. It can invent dish names, produce impossible quantities, or attempt invalid steps in the ordering sequence. Such errors cannot be prevented outright without fine-tuning, so the system must instead detect and block them before they reach the cart, the kitchen, or payment, on every call and with no human review.

- The way customers describe food does not match how the menu is stored. Customers ask by taste, sensation, or occasion, whereas the menu is organised by name, category, and price, so a query and the dish that answers it may share no words at all. Retrieval must actively bridge this gap, reshaping the query before the search and interpreting the results after it.

- The backend is a shared state machine driven by the AI rather than by staff. Several client roles each need a different, live view of the same events as the agent creates orders, updates carts, dispatches robots, and settles payments. Polling is too slow for time-critical events such as a new order reaching the kitchen board, and a cloud dependency fails when the local network drops, so the whole backend must run on one on-premises machine and push changes as they happen.

- The link between a robot and the table it serves must survive disconnection. When a robot reaches a table, that table's voice commands are routed to that particular robot; if the robot loses its connection mid-visit, the system must release the link, hand the task to another robot, and rebind the new one, all without the customer noticing that the robot behind the voice has changed.
