from __future__ import annotations

import numpy as np

ORDER_STAGES = ["IDLE", "BUILDING", "AWAITING_CONFIRMATION", "CONFIRMED", "MODIFYING"]
STAGE_TO_IDX = {s: i for i, s in enumerate(ORDER_STAGES)}

FEATURE_DIM = 10
MAX_CART_SIZE = 10
MAX_SEARCH_SIZE = 20
MAX_UTTERANCE_LEN = 200


def extract_context_features(
    state: dict | None,
    utterance: str = "",
) -> np.ndarray:
    features = np.zeros(FEATURE_DIM, dtype=np.float32)

    if state is None:
        return features

    order_stage = state.get("order_stage", "IDLE")
    if order_stage == "DRAFTING":
        order_stage = "BUILDING"
    if order_stage in STAGE_TO_IDX:
        features[STAGE_TO_IDX[order_stage]] = 1.0
    else:
        features[0] = 1.0

    has_cart = state.get("has_cart", False)
    features[5] = 1.0 if has_cart else 0.0

    cart_size = state.get("cart_size", 0)
    if isinstance(cart_size, (list, tuple)):
        cart_size = len(cart_size)
    cart_size = min(float(cart_size), MAX_CART_SIZE) / MAX_CART_SIZE
    features[6] = cart_size

    has_search_context = state.get("has_search_context", False)
    features[7] = 1.0 if has_search_context else 0.0

    search_context_size = state.get("search_context_size", 0)
    if isinstance(search_context_size, (list, tuple)):
        search_context_size = len(search_context_size)
    search_context_size = min(float(search_context_size), MAX_SEARCH_SIZE) / MAX_SEARCH_SIZE
    features[8] = search_context_size

    utterance_len = len(utterance) if utterance else state.get("utterance_length", 0)
    features[9] = min(float(utterance_len), MAX_UTTERANCE_LEN) / MAX_UTTERANCE_LEN

    return features
