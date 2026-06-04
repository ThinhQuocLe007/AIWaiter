import math
from typing import List
from ai_waiter_core.utils import logger

def sigmoid_normalize(score: float, mean: float = 0.0, scale: float = 1.0) -> float:
    try: 
        exponent = -scale * (score - mean)
        exponent = max(min(exponent, 500), -500)
        
        sigmoid = 1.0 / (1.0 + math.exp(exponent))
        return sigmoid
    except Exception as e:
        logger.error(f'sigmoid_normalize: {e}')
        return 0.5

def calculate_hybrid_score(bm25_score: float, vector_score: float, 
                        bm25_mean: float = 0.0, bm25_scale: float = 1.0,
                        bm25_weight: float = 0.6, vector_weight: float = 0.4) -> float:
    try: 
        bm25_score_normalization = sigmoid_normalize(bm25_score, bm25_mean, bm25_scale)
        hybrid_score = (bm25_score_normalization * bm25_weight) + (vector_score * vector_weight)
        return hybrid_score
    except Exception as e:
        logger.error(f'calculate_hybrid_score: {e}')
        return 0.0

def normalize_vector_score(distance: float) -> float:
    return 1.0 / (1.0 + distance)

def normalize_bm25_batch(scores: List[float]) -> List[float]:
    if not scores: return []
    mean = sum(scores) / len(scores)
    return [sigmoid_normalize(s, mean) for s in scores]
