"""Hybrid retrieval over the fixed corpus: FAISS (dense) + BM25 (sparse), fused with RRF.

Used for *resolving* a spoken item name / SOP query to candidate documents. Live quantities come
from `warehouse_data`, not from here.
"""

from __future__ import annotations

import numpy as np
from rank_bm25 import BM25Okapi

from src.agent_brain.warehouse.rag import embed as _embed_mod
from src.agent_brain.warehouse.rag.loader import Doc


class HybridIndex:
    def __init__(self, docs: list[Doc]):
        self.docs = docs
        if docs:
            self._emb = np.asarray(_embed_mod.embed([d.text for d in docs]), dtype=np.float32)
            import faiss

            self._faiss = faiss.IndexFlatIP(self._emb.shape[1])
            self._faiss.add(self._emb)
            self._bm25 = BM25Okapi([d.tokens for d in docs])
        else:
            self._emb = np.zeros((0, 1), dtype="float32")
            self._faiss = None
            self._bm25 = None

    def search(self, query: str, k: int = 5, rrf_k: int = 60, min_score: float = 0.0) -> list[tuple[Doc, float]]:
        if not self.docs:
            return []
        q_tokens = query.lower().split()
        q_vec = np.asarray(_embed_mod.embed([query]), dtype="float32")

        # Dense cosine (FAISS inner product on L2-normalized vectors).
        qn = q_vec / (np.linalg.norm(q_vec) + 1e-9)
        docn = self._emb / (np.linalg.norm(self._emb, axis=1, keepdims=True) + 1e-9)
        dense = (docn @ qn.T)[:, 0]

        # Sparse (BM25)
        bm25_scores = self._bm25.get_scores(q_tokens)

        # Relevance gate — a candidate only counts if it has lexical overlap (BM25>0) or, when a
        # dense threshold is configured, a sufficiently similar dense vector. This is what makes
        # out-of-scope / non-existent queries resolve to NOTHING instead of a fuzzy neighbour.
        eligible = bm25_scores > 0
        if min_score > 0:
            eligible |= dense >= min_score
        if not eligible.any():
            return []

        # RRF fusion over the eligible docs only.
        rrf = np.zeros(len(self.docs), dtype="float64")
        dorder = np.argsort(dense)[::-1]
        for rank, i in enumerate(dorder):
            if eligible[i]:
                rrf[i] += 1.0 / (rrf_k + rank)
        bm25_order = np.argsort(bm25_scores)[::-1][:k]
        for rank, i in enumerate(bm25_order):
            if eligible[i]:
                rrf[i] += 1.0 / (rrf_k + rank)

        order = np.argsort(rrf)[::-1][:k]
        return [(self.docs[i], float(rrf[i])) for i in order if rrf[i] > 0]
