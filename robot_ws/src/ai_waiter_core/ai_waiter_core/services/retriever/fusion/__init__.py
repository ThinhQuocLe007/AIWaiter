from ai_waiter_core.services.retriever.fusion.rrf import RRFFusion
from ai_waiter_core.services.retriever.fusion.weighted import WeightedFusion
from ai_waiter_core.services.retriever.fusion.base import BaseFusion

def get_fusion_strategy(mode: str) -> BaseFusion:
    strategies = {
        "rrf": RRFFusion(),
        "weighted": WeightedFusion()
    }
    
    strategy = strategies.get(mode.lower())
    if not strategy:
        raise ValueError(f"Unknown fusion mode: {mode}. Supported: {list(strategies.keys())}")
        
    return strategy
