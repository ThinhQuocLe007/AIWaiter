from ai_waiter_core.services.retriever.fusion.rrf import RRFFusion

def get_fusion_strategy(mode: str):
    strategies = {
        "rrf": RRFFusion()
    }

    strategy = strategies.get(mode.lower())
    if not strategy:
        raise ValueError(f"Unknown fusion mode: {mode}. Supported: {list(strategies.keys())}")

    return strategy
