### 5.4.4 Knowledge Retrieval

Objective 4 requires the system to retrieve relevant dishes from the 219-entry menu in response to
Vietnamese sensory descriptions rather than dish names, measured by recall and mean reciprocal rank at
rank five. Recall and hit rate carry more weight than precision, because the agent paraphrases what it
retrieves instead of presenting a ranked list, so it can ignore a weak result but cannot recover a dish
the retriever never returned. The pipeline is described in §4.6: a lexical index, a dense vector index
over the same corpus, a fusion of the two rankings, and a gate that inspects the result before any of it
reaches the language model. The dataset is 24 menu queries with graded relevance judgements across three
difficulty levels, and no language model is involved, so these figures are exact.

The figures are a re-measurement. A first pass produced a cosine similarity of 0.06 between the query "cho
xem lẩu thái" and the document for Lẩu Thái, the dish it names, which is a broken encoder path rather than
a ranking weakness. The cause was `underthesea.word_tokenize`, which the pipeline runs over both documents
and queries because the PhoBERT-family bi-encoder expects word-segmented Vietnamese, but which does not
treat a line break as a token boundary: the multi-line menu template segmented as `Lẩu Thái_Giá`,
destroying the dish name at index time, while the customer's question segmented cleanly to `lẩu_thái`.
Disabling segmentation for retrieval, while the classifier and the semantic router keep it because their
weights were trained with it, lifts the dense lane from R@5 0.473 to 0.595 and its hit rate from 0.667 to
0.792.

#### Retrieval Quality and the Fusion Ablation

**Table 5.9.** Retrieval quality by mode (n = 24 queries). (`eval_retrieval_full.py`)

| Mode | P@5 | R@5 | MRR | Hit Rate | p50 | p95 |
|------|:----:|:----:|:----:|:--------:|:----:|:----:|
| **BM25 only** | **0.408** | **0.757** | **0.722** | **0.958** | 0.5 ms | 0.8 ms |
| FAISS only | 0.300 | 0.595 | 0.586 | 0.792 | 7.1 ms | 8.3 ms |
| RRF fusion | 0.375 | 0.681 | 0.692 | 0.958 | 8.9 ms | 10.0 ms |

Fusion does not improve on the lexical index. It matches BM25 on hit rate and stays below it on the other
three metrics, at roughly eighteen times the latency. Weighting the lanes does not recover the gap either:
sweeping w(BM25) : w(dense) from 1 : 1 to 6 : 1 raises quality monotonically as the dense lane loses
influence, and the best setting is 1 : 0, which removes it. It is not that fusion needs tuning, it is that
on this corpus the second ranking carries no information the first does not already have. The deployment
runs at 3 : 1, which recovers most of the gap while keeping the lane that answers restaurant-information
questions.

The reason is the one §2.5 anticipated, and it is a property of the corpus rather than of either
retriever. Customers name dishes using the words printed on the menu, so lexical overlap between query and
document is high and the vocabulary gap dense retrieval exists to bridge is narrow. A dense index earns
its place where users and documents use different words for the same thing, which is exactly what a menu
corpus does not do.

![Figure 5.2. Retrieval Quality by Query Difficulty](../images/ch5_retrieval_difficulty.svg)

*Figure 5.2. Retrieval Quality by Query Difficulty: precision, recall, mean reciprocal rank and hit rate at
rank five for the fused ranking, split by difficulty. (`render_ch5_figures.py`)*

Easy queries retrieve a relevant dish every time and rank it first every time, and medium queries also
reach a hit rate of 1.000. Performance falls on the hard set, where recall drops to 0.371 and hit rate to
0.857, meaning one of seven returns nothing relevant. Those queries describe an information need through
terms absent from the menu text, such as asking for something suitable for a group to share, where no dish
description contains the concept of sharing. This is the structural failure identified in §2.5.1: query
and documents occupy disconnected regions of the vocabulary, and no index tuning closes a gap that exists
in the corpus rather than in the retriever.

#### Dual-Lane Gatekeeper

The gate admits a query's results only if at least one lane provides evidence of relevance, the semantic
lane on the top result's cosine similarity and the lexical lane on a query term appearing in a top-ranked
document. When neither passes, the pipeline returns empty results rather than passing weakly related
documents to the language model.

It admitted all 24 queries and rejected none. Every query in the set has at least one relevant dish on the
menu, so admitting all of them is the correct outcome: the set contains no query the gate was designed to
reject. The evaluation therefore establishes the false-positive half of the requirement, that the gate
does not withhold results it should admit, and leaves the rejection path untested. Measuring the other
half needs a query set containing requests the menu genuinely cannot answer, which §5.6.3 records as a
limitation of the data rather than a result about the gate.

**Objective 4 is partially met:** the retriever finds a relevant dish for 23 of 24 queries and ranks it
first on every easy query, and the residual failure on the hard set is a property of a corpus whose
documents never mention what those queries ask about. What is not vindicated is the hybrid design, since
the lexical lane alone equals or beats the fused ranking at every weighting tested.
