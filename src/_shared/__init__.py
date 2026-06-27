"""Cross-role shared utilities.

The ``_shared`` package is the one place code from any role can import
without creating a circular dependency between the three role-specific
packages:

  - src.agent_brain/   (server: LLM brain + RAG)
  - src.edge_voice/    (Jetson: voice device)
  - src.server_orchestrator/  (server: FastAPI backend)

Today this package is small by design — it only exposes path constants
and the cross-role type vocabulary (status enums + table-id normalisation).
If you find yourself reaching for ``_shared`` from more than two roles,
that's the signal to promote something here.
"""
