## 4.5.6 Response Generation

The response generation architecture completes the validation-gated execution pattern that
§2.4.7 found had not been combined with other layers for Vietnamese task-oriented dialogue.
The survey identified that prompt engineering techniques — system prompts, few-shot examples,
dynamic context injection, and DSPy optimization — are documented in the literature but
untested on Vietnamese restaurant ordering. The approach here uses a hybrid template-and-LLM
design: template responses for formula-driven, deterministic outputs where speed, correctness,
and consistency are paramount; language model generation only for variable-content situations
where the structured data the model receives is pre-verified, eliminating hallucination risk.

Every utterance follows a guaranteed path: the state outcome always produces a typed response
context, and the response node always produces a spoken reply — the customer always hears
something, regardless of whether the turn succeeded, failed validation, or triggered the
circuit breaker.

### 4.5.6.1 Typed Response Contexts

The response context is a discriminated union of five subtypes, each carrying the structured
data specific to the tool that executed. An order response context carries the cart contents,
total price, off-menu items with nearest-match suggestions, ambiguous items needing
clarification, the order stage, and — when an order was confirmed — the order identifier. A
search response context carries the original query text and the ranked results with dish names,
prices, categories, and taste tags. A payment response context carries the amount in
Vietnamese đồng, the QR code URL, the table identifier, and the payment status. A chat
response context, built by the chat worker rather than the state outcome, carries the
customer's utterance, the active cart, the order stage, the full conversation history, up to
five curated dishes from the most recent search, and — when reached via delegation — the
reason the domain worker passed control. A retry response context, built only when the
circuit breaker trips, carries the name of the failed tool and the validator's feedback
string.

### 4.5.6.2 Template-Based Responses

Template responses are pre-written Vietnamese strings assembled with string formatting.
They are used for deterministic outcomes — situations where the content is formula-driven
and the phrasing should be predictable across every occurrence.

Order confirmation uses a fixed template: "Dạ, đơn hàng #42 của anh/chị đã được gửi đến bếp
ạ. Món sẽ được làm ngay!" Cart echoing iterates over the cart items and computes the total
deterministically: "Dạ, giỏ hàng của anh/chị có: Ốc Hương Xốt Trứng Muối ×2 — 340k, Lẩu
Thái ×1 — 250k. Tổng 590k. Anh/chị xác nhận đặt món ạ?" Ambiguity clarification lists
all matching variants: "Dạ, Ốc Hương có nhiều loại sốt: trứng muối, me, tỏi, bơ... anh/chị
muốn loại nào ạ?" Off-menu rejection names the missing item and suggests the nearest match:
"Dạ, món 'Cơm Tấm' không có trong thực đơn. Món gần giống nhất là Cơm Chiên (150k). Anh/chị
muốn thử không ạ?" Removal and clearing confirmations use fixed acknowledgment patterns.
Payment prompts display the total and the QR code. Greetings and thanks use standard
Vietnamese waiter courtesy phrases. The circuit breaker apology is also template-based:
"Dạ, em xin lỗi anh/chị, em xử lý thông tin bị lỗi. Anh/chị kiểm tra lại giúp em nhé ạ."

Templates offer four advantages. They are fast — assembly takes microseconds with no
language model inference. They are correct — prices are computed from the cart state, not
hallucinated, and quantity arithmetic is Python arithmetic rather than language model
generation. They are consistent — the same situation produces the same phrasing every time,
making the system's behavior predictable for the customer. They are natural Vietnamese —
templates are written by a Vietnamese speaker, using natural waiter vocabulary and
appropriate politeness levels, not translated from English.

### 4.5.6.3 Language-Model-Based Responses

Three situations require language model generation because the content is too variable
for templates. Search results must be listed conversationally — the model receives the
ranked dish list with names, prices, and categories, and paraphrases it into natural
Vietnamese: "Dạ, quán mình có các món nước ấm: Lẩu Thái (250k) — cay, chua; Lẩu Hải
Sản (300k) — ngọt, thanh. Anh/chị muốn thử món nào ạ?" Off-menu situations with
suggestions require natural paraphrasing of alternatives — naming the missing item,
explaining it is unavailable, and offering the nearest matches with prices. Free-form
chat responses are open-ended and grounded in the full conversation history, the cart,
and the curated memory of previously discussed dishes.

The language model used for response generation is the same Qwen2.5 7B instance, but
configured with temperature 0.3 — higher than the router and workers because response
generation benefits from varied phrasing. Crucially, the model never invents content: it
receives only pre-verified structured data — dish names resolved against the menu, prices
computed from the menu data, quantities verified by the validator — and its job is to
reformat that data into conversational Vietnamese. The model does not decide what dishes
exist, what they cost, or what the customer ordered; it only decides how to say what has
already been verified.

### 4.5.6.4 Response Selection

The response node applies heuristics to select between template and language model paths
within each context type.

For order responses, the decision tree is: if ambiguous items exist, use a template to
request clarification; if off-menu items have suggestions, use the language model for
natural paraphrasing of alternatives; if off-menu items have no suggestions, use a
template for a clean rejection; if the tool produced an error, use a template for the
error message; if the tool was confirm-order and it succeeded, use a template for the
confirmation; if the tool was remove-from-cart or clear-cart, use a template for the
acknowledgment; otherwise — a successful add-to-cart — use a template for the cart echo
with per-item prices and a running total.

For chat responses, the decision tree is: if the chat worker was reached via delegation
with a cart review reason, use a template to echo the cart; if the delegation reason was
unclear input, use a template to request clarification; if the message is a greeting,
use a greeting template; if the message is thanks, use a thanks template; otherwise, use
the language model for free-form conversation grounded in the curated memory context.

This hybrid approach — templates for formula-driven outputs, the language model for
variable content — maximizes speed and correctness while maintaining conversational
flexibility where it is needed.

### 4.5.6.5 Streaming Architecture

The response generator supports sentence-by-sentence streaming to the voice pipeline on
the robot, enabling the speech synthesis engine to begin playback of the first sentence
while the language model is still generating subsequent sentences.

Language-model-generated text is streamed token-by-token and split into sentences at
Vietnamese punctuation boundaries. Each complete sentence is emitted as a streaming event
immediately, without waiting for the full response. Template responses — which are
pre-assembled — are emitted as a single event. The streaming events flow through the
server to the robot's voice pipeline, where the synthesis engine plays sentences
sequentially. Meanwhile, the customer's tablet receives the same stream via the backend's
voice bridge, displaying each sentence as it is spoken.

The streaming design means the first spoken sentence reaches the customer in approximately
half a second after the response node begins generating, rather than waiting for the full
multi-sentence reply. The "done" event at the end of the stream carries the full response
text, the UI action command, and the synchronized cart state — the tablet uses this to
update its display after the last sentence plays.
