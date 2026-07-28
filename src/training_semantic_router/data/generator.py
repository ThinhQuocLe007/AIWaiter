from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)

Intent = Literal["ORDER", "SEARCH", "PAYMENT", "CHAT"]
Style = Literal["formal", "casual", "dialect", "edge", "fragment"]

OUTPUT_DIR = Path(__file__).resolve().parent

# Vocabulary audit, 2026-07-23. The previous corpus (3,712 utterances) contained only 609
# unique tokens, because the generator echoes the lexicon of whatever appears in these
# definitions. Words absent from every example were absent from the whole corpus, and the
# classifier was confidently wrong on them at serving time -- "xoá hết giỏ hàng" was routed
# PAYMENT at confidence 0.998, having never seen "xoá" or "giỏ hàng" in training. Notably
# "tôi", the standard first-person pronoun, occurred zero times.
#
# The definitions below therefore name the vocabulary explicitly rather than leaving it to
# the generating model's sense of what sounds typical. When adding a capability to the agent,
# add its words here too, or the router will not learn them.
INTENT_DEFINITIONS: dict[Intent, str] = {
    "ORDER": (
        "ORDER — khách muốn gọi món hoặc thay đổi giỏ hàng: đặt, gọi, lấy, thêm, bớt, bỏ, "
        "xoá, xóa, huỷ, hủy, sửa, đổi, giảm số lượng, tăng số lượng, làm lại từ đầu, "
        "dọn sạch giỏ hàng, xác nhận đơn hàng, chốt đơn, lên đơn. "
        'Ví dụ: "cho 2 ốc hương", "tôi muốn gọi thêm 1 lẩu thái", "xác nhận đặt luôn", '
        '"bỏ món mực chiên đi em", "xoá hết giỏ hàng giúp mình", "xóa món ốc hương ra khỏi giỏ", '
        '"dọn giỏ hàng làm lại từ đầu", "giảm ốc hương xuống còn 1 phần", '
        '"thêm 1 bia nữa", "ok chốt đơn đi", "đổi món này qua món kia", "lên đơn giúp tôi". '
        "Bao gồm cả câu xác nhận ngắn: 'ừ', 'ok em', 'được', 'đúng rồi' "
        "(nếu đang trong ngữ cảnh chờ xác nhận đơn)."
    ),
    "SEARCH": (
        "SEARCH — khách hỏi thông tin: giá cả, món ăn, nguyên liệu, mùi vị, độ cay, "
        "thực đơn, menu, danh sách món, giờ mở cửa, khuyến mãi, wifi, nhà vệ sinh, "
        "chỗ đậu xe, best seller, món bán chạy, giao hàng, ship, khu vực giao (quận, phường). "
        'Ví dụ: "ốc hương giá bao nhiêu", "món này có cay không", '
        '"cho tôi xem menu", "cho mình xem thực đơn với", "quán có những món gì", '
        '"quán mình có món chay không", "có giao hàng không", "có ship về quận 7 không shop", '
        '"gợi ý món ngon đi em", "quán mở cửa tới mấy giờ", "món nào bán chạy nhất".'
    ),
    "PAYMENT": (
        "PAYMENT — khách muốn thanh toán, trả tiền, xin hóa đơn, hỏi phương thức "
        "thanh toán, tổng tiền, kiểm tra đã thanh toán chưa. "
        'Ví dụ: "tính tiền đi em", "cho anh xin hóa đơn", "tôi muốn thanh toán", '
        '"hết bao nhiêu tiền rồi", "thanh toán chuyển khoản được không", '
        '"cho xin mã qr", "quẹt thẻ được không em", "bill đi em", '
        '"kiểm tra giúp mình đã thanh toán chưa", "trả tiền mặt được không shop".'
    ),
    "CHAT": (
        "CHAT — khách chào hỏi, cảm ơn, tán gẫu, khen chê, phàn nàn, nói chuyện phiếm, "
        "hỏi về bản thân trợ lý, lạc đề. KHÔNG có hành động gọi món, hỏi menu, "
        "hay đòi thanh toán. "
        'Ví dụ: "xin chào em", "cảm ơn nhiều nha", "đồ ăn ngon quá", '
        '"món này mặn quá", "bạn là robot hay người thật vậy", '
        '"trời hôm nay mưa to thật", "quán đông ghê ha".'
    ),
}

STYLE_DESCRIPTIONS: dict[Style, str] = {
    "formal": (
        "Lịch sự, đầy đủ câu cú. Dùng kính ngữ 'ạ', 'dạ'. "
        'Ví dụ: "Cho em 2 phần Ốc Hương Xốt Trứng Muối ạ", '
        '"Dạ cho em hỏi quán mình có món chay không ạ?"'
    ),
    "casual": (
        "Nói chuyện bình thường hàng ngày, tự nhiên. Có thể nói trống không, "
        'rút gọn. Ví dụ: "cho 2 ốc hương đi em", "món ni cay hông", '
        '"tính tiền cho anh". Dùng giọng miền Nam/Nam Bộ tự nhiên.'
    ),
    "dialect": (
        "Biến thể địa phương: giọng miền Nam ('nghen', 'hông', 'dạ', 'dị', 'ghê'), "
        "miền Trung ('mô', 'tê', 'răng', 'rứa'), miền Bắc ('nhé', 'nhỉ', 'nhờ'). "
        'Ví dụ: "cho anh 2 phần ốc hương nghen", "món ni giá bao nhiêu rứa em", '
        '"tính tiền cho chị nhé". Kết hợp từ địa phương tự nhiên.'
    ),
    "edge": (
        "Câu cực ngắn, mơ hồ, một hai từ, khó phân loại nếu không có ngữ cảnh. "
        'Từ đệm, câu dở dang, ngập ngừng. Ví dụ: "ừ", "ok", "được", '
        '"để anh xem đã", "từ từ đi", "khoan đã", "cho anh... ừm...", '
        '"à mà thôi", "đúng rồi", "ok em". Đây là dạng KHÓ NHẤT để phân loại.'
    ),
    # Added 2026-07-23. At serving time a multi-clause utterance is split by the rewriter and
    # each fragment is classified on its own, but no fragment-shaped example existed in
    # training: every sample was a whole, polite, particle-bearing sentence. The fragments the
    # rewriter actually emits -- "Cho 1 Lẩu Thái", "Xoá hết giỏ hàng", "2 Bia Sài Gòn" -- were
    # therefore out of distribution, and multi-intent turns collapsed accordingly.
    "fragment": (
        "Mệnh đề rời được tách ra từ câu dài, KHÔNG phải câu hoàn chỉnh. "
        "Bỏ hết từ đệm lịch sự ('ạ', 'dạ', 'nha', 'nhé', 'em ơi'), bỏ chủ ngữ, "
        "chỉ giữ phần lõi mang ý định. Có thể chỉ là một cụm danh từ có số lượng. "
        'Ví dụ: "Cho 1 Lẩu Thái", "2 Bia Sài Gòn", "Xoá hết giỏ hàng", '
        '"Chốt đơn", "Thêm 1 bia nữa", "Cho xem menu", "Tính tiền", '
        '"Cho xin mã QR", "Bắt đầu lại với 1 lẩu thái", "Món nào bán chạy nhất". '
        "Độ dài điển hình 2–6 từ. Đây là dạng bộ phân loại gặp khi câu gốc có nhiều ý định."
    ),
}

SYSTEM_PROMPT_TEMPLATE = """Bạn là chuyên gia ngôn ngữ tiếng Việt, chuyên tạo dữ liệu huấn luyện cho AI phục vụ nhà hàng.

NHIỆM VỤ: Tạo {count} câu nói của khách hàng trong nhà hàng hải sản Việt Nam, với intent là "{intent}".

INTENT ĐỊNH NGHĨA:
{intent_def}

PHONG CÁCH:
{style_desc}

YÊU CẦU NGHIÊM NGẶT:
1. Đây là dữ liệu cho AI VOICE (giọng nói) — KHÔNG dùng teencode, viết tắt, chat slang. Khách HÀNG ĐANG NÓI, không gõ phím.
2. Mọi câu phải là tiếng Việt tự nhiên như người thật nói trong quán ăn.
3. Mỗi câu rõ ràng thuộc về intent "{intent}" — không mơ hồ giữa các intent.
4. INTENT ĐƠN — mỗi câu chỉ MỘT intent, không được gộp nhiều intent.
5. Đa dạng: dùng nhiều cách diễn đạt, nhiều tên món, nhiều cấu trúc câu khác nhau.
6. Tên món ăn: dùng tên món hải sản Việt Nam thực tế (ốc hương, hàu nướng, lẩu thái, cháo hàu, mì xào, gỏi xoài, tôm càng, sò điệp, nghêu hấp, cua rang me, bia, coca, trà tắc, trà đào, v.v.).
7. BẮT BUỘC ĐA DẠNG XƯNG HÔ — đây là yêu cầu quan trọng nhất về từ vựng.
   Phân bổ đại từ nhân xưng gần đều nhau trên toàn bộ {count} câu, KHÔNG được
   chỉ dùng "em"/"anh":
     - "tôi"  (trang trọng, trung tính)   — ít nhất 20% số câu
     - "mình" (thân mật)                  — ít nhất 15% số câu
     - "anh" / "chị" / "em"               — phần còn lại
     - xưng hô với quán: "shop", "quán", "nhà hàng", hoặc không xưng hô
   Một bộ dữ liệu chỉ có "em ơi cho anh..." sẽ khiến bộ phân loại hỏng khi khách
   dùng "tôi" hay "shop", vì những từ đó chưa từng xuất hiện lúc huấn luyện.
8. Đa dạng từ vựng hành động: với mỗi khái niệm hãy dùng nhiều từ đồng nghĩa
   (ví dụ xoá/xóa/bỏ/huỷ/hủy/dọn/loại bỏ; menu/thực đơn/danh sách món;
   tính tiền/thanh toán/trả tiền/hoá đơn/bill). Không lặp lại một từ duy nhất.
9. Trả về JSON array, mỗi phần tử có format chính xác bên dưới.

OUTPUT FORMAT (chỉ JSON, không markdown, không giải thích):
[
  {{"utterance": "<câu nói>", "intent": "{intent}", "style": "{style}", "notes": "<mô tả ngắn đặc điểm câu>"}}
]
"""


def _build_prompt(intent: Intent, style: Style, count: int) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        count=count,
        intent=intent,
        intent_def=INTENT_DEFINITIONS[intent],
        style=style,
        style_desc=STYLE_DESCRIPTIONS[style],
    )


def _call_gemini(prompt: str, api_key: str) -> list[dict[str, Any]]:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent"
    )
    resp = httpx.post(
        url,
        params={"key": api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.9, "topP": 0.95},
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_json_response(text)


def _call_ollama(prompt: str, model: str = "qwen2.5:7b-instruct") -> list[dict[str, Any]]:
    resp = httpx.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.9, "top_p": 0.95},
        },
        timeout=120,
    )
    resp.raise_for_status()
    text = resp.json()["response"]
    return _parse_json_response(text)


def _parse_json_response(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    text = text.strip()
    text = "".join(ch for ch in text if ord(ch) >= 32 or ch in "\n\r\t")
    if text.startswith("["):
        return json.loads(text)
    start = text.find("[")
    end = text.rfind("]") + 1
    if start != -1 and end > start:
        return json.loads(text[start:end])
    raise ValueError(f"Cannot parse JSON from response: {text[:200]}...")


# Strong lexical markers per intent. Used only to reject cross-labelled samples, never to
# label anything: the generating model writes the `intent` field itself, always echoing the
# one it was asked for, so the original `intent == expected_intent` check could not detect a
# semantic mismatch. A smoke test of 12 ORDER samples returned two that were plainly SEARCH
# and PAYMENT ("cho mình biết menu quán", "tính tiền cho tôi nha") -- 17% label noise going
# straight into training.
_INTENT_MARKERS: dict[Intent, tuple[str, ...]] = {
    # No generic request framing here ("cho tôi", "cho mình"): that construction is
    # intent-neutral -- "cho tôi xem menu" is SEARCH and "cho tôi thanh toán" is PAYMENT --
    # so counting it as an ORDER marker made every mislabelled sample look self-consistent
    # and defeated the check. Only genuinely order-specific verbs and objects belong here.
    "ORDER": (
        "gọi món", "đặt", "lấy", "thêm", "bớt", "bỏ", "xoá", "xóa", "huỷ", "hủy",
        "đổi", "sửa", "giảm", "tăng", "giỏ hàng", "chốt đơn", "lên đơn", "xác nhận",
        "làm lại", "dọn",
    ),
    "SEARCH": (
        "bao nhiêu", "giá", "có không", "menu", "thực đơn", "danh sách món", "món gì",
        "gợi ý", "bán chạy", "best seller", "mở cửa", "đóng cửa", "khuyến mãi", "wifi",
        "nhà vệ sinh", "đậu xe", "giao hàng", "ship", "cay không", "ngon không", "nguyên liệu",
    ),
    "PAYMENT": (
        "tính tiền", "thanh toán", "trả tiền", "hoá đơn", "hóa đơn", "bill", "mã qr", "quét mã",
        "chuyển khoản", "quẹt thẻ", "tiền mặt", "tổng tiền", "hết bao nhiêu tiền",
    ),
    "CHAT": (
        "xin chào", "chào", "cảm ơn", "cám ơn", "ngon quá", "mặn quá", "dở",
        "robot", "người thật", "thời tiết", "mưa", "nắng", "đông ghê", "tạm biệt",
    ),
}

# Politeness particles a genuine rewriter fragment would not carry.
_PARTICLES = ("nhé", "nha", "nghen", "ạ", "dạ", "em ơi", "anh ơi", "giúp em", "giùm em")


def _marker_hit(marker: str, utterance_low: str) -> bool:
    """Whether a marker occurs as whole word(s), not as a substring.

    Substring matching silently rejected correct samples: "giá" matches inside "Ốc Giác", so
    every order mentioning that dish looked like a price question and was thrown away. In a
    language written with spaces between syllables this failure mode is common enough that it
    measurably shrank the generated corpus before it was caught.
    """
    return re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", utterance_low) is not None


def _conflicting_intent(utterance: str, expected: Intent) -> Intent | None:
    """Return an intent whose markers dominate this utterance over the expected one.

    Deliberately conservative: a sample is only rejected when it carries markers of another
    intent and none of its own, so ordinary overlap ("chốt đơn" inside an ORDER sentence that
    also mentions a price) survives. The aim is to drop clear mislabels, not to police style.
    """
    low = utterance.lower()
    if any(_marker_hit(m, low) for m in _INTENT_MARKERS[expected]):
        return None
    for intent, markers in _INTENT_MARKERS.items():
        if intent != expected and any(_marker_hit(m, low) for m in markers):
            return intent
    return None


def _validate_record(record: dict, expected_intent: Intent, style: Style | None = None) -> bool:
    if not isinstance(record, dict):
        return False
    utterance = record.get("utterance", "")
    intent = record.get("intent", "")
    if not utterance or not isinstance(utterance, str):
        return False
    if len(utterance) < 1 or len(utterance) > 500:
        return False
    if intent != expected_intent:
        return False

    conflict = _conflicting_intent(utterance, expected_intent)
    if conflict:
        logger.debug("  reject %r: labelled %s but reads as %s", utterance, expected_intent, conflict)
        return False

    # Fragments are the input shape the rewriter produces. A "fragment" carrying politeness
    # particles or running past a clause length is a full sentence the model relabelled, and
    # keeping it would leave the fragment path as under-covered as it was before.
    if style == "fragment":
        low = utterance.lower()
        if any(p in low for p in _PARTICLES) or len(utterance.split()) > 8:
            logger.debug("  reject %r: not fragment-shaped", utterance)
            return False
    return True


def generate_batch(
    intent: Intent,
    style: Style,
    count: int,
    provider: Literal["gemini", "ollama"] = "gemini",
    api_key: str | None = None,
    model: str = "qwen2.5:7b-instruct",
    retries: int = 3,
) -> list[dict[str, Any]]:
    prompt = _build_prompt(intent, style, count)
    logger.info("Generating %d %s/%s examples via %s", count, intent, style, provider)

    for attempt in range(1, retries + 1):
        try:
            if provider == "gemini":
                if not api_key:
                    raise ValueError("GEMINI_API_KEY not set")
                records = _call_gemini(prompt, api_key)
            else:
                records = _call_ollama(prompt, model)

            valid = [r for r in records if _validate_record(r, intent, style)]
            if len(valid) >= count * 0.7:
                logger.info("  Got %d/%d valid records", len(valid), count)
                return valid
            logger.warning(
                "  Attempt %d: only %d/%d valid records, retrying...",
                attempt, len(valid), count,
            )
        except Exception as e:
            logger.warning("  Attempt %d failed: %s", attempt, e)
            if attempt < retries:
                time.sleep(2 * attempt)

    logger.error("All %d attempts failed for %s/%s", retries, intent, style)
    return []


def generate_all(
    counts: dict[Intent, int] | None = None,
    styles: list[Style] | None = None,
    provider: Literal["gemini", "ollama"] = "gemini",
    api_key: str | None = None,
    model: str = "qwen2.5:7b-instruct",
    output_path: Path | None = None,
) -> list[dict[str, Any]]:
    if counts is None:
        counts = {intent: 200 for intent in ["ORDER", "SEARCH", "PAYMENT", "CHAT"]}
    if styles is None:
        # "fragment" belongs in the default set, not as an opt-in: the rewriter splits
        # multi-clause utterances at serving time, so fragments are a routine input shape
        # rather than an exotic one. Leaving it out is what made multi-intent turns fail.
        styles = ["formal", "casual", "dialect", "edge", "fragment"]

    all_records: list[dict[str, Any]] = []
    output_path = Path(output_path) if output_path else OUTPUT_DIR / "synthetic_raw.json"

    for intent, total in counts.items():
        per_style = max(total // len(styles), 10)
        for style in styles:
            batch = generate_batch(
                intent=intent,
                style=style,
                count=per_style,
                provider=provider,
                api_key=api_key,
                model=model,
            )
            all_records.extend(batch)
            logger.info("Total so far: %d records", len(all_records))

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(all_records, f, ensure_ascii=False, indent=2)

    logger.info("Done. %d total records saved to %s", len(all_records), output_path)
    return all_records
