from src.agent_brain.services.retriever.fusion.rrf import RRFFusion
from src.agent_brain.services.retriever.fusion.weighted_score import LinearScoreFusion


def get_fusion_strategy(mode: str):
    strategies = {
        "rrf": RRFFusion(),
        "linear": LinearScoreFusion(),
    }

    strategy = strategies.get(mode.lower())
    if not strategy:
        raise ValueError(f"Unknown fusion mode: {mode}. Supported: {list(strategies.keys())}")

    return strategy
