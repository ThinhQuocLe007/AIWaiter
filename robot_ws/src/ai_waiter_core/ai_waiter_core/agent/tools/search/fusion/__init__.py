from .rrf import RRFFusion
from .weighted import WeightedFusion
from .base import BaseFusion

def get_fusion_strategy(mode: str) -> BaseFusion:
    """
    Factory to return the selected search fusion strategy.
    """
    strategies = {
        "rrf": RRFFusion(),
        "weighted": WeightedFusion()
    }
    
    strategy = strategies.get(mode.lower())
    if not strategy:
        raise ValueError(f"Unknown fusion mode: {mode}. Supported: {list(strategies.keys())}")
        
    return strategy
