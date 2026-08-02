### 4.5.2 Intent Classification

Every turn begins with one decision: which of the four workers receives the utterance.
Customers make that decision hard. They speak in regional forms and clipped fragments
("Cho anh 2 phần ốc hương nghen", "Món ni giá bao nhiêu rứa em"), they answer in a single
word whose meaning depends entirely on what was just asked ("ừ", "ok", "chuẩn"), and they
put two requests into one sentence ("Cho 2 Ốc Hương rồi tính tiền luôn").

A routing error cascades: an ordering intent sent to the chat worker produces a
conversational reply instead of a cart operation, and a chat intent sent to the order
worker produces a spurious tool call that the validator must later reject.

No single approach in the survey of Section 2.4.4 of Chapter 2 covers all of this. The
deterministic ones are fast but fail on teencode and on turns whose meaning comes from the
conversation rather than from the words. The language-model ones handle both, at
second-scale latency and without returning the same answer twice on the same input. The
state-augmented classifiers that would otherwise fit need dialogue-state corpora that do
not exist for Vietnamese, and are reported as unable to handle multi-intent utterances.

The design here takes two of those mechanisms and uses each where it is strong: a classifier
trained on a corpus written by hand for this restaurant, and a rewriter that splits a
compound utterance into single-intent fragments before any of them is classified.

The router is a multi-layer perceptron that accepts a 768-dimensional Vietnamese sentence
embedding and produces a four-class probability distribution via softmax through two hidden
layers. Table 4.3 gives the layer-by-layer composition.

*Table 4.3. Layer composition of the intent classifier MLP.*

| Layer | Dimensions | Activation | Dropout |
|-------|-----------|------------|---------|
| Input | 768 | n/a | n/a |
| Hidden 1 | 768 → 256 | ReLU | 0.2 |
| Hidden 2 | 256 → 64 | ReLU | 0.2 |
| Output | 64 → 4 | Softmax | n/a |

The two hidden layers progressively compress the embedding down to four logits, one per
intent class. The dropout layers, applied after each hidden activation during training,
prevent the network from relying on any single embedding dimension and improve
generalisation to unseen utterances. The entire model holds approximately 220 thousand
parameters, small enough that inference completes in under one millisecond on the CPU
with no GPU dependency.

The sentence embedding is produced by a Vietnamese-native
bi-encoder, `bkai-foundation-models/vietnamese-bi-encoder`, selected from the survey
of §2.5.2 for its Vietnamese-language pre-training and 768-dimensional output. The same
model serves the retrieval pipeline (§4.6) and is loaded once at agent startup, so the
classifier and the retriever share one embedding model with no additional memory cost.
Figure 4.4 illustrates the pipeline.

![Figure 4.4. Intent Classification Pipeline](../images/router_flow.svg)

*Figure 4.4. Intent Classification Pipeline: the utterance is word-segmented by
underthesea, embedded by the same bi-encoder the retriever uses, and classified.
The fast path accepts a prediction when confidence reaches its class threshold,
0.85 for SEARCH and 0.70 for the other three, and no boundary marker is present;
otherwise a rewriter decomposes the utterance into fragments classified one by
one. (drawn by the group)*

No labelled dataset of Vietnamese restaurant utterances exists, so one was written by
hand: 1 639 utterances composed against the restaurant's menu, spread across five
linguistic styles. Table 4.4 gives the style breakdown with representative examples.

*Table 4.4. The five styles of the manual dataset.*

| Style | Count | Description | Example |
|-------|:----:|-------------|---------|
| Casual | 561 | Natural everyday speech, shortened forms | "Cho 2 ốc hương đi em", "Bỏ món mực chiên sả ra khỏi đơn giúp mình" |
| Formal | 300 | Full sentences with polite particles "ạ", "dạ" | "Dạ cho em gọi 1 Lẩu Thái và 3 chai Bia Saigon ạ" |
| Fragment | 298 | Verbless clauses matching the output shape of the rewriter: 2–6 words, no politeness particles | "Cho 2 Ốc Hương", "Xoá hết giỏ hàng", "Tính tiền" |
| Dialect | 267 | Regional variants: Southern "nghen", "hông"; Central "mô", "rứa" | "Cho anh 2 phần ốc hương nghen", "Món ni giá bao nhiêu rứa em" |
| Edge | 213 | One- or two-word utterances, inherently ambiguous | "ok", "ừ", "được", "chuẩn" |

The fragment style is essential for multi-intent turns. At inference, compound utterances
are split by the rewriter into single-intent fragments, and the classifier must handle
these stripped-down clauses, which carry no subject and no politeness particles, only the
words that bear the intent. Without fragment-shaped examples in training, multi-intent turns
consistently fail.

The training split is grouped by utterance using `GroupShuffleSplit`, which ensures that
all rows carrying the same utterance text land in the same split. A split by row would
scatter copies of one utterance across training and validation, inflating the validation
score with memorisation rather than generalisation.

A 39-case holdout set was separated before any training, so no holdout utterance appears
in the training split.

The model is trained on precomputed embeddings. Embeddings are computed once over the
entire corpus and cached, so training iterates over tensors rather than re-encoding every
epoch. The training configuration is given in Table 4.5.

*Table 4.5. Training hyperparameters and methodology.*

| Setting | Value |
|---------|-------|
| Optimizer | Adam (learning rate 1 × 10⁻³, weight decay 1 × 10⁻⁴) |
| Loss | Cross-entropy with inverse-frequency class weights |
| Train/validation split | 80/20, grouped by utterance (`GroupShuffleSplit`) |
| Batch size | 64 |
| Maximum epochs | 80, with early stopping (patience 15 on validation accuracy) |
| Training time | ~3 minutes on precomputed embeddings (CPU) |

Class weights are computed as the inverse frequency of each intent in the training set.
After grouping, ORDER is the largest class at 655 examples and CHAT the smallest at 204,
a ratio of roughly three to one. Without the weights the model favours ORDER at the
expense of CHAT and PAYMENT.

Two artefacts are serialised and loaded at agent startup: `model.pt` (the trained weights)
and `label_encoder.json` (the label-to-index mapping). No scaler is saved, since there are
no context features to scale.

At inference the utterance is word-segmented by `underthesea.word_tokenize`, embedded by
the frozen bi-encoder, and fed directly to the MLP. The embedding is produced at float32
precision rather than float16, because the classifier's margin between a correct and an
incorrect intent is narrow enough that half-precision rounding could flip a borderline
prediction.

Two outcomes determine the next step. If the confidence exceeds 0.7 and no
boundary marker is present (words such as "rồi," "và," "thì," "xong," or "với lại" that
signal clause boundaries in Vietnamese), the predicted intent is accepted directly and
dispatched to the corresponding worker. For SEARCH, a higher threshold of 0.85 is applied,
because dish-name tokens bias the MLP toward SEARCH even when the utterance carries ORDER
markers ("cho mình 1 Mực Cháy Tỏi" scoring SEARCH 0.740). Raising the SEARCH bar sends
borderline dish-name utterances through the rewriter where they reclassify correctly as
ORDER. The fast path handles the majority of utterances.

If the confidence falls below its class-specific threshold or boundary markers are detected,
the utterance is routed to a language-model-based rewriter that decomposes it into
single-intent Vietnamese fragments. For "Cho 2 Ốc Hương rồi tính tiền luôn," the rewriter
produces two fragments that are classified independently and queued for sequential execution
(§4.5.5). The rewriter is invoked only when the fast path cannot resolve the utterance, so
the language model cost is paid only when necessary, not on every turn.
