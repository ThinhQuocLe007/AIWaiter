# 2.8 Web, Backend and Deployment Technologies

### 2.8.1 Vue.js and Vite

Vue.js is a progressive, open-source JavaScript framework for building user interfaces, based on the component model: an interface is composed of small, self-contained components, each bundling its own template, logic, and styling in a single file. Interfaces built with Vue are typically single-page applications (SPAs): the browser loads the application once and thereafter updates the view dynamically in response to data, instead of requesting a new page from the server for every action. The main characteristics of Vue are:

Reactivity: the view is bound declaratively to the application data, so when the data changes (for example, an order status is updated), the affected parts of the screen re-render automatically without manual DOM manipulation.

Component-based structure: screens are assembled from reusable components (a menu card, a cart panel, a table tile), which keeps the code of the three different interfaces in this system consistent and maintainable.

TypeScript support: components can be written in TypeScript, catching type errors at build time rather than at run time.

Lightweight and approachable: Vue has a small runtime and a gentle learning curve compared with heavier frameworks, while still providing an official router and state-management ecosystem.

The Vue applications are built and served by Vite, a modern front-end build tool that provides a very fast development server with hot-module replacement (changed components are swapped into the running page without a full reload) and produces optimized, minified bundles for production. In this system, all three user-facing interfaces the customer tablet UI, the check-in kiosk, and the staff management panel are Vue single-page applications built with Vite, a model well suited to a real-time ordering interface whose screen must react continuously to events (an order confirmed, the robot arriving) without page reloads.

> Figure 2.18 — Component-based structure of a Vue single-page application: a tree of reusable components bound reactively to shared application data (drawn by the group).

### 2.8.2 FastAPI

FastAPI is a modern, high-performance web framework for building APIs in Python, built on the ASGI (Asynchronous Server Gateway Interface) standard and on Python type hints. It is particularly well suited to applications that integrate AI components, thanks to the following characteristics:

High performance: its asynchronous foundation lets a single server process handle many simultaneous connections efficiently. Important when several tables, a kitchen display, and the robot are all connected at once with throughput comparable to Node.js frameworks and well above traditional synchronous Python frameworks.

Automatic validation from type hints: request and response bodies are declared as typed Pydantic models, and FastAPI validates every incoming request against them automatically, so malformed data is rejected before it reaches the application logic.

Automatic interactive documentation: an OpenAPI specification and a Swagger UI test page are generated from the code itself, which makes the API easy to explore and test during development without writing any additional documentation.

Async/await support: long-running operations such as calling the LLM agent service or waiting on the database do not block other requests.

### 2.8.3 RESTful API

For ordinary request-response interactions, the backend exposes a REST (Representational State Transfer) interface over HTTP. In the REST style, each piece of data is a resource addressed by a URL (for example, /orders or /tables/3), and the standard HTTP methods express the operation performed on it:

GET: read a resource (fetch the menu, query a table's status);

POST: create a new resource (place an order, register a payment);

PATCH/PUT: modify an existing resource (update an order's status);

DELETE: remove a resource.

REST is stateless: every request carries all the information needed to process it, and the server keeps no per-client conversation state between requests. This keeps the server simple, makes the API easy to test with standard tools, and allows any client - a browser, the robot's voice device, or a test script - to use the same interface.

### 2.8.4 WebSocket

REST is a poor fit for information that must be pushed to clients the moment it changes, because an HTTP client can only ask; it cannot be notified. Covering live updates with REST would require each client to poll the server repeatedly, wasting bandwidth and adding delay. The WebSocket protocol solves this: an ordinary HTTP connection is upgraded once into a persistent, full-duplex channel over which both sides can send messages at any time, with very low overhead per message. Typical uses in this system are:

Pushing order-status changes to the kitchen display and the customer's tablet the moment they occur.

Streaming the robot's live position to the management panel's mini-map.

Delivering service events (a customer pressing the "talk to the AI" button, a robot task assignment) to the devices concerned.

> Figure 2.19 — HTTP request–response with polling versus a persistent WebSocket connection with server push (drawn by the group, adapted from [n]).

### 2.8.5 SQLite

SQLite is a lightweight relational database engine used to store the system's persistent data (tables, sessions, orders, payments, robot and task records). Unlike client–server databases such as MySQL or PostgreSQL, SQLite is embedded: the entire database is a single ordinary file read and written directly by the application process, with no separate database server to install, configure, or maintain. Its key characteristics are:

Serverless and zero-configuration: the database is created simply by opening a file, which removes an entire operational component from the deployment;

Full SQL support: standard relational queries, joins, and indexes are available;

ACID transactions: concurrent writes are serialized safely, so records such as orders and payments cannot be left half-written;

Portability: the database file can be copied, backed up, and inspected with standard tools.

For a single-server deployment with a moderate request volume - one restaurant with a handful of tables - these properties make SQLite a better operational fit than a full client–server database, whose main advantages (many concurrent writers, distributed access) are not needed here.

### 2.8.6 Ollama

Ollama is an open-source runtime for serving large language models locally. It downloads open-weight models in quantized form, hosts them behind a simple local HTTP API, and keeps loaded models resident in memory and on the GPU so that consecutive requests do not pay a reload cost. Its main characteristics are:

Simple model management: models are pulled, versioned, and swapped by name, so different models can be assigned to different roles (routing, generation) without code changes;

Quantized inference: reduced-precision weights let multi-billion-parameter models run on a single consumer GPU;

Persistent loading (keep-alive): models stay warm in memory between requests, keeping per-request latency low;

A single local API for multiple models, which the application calls exactly as it would call a cloud LLM provider.

Serving the language models on the organization's own hardware - rather than calling a third-party cloud API - keeps customer conversations on-premises, removes per-request cloud costs, and avoids dependence on an external service's availability, all of which matter for restaurant deployment.

