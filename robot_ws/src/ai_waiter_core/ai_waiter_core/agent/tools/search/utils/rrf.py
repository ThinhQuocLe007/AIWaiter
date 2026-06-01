def compute_reciprocal_rank(rank: int, k: int = 60) -> float:
    """
    Computes the Reciprocal Rank Fusion (RRF) score for a given rank.
    RRF score = 1 / (k + rank)
    
    Args:
        rank (int): 1-indexed ranking position of the document.
        k (int): Smoothing constant, commonly set to 60.
        
    Returns:
        float: RRF fused score component.
    """
    # Defensive programming: ensure rank is strictly positive
    rank = max(1, rank)
    return 1.0 / (k + rank)
