## 2.5 Menu Knowledge Retrieval (RAG)

### 2.5.1 The Knowledge Problem and Standard RAG

A language model asked about a restaurant's own menu has no source for the answer, since the menu was not in its training data. An answer produced anyway is constrained by no record of what the restaurant serves. Retrieval-Augmented Generation addresses this by fetching relevant domain documents into the prompt before generation [2.5.1]. The literature describes three generations, Naive, Advanced, and Modular, which progressively decouple the pipeline stages so that each can be improved on its own [2.5.2]. Modular RAG makes the components swappable, and swappability is where it stops: nothing in the architecture states whether a module's output is adequate or whether retrieval has failed.

All three architectures rest on one assumption, that the query and the documents share a vocabulary and a vector space. The assumption does not hold when a need is expressed in terms absent from the corpus, a condition documented as query-document vocabulary mismatch [2.5.3]. Query and document vectors then occupy disconnected regions of the space, so a better encoder or a different chunking strategy does not reach the problem.

The reason is architectural. Standard RAG runs one way, from query to retrieval to generation, and places the model at the end of that sequence. The model receives whatever retrieval returned, took no part in deciding how the search was conducted, and has no channel through which to report that the results are unusable. The architecture therefore offers no position from which a vocabulary mismatch could be detected, since detecting one would require the model to assess what retrieval returned and reformulate the query before generating.

### 2.5.2 Representing Vietnamese Text for Retrieval

Two paradigms make text comparable for relevance: dense embeddings place text in a learned continuous space, while sparse representations weight vocabulary terms by frequency statistics. Both depend on a prerequisite the language imposes rather than the method, namely word segmentation.

Vietnamese script places spaces between syllables, not between words. A three-syllable compound such as "bún bò Huế" is written as three tokens but names one dish. Without segmentation a dense model embeds three fragments rather than the compound, and a sparse index treats the three as independent terms, so a query containing "bò" matches any document containing that syllable. Table 2.5a lists the three documented tools [2.5.9]. Their reported accuracies are measured on formal written Vietnamese; no published evaluation covers domain-specific proper nouns, which is where a segmenter's dictionary and statistical model are least reliable, and a menu is composed almost entirely of proper nouns.

**Table 2.5a.** Vietnamese word segmentation tools.

| Tool | Method | Accuracy (VLSP 2013) | Deployment | Documented limitations |
|------|--------|:---:|---|---|
| `underthesea` | CRF, Vietnamese Treebank | ~97% | Pure Python, ~50 MB | Accuracy on informal and elided forms unbenchmarked; domain-specific proper nouns not evaluated |
| `VnCoreNLP` | RNN + word embeddings + CRF | Higher (~98%+) | Java (separate process) | Java runtime dependency; per-call process overhead compared with in-process alternatives |
| `pyvi` | Dictionary + regex | Lower | Pure Python, no model | Weak on compound terms with ambiguous boundaries; dictionary coverage limited |

Dense encoders for Vietnamese fall into two categories, separated by an axis running from language fidelity to ecosystem maturity:
- Vietnamese-Native Bi-encoders [2.5.10]–[2.5.14]: Built on PhoBERT [2.5.11] or comparable monolingual encoders, so their tokenizers preserve diacritics without the subword boundary artifacts multilingual BPE introduces, and their training corpora include the informal registers of social media and forums. They report gains of 8 % to 15 % over multilingual alternatives on Vietnamese sentence-similarity benchmarks [2.5.15]. Retrieval-specific results, measured over document collections rather than sentence pairs, are unreported for the category.
- Multilingual Models [2.5.16]–[2.5.18]: Lead cross-lingual retrieval benchmarks and offer features the native models lack, such as multi-vector retrieval. Their diacritic handling is adequate rather than tuned: tokenizers preserve diacritic-bearing characters but allocate no attention to tonal distinctions, and compound-word boundaries are not recognized as units distinct from syllable spans.

**Table 2.5b.** Dense embedding models with Vietnamese capability.

| Model | Dim | Vietnamese-native | Diacritic-aware | Parameters | Documented strengths | Documented limitations |
|-------|-----|:---:|:---:|:---:|---|---|
| `bkai-foundation-models/vietnamese-bi-encoder` | 768 | ✓ | ✓ | ~135M | Trained on Vietnamese sentence pairs including informal registers; L2-normalized; teencode-aware | Single-language only; code-switching not supported; retrieval-specific benchmarks unreported |
| `VoVanPhuc/sup-SimCSE-VietNamese-phobert-base` | 768 | ✓ | ✓ | ~135M | SimCSE contrastive training on PhoBERT; evaluated on Vietnamese STS | Encoder-only; less evaluated on retrieval tasks than on similarity tasks |
| `AITeamVN/Vietnamese_Embedding` | 1024 | ✓ | ✓ | Not specified | Larger dimension; BART-based encoder with contrastive fine-tuning | Larger index size and search time; benchmark coverage narrower than alternatives |
| `BAAI/bge-m3` | 1024 | ✗ (multilingual) | Partial | 568M | State of the art on multilingual retrieval (MIRACL); native dense, sparse, and multi-vector retrieval | Diacritic attention not Vietnamese-tuned; Vietnamese training proportion undisclosed |
| `intfloat/multilingual-e5-large` | 1024 | ✗ (multilingual) | Partial | 560M | Top-ranked on cross-lingual retrieval; E5 contrastive recipe | Primarily high-resource language evaluation; Vietnamese domain-specific effects uncharacterized |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 | ✗ (multilingual) | Weak | 118M | Compact, fast inference, widely integrated | 384-dim reduced representational resolution; BPE tokenizer strips diacritics in Vietnamese |

Neither category is characterized on the kind of corpus a menu constitutes. MIRACL and MTEB, the benchmarks the multilingual models are ranked on, are built from news articles and encyclopedia entries: documents of several hundred tokens whose term distributions approximate general language. A menu is the opposite in every respect retrieval depends on. Its documents are short and structurally uniform, its vocabulary is dominated by proper nouns absent from any general corpus, and the terms distinguishing two entries may amount to a single word. No published retrieval evaluation, for either category, uses a corpus with those properties.

The sparse alternative is BM25 [2.5.19], which extends TF-IDF with two tunable parameters: k₁ saturates the contribution of a repeated term, and b controls how far document length is normalized away. It excels at exact lexical matching, separating documents that contain the query terms from those that do not. What it cannot do is bridge a vocabulary gap, since a query sharing no term with the index returns nothing whatever the parameter values. For Vietnamese its behaviour is decided upstream by the segmenter, because mis-segmented compounds fragment into syllables that then match across unrelated dishes, and the interaction between segmentation quality and retrieval precision has not been studied systematically for Vietnamese domain-specific corpora.

Both representations need an index. Dense vectors are searched with FAISS [2.5.20], whose exact search costs linearly in corpus size; at a few hundred documents that cost is negligible, so the choice among approximate structures is not a live question at this scale. The sparse side uses an inverted index, the foundational data structure of information retrieval, validated across decades of evaluation at TREC, CLEF, and NTCIR [2.5.21].

### 2.5.3 Result Fusion

A dense and a sparse retriever running in parallel produce two ranked lists that have to become one, and the scores cannot simply be added: BM25 scores are unbounded term-weight sums while cosine similarities are bounded in [−1, 1], and the two ranges carry no common meaning. Three fusion techniques handle that incommensurability differently:
- Reciprocal Rank Fusion (RRF) [2.5.22]: Sidesteps normalization by operating on ranks. Each document's fused score sums, across the lists it appears in, the reciprocal of its rank shifted by a constant k, conventionally 60. It assumes nothing about score distributions and needs no per-domain tuning, and a document present in only one list can still rank highly if that rank is competitive.
- Linear Combination: Normalizes scores by min-max or z-score, then sums them under a weight α. Well calibrated for a collection, it can beat RRF by exploiting the magnitude information RRF discards [2.5.23]. The weight does not transfer: one tuned on news articles will not suit menu entries, and without calibration data the method can underperform RRF, because magnitude differences carrying no signal are amplified by α.
- Condorcet Voting [2.5.24]: Ranks each document by how many others it beats pairwise across the lists. It needs no normalization and extends beyond two retrievers, but costs O(n²) in unique documents, and for two-retriever fusion no evaluation shows a systematic advantage over the simpler RRF baseline.

**Table 2.5c.** Fusion methods for combining ranked lists from several retrievers.

| Method | Score normalization | Domain transfer | Computational cost | Single-list documents |
|--------|:---:|:---:|:---:|---|
| RRF | Not required; operates on ranks | Domain-independent (k = 60 is fixed; no per-domain tuning needed) | O(n log n) for sorting n unique documents | Receive contribution from one retriever; no penalty for absence from other lists |
| Linear combination | Required; min-max or z-score per retriever | Weight α must be re-tuned per domain and document collection | O(n) after normalization | Score depends on normalization of the present retriever; absent retriever contributes 0 |
| Condorcet voting | Not required; uses pairwise rank comparisons | Domain-independent | O(n²) for n unique documents | Win against documents ranked lower in all lists where both appear; absent documents lose all pairings |

---

### 2.5.4 Beyond Retrieve-then-Generate: Rewriting, Evaluation, Context

The standard pipeline runs one way: retrieval produces a ranked list and the model consumes it. Three classes of extension address pieces of that limitation, one before retrieval, one after it, and one across turns. Each has been evaluated as an independent point solution on English benchmarks.

Pre-retrieval query rewriting transforms the query before it reaches the retriever, bridging the vocabulary gap by two different mechanisms:
- HyDE, Hypothetical Document Embeddings [2.5.25]: Prompts a model to generate a plausible relevant document and embeds that document in place of the raw query, on the premise that generated text, even where factually wrong, shares vocabulary and structure with the target corpus while the user's phrasing may not. On TREC DL and Web Questions it improved recall on vocabulary-gap queries in English. Its documented limitation is unbounded generation: the model may fabricate terms or entities absent from the real corpus, and the hypothetical embedding then pulls retrieval toward the fabrication.
- Step-Back Prompting [2.5.26]: Abstracts the query to a higher conceptual level and retrieves against the abstraction. Producing a category rather than free-form text lowers the hallucination risk relative to HyDE, but the approach depends on choosing the right level: too abstract and retrieval loses specificity, too specific and the gap persists. Its evaluations, on MMLU and TimeQA, abstract over factual taxonomy and yield one step-back question per query. Neither property transfers to a menu, where a description of how a dish should feel to eat may map to several unrelated categories at once, and the mapping from sensation to category is a culinary association held by a culture rather than a fact recorded in text.

Both share a structural property that keeps them out of a control loop: they transform the query and hand off to retrieval with no return path. The model that rewrote the query never sees the retrieved results, cannot judge whether the rewrite helped, and cannot adjust its strategy from retrieval quality. The rewriting is an open-loop transformation.

Post-retrieval evaluation inspects the retrieved documents before generation, filtering noise and, in some architectures, triggering corrective action:
- Self-RAG [2.5.27]: Uses reflection tokens, learned during fine-tuning, indicating whether each passage is relevant and whether the generated text is supported by it. Assessment is embedded in generation, allowing per-passage filtering without a separate evaluation model. Its limitation is the fine-tuning requirement: the tokens must be trained into the model's output distribution, which takes infrastructure and labelled data most domain-specific deployments lack.
- CRAG, Corrective RAG [2.5.28]: Scores relevance at inference time instead, discarding documents below a threshold and triggering a fallback if nothing passes. It costs one extra model call per retrieval and was evaluated on English QA benchmarks including PopQA, PubHealth, and Arc-Challenge. Its corrective action is fixed rather than strategy-aware: the fallback is a web search, and the model does not decide what to search for next.

Neither has been evaluated where relevance depends on structured metadata matching, that is on whether a dish's ingredients, taste profile, and preparation method fit a sensory description, rather than on factual concordance with a knowledge base.

Multi-turn search context addresses a limitation specific to conversational retrieval. A user who searches in turn 3 and refers back pronominally in turn 6 ("cái đó có cay không?") expects the reference resolved against prior results rather than a fresh retrieval on the literal string. Dialogue state tracking [2.5.29] maintains structured per-session state, but was designed for frame-based architectures holding scalar slot values, where a retrieval result is a ranked list with metadata. Memory-augmented architectures including MemoryBank [2.5.30] and LongMem [2.5.31] persist retrieved context across conversations, but for cross-session user modelling rather than deduplication within a single visit. None addresses the entity resolution problem specific to multi-turn retrieval: determining whether a new utterance refers to an already retrieved item and answering from memory instead of re-querying.

Set beside one another the three extensions share a property none reveals alone. Query rewriting acts before retrieval and hands off without a return path. Post-retrieval evaluation acts after retrieval and, where it corrects at all, takes an action fixed in advance rather than chosen in response to what came back. Multi-turn context persists across turns without informing the retrieval inside any of them. Each attaches to an edge of the pipeline, and none produces a signal travelling from the output of retrieval back to its input, which is why a pipeline with all three installed still cannot register that a retrieval failed and then do something different in consequence.

---

### 2.5.5 Identified Literature Gaps

The gap this survey ends on was opened by the fix for an earlier one. Modular RAG answered a real complaint, that the naive pipeline was rigid, by making its stages independent and swappable so each could be optimized per domain. Independence was the point. But it was achieved by specifying what each module hands to its neighbours and leaving unspecified what any module should do about what it receives, so a module returning poor output and one returning good output present the same interface. The pattern that made the components composable is the same pattern that omits coordination, which is why the extensions of §2.5.4 attach so readily to the pipeline's edges while none of them closes it.

What the pipeline lacks is a component that is not a well-behaved module: something that reads the output of a stage and decides what happens next. The vocabulary mismatch of §2.5.1 gives that absence its concrete form, since bridging a sensory query to a corpus indexed by name requires knowledge about the domain, and the only component holding that knowledge is the one placed last and consulted never.
