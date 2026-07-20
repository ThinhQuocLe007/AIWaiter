from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)

Intent = Literal["ORDER", "SEARCH", "PAYMENT", "CHAT"]
Style = Literal["formal", "casual", "dialect", "edge"]

OUTPUT_DIR = Path(__file__).resolve().parent

INTENT_DEFINITIONS: dict[Intent, str] = {
    "ORDER": (
        "ORDER — khách muốn gọi món: đặt, thêm, bỏ, sửa, hủy món, xác nhận đơn hàng, "
        'chốt đơn. Ví dụ: "cho 2 ốc hương", "xác nhận đặt luôn", "bỏ món mực chiên đi em", '
        '"thêm 1 bia nữa", "ok chốt đơn đi", "đổi món này qua món kia". '
        "Bao gồm cả câu xác nhận ngắn: 'ừ', 'ok em', 'được', 'đúng rồi' "
        "(nếu đang trong ngữ cảnh chờ xác nhận đơn)."
    ),
    "SEARCH": (
        "SEARCH — khách hỏi thông tin: giá cả, món ăn, nguyên liệu, mùi vị, độ cay, "
        'thực đơn, giờ mở cửa, khuyến mãi, wifi, nhà vệ sinh, best seller. '
        'Ví dụ: "ốc hương giá bao nhiêu", "món này có cay không", '
        '"quán mình có món chay không", "có giao hàng không", '
        '"gợi ý món ngon đi em", "quán mở cửa tới mấy giờ".'
    ),
    "PAYMENT": (
        "PAYMENT — khách muốn thanh toán, trả tiền, xin hóa đơn, hỏi phương thức "
        'thanh toán, tổng tiền. Ví dụ: "tính tiền đi em", "cho anh xin hóa đơn", '
        '"hết bao nhiêu tiền rồi", "thanh toán chuyển khoản được không", '
        '"cho xin mã qr", "quẹt thẻ được không em", "bill đi em".'
    ),
    "CHAT": (
        "CHAT — khách chào hỏi, cảm ơn, tán gẫu, khen chê, nói chuyện phiếm, "
        "lạc đề. KHÔNG có hành động gọi món, hỏi menu, hay đòi thanh toán. "
        'Ví dụ: "xin chào em", "cảm ơn nhiều nha", "đồ ăn ngon quá", '
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
7. Trả về JSON array, mỗi phần tử có format chính xác bên dưới.

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


def _validate_record(record: dict, expected_intent: Intent) -> bool:
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

            valid = [r for r in records if _validate_record(r, intent)]
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
        styles = ["formal", "casual", "dialect", "edge"]

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
