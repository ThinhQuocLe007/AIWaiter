"""Build an enriched, balanced training set for the warehouse intent router.

The current `intents.json` is hand-written and narrow: 98 `answer` rows dominated by the same
~20 product names, with `control` (33) and `chat` (27) badly under-represented. That imbalance
hurts exactly the intents that matter most for safety (stop/cancel) and for UX (chat). It also
lacks *hard negatives*: near-identical phrasings that must route to DIFFERENT intents
("bột mì ở đâu" -> answer vs "đi lấy bột mì" -> navigate), which is the router's hardest failure
mode. Real edge-voice input also arrives noisy (STT tone slips, truncated speech, informal
Vietnamese), none of which the curated set covers.

This script:
  1. loads the existing curated `intents.json` (never throws away human curation),
  2. augments every curated row with STT-style noise (tone stripping, light phoneme swaps) so the
     MLP sees the messy text it will actually classify,
  3. generates template-based utterances grounded in the real warehouse vocab (sections A/B/C,
     named places, inventory products),
  4. injects hard-negative near-duplicate pairs across intents,
  5. rebalances to a target per-intent budget (oversampling minorities via noise, not dupes),
  6. de-duplicates, shuffles, and writes the merged `intents.json`.

Run: `uv run python scripts/build_router_dataset.py`
"""

from __future__ import annotations

import json
import random
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "src" / "agent_brain" / "warehouse" / "router" / "intents.json"

SEED = 42
TARGET_PER_INTENT = {"answer": 130, "navigate": 110, "control": 90, "chat": 80}

PRODUCTS = [
    "bột mì", "gạo", "đường", "đường thốt nốt", "bột ngọt", "bột năng", "mì tôm",
    "thùng bia", "nước ngọt", "trà xanh", "muối", "tương ớt", "dầu ăn", "dầu dừa",
    "nước mắm", "cà phê", "sữa", "bánh quy", "hạt điều", "tôm khô",
]
SECTIONS = ["khu A", "khu B", "khu C"]
PLACES = ["trạm đóng gói", "trạm sạc"]


# --------------------------------------------------------------------------- #
# STT-style noise                                                             #
# --------------------------------------------------------------------------- #
_TONE_MARKS = dict.fromkeys(
    "\u0300\u0301\u0303\u0309\u0323"
)  # combining gravis / acute / tilde / hook / dot


def strip_tones(text: str) -> str:
    """Simulate a tone-deaf STT hypothesis (e.g. 'bột mì ở đâu' -> 'bot mi o dau')."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if c not in _TONE_MARKS)


# Common Vietnamese phoneme confusions in speech recognition.
_PHONEME_SWAPS = [
    (r"\bp(?:h)?(?:á|à|ạ|ả|a|ã)", "ba"),  # ph->b start
    (r"\b(?:x|s)(?:á|à|ạ|ả|a|ã)", "sa"),  # s/x start
    (r"\btr", "ch"),                        # tr->ch
    (r"\b(?:r|d)(?:á|à|ạ|ả|a|ã)", "da"),    # r/d start
]


def phoneme_noise(text: str, rng: random.Random) -> str:
    for pat, repl in _PHONEME_SWAPS:
        if rng.random() < 0.5 and re.search(pat, text):
            text = re.sub(pat, repl, text, count=1)
    return text


def noisy(text: str, rng: random.Random) -> str:
    """Occasionally degrade a clean utterance the way STT would."""
    if rng.random() < 0.45:
        text = strip_tones(text)
    if rng.random() < 0.2:
        text = phoneme_noise(text, rng)
    # occasional trailing filler / truncation
    if rng.random() < 0.1:
        text = rng.choice([text + " nghen", text + " nha", text.rstrip(" ơi")])
    return text


# --------------------------------------------------------------------------- #
# Template generators (clean, realistic Vietnamese)                           #
# --------------------------------------------------------------------------- #
def _answer_rows() -> list[str]:
    rows: list[str] = []
    for p in PRODUCTS:
        rows += [
            f"{p} ở đâu",
            f"cho tôi biết vị trí {p}",
            f"{p} để {random.choice(SECTIONS)}",
            f"tìm giúp tôi {p}",
            f"{p} nằm lối mấy",
            f"ngăn nào chứa {p}",
            f"{p} còn bao nhiêu",
            f"tồn kho {p} bao nhiêu",
            f"kiểm tra số lượng {p}",
            f"{p} còn không",
            f"{p} hết chưa",
            f"màu gì của {p}",
            f"{p} thuộc khu nào",
            f"báo tồn kho {p} giúp tôi",
            f"còn lại bao nhiêu {p}",
        ]
    for s in SECTIONS:
        rows += [
            f"{s} để mặt hàng nào",
            f"{s} có gì",
            f"trong {s} có những gì",
            f"{s} chứa hàng gì",
        ]
    rows += [
        "kho còn mặt hàng gì",
        "tổng tồn kho bao nhiêu",
        "mã vạch của thùng bia là gì",
        "nhà cung cấp bột mì là ai",
        "bảo quản dầu ăn thế nào",
        "hàng sắp hết là những gì",
        "khu nào gần trạm sạc nhất",
    ]
    return rows


def _navigate_rows() -> list[str]:
    """Residual navigation: move verb + item/place, WITHOUT an explicit section/place token
    that the rule layer would already catch (those are kept as a backup below)."""
    rows: list[str] = []
    for p in PRODUCTS:
        rows += [
            f"đi lấy {p}",
            f"mang {p} về đây",
            f"đưa tôi {p}",
            f"lấy {p} ra",
            f"tới chỗ {p}",
            f"dẫn tôi đi lấy {p}",
            f"robot đi lấy {p} giùm",
            f"gọi {p} cho tôi",
            f"bốc {p} lên xe",
        ]
    for s in SECTIONS:
        rows += [
            f"đi tới {s}",
            f"dẫn tôi ra {s}",
            f"di chuyển đến {s}",
            f"chạy tới {s} đi",
        ]
    for pl in PLACES:
        rows += [
            f"đi ra {pl}",
            f"tới {pl}",
            f"dẫn tôi đến {pl}",
        ]
    rows += [
        "đi lấy hàng rồi mang về",
        "robot ơi đi lấy giúp tôi cái bia",
        "thử đi lấy hộ tôi bịch muối",
    ]
    return rows


def _control_rows() -> list[str]:
    return [
        "dừng lại", "dừng ngay lại", "đứng lại", "ngừng lại", "ngưng ngay",
        "dừng yên", "dừng ở đó", "dừng xe lại", "khoan đã", "khoan cái đã",
        "dừng phanh lại", "stop lại đi", "phanh gấp",
        "đi tiếp", "chạy tiếp", "tiếp tục đi", "đi đi", "chạy đi",
        "đi được rồi", "đường thông rồi", "hết người rồi", "resume đi",
        "hủy chuyến", "hủy lệnh", "bỏ chuyến", "khôi đi nữa", "không lấy nữa",
        "hủy bỏ nhiệm vụ", "thôi không lấy nữa",
        "hạ càng xuống", "hạ càng", "nâng càng lên", "kích càng lên",
        "hạ khay xuống", "nâng bàng lên", "tha hàng xuống",
        "robot dừng ngay", "đứng im lại", "đi tiếp đi em",
    ]


def _chat_rows() -> list[str]:
    return [
        "xin chào", "chào robot", "chào bạn", "cảm ơn nhiều", "tạm biệt nhé",
        "bạn là ai", "bạn tên gì", "robot ơi", "khỏe không", "bạn làm được gì",
        "giúp gì được cho tôi", "hôm nay thế nào", "kể chuyện đi", "mấy giờ rồi",
        "chào buổi sáng", "cảm ơn em", "tạm biệt robot", "bạn thông minh thật",
        "hôm nay vui không", "làm quen chút", "bạn có biết tôi không",
        "chào nghe nói bạn mới về", "câu đùa gì không",
        "kể cho tôi nghe đi", "nói chuyện đi", "tạm biệt nhé bạn",
        "chào tạm biệt", "bạn giúp được gì nào", "mấy giờ rồi nhỉ",
        "kể chuyện vui đi", "trò chuyện với tôi đi", "chào em robot",
    ]


# --------------------------------------------------------------------------- #
# Hard negatives: near-identical phrasings that MUST split by intent          #
# --------------------------------------------------------------------------- #
def _hard_negatives() -> list[tuple[str, str]]:
    """(text, intent) pairs deliberately close to a different-intent phrasing."""
    pairs: list[tuple[str, str]] = []
    # answer vs navigate: location question vs fetch command for the SAME item
    for p in ["bột mì", "thùng bia", "dầu ăn", "gạo", "muối", "trà xanh"]:
        pairs.append((f"{p} ở đâu", "answer"))
        pairs.append((f"{p} để đâu", "answer"))
        pairs.append((f"còn {p} không", "answer"))
        pairs.append((f"đi lấy {p}", "navigate"))
        pairs.append((f"mang {p} tới đây", "navigate"))
        pairs.append((f"lấy {p} giúp tôi", "navigate"))
    # answer(stock) vs control: "còn không" stock vs "dừng lại" command — keep distinct
    pairs.append(("còn bia không", "answer"))
    pairs.append(("dừng lại ngay", "control"))
    # chat vs control: polite vs command
    pairs.append(("robot ơi dừng lại", "control"))
    pairs.append(("robot ơi giúp tôi", "chat"))
    # polysemous "đi": "kể chuyện đi" is chat, NOT navigate
    pairs.append(("kể chuyện đi", "chat"))
    pairs.append(("nói chuyện đi", "chat"))
    pairs.append(("kể cho tôi nghe đi", "chat"))
    # "tìm X" is an answer (search) request, NOT a fetch/navigate
    for p in ["bột mì", "thùng bia", "dầu ăn", "gạo", "muối", "trà xanh", "cà phê", "mì tôm"]:
        pairs.append((f"tìm giúp tôi {p}", "answer"))
        pairs.append((f"tìm hộ tôi {p}", "answer"))
        pairs.append((f"tìm {p}", "answer"))
    # navigate(section) vs answer(section): move cue vs info cue
    for s in SECTIONS:
        pairs.append((f"đi tới {s}", "navigate"))
        pairs.append((f"{s} có gì", "answer"))
    return pairs


# --------------------------------------------------------------------------- #
# Build                                                                        #
# --------------------------------------------------------------------------- #
def load_curated() -> list[dict]:
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return []


def build() -> list[dict]:
    rng = random.Random(SEED)
    out: list[dict] = []

    # 1) keep curated rows, but add noisy variants of them too
    for row in load_curated():
        out.append(row)
        out.append({"intent": row["intent"], "text": noisy(row["text"], rng)})

    # 2) template-generated clean rows
    generators = {
        "answer": _answer_rows,
        "navigate": _navigate_rows,
        "control": _control_rows,
        "chat": _chat_rows,
    }
    for intent, gen in generators.items():
        for text in gen():
            out.append({"intent": intent, "text": text})

    # 3) hard negatives
    for text, intent in _hard_negatives():
        out.append({"intent": intent, "text": text})
        out.append({"intent": intent, "text": noisy(text, rng)})

    # 4) rebalance: oversample minorities with noise, trim oversized with noise
    by_intent: dict[str, list[dict]] = {}
    for r in out:
        by_intent.setdefault(r["intent"], []).append(r)

    balanced: list[dict] = []
    for intent, target in TARGET_PER_INTENT.items():
        rows = by_intent.get(intent, [])
        if not rows:
            continue
        rng.shuffle(rows)
        if len(rows) < target:
            while len(rows) < target:
                src = rng.choice(rows)
                rows.append({"intent": intent, "text": noisy(src["text"], rng)})
        balanced += rows[:target]

    # 5) dedupe + shuffle
    seen: set[str] = set()
    uniq: list[dict] = []
    for r in balanced:
        key = r["text"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    rng.shuffle(uniq)
    return uniq


def main() -> None:
    rows = build()
    OUT.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    from collections import Counter

    print(f"Wrote {len(rows)} rows -> {OUT}")
    print("intent counts:", dict(Counter(r["intent"] for r in rows)))


if __name__ == "__main__":
    main()
