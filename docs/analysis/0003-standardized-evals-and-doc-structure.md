# ADR 0003: Standardized Evals & Doc Structure

## Context
Project documentation and evaluation results were becoming fragmented and difficult to version-control alongside code.

## Decision
1.  **Refactored `evals/`**: Grouped results by dataset version (`eval_dataset_v1/`) and added Markdown reports with Mermaid diagrams.
2.  **Repurposed `docs/`**: Converted the `docs/` folder into an ADR-only repository to track architectural history.
3.  **Knowledge Hub Integration**: Moved all static technical deep-dives and research to a centralized "Second Brain" (`KNOWLEDGE_HUB`).

## Consequences
- **Pros**: Project repository is now "lean"; architectural history is clearly visible; research is centralized.
- **Cons**: Documentation is split between two locations (Repo vs Hub).

## References
- [Refactor Walkthrough](file:///home/lequocthinh/.gemini/antigravity/brain/39640887-66d2-4710-a0c0-60c35c71e602/walkthrough.md)
