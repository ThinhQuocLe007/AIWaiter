## 4.5.2 Intent Classification

The intent classifier addresses the gap identified in §2.4.4: no classification approach
combines speed and determinism with Vietnamese-language handling. The survey found that
rule-based classifiers are fast but language-specific and stateless, centroid-based routers
handle domain vocabulary but fail on teencode and context-dependent utterances, and
LLM-based routers handle all accuracy criteria but cost latency and non-determinism. The
classifier presented here resolves this trade-off by combining a frozen Vietnamese
bi-encoder for semantic representation with ten hand-crafted context features extracted
from the conversation state, processed through a small multi-layer perceptron trained on
synthetic Vietnamese restaurant utterances.

### 4.5.2.1 Intent Taxonomy

The classifier recognizes four output classes. ORDER\_CONFIRM utterances ("ok em", "chốt
đơn") are merged with ORDER — the distinction is handled downstream by the cart state
machine (§4.5.5.4), not the classifier. Multi-intent utterances ("Cho 2 Ốc Hương rồi tính
tiền luôn") are classified by their dominant intent; sequential multi-intent execution is
handled by the graph's intent queue loop (§4.5.5.5).

| Intent | Vietnamese Trigger Examples | Worker | Notes |
|--------|----------------------------|--------|-------|
| **ORDER** | "Cho 2 Ốc Hương", "Gọi thêm 1 Lẩu Thái", "Bỏ món X", "Ok chốt đơn" | Order worker | ORDER\_CONFIRM merged at classifier level |
| **SEARCH** | "Món nào cay cay?", "Ốc Hương giá bao nhiêu?", "Có món chay không?" | Search worker | All informational queries |
| **PAYMENT** | "Tính tiền", "Cho xin bill", "Thanh toán QR" | Payment dispatch | Deterministic dispatch |
| **CHAT** | "Chào em", "Cảm ơn", "Ngon quá", "Quán đông ghê" | Chat worker | Smalltalk and non-task utterances |

### 4.5.2.2 Classifier Architecture

The classifier is a three-layer multi-layer perceptron accepting a 778-dimensional input
vector and producing a four-class probability distribution. The input vector is the
concatenation of a 768-dimensional sentence embedding and ten context features. Figure 4
illustrates the full pipeline from utterance to intent.

The sentence embedding is produced by the Vietnamese bi-encoder selected in §4.6 — a
SentenceTransformer model pre-trained on Vietnamese sentence pairs, producing L2-normalized
768-dimensional vectors. This model was chosen for its native handling of Vietnamese
diacritics, compound words, and informal speech patterns — critical for a restaurant setting
where customers use teencode abbreviations ("ad", "vs", "ck", "z", "nhiêu") and dialectal
variants. The embedding step is shared with the retrieval pipeline, so the model is loaded
once and reused.

The ten context features are the architectural innovation that distinguishes this classifier
from pure embedding-based approaches. An utterance of "ok" maps to ORDER when the cart is
awaiting confirmation but to CHAT when no order is in progress — the embedding alone cannot
make this distinction, since "ok" carries the same semantic vector regardless of context.
The context features encode the conversation state that resolves such ambiguities. Five
features capture the order stage as a one-hot encoding — whether the customer is idle,
drafting an order, awaiting confirmation, or has a confirmed order. One feature indicates
whether a cart exists; another normalizes the cart size to account for how full the order
already is. One feature signals whether search results from a previous turn are still in
context; another normalizes the count of those results. The final feature normalizes the
utterance length, helping distinguish short affirmations from longer queries.

The network itself is intentionally small — three layers totaling approximately 220 thousand
parameters — because the 768-dimensional embedding already provides a strong semantic
representation. The first hidden layer projects the 778-dimensional input to 256 dimensions
with ReLU activation and 20% dropout. The second layer reduces to 64 dimensions, again with
ReLU and dropout. The output layer produces four logits with softmax normalization. The
dropout layers prevent overfitting to the synthetic training data and ensure generalization
to real customer utterances not seen during training.

### 4.5.2.3 Training

The classifier was trained on 3,712 synthetically generated Vietnamese utterances covering
all four intents across diverse restaurant scenarios. A subset of 795 raw utterances was
expanded to 3,712 through systematic augmentation: each utterance was paired with multiple
context configurations — different order stage values and cart states at which that utterance
could realistically occur. A 39-case holdout set was separated before augmentation and never
seen during training.

Training used an 80/20 stratified split with cross-entropy loss weighted inversely by class
frequency to compensate for the under-representation of SEARCH and CHAT in the raw data.
The Adam optimizer ran with a learning rate of 1e-3 and weight decay of 1e-4, with early
stopping at ten epochs of no validation improvement. All 3,712 embeddings were precomputed
offline, so training converged in approximately two minutes on CPU.

Three artifacts are saved and loaded at agent startup: the model weights, a label encoder
mapping class names to indices, and a standard scaler fitted on the training set's context
features to normalize each feature to zero mean and unit variance.

### 4.5.2.4 Online Inference

At inference time, the pipeline executes in four stages. First, the utterance is tokenized
via Vietnamese word segmentation, preserving compound words as single tokens. Second, the
segmented text is encoded by the frozen bi-encoder. Third, the ten context features are
extracted from the current conversation state and normalized using the saved scaler. Fourth,
the 778-dimensional concatenated vector passes through the MLP in approximately 0.17
milliseconds, producing a four-class probability distribution.

The classifier outputs the predicted intent, the confidence score, and the full probability
distribution. The intent queue is set to contain that single intent, and the graph proceeds
to the corresponding worker node. The embedding step — shared with the retrieval pipeline
and dominating at approximately 50 milliseconds — accounts for virtually all classification
latency; the MLP forward pass itself is negligible.

### 4.5.2.5 Design Rationale

The MLP classifier was chosen over two prior iterations evaluated as ablation baselines.
The first iteration — a pure semantic centroid router computing cosine similarity to five
per-intent centroids — achieved 89.0% accuracy on 100 cases but failed on approximately 11%
of utterances where the maximum similarity fell below the confidence gate threshold. The
second iteration — a two-tier hybrid combining the semantic fast-path with an LLM fallback
— dropped to 73.3% on a 45-case evaluation set because many utterances fell below the gate
and defaulted to CHAT, and the LLM fallback added 1.8 seconds per invocation.

The MLP classifier achieves 95.6% on the same 45-case comparison — a 22-point improvement
over the hybrid. On the 39-case holdout, it achieves 97.4% with a single misclassification.
ORDER, CHAT, and non-delivery SEARCH queries are classified perfectly. The progression
demonstrates three design principles: pure embedding similarity is insufficient for
Vietnamese restaurant ordering — context features are necessary; LLM-based routing adds
latency without proportional accuracy gain over a trained classifier; and a small MLP
trained on domain-specific data outperforms both a hand-crafted gating system and a
general-purpose language model on this task.

The classifier is deterministic — the same utterance with the same context always produces
the same output. It is fast — the MLP forward pass is three orders of magnitude faster than
an LLM call. It is Vietnamese-aware — the bi-encoder embedding captures diacritics and
compound-word semantics that general multilingual models handle partially. Its single
limitation is that it requires the frozen embedding model to remain unchanged; upgrading
to a model with a different dimension would require retraining.
