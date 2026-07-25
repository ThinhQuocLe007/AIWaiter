## 4.5.7 Prompt Architecture

The prompt architecture addresses the gap identified in §2.4.7: prompt engineering
techniques for domain adaptation — system prompts, few-shot examples, dynamic context
injection, and DSPy optimization — are documented in the literature but untested on
Vietnamese restaurant ordering. No fine-tuning is used anywhere in the agent; all model
adaptation is achieved through prompting. The intent classifier (§4.5.2) is the exception
— it is a trained MLP that learns from synthetic data, but it uses a frozen bi-encoder
embedding, so only the lightweight classifier head is trained. Domain adaptation —
Vietnamese restaurant vocabulary, menu knowledge, the ordering workflow, and the
hospitality tone — is encoded in prompt files loaded at agent startup. The prompt
architecture is therefore a first-class design element, not an implementation detail.

### 4.5.7.1 Prompt File Inventory

Seven system prompts, five few-shot example sets, and three skill documents are stored
as editable text files — a menu change or a tone adjustment requires only editing the
files and restarting the agent, with no retraining and no code changes.

Each language-model-calling node has its own system prompt defining its role, reasoning
protocol, output format, and constraints. The router prompt specifies a four-step
reasoning protocol — check context, identify primary intent, check for sequential
intents, produce a structured output — with five intent categories and Vietnamese trigger
keywords. The order worker prompt defines cart CRUD rules, Vietnamese quantity patterns
("2 phần", "1 dĩa"), and modification handling ("ít cay", "thêm hành"). The search
worker prompt provides query rewriting instructions and non-food delegation triggers.
The response node uses two prompts: one for the waiter persona when paraphrasing search
results and off-menu suggestions, and one for open-ended conversational chat.

All system prompts are written in Vietnamese. This is an intentional design choice:
prompting the model in Vietnamese produces more natural Vietnamese output than prompting
in English and requesting Vietnamese output. The model's internal representations for
Vietnamese are activated more strongly when the prompt itself is in Vietnamese.

Five few-shot example sets are provided as static lists of utterance-to-action pairs,
injected into the prompts at runtime. The router examples include fourteen pairs covering
single-intent utterances across all four classes, multi-intent compound sentences such as
"Cho 2 Ốc Hương rồi tính tiền luôn," teencode abbreviations such as "ad," "vs," and "ck,"
and context-dependent short affirmations — "ok" at idle versus "ok" at awaiting
confirmation, teaching the model that the same word maps to different intents depending on
conversation state. The order worker examples cover single-item and multi-item additions,
items with modifiers and quantities, removals, clear-cart, confirm-order, and delegation.
The search worker examples cover keyword search, attribute-based search such as "món chay,"
price-based search, recommendation requests, and delegation for non-search queries.

Three skill documents define behavioral rules that are composed into prompts across
multiple nodes. The hospitality skill defines Vietnamese restaurant service etiquette —
greeting patterns, politeness levels, refusal phrasing, and upselling guidelines. The
menu grounding skill enforces that the agent must never claim knowledge of dishes not on
the menu and must search rather than invent when uncertain. The service boundary skill
defines what the agent should refuse to answer — inappropriate requests, unrelated
questions, and personal questions — with refusal templates: "Dạ, em chỉ biết về thực
đơn và quán ạ."

### 4.5.7.2 Dynamic Context Injection

Static prompts define behavior; dynamic context provides the specific situation the
language model must act on. Three forms of dynamic context are injected at runtime.

Conversation history is injected into the router, workers, and response node. The router
receives the last two user-assistant pairs, formatted as plain text, to enable
context-dependent classification — "ok" at awaiting confirmation is ORDER\_CONFIRM, but
at idle is CHAT. The workers receive the last three turns, including the error messages
from validation retries, so the language model sees its own prior failed attempt plus the
corrective feedback on retry. The response node for the chat path receives the full
conversation history, formatted as alternating customer and system messages.

The order stage is injected as a plain string — IDLE, DRAFTING, AWAITING\_CONFIRMATION,
or CONFIRMED — into the router and worker prompts. For the router, it is accompanied by
an explicit instruction: if the stage is awaiting confirmation, a short affirmation is
ORDER\_CONFIRM, not CHAT.

Validator feedback is injected into the worker's dynamic context on retry, preceded by
a header marking it as mandatory corrective information. The feedback names the specific
error and provides a correction instruction, enabling the language model to fix its
output without re-reasoning the entire utterance from scratch.

### 4.5.7.3 Prefix Caching

Ollama's attention key-value caching is exploited for latency reduction. The prompt
sequence is ordered so that all static content — the system prompt and few-shot examples
— appears at the beginning, followed by dynamic content such as conversation history,
cart state, and validation feedback at the end. Because the static prefix is identical
across all turns for the same worker, Ollama caches the attention key-value pairs for
that prefix. Only the dynamic suffix requires fresh computation each turn.

If dynamic content were interleaved with static content — for example, if the cart state
were injected between few-shot examples — the key-value cache would be invalidated for
all subsequent tokens, eliminating the latency benefit. The strict separation of static
and dynamic content preserves the cache.

### 4.5.7.4 Per-Stage Model Configuration

All three language-model-calling nodes use the same Qwen2.5 7B model instance, but each
stage configures it differently. The router — when the language model path is invoked for
utterance decomposition — uses temperature zero and structured output constrained to a
controlled set of intent labels, producing deterministic classification. The workers use
temperature 0.1 and forced tool choice, keeping tool selection near-deterministic while
allowing minor orthographic variation in tool arguments. The response node uses
temperature 0.3 and free-form generation, enabling varied Vietnamese phrasing for natural
conversation — safe because the model receives only pre-verified structured data as context,
eliminating hallucination risk.

A single Ollama model instance serves all three stages. Three client objects point to the
same model name with different runtime parameters. Ollama pins the model in GPU memory with
persistent keep-alive, so there is zero model-switching overhead between stages — the same
loaded model handles routing, decision, and response.

### 4.5.7.5 Design Principles

Seven principles govern the prompt architecture. All prompts are written in Vietnamese —
the model thinks in Vietnamese, not translated English. Every prompt that calls the
language model for classification or decision-making includes explicit numbered reasoning
steps. Few-shot examples are chosen to cover observed failure modes, not random utterances
— each example teaches a specific skill the model lacked in zero-shot testing. Static
content is positioned before dynamic content to maximize key-value cache reuse. Behavioral
rules are isolated in skill files and composed into prompts across nodes — changing the
waiter's tone or boundaries requires editing one file, not seven. The menu is excluded
from decision prompts — the language model only needs to decide which action to take and
extract what the customer said, with menu validation deferred to the deterministic
validator. No fine-tuning is used — all model adaptation is achieved through prompting,
eliminating the need for a labeled Vietnamese restaurant ordering dataset and enabling
rapid iteration where a prompt change takes effect at the next restart without retraining.
