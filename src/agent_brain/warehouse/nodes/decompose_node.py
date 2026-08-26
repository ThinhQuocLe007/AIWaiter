"""Decomposer node — the LLM-as-parser tier for complex / compound / low-confidence turns.

Instead of answering a hard request directly, this node asks the LLM to **break it into a sequence
of simple, single-intent steps** that the deterministic workers already understand. Each step is a
plain Vietnamese command plus its intent, so the executor can run it through the existing workers
without re-classifying. This is what lets the brain "understand" compound requests ("lấy thùng bia
rồi mang về") while keeping execution fast and rule-based.

The LLM is only ever reached on this path (route() sends here on low MLP confidence or a detected
compound); the common single command never waits for it.
"""

from __future__ import annotations

import json
import re

from src.agent_brain.warehouse.services.llm_client import chat, STEP_SCHEMA
from src.agent_brain.warehouse.state import AgentState
from src.agent_brain.warehouse.types import Intent

_SYS = (
    "Bạn là bộ phân tích lệnh kho. Tách yêu cầu thành chuỗi các bước ĐƠN GIẢN, mỗi bước MỘT ý định.\n"
    "Chỉ dùng 5 loại ý định, định nghĩa NGHIÊM NGẶT:\n"
    "- navigate: đi tới / lấy (gắp) một mặt hàng, hoặc mang hàng về trạm đóng gói. "
    "Ví dụ: 'lấy thùng bia', 'đi tới khu A', 'mang về trạm đóng gói'. "
    "Lưu ý: lấy/mang/gắp LUÔN là navigate, KHÔNG phải motion.\n"
    "- answer: hỏi vị trí / tồn kho / thông tin hàng. Ví dụ: 'khu A có gì', 'thùng bia còn bao nhiêu'.\n"
    "- control: dừng / tiếp tục / hủy. Ví dụ: 'dừng lại'.\n"
    "- motion: CHỈ 'đi thẳng' / 'lùi' / 'quẹo trái' / 'quẹo phải'. KHÔNG dùng cho lấy/mang đi.\n"
    "- chat: trò chuyện thông thường (chào hỏi, cảm ơn).\n"
    "QUY TẮC:\n"
    "- CHỈ tạo bước cho điều người dùng THỰC SỰ yêu cầu. KHÔNG thêm bước xác nhận ('ok', 'xong'), "
    "KHÔNG tự bịa thêm di chuyển.\n"
    "- Mỗi 'text' là một câu lệnh tiếng Việt hoàn chỉnh, đủ để một worker thực thi.\n"
    "- Trả về DUY NHẤT mảng JSON: [{\"intent\":\"<loại>\",\"text\":\"<câu lệnh>\"}]. Không giải thích.\n"
    "VÍ DỤ:\n"
    "Người dùng: 'lấy thùng bia rồi mang về'\n"
    "→ [{\"intent\":\"navigate\",\"text\":\"lấy thùng bia\"},"
    "{\"intent\":\"navigate\",\"text\":\"mang về trạm đóng gói\"}]\n"
    "Người dùng: 'khu B có gì và khu C có gì'\n"
    "→ [{\"intent\":\"answer\",\"text\":\"khu B có gì\"},"
    "{\"intent\":\"answer\",\"text\":\"khu C có gì\"}]\n"
    "Người dùng: 'đi thẳng rồi quẹo trái'\n"
    "→ [{\"intent\":\"motion\",\"text\":\"đi thẳng\"},"
    "{\"intent\":\"motion\",\"text\":\"quẹo trái\"}]"
)


def _parse_steps(raw: str) -> list[dict] | None:
    """Tolerant extraction of the JSON step array from an LLM reply.

    Small models often emit *almost* valid JSON — the common failure here is swapping the final
    `]` and `}` (e.g. `[{...},{...text:"x"]}`), which `json.loads` rejects. We try the raw slice,
    then a few cheap bracket repairs, before giving up.
    """
    text = raw.strip()
    # Drop ```json … ``` fences if the model wrapped the output.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    start, end = text.find("["), max(text.rfind("]"), text.rfind("}"))
    if start == -1 or end == -1 or end <= start:
        return None
    cand = text[start:end + 1]

    repairs = [
        cand,
        cand.replace('"]}', '"}]'),   # the observed ]/} swap at the tail
        cand.replace("]}", "}]"),
    ]
    for attempt in repairs:
        try:
            data = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, list) or not data:
            continue
        out = []
        for step in data:
            if isinstance(step, dict) and "intent" in step:
                out.append({"intent": str(step["intent"]),
                            "text": str(step.get("text", "")).strip()})
            elif isinstance(step, str) and step.strip():
                # Model returned a bare string step — treat as a navigate command.
                out.append({"intent": "navigate", "text": step.strip()})
        if out:
            return out
    return None


def decompose_node(state: AgentState, model: str | None = None) -> dict:
    text = state["user_text"]
    steps: list[dict] | None = None
    raw: str | None = None
    try:
        raw = chat([
            {"role": "system", "content": _SYS},
            {"role": "user", "content": f"Yêu cầu: {text}"},
        ], model=model)
        steps = _parse_steps(raw)
    except Exception as e:  # noqa: BLE001 — decomposition failure must degrade, not crash the turn
        from src.agent_brain.utils import logger as log
        log.warning("decompose failed: %s", e)

    if not steps:
        # The LLM reply didn't parse into steps. Degrade gracefully:
        #  1) if the MLP router is trained, use its single-intent guess as one step;
        #  2) otherwise fall back to a single chat step so the turn still produces a reply.
        # Either way we never crash on a malformed LLM reply (and in this sandbox the router may
        # be untrained, so the MLP path must not be a hard dependency).
        if raw:
            from src.agent_brain.utils import logger as log
            log.warning("decompose: unparseable LLM reply: %s", raw[:400])
        try:
            from src.agent_brain.warehouse.nodes.mlp_router_node import classify
            intent, _ = classify(text)
            steps = [{"intent": intent.value, "text": text}]
        except Exception:
            steps = [{"intent": "chat", "text": text}]
        return {"plan": steps, "routed_to_planner": True, "raw_reply": raw}

    return {"plan": steps, "routed_to_planner": True}
