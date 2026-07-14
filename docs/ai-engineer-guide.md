# Working With AI Waiter as an AI Engineer

> **Purpose**: This document reframes AI Waiter from a *software project that calls an LLM* into an *AI engineering sandbox* — a platform for learning the skills that separate an application developer from an AI engineer.  
> **Audience**: You, the developer of this project, after realizing that integrating models is not the same as engineering them.  
> **Prerequisite reading**: `agent-brain-analysis.md` — the architectural deep-dive done from a code-quality perspective.

---

## Table of Contents

1. [The Mindset Shift](#1-the-mindset-shift)
2. [What Your Project Looks Like to an AI Engineer](#2-what-your-project-looks-like-to-an-ai-engineer)
3. [The AI Engineering Stack You're Missing](#3-the-ai-engineering-stack-youre-missing)
4. [Learning Path 1: From User to Builder (Fine-Tuning)](#4-learning-path-1-from-user-to-builder-fine-tuning)
5. [Learning Path 2: From Guessing to Measuring (Eval Science)](#5-learning-path-2-from-guessing-to-measuring-eval-science)
6. [Learning Path 3: From Writing to Optimizing (Prompt Engineering)](#6-learning-path-3-from-writing-to-optimizing-prompt-engineering)
7. [Learning Path 4: From One-Shot to Learning (Data Flywheel)](#7-learning-path-4-from-one-shot-to-learning-data-flywheel)
8. [Recommended Sequence](#8-recommended-sequence)
9. [The First 30 Days](#9-the-first-30-days)
10. [What "Done" Looks Like](#10-what-done-looks-like)
11. [Appendix: Skill Map](#11-appendix-skill-map)

---

## 1. The Mindset Shift

### Software Engineer Mindset (where you are now)

```
Problem: The LLM sometimes fails to produce a tool call.

Solution: Add retry logic in order_worker_node.py.
         → Layer 1: retry with text prompt
         → Layer 2: retry with Ollama native tool_choice
         → Layer 3: call Ollama HTTP API directly

Result: It works more often, but the root cause is still there.
        You built a workaround, not a fix.
```

### AI Engineer Mindset (where you want to be)

```
Problem: The LLM sometimes fails to produce a tool call.

Question: WHY does it fail?

Investigation:
  1. Tokenize the failing inputs. Which tokens trigger the failure?
  2. Check token probabilities. Is the model uncertain, or confidently wrong?
  3. Is it a prompt problem (bad instruction) or a model problem (capability gap)?
  4. If prompt: how can I optimize it systematically, not manually?
  5. If model: what data would I need to fine-tune it to fix this?
  6. How do I measure the improvement precisely?

Result: You understand the failure mode. You've measured it. You fix the root
        cause (better prompt OR better model). You can prove it got better.
```

### The Core Difference

| Software Engineer | AI Engineer |
|------------------|-------------|
| Treats the model as a **service** (like a database or API) | Treats the model as a **system to be improved** |
| Fixes problems **around** the model | Fixes problems **inside** the model |
| Measures: does it work? (binary) | Measures: how well does it work? (continuous, statistical) |
| Optimizes: code, architecture, latency | Optimizes: prompts, datasets, model weights, retrieval quality |
| Ships features | Ships improvements measured by eval metrics |
| Debugging: read logs, trace code | Debugging: analyze token probabilities, attention patterns, embedding distances |
| "The model returned an error" | "The model's calibration is 0.3 off — let me adjust the prompt scaffold" |

---

## 2. What Your Project Looks Like to an AI Engineer

### Your Current Stack (annotated honestly)

```
┌──────────────────────────────────────────────────────────┐
│  AI WORK DONE BY SOMEONE ELSE                            │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │ Ollama       │ │ Sentence-    │ │ faster-whisper   │  │
│  │ (gemma4)     │ │ Transformers │ │ (CTranslate2)    │  │
│  │ LLM hosting  │ │ Embeddings   │ │ STT model        │  │
│  └─────────────┘ └──────────────┘ └──────────────────┘  │
│  ┌─────────────┐                                        │
│  │ edge-tts    │                                        │
│  │ TTS model   │                                        │
│  └─────────────┘                                        │
│                                                         │
│  These are pre-trained models. You call them.           │
│  You did NOT train, fine-tune, or optimize them.        │
└──────────────────────────────────────────────────────────┘
                         │
                         │ .invoke() / .encode() / .transcribe()
                         ▼
┌──────────────────────────────────────────────────────────┐
│  YOUR WORK — Software Engineering                        │
│  ┌────────────────────────────────────────────────────┐  │
│  │ LangGraph StateGraph (10 nodes)                    │  │
│  │ FastAPI server (2 services)                        │  │
│  │ WebSocket real-time fan-out                        │  │
│  │ SQLite schema (plain sqlite3)                      │  │
│  │ Pydantic typed contracts                           │  │
│  │ Vue 3 + Pinia frontend                             │  │
│  │ ROS 2 robot integration                            │  │
│  │ Deterministic validator (string matching)          │  │
│  │ Makefile + uv build system                         │  │
│  └────────────────────────────────────────────────────┘  │
│                                                         │
│  This is well-structured, well-documented SWE.          │
│  But it's not AI engineering.                           │
└──────────────────────────────────────────────────────────┘
```

### Where the AI Engineering Work Lives

Everything **below** the `ChatOllama().invoke()` call. That's the gap:

```python
# Your code (agent_brain/agent/nodes/order_worker_node.py:119)
ai_msg = _llm.invoke(input_messages)   # ← This line. Everything after it
                                       #   reacts to what the model returned.
                                       #   Everything before it prepares the input.
                                       #
                                       # The AI engineering question is:
                                       # "How do I make THIS LINE return the right
                                       #  answer the FIRST time, every time?"
```

An AI engineer works in the **space between** message assembly and response parsing:

```
Your code:          build_prompt()  →  model.invoke()  →  parse_response()
                                                            ↑
AI engineer works here: ─────────────────────────────────────┘
  - Why did the model choose this output?
  - What would make it choose the correct one?
  - Can I change the model itself to make it better?
  - Can I change the prompt systematically?
  - How do I measure the improvement?
```

---

## 3. The AI Engineering Stack You're Missing

Every AI system has layers. Here's what you have vs what's missing:

```
Layer 7: Production Monitoring & Continuous Improvement  ❌ MISSING
  ↳ Model performance dashboards, drift detection, A/B testing

Layer 6: Data Collection & Curation Pipeline              ❌ MISSING
  ↳ Systematic dataset building, annotation, quality control

Layer 5: Fine-Tuning & Model Adaptation                   ❌ MISSING
  ↳ LoRA/QLoRA fine-tuning, instruction-tuning, RLHF

Layer 4: Prompt Optimization & Search                     ❌ MISSING
  ↳ DSPy, automatic few-shot selection, iterative prompt search

Layer 3: Evaluation & Measurement                         ❌ WEAK
  ↳ Statistical eval design, confidence intervals, regression testing
  ↳ You have: 14 router test cases, a few manual scripts

Layer 2: Retrieval & Knowledge Grounding                  ✅ DONE (basic)
  ↳ FAISS + BM25 + RRF fusion. Works. Could be optimized further.

Layer 1: Application Orchestration                        ✅ DONE WELL
  ↳ LangGraph, FastAPI, typed schemas, circuit breakers

Layer 0: Model Inference                                  ✅ DONE (via Ollama)
  ↳ You serve the model. You didn't build or train it.
```

**The gap**: Layers 3 through 7. That's where AI engineering happens. That's what separates someone who *uses* AI from someone who *builds* AI systems.

---

## 4. Learning Path 1: From User to Builder (Fine-Tuning)

### What You'll Learn

- How language models actually learn (gradient descent, loss functions, token prediction)
- What fine-tuning does vs prompt engineering (permanent weight changes vs ephemeral context)
- How to build a domain-specific training dataset
- LoRA/QLoRA — efficient fine-tuning that fits on consumer GPUs
- Evaluating before/after: did the model actually get better?

### Why This Project Is Perfect for It

You have a **narrow, well-defined task** with a **clear success metric**:

- Task: Given Vietnamese restaurant utterance → produce correct tool call + arguments
- Success metric: Did the tool get called? Were the arguments correct?
- You already have: a working pipeline (just swap the model), eval scenarios (extendable)

### Concrete Plan

#### Step 1: Build a Training Dataset (1 week)

You need 500-1000 examples in this format:

```jsonl
{"messages": [
  {"role": "system", "content": "Bạn là trợ lý gọi món. Trả về tool call chính xác."},
  {"role": "user", "content": "Cho em 2 phần ốc hương xốt trứng muối, không cay"},
  {"role": "assistant", "content": null, "tool_calls": [{"name": "add_cart", "arguments": {"items": [{"name": "Ốc Hương Xốt Trứng Muối", "quantity": 2, "special_requests": "không cay"}]}}]}
]}
```

**How to get 500-1000 examples without manual annotation:**

1. **Use your 9 few-shot examples** as seeds (already have them in `order_worker.json`)
2. **Generate variations with an LLM**: For each seed example, ask a cloud LLM (GPT-4o, Groq) to generate 20 variations — paraphrases, different wording, teencode, dialects, edge cases
3. **Filter with your validator**: Run generated examples through `deterministic_validator_node`. Keep only the ones where the ground-truth tool call passes validation (this ensures data quality)
4. **Add your eval scenarios**: The E2E scenario JSONs already contain user utterances + expected tools. Convert them to training format.
5. **Add negative examples**: Utterances that should NOT trigger a tool call (greetings, chitchat, ambiguous questions)
6. **Manual review**: Spot-check 50 examples. Fix any errors.

**Tools**: `unsloth` or `axolotl` for dataset management, `datasets` library (HuggingFace).

#### Step 2: Fine-Tune with LoRA (2-3 days)

```python
# Using Unsloth (simplest for beginners)
from unsloth import FastLanguageModel
import torch

# Load base model (qwen2.5-7b is a strong starting point)
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-7B-Instruct-bnb-4bit",
    max_seq_length=2048,
    load_in_4bit=True,
)

# Apply LoRA — only ~1% of weights are trainable
model = FastLanguageModel.get_peft_model(
    model,
    r=16,                    # LoRA rank — higher = more capacity, slower
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
)

# Train
from trl import SFTTrainer
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=2048,
)
trainer.train()

# Save
model.save_pretrained("ai-waiter-order-lora")
```

**Cost**: Free if you have an NVIDIA GPU with 8GB+ VRAM. Otherwise ~$2-5 on RunPod/Vast.ai for a few hours.

#### Step 3: Evaluate (1 day)

```python
# Run the same eval suite on both models
baseline_results = run_eval(base_model="qwen2.5:7b-instruct")
finetuned_results = run_eval(base_model="./ai-waiter-order-lora")

print(f"Baseline accuracy: {baseline_results.accuracy:.1%}")
print(f"Fine-tuned accuracy: {finetuned_results.accuracy:.1%}")
print(f"Improvement: {finetuned_results.accuracy - baseline_results.accuracy:.1%}")
```

**What you should see**: Fine-tuned model >90% tool call accuracy, vs ~60-80% for base model. The 3-tier retry in `order_worker_node.py` becomes unnecessary.

#### Step 4: Deploy (1 day)

```python
# Convert LoRA to GGUF for Ollama
# Option 1: Merge LoRA weights into base model, export as GGUF
# Option 2: Serve with vLLM (if you have GPU on server)

# Update .env
ORDER_WORKER_MODEL=ai-waiter-order-v1  # Your fine-tuned model
```

### What You Can Say After

"I fine-tuned a 7B model for Vietnamese restaurant tool calling. Built a 800-sample dataset from seed examples + LLM augmentation. Achieved 94% tool-call accuracy (baseline: 72%). Deployed via Ollama. Reduced per-turn latency by 60% by eliminating retry logic."

---

## 5. Learning Path 2: From Guessing to Measuring (Eval Science)

### What You'll Learn

- Statistical experiment design for AI systems
- Confidence intervals, statistical power, sample size calculation
- Per-class metrics (not just "accuracy")
- Calibration: does the model know when it's wrong?
- Regression testing as a deployment gate

### Why This Project Is Perfect for It

You have a **multi-component system** where each component needs different metrics:

| Component | What to Measure | Current State |
|-----------|----------------|---------------|
| Router (semantic + SLM) | Per-intent accuracy, F1, confidence calibration | 45 test cases in JSON |
| Search worker | Query rewrite quality, filter extraction F1 | 24 test cases in JSON |
| Order worker | Tool call accuracy, argument extraction F1 | E2E only (indirect) |
| Validator | False positive rate (rejecting valid), false negative (accepting invalid) | Not measured at all |
| Response node | Response quality, hallucination rate, politeness | Not measured at all |
| RAG (FAISS + BM25) | Recall@5, Precision@5, MRR, NDCG | 24 eval cases only |

### Concrete Plan

#### Step 1: Design Proper Eval Sets (1 week)

For each component, you need enough samples to detect meaningful change:

```python
# Sample size calculator — how many tests do I need?
import math
from scipy import stats

def required_samples(baseline_accuracy, minimum_detectable_effect, confidence=0.95, power=0.80):
    """
    Example: If baseline = 0.80 and I want to detect a 5% improvement:
    → 1,088 samples needed per variant
    """
    z_alpha = stats.norm.ppf(1 - (1 - confidence) / 2)
    z_beta = stats.norm.ppf(power)
    p = baseline_accuracy
    d = minimum_detectable_effect
    n = ((z_alpha + z_beta)**2 * p * (1-p)) / d**2
    return math.ceil(n)

# For your router:
# Baseline: ~80% accuracy (estimated)
# Want to detect: 5% improvement
# → Need: ~1,000 test cases per intent class
```

**How to get 1,000 router test cases:**

1. **Template generation**: Write 20 patterns per intent (`"Cho [quantity] [dish]"`, `"[dish] có [adjective] không?"`, etc.), fill with menu items (152 dishes × 20 patterns × variety of quantities/modifiers)
2. **LLM augmentation**: For each pattern, ask an LLM to generate 50 natural variations in Vietnamese, including teencode, dialect, and ambiguous forms
3. **Edge case mining**: From your `conversation_logger.py` JSONL logs, extract real user utterances that caused router failures
4. **Adversarial examples**: Generate near-boundary cases (ORDER vs CHAT, SEARCH vs CHAT)
5. **Human spot-check**: Verify 100 random samples. If error rate >5%, review more.

#### Step 2: Build Per-Component Metrics (3 days)

```python
# evals/metrics.py

from dataclasses import dataclass
from typing import Dict, List
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix

@dataclass
class RouterEvalResult:
    """Structured eval result for the router."""
    accuracy: float
    per_intent_f1: Dict[str, float]   # F1 per intent class
    semantic_hit_rate: float           # % routed by semantic (fast path)
    slm_fallback_rate: float           # % routed to SLM
    agreement_rate: float              # When both run, do they agree?
    avg_confidence_when_correct: float
    avg_confidence_when_wrong: float
    calibration_error: float           # Expected Calibration Error (ECE)
    confusion: np.ndarray              # Confusion matrix (intent x intent)
    latency_p50: float
    latency_p95: float

    @property
    def mean_f1(self) -> float:
        return np.mean(list(self.per_intent_f1.values()))

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

@dataclass
class OrderWorkerEvalResult:
    tool_call_accuracy: float          # % of turns where correct tool was called
    argument_name_f1: float            # F1 for item name extraction
    argument_quantity_mae: float       # Mean absolute error for quantity
    argument_special_request_f1: float # F1 for special request extraction
    false_positive_rate: float         # Called a tool when shouldn't
    false_negative_rate: float         # Didn't call tool when should
    avg_retries: float                 # Average number of retry attempts

@dataclass
class RetrievalEvalResult:
    recall_at_5: float
    recall_at_10: float
    precision_at_5: float
    mrr: float                          # Mean Reciprocal Rank
    ndcg_at_5: float                    # Normalized Discounted Cumulative Gain
    hit_rate_at_5: float               # % of queries with at least 1 relevant result
    avg_relevant_in_top5: float        # Average number of relevant items in top 5
```

#### Step 3: Build a Regression Test Runner (2 days)

```python
# evals/regression.py

import json
from pathlib import Path
from datetime import datetime

BASELINE_FILE = Path("evals/baselines/baseline-2026-07.json")
REGRESSION_THRESHOLD = 0.03  # 3% drop = regression

def load_baseline():
    with open(BASELINE_FILE) as f:
        return json.load(f)

def check_regression(current: dict, baseline: dict, threshold=REGRESSION_THRESHOLD):
    """Compare current metrics against baseline. Return regressions found."""
    regressions = []
    for metric_name, current_value in current.items():
        baseline_value = baseline.get(metric_name)
        if baseline_value is None:
            continue
        # For metrics where higher is better (accuracy, F1, recall)
        if 'accuracy' in metric_name or 'f1' in metric_name or 'recall' in metric_name:
            if current_value < baseline_value - threshold:
                regressions.append({
                    'metric': metric_name,
                    'baseline': baseline_value,
                    'current': current_value,
                    'drop': baseline_value - current_value,
                })
        # For metrics where lower is better (error rate, latency)
        if 'error' in metric_name or 'latency' in metric_name or 'retries' in metric_name:
            if current_value > baseline_value + threshold:
                regressions.append({
                    'metric': metric_name,
                    'baseline': baseline_value,
                    'current': current_value,
                    'increase': current_value - baseline_value,
                })
    return regressions

# Usage in CI:
# current = run_all_evals()
# regressions = check_regression(current, baseline)
# if regressions:
#     print(f"REGRESSION DETECTED: {len(regressions)} metrics dropped")
#     sys.exit(1)
```

#### Step 4: Measure Calibration (1 day)

```python
# Does the model know when it's confused?

def expected_calibration_error(confidences, accuracies, n_bins=10):
    """
    ECE: For each confidence bin (0-0.1, 0.1-0.2, ...), compute:
    |avg_confidence_in_bin - accuracy_in_bin|
    Perfect model: ECE = 0.0 (when model says 80% confident, it's right 80% of the time)
    """
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        in_bin = (confidences > bin_boundaries[i]) & (confidences <= bin_boundaries[i+1])
        if in_bin.sum() == 0:
            continue
        bin_conf = confidences[in_bin].mean()
        bin_acc = accuracies[in_bin].mean()
        ece += (in_bin.sum() / len(confidences)) * abs(bin_conf - bin_acc)
    return ece

# Example: your semantic router returns confidence scores.
# ECE > 0.15 → the model is overconfident. Adjust SOFTMAX_TEMPERATURE.
# ECE < 0.05 → well-calibrated. Trust the confidence scores.
```

### What You Can Say After

"I built a statistically rigorous evaluation pipeline for a multi-component Vietnamese conversational AI system. The router eval has 1,200 test cases across 5 intent classes (95% confidence, 3% MDE). Automated regression testing catches performance drops before deployment. Per-component metrics (F1, ECE, MRR) enable targeted improvement."

---

## 6. Learning Path 3: From Writing to Optimizing (Prompt Engineering)

### What You'll Learn

- That manual prompt writing is guesswork — optimization finds better prompts systematically
- DSPy: programmatic prompt optimization (declarative AI programming)
- Few-shot selection: which examples help the model most?
- Instruction optimization: what wording produces the best results?
- Iterative optimization loops: measure → improve → measure → improve

### Why This Project Is Perfect for It

You have 5 hand-written `.md` prompts. Each is a **hypothesis** about what instructions produce good behavior. Turn each into an **optimization target** with a measured score.

### Concrete Plan

#### Step 1: DSPy Setup (1 day)

```python
# Install DSPy
# pip install dspy-ai

import dspy

# Configure with your Ollama model
lm = dspy.OllamaLocal(model="qwen2.5:7b-instruct")
dspy.configure(lm=lm)

# Define the order worker task as a DSPy Signature
class OrderWorkerSignature(dspy.Signature):
    """
    Given a Vietnamese restaurant customer utterance and current cart state,
    produce the correct CRUD tool call (add_cart, remove_cart, clear_cart, or confirm_order).

    Rules:
    - "cho"/"thêm"/"lấy" → add_cart
    - "bỏ"/"hủy"/"thôi không lấy" → remove_cart
    - "hủy đơn" → clear_cart
    - "xác nhận"/"chốt đơn"/"ok" → confirm_order (only if cart has items and awaiting confirmation)
    - "đổi A thành B" → remove_cart(A) + add_cart(B)
    """
    utterance = dspy.InputField(desc="Customer's Vietnamese utterance")
    cart_state = dspy.InputField(desc="Current cart: items, quantities, order stage")
    tool_calls = dspy.OutputField(desc="JSON array of tool calls to execute")

# Load your eval data
order_trainset, order_devset, order_testset = load_order_eval_splits()
```

#### Step 2: Baseline Measurement (1 day)

```python
# Measure your hand-written prompt FIRST
baseline_program = dspy.ChainOfThought(OrderWorkerSignature)
# ^ DSPy will use the Signature's docstring as the system prompt by default

evaluate = dspy.Evaluate(
    devset=order_devset,
    metric=tool_call_exact_match,  # Your metric: did the right tool get called with right args?
    num_threads=1,
    display_progress=True,
)

baseline_score = evaluate(baseline_program)
print(f"Baseline (manual prompt): {baseline_score:.1%}")
```

#### Step 3: Optimize Few-Shot Examples (1 day)

```python
# DSPy automatically finds the best few-shot examples
from dspy.teleprompt import BootstrapFewShot

optimizer = BootstrapFewShot(
    metric=tool_call_exact_match,
    max_bootstrapped_demos=4,    # Try 4 few-shot examples
    max_labeled_demos=8,          # Select from up to 8 labeled examples
)

optimized_program = optimizer.compile(
    baseline_program,
    trainset=order_trainset,
)

optimized_score = evaluate(optimized_program)
print(f"Optimized few-shot: {optimized_score:.1%}")
print(f"Improvement: {optimized_score - baseline_score:.2%}")
```

#### Step 4: Optimize Instructions (1 day)

```python
# DSPy can also optimize the instruction text itself
from dspy.teleprompt import BootstrapFewShotWithRandomSearch

optimizer = BootstrapFewShotWithRandomSearch(
    metric=tool_call_exact_match,
    num_candidate_programs=10,    # Try 10 different prompt variations
    num_threads=4,
)

best_program = optimizer.compile(
    baseline_program,
    trainset=order_trainset,
)

# Inspect what DSPy learned
print("Optimized prompt:")
print(best_program.extended_signature.instructions)

best_score = evaluate(best_program)
print(f"Optimized prompt + few-shot: {best_score:.1%}")
print(f"Total improvement: {best_score - baseline_score:.2%}")
```

#### Step 5: Save and Deploy the Optimized Prompt (0.5 day)

```python
# Save the optimized prompt
best_program.save("evals/optimized_prompts/order_worker_v1.json")

# The optimized prompt becomes your new system_prompts/order_worker_agent.md
# No code changes needed — just swap the prompt file.
```

### What You Can Say After

"I used DSPy to automatically optimize prompts for a Vietnamese restaurant ordering agent. Bootstrap few-shot selection improved tool-call accuracy from 78% to 86%. Instruction optimization via random search pushed it to 91%. The entire optimization ran overnight with no manual prompt editing required."

---

## 7. Learning Path 4: From One-Shot to Learning (Data Flywheel)

### What You'll Learn

- Production ML: systems that improve from usage data
- Data curation: turning raw logs into training examples
- Failure analysis: clustering and categorizing model mistakes
- Continuous improvement: monthly fine-tuning cycles
- MLOps basics: model registry, deployment, rollback

### Why This Project Is Perfect for It

You already have `conversation_logger.py` writing JSONL. You have a restaurant that (in theory) generates real customer interactions. Every customer session is training data waiting to be captured.

### Concrete Plan

#### Step 1: Structured Logging (3 days)

Enhance `conversation_logger.py` to capture everything needed for training:

```python
# conversations/{date}/{session_id}.jsonl
{
  "session_id": "sess_abc123",
  "table_id": "T3",
  "turn": 5,
  "timestamp": "2026-07-14T19:32:15Z",
  
  "input": {
    "user_utterance": "Cái đó có cay không em?",
    "asr_confidence": 0.94,          # STT confidence
    "vad_duration_ms": 3200,         # How long they spoke
  },
  
  "routing": {
    "decided_by": "SEMANTIC",
    "predicted_intent": "SEARCH",
    "confidence": 0.72,
    "all_similarities": {"SEARCH": 0.72, "CHAT": 0.45, "ORDER": 0.12, ...}
  },
  
  "execution": {
    "worker": "search_worker",
    "tool_called": "search",
    "tool_args": {"query": "cái đó", "max_price": null, ...},
    "tool_status": "success",
    "num_results": 0,
    "retry_count": 0,
    "validation_passed": true
  },
  
  "output": {
    "ai_response": "Dạ, cái đó không có trong thực đơn của quán mình ạ...",
    "response_type": "SEARCH",       # Which rewriter branch was used
    "ui_action": null,
    "latency_total_ms": 2340,
    "latency_breakdown": {
      "router_ms": 320,
      "worker_ms": 1200,
      "validator_ms": 45,
      "tools_ms": 180,
      "response_ms": 520
    }
  },
  
  "outcome": {
    "user_next_action": "rephrase",  # What did the user do next?
    "was_successful": false,         # Did the system handle it correctly?
    "failure_category": "reference_resolution",  # Why did it fail?
    "notes": "User had to repeat with explicit dish name in turn 6"
  }
}
```

#### Step 2: Automatic Failure Detection (2 days)

```python
# Auto-label failures without human review

def detect_failures(log_entry: dict) -> Optional[str]:
    """Heuristic failure detection from conversation log signals."""
    
    # Signal 1: Retry loop — validator rejected the tool call
    if log_entry["execution"]["retry_count"] > 0:
        return "validator_rejected"
    
    # Signal 2: User immediately repeats/rephrases (next turn is similar)
    if log_entry["outcome"]["user_next_action"] == "rephrase":
        return "misunderstanding"
    
    # Signal 3: Tool returned error status
    if log_entry["execution"]["tool_status"] == "error":
        return "tool_error"
    
    # Signal 4: Router was uncertain (went to SLM, low confidence)
    if (log_entry["routing"]["decided_by"] == "SLM" and 
        log_entry["routing"]["confidence"] < 0.5):
        return "router_uncertain"
    
    # Signal 5: Search with specific query returned empty
    if (log_entry["execution"]["tool_called"] == "search" and
        log_entry["execution"]["num_results"] == 0 and
        not is_generic_reference(log_entry["input"]["user_utterance"])):
        return "search_zero_results"
    
    # Signal 6: Response has less than 3 words (likely fallback/error)
    if len(log_entry["output"]["ai_response"].split()) < 3:
        return "minimal_response"
    
    return None  # Looks successful

# After 1 week of logging:
# failures_by_category = group failures
# → "reference_resolution: 34%", "validator_rejected: 22%", "search_zero: 18%", ...
```

#### Step 3: Monthly Fine-Tuning Cycle (ongoing)

```
Week 1: Collect logs → detect failures → sample 200 hardest examples
Week 2: Human review the 200 → fix any → add to training dataset
Week 3: Fine-tune model on expanded dataset
Week 4: Run eval suite → if improvement >2% → deploy → else → keep investigating
```

#### Step 4: Dashboard (2 days)

```python
# Simple metrics dashboard showing:
# - Daily: number of turns, success rate, avg latency
# - Weekly: top 3 failure categories, trend line
# - Monthly: model version comparison, improvement over time

# Export to a simple HTML page or Streamlit app
```

### What You Can Say After

"I built a data flywheel for a production Vietnamese conversational AI system. Automated failure detection categorizes 2,000+ daily interactions. Monthly fine-tuning cycles on curated failure examples have improved tool-call accuracy from 78% to 94% over 4 months. The system improves without manual engineering effort."

---

## 8. Recommended Sequence

You cannot do everything at once. Here's the learning order:

```
Phase 1: EVAL PIPELINE (Path 2)           ← Start here. Everything depends on it.
  │  Duration: 2-3 weeks
  │  Why first: You can't improve what you can't measure. Every other path
  │             requires a reliable eval framework to know if you're getting better.
  │
  ▼
Phase 2: PROMPT OPTIMIZATION (Path 3)     ← Quickest ROI. No GPU needed.
  │  Duration: 1-2 weeks
  │  Why second: DSPy gives you measurable wins fast. You'll learn how to
  │             think about prompts as optimization targets, not prose.
  │
  ▼
Phase 3: FINE-TUNING (Path 1)             ← The big one. This is where you
  │  Duration: 2-3 weeks                   become an AI engineer, not just a user.
  │  Why third: You need good evals (Phase 1) to measure improvement and good
  │             prompts (Phase 2) as a baseline to beat. Fine-tuning without
  │             evals is blind. Fine-tuning without a good baseline is wasteful.
  │
  ▼
Phase 4: DATA FLYWHEEL (Path 4)           ← Production maturity.
     Duration: Ongoing
     Why last: You need the eval pipeline, optimized prompts, and a fine-tuned
               model before you can build a system that improves itself.
```

### Why This Order

Each phase builds on the previous:

| Phase | Produces | Used By |
|-------|----------|---------|
| Phase 1 (Evals) | Reliable metrics, baseline scores, regression detection | Phases 2, 3, 4 |
| Phase 2 (DSPy) | Optimized prompts, few-shot selection methodology | Phase 3 (baseline to beat) |
| Phase 3 (Fine-tune) | Custom model, training dataset, LoRA expertise | Phase 4 (model to improve) |
| Phase 4 (Flywheel) | Automated improvement, production monitoring | (self-reinforcing) |

---

## 9. The First 30 Days

Here's a concrete day-by-day plan for Phase 1 (Eval Pipeline):

### Week 1: Router Eval

```
Day 1-2: Design router test case templates
  - 5 intents × 20 utterance patterns each = 100 templates
  - Cover: standard forms, teencode, dialect, ambiguous, multi-intent
  
Day 3-4: Generate test cases
  - Use script to fill templates with menu items
  - Use LLM to generate natural variations
  - Target: 250-300 cases per intent = ~1,200 total
  - Manual spot-check 50 random cases
  
Day 5: Build eval runner
  - Run each case through hybrid_router_node
  - Record: predicted intent, decided_by, confidence, latency
  - Output: confusion matrix, per-intent F1, ECE score
```

### Week 2: Retrieval + Order Worker Eval

```
Day 6-7: Retrieval eval
  - Expand from 24 to 100+ test queries
  - Include: exact matches, fuzzy matches, category queries, vibe queries
  - Measure: Recall@5, Precision@5, MRR, NDCG
  - Compare: BM25 only vs FAISS only vs RRF fusion
  
Day 8-9: Order worker eval
  - Extract from E2E scenarios: user utterances → expected tool calls
  - Generate 200+ additional cases from templates
  - Measure: tool_call_accuracy, argument extraction F1, retry rate
  
Day 10: Baseline document
  - Compile all metrics into one report
  - Save as evals/baselines/baseline-YYYY-MM.json
  - This becomes your measurement anchor
```

### Week 3: Automation

```
Day 11-12: Regression test script
  - Load baseline, run all evals, compare
  - Exit non-zero if any metric drops >3%
  
Day 13-14: CI integration
  - GitHub Actions workflow
  - Runs on PR to src/agent_brain/, evals/
  - Blocks merge if regression detected
  
Day 15: Write up findings
  - Document: what did you learn from the proper evals?
  - Which component is the weakest? Where should Phase 2 focus?
```

---

## 10. What "Done" Looks Like

### You've completed the AI engineering journey when:

**Phase 1 (Evals)** — Done when:
- [ ] Router eval: 1,000+ test cases, per-intent F1 > 0.85
- [ ] Retrieval eval: 100+ queries, NDCG@5 measured and tracked
- [ ] Order worker eval: 200+ cases, tool-call accuracy measured per tool type
- [ ] Regression test script blocks deployment if metrics drop >3%
- [ ] Baseline document committed to repo

**Phase 2 (Prompt Optimization)** — Done when:
- [ ] DSPy-optimized order worker prompt beats hand-written by >5% accuracy
- [ ] DSPy-optimized search worker prompt improves query rewrite quality
- [ ] Optimized few-shot selection replaces hand-picked examples
- [ ] All optimized prompts saved with their eval scores

**Phase 3 (Fine-Tuning)** — Done when:
- [ ] Training dataset: 800+ Vietnamese restaurant tool-calling examples
- [ ] Fine-tuned model: tool-call accuracy >90% (baseline: ~75%)
- [ ] 3-tier retry code in order_worker_node.py REMOVED (model is reliable)
- [ ] Fine-tuned model deployed, eval scores documented
- [ ] Dataset published on HuggingFace (optional but impactful)

**Phase 4 (Data Flywheel)** — Done when:
- [ ] Structured conversation logging captures all turn metadata
- [ ] Automatic failure detection categorizes 80%+ of failures
- [ ] Monthly fine-tuning cycle: collect → curate → train → evaluate → deploy
- [ ] 6-month accuracy trend: steady improvement (not plateau)
- [ ] Dashboard shows daily/weekly/monthly metrics

---

## 11. Appendix: Skill Map

### What You Know Now (Software Engineer)

```
✅ Backend development (FastAPI, WebSockets, SQLite)
✅ Frontend development (Vue 3, Pinia, PrimeVue)
✅ System architecture (distributed multi-role)
✅ CI/CD, build systems (Makefile, uv, npm)
✅ Type-safe design (Pydantic, TypeScript)
✅ ROS 2 integration
✅ Documentation
```

### What You'll Know After Phase 1 (Eval Engineer)

```
✅ Statistical experiment design
✅ Sample size calculation, confidence intervals
✅ Per-class metrics (F1, precision, recall)
✅ Calibration metrics (ECE, reliability diagrams)
✅ Regression testing as deployment gate
✅ Confusion matrix analysis
✅ Metric-driven development
```

### What You'll Know After Phase 2 (Prompt Engineer)

```
✅ DSPy — declarative AI programming
✅ Automatic few-shot example selection
✅ Instruction optimization via search
✅ Iterative prompt refinement with measured feedback
✅ KV-cache optimization for latency
✅ Prompt versioning and A/B testing
```

### What You'll Know After Phase 3 (Model Engineer)

```
✅ LoRA/QLoRA fine-tuning theory and practice
✅ Dataset curation and quality control
✅ Training loop mechanics (loss curves, learning rates, overfitting detection)
✅ Model evaluation: train/dev/test split strategy
✅ GGUF export and Ollama deployment
✅ GPU memory management for training
```

### What You'll Know After Phase 4 (MLOps Engineer)

```
✅ Production data collection pipelines
✅ Automated failure detection and categorization
✅ Continuous training cycles
✅ Model versioning and rollback
✅ Metrics dashboards
✅ Data flywheel architecture
```

---

## Final Note

This project is a rare gift: a **fully working, well-architected AI application** where you can see every layer. Most AI engineers work on one tiny piece (eval, training, or inference) of a much larger system they can't fully understand. You built the whole thing. Now you get to go deep into each layer.

The SWE work isn't wasted — it's the **scaffolding that makes the AI work possible**. Without solid SWE, you can't run evals (no test infrastructure), can't fine-tune (no data pipeline), can't deploy (no serving infrastructure). You've done the prerequisite. Now start at Phase 1.
