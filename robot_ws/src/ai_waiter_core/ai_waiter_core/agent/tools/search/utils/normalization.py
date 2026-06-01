import math
from typing import List
from ai_waiter_core.utils import logger

def sigmoid_normalize(score: float, mean: float = 0.0, scale: float = 1.0) -> float:
    """
    Normalize BM25 score to 0-1 range using sigmoid function
    
    Args:
        score: BM25 score to normalize
        mean: Mean/center point of the sigmoid (shifts the curve)
        scale: Steepness of the sigmoid curve (default 1.0)
    
    Returns:
        Normalized score in 0-1 range
    """
    try: 
        # Clamp exponent to prevent overflow
        exponent = -scale * (score - mean)
        exponent = max(min(exponent, 500), -500)  # Prevent overflow/underflow
        
        sigmoid = 1.0 / (1.0 + math.exp(exponent))
        return sigmoid
    except Exception as e:
        logger.error(f'sigmoid_normalize: {e}')
        return 0.5

def calculate_hybrid_score(bm25_score: float, vector_score: float, 
                        bm25_mean: float = 0.0, bm25_scale: float = 1.0,
                        bm25_weight: float = 0.6, vector_weight: float = 0.4) -> float:
    """
    Calculate the hybrid score using the formula: 
    hybrid_score = (bm25_score_normalization * bm25_weight) + (vector_score * vector_weight)
    
    Args:
        bm25_score: BM25 score to normalize
        vector_score: Vector score 
        bm25_weight: Weight for BM25 score (default 0.6)
        vector_weight: Weight for vector score (default 0.4)
    
    Returns:
        Hybrid score in 0-1 range
    """
    try: 
        bm25_score_normalization = sigmoid_normalize(bm25_score, bm25_mean, bm25_scale)
        hybrid_score = (bm25_score_normalization * bm25_weight) + (vector_score * vector_weight)
        return hybrid_score
    except Exception as e:
        logger.error(f'calculate_hybrid_score: {e}')
        return 0.0

def normalize_vector_score(distance: float) -> float:
    """
    Normalize vector score to 0-1 range using sigmoid function
    
    Args:
        distance: Vector distance to normalize
    
    Returns:
        Normalized vector score in 0-1 range
    """
    return 1.0 / (1.0 + distance)

def normalize_bm25_batch(scores: List[float]) -> List[float]:
    """ Takes a list of raw BM25 scores and returns them all normalized by Sigmoid """
    if not scores: return []
    mean = sum(scores) / len(scores)
    return [sigmoid_normalize(s, mean) for s in scores]
