## 4.5.6 Response Generation

The final stage converts the executed action's result into spoken Vietnamese. Every
utterance follows a guaranteed path: the state outcome always produces a typed response
context, and the response node always produces a spoken reply. The customer always hears
something, regardless of whether the turn succeeded, failed validation, or triggered the
circuit breaker.

The response architecture addresses a finding from §2.4.3: prompt engineering techniques for
domain adaptation are documented in the literature but untested on Vietnamese restaurant
ordering. The approach uses a hybrid design: pre-written Vietnamese templates for formula-
driven outputs where speed, correctness, and consistency are paramount; language model
generation only for variable-content situations where the structured data the model receives
has already passed through the validator, eliminating the risk of hallucinated dish names,
prices, or quantities reaching the customer.

The response context, built by the state outcome or by the chat worker, is a discriminated union
of five subtypes, one for each kind of outcome a turn can reach. Each carries only data that has
already been verified, which is what makes the model safe to call on it. Table 4.14 sets out the
five.

*Table 4.14. The five response contexts, and what each carries into the reply stage.*

| Context | Built by | Carries | Produced when |
|---------|----------|---------|---------------|
| Order | State outcome | Cart, total, off-menu items, ambiguous items, stage, order identifier | A cart tool ran |
| Search | State outcome | Query, ranked results, dishes already shown in earlier turns | The search tool ran |
| Payment | State outcome | Amount, QR code address, table identifier, status | A payment tool ran |
| Chat | Chat agent | Utterance, cart, stage, history, up to five remembered dishes, delegate reason | No tool ran this turn |
| Retry | State outcome | Name of the failed tool, validator feedback | The circuit breaker tripped |

Template responses are pre-written Vietnamese strings assembled with string formatting, used
for deterministic outcomes where the content is formula-driven and the phrasing should be
predictable across every occurrence. Order confirmation uses a fixed template: "Dạ, đơn hàng
của anh/chị đã được gửi đến bếp ạ. Món sẽ được làm ngay!" Cart echoing iterates over the cart
items and computes the total deterministically: "Dạ, giỏ hàng của anh/chị có: Ốc Hương Xốt
Trứng Muối ×2, 340k; Lẩu Thái ×1, 250k. Tổng 590k. Anh/chị xác nhận đặt món ạ?" Ambiguity
clarification lists all matching variants: "Dạ, Ốc Hương có nhiều loại sốt: trứng muối, me,
tỏi, bơ... anh/chị muốn loại nào ạ?" Off-menu rejection names the missing item and suggests
the nearest match: "Dạ, món 'Cơm Tấm' không có trong thực đơn. Món gần giống nhất là Cơm
Chiên (150k). Anh/chị muốn thử không ạ?" Removal and clearing confirmations use fixed
acknowledgment patterns. Payment prompts display the total and the QR code. Greetings and
thanks use standard Vietnamese waiter courtesy phrases. The circuit breaker apology is also
template-based: "Dạ, em xin lỗi anh/chị, em xử lý thông tin bị lỗi. Anh/chị kiểm tra lại
giúp em nhé ạ."

Templates offer four advantages over language-model-based generation for these outputs. They
are fast: assembly takes microseconds with no inference. They are correct: prices are computed
from the cart state, not hallucinated; quantity arithmetic is deterministic computation rather
than language model generation. They are consistent: the same situation produces the same
phrasing every time. They are natural Vietnamese: templates are written by a Vietnamese
speaker using natural waiter vocabulary and appropriate politeness levels, not translated from
English.

Two situations require language model generation because the content is too variable for
templates. Search results must be listed conversationally. The model receives the ranked dish
list with names, prices, and categories, and paraphrases it into natural Vietnamese: "Dạ,
quán mình có các món nước ấm: Lẩu Thái (250k), cay, chua; Lẩu Hải Sản (300k), ngọt, thanh.
Anh/chị muốn thử món nào ạ?" Free-form chat responses are open-ended and grounded
in the full conversation history, the cart, and the curated memory of previously discussed
dishes. Every other outcome, including the off-menu apology with its nearest-match suggestion,
is assembled from a template, because the dish name and the price it quotes come from the menu
data and there is nothing for the model to add beyond phrasing.

The language model used for response generation is the same Qwen2.5 14B Instruct instance that
serves the specialized agents, and configured with the same low temperature of 0.1. Response
generation does not need creative latitude: the wording may vary a little between turns, but
the facts it is verbalising are fixed, and a higher setting would only increase the chance of
the model drifting away from them. The model never invents
content. It receives only pre-verified structured data (dish names resolved against the menu,
prices computed from the menu data, quantities verified by the validator), and its job is to
reformat that data into conversational Vietnamese. The model does not decide what dishes
exist, what they cost, or what the customer ordered; it only decides how to say what has
already been verified.

Within each context type, an ordered set of conditions selects the path. Table 4.15 lists them
in the order they are tested; the first match produces the reply. Reading down the table shows
how narrow the model's role is: of the twenty outcomes a turn can reach, seventeen are
assembled from templates, and the model is called only for a search that returned dishes and
for open conversation. This hybrid approach, templates for deterministic outputs and the
language model for variable content, maximizes speed and correctness while maintaining
conversational flexibility where it is needed.

*Table 4.15. How a reply is chosen. Conditions are tested top to bottom within each context,
and the first one that matches wins.*

| Context | Condition | Reply |
|---------|-----------|-------|
| Order | Ambiguous items present | Template: ask which variant |
| | Off-menu item with a nearest match | Template: name it as unavailable, offer the match |
| | Off-menu item with no match | Template: plain rejection |
| | Tool reported an error | Template: convey the error |
| | Confirm order succeeded | Template: the order has gone to the kitchen |
| | Remove succeeded | Template: acknowledge, then echo the cart |
| | Clear succeeded | Template: acknowledge |
| | Otherwise, add succeeded | Template: echo the cart with prices and total |
| Search | Tool reported an error | Template: nothing suitable found |
| | No results | Template: not on the menu, offer to suggest something |
| | Results returned | **Model**, generated whole, checked against the retrieved dishes, then spoken sentence by sentence |
| Payment | Request without an amount, or an error | Template: apologise |
| | Request succeeded | Template: state the total, show the QR code |
| | Verification succeeded | Template: confirm the bill is settled |
| Chat | Delegated to review the cart | Template: echo the cart, or say it is empty |
| | Delegated as unclear | Template: ask the customer to repeat |
| | Greeting or thanks | Template: standard courtesy reply |
| | Dishes held in memory | **Model**, generated whole, checked, then spoken sentence by sentence |
| | Otherwise | **Model**, streamed token by token |
| Retry | Always | Template: apologise, quoting the validator's feedback |

The response generator supports sentence-by-sentence streaming to the voice pipeline on the
robot, but not every path streams in the same way, and the difference is deliberate. Open
conversation with nothing to verify is streamed token by token and split into sentences at
Vietnamese punctuation boundaries, so each sentence is emitted the moment it completes. A reply
that names dishes cannot be treated that way: grounding can only be judged on the finished
text, and a sentence already spoken cannot be recalled. Those replies are therefore generated
in full, checked against the dishes actually retrieved, and only then emitted sentence by
sentence. The cost is a slower first word on exactly the turns where a wrong dish name would
reach the customer. Template responses are emitted as a single event. The
streaming events flow through the server to the robot's voice pipeline, where the synthesis
engine plays sentences sequentially. Meanwhile, the customer's tablet receives the same stream
via the backend's voice bridge, displaying each sentence as it is spoken. This design means
the first spoken sentence reaches the customer while the response is still being generated,
rather than forcing the customer to wait for the full multi-sentence reply. The done event at
the end of the stream carries the full response text, the UI action command, and the
synchronized cart state, which the tablet uses to update its display after the last sentence
plays.
