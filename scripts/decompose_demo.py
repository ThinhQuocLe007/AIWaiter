#!/usr/bin/env python3
"""Decompose-path smoke test — runs ~10 warehouse utterances through the real `decompose_node`
(Qwen 7B via Ollama) and prints the step breakdown, so we can eyeball whether the LLM-as-parser
splits compound / complex requests the way we want.

Runs WITHOUT the embedding/MLP stack (decompose_node is import-light) — only needs a reachable
OpenAI-compatible LLM. Point it at Qwen 7B with the LLM_MODEL env var or your .env.

    uv run python scripts/decompose_demo.py            # uses settings.llm_model
    LLM_MODEL=qwen2.5:7b uv run python scripts/decompose_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent_brain.warehouse.nodes.decompose_node import decompose_node
from src.agent_brain.warehouse.services.llm_client import chat as _probe

SCENARIOS = [
    "lấy thùng bia rồi mang về",                                  # fetch + deliver
    "khu B có gì và khu C có gì",                                  # two answers
    "đi tới khu A lấy hộp xanh rồi quẹo phải",                     # navigate + motion
    "thùng bia còn bao nhiêu rồi dẫn tôi đến đó",                   # answer + navigate
    "dừng lại, lấy thùng nước, rồi tiếp tục",                      # control + navigate + control
    "kiểm tra khu A thiếu đồ gì và báo cái nào gần khu B nhất",    # two answers
    "lấy mì tôm mang về trạm đóng gói",                            # single fetch (should be 1 step)
    "chào bạn, khu C để mặt hàng gì",                               # chat + answer
    "đi thẳng rồi quẹo trái tới kệ đỏ khu B",                      # motion + navigate
    "nếu khu A hết bia thì dẫn tôi đi khu B",                      # conditional reasoning
]


def main() -> int:
    model = os.environ.get("LLM_MODEL") or os.environ.get("DECOMPOSE_MODEL")
    # Probe the endpoint so a missing Ollama fails loudly here, not mid-loop.
    print(f"LLM model : {model or '(settings default)'}")
    try:
        _probe([{"role": "user", "content": "ping"}], model=model, max_tokens=4)
        print("LLM       : reachable\n")
    except Exception as e:  # noqa: BLE001
        print(f"LLM       : UNREACHABLE ({e})\n")
        print("Start Ollama with Qwen 7B, e.g.  ollama pull qwen2.5:7b && ollama serve")
        return 1

    for i, text in enumerate(SCENARIOS, 1):
        print("=" * 70)
        print(f"[{i:02d}] {text}")
        try:
            out = decompose_node({"user_text": text}, model=model)
            plan = out.get("plan") or []
            if not plan:
                print("   (no plan produced)")
                continue
            for j, step in enumerate(plan, 1):
                print(f"    {j}. [{step.get('intent'):8}] {step.get('text')}")
            if out.get("raw_reply"):
                print(f"    ~~ raw LLM (unparsed): {out['raw_reply'][:200]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"   ERROR: {e}")

    print("=" * 70)
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
