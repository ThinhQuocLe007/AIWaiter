"""AI Waiter — LLM brain (LangGraph + RAG).

Runs on the **central server**. Hosts the LangGraph agent graph, hybrid RAG
retrieval (BM25 + vector + RRF), tools, conversation memory, and the agent
HTTP service (``POST /chat``).

Lives alongside the edge voice device in ``src/edge_voice/`` and the
orchestrator backend in ``src/server_orchestrator/``; the brain reaches
the orchestrator over HTTP only — no direct DB access.
"""
