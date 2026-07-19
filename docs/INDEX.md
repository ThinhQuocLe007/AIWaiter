# Docs Index

> Quick reference to find any document in the `docs/` folder.

---

## Architecture

| File | Description |
|------|-------------|
| [`architecture/system-design.md`](architecture/system-design.md) | Product design, deployment model (3 laptops, Netbird), business flows, API design (Vietnamese) |
| [`architecture/code-architecture.md`](architecture/code-architecture.md) | Code-level architecture: component map, ERD, session lifecycle, agent seam, dispatch, file map |
| [`architecture/agent-brain-analysis.md`](architecture/agent-brain-analysis.md) | Deep-dive into the LangGraph agent: nodes, edges, data flow, design critique |
| [`architecture/voice-web-button-summary.md`](architecture/voice-web-button-summary.md) | Design summary for voice pipeline, web interfaces, and call button |
| [`architecture/memory_design.md`](architecture/memory_design.md) *(symlink → `../../memory_design.md`)* | Per-agent context report: what each worker sees, memory lifecycle, token budgets |

## Guides

| File | Description |
|------|-------------|
| [`guides/run-guide-vi.md`](guides/run-guide-vi.md) | Setup & run instructions (Vietnamese) |
| [`guides/run-voice-vi.md`](guides/run-voice-vi.md) | Voice pipeline setup guide (Vietnamese) |
| [`guides/setup-deploy.md`](guides/setup-deploy.md) | Deployment configuration, CUDA extras, environment setup |
| [`guides/makefile-reference.md`](guides/makefile-reference.md) | Complete Makefile target reference |
| [`guides/jetson-ctranslate2-build.md`](guides/jetson-ctranslate2-build.md) | Building ctranslate2 on Jetson |

## Evaluation

| File | Description |
|------|-------------|
| [`evaluation/eval-baseline-2026-07.md`](evaluation/eval-baseline-2026-07.md) | Evaluation baseline: router (95.56%), retrieval, prompt versions |
| [`evaluation/evaluation-llm.md`](evaluation/evaluation-llm.md) | LLM evaluation details |
| [`evaluation/analysis/`](evaluation/analysis/) | Architecture Decision Records (ADR 0001–0006) tracking system evolution |

## AI Engineering

| File | Description |
|------|-------------|
| [`ai-engineering/ai-engineer-guide.md`](ai-engineering/ai-engineer-guide.md) | Mindset shift from software engineer to AI engineer; learning paths |
| [`ai-engineering/agent-bug-investigation-guide.md`](ai-engineering/agent-bug-investigation-guide.md) | Systematic LLM agent bug investigation methodology |

## Progress

| File | Description |
|------|-------------|
| [`progress/progress.md`](progress/progress.md) | Implementation progress, what's done, what's next, run commands |

## Logs

| Directory | Description |
|-----------|-------------|
| [`logs/`](logs/) | Daily development logs (2026-05 → 2026-06) |

## Problem Reports

| File | Description |
|------|-------------|
| [`problem/0006-semantic-router-dataset-problems.md`](problem/0006-semantic-router-dataset-problems.md) | Semantic router dataset issues and fixes |

## Thesis

| Directory | Description |
|-----------|-------------|
| [`thesis/`](thesis/README.md) | Thesis report organized by chapter (Ch.1–6 + appendices) |

## External References

| Location | Description |
|----------|-------------|
| [`writing/outline.md`](../writing/outline.md) | Full thesis outline (529 lines) |
| [`writing/thesis-writing.md`](../writing/thesis-writing.md) | Thesis writing guide with section-by-section instructions |
| [`writing/diagram.md`](../writing/diagram.md) | PlantUML diagrams for thesis (architecture, state graph, router, RAG, etc.) |
| [`writing/CHAPTER_2_THEORETICAL_BACKGROUND.docx`](../writing/CHAPTER_2_THEORETICAL_BACKGROUND.docx) | Chapter 2 draft (DOCX) |
| [`memory_design.md`](../memory_design.md) | Per-agent context report (original, symlinked in architecture/) |
