"""Build retrieval_eval_v2.json — expand from 24 to 50 cases.

Reads menu.json for exact dish-name ground truth, combines with the existing
v1 cases, and writes the expanded dataset.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

MENU_PATH = PROJECT_ROOT / "assets" / "data" / "menu.json"
V1_PATH = PROJECT_ROOT / "evals" / "data" / "retrieval" / "retrieval_eval.json"
V2_PATH = PROJECT_ROOT / "evals" / "data" / "retrieval" / "retrieval_eval_v2.json"


def load_menu() -> list[dict]:
    return json.loads(MENU_PATH.read_text(encoding="utf-8"))


def by_tag(menu: list[dict], tag: str) -> list[str]:
    return [i["name"] for i in menu if tag in [t.strip().lower() for t in i.get("tags", "").split(",")]]


def by_cat(menu: list[dict], cat: str) -> list[str]:
    return [i["name"] for i in menu if i.get("category") == cat]


def by_diet(menu: list[dict], diet: str) -> list[str]:
    return [i["name"] for i in menu if i.get("diet_type") == diet]


def by_name_contains(menu: list[dict], s: str) -> list[str]:
    return [i["name"] for i in menu if s.lower() in i["name"].lower()]


def build_v2() -> dict:
    menu = load_menu()

    # Load existing v1 cases
    v1 = json.loads(V1_PATH.read_text(encoding="utf-8"))
    existing_cases: list[dict] = v1["cases"]


def _cleanup_cases(cases: list[dict], menu: list[dict]) -> None:
    """Fix typos, remove hallucinated dish names, and correct ground truth
    in existing cases. Applied after all cases are assembled."""
    menu_names = {i["name"] for i in menu}
    best_seller = json.loads(
        (PROJECT_ROOT / "assets" / "data" / "best_seller.json").read_text(encoding="utf-8")
    )
    bs_names = [b["dish_name"] for b in best_seller]

    for case in cases:
        cid = case["id"]
        rel = case["expected_relevant"]

        # --- SR-016: typo Gỏi Xoài Óc Giác → Gỏi Xoài Ốc Giác ---
        if cid == "SR-016":
            for i, name in enumerate(rel):
                if name == "Gỏi Xoài Óc Giác":
                    rel[i] = "Gỏi Xoài Ốc Giác"

        # --- SR-019: typo Cháo Huyết → Cháo Sò Huyết ---
        if cid == "SR-019":
            for i, name in enumerate(rel):
                if name == "Cháo Huyết":
                    rel[i] = "Cháo Sò Huyết"

        # --- SR-020: replace with exact best_seller.json ---
        if cid == "SR-020":
            case["expected_relevant"] = sorted(bs_names)

        # --- Remove generic group names where variants cover ---
        # SR-001: "Ốc Hương" → 11 variants cover it
        if cid == "SR-001" and "Ốc Hương" in rel:
            rel.remove("Ốc Hương")
        # SR-006: "Tôm Càng Xanh" → 9 variants cover it
        if cid == "SR-006" and "Tôm Càng Xanh" in rel:
            rel.remove("Tôm Càng Xanh")
        # SR-024: "Hàu Nướng" → 3 Hàu Nướng variants cover it
        if cid == "SR-024" and "Hàu Nướng" in rel:
            rel.remove("Hàu Nướng")


def build_v2() -> dict:

    # --- New cases (26) ---

    new_cases: list[dict] = []

    # ---- GAP 1: Info-document queries (4 cases) ----
    new_cases.append({
        "id": "SR-025",
        "query": "hotline liên hệ quán",
        "expected_relevant": ["2. Hotline & Liên hệ"],
        "expected_irrelevant": [],
        "category": "info",
        "difficulty": "easy",
        "note": "Info doc: hotline contact. Tests type=info retrieval path."
    })
    new_cases.append({
        "id": "SR-026",
        "query": "quán có mấy chi nhánh ở đâu",
        "expected_relevant": ["3. Hệ thống chi nhánh"],
        "expected_irrelevant": [],
        "category": "info",
        "difficulty": "easy",
        "note": "Info doc: branch locations. FAISS semantic match."
    })
    new_cases.append({
        "id": "SR-027",
        "query": "giờ mở cửa đóng cửa",
        "expected_relevant": ["4. Thời gian hoạt động (Giờ mở cửa)"],
        "expected_irrelevant": [],
        "category": "info",
        "difficulty": "easy",
        "note": "Info doc: opening hours."
    })
    new_cases.append({
        "id": "SR-028",
        "query": "wifi gửi xe thanh toán quán có gì",
        "expected_relevant": ["5. Tiện ích & Dịch vụ (Amenities)"],
        "expected_irrelevant": [],
        "category": "info",
        "difficulty": "medium",
        "note": "Info doc: amenities. Lexical terms may be spread across lanes."
    })

    # ---- GAP 2: Negative / out-of-corpus (3 cases) ----
    new_cases.append({
        "id": "SR-029",
        "query": "cho xem món pizza",
        "expected_relevant": [],
        "expected_irrelevant": ["Bánh Mì Bơ Tỏi"],
        "category": "negative",
        "difficulty": "easy",
        "note": "Out-of-corpus: pizza not on menu. Gatekeeper should reject."
    })
    new_cases.append({
        "id": "SR-030",
        "query": "có sushi sashimi không",
        "expected_relevant": [],
        "expected_irrelevant": ["Gỏi Cuốn Tôm Thịt", "Bò Bía"],
        "category": "negative",
        "difficulty": "easy",
        "note": "Out-of-corpus: sushi not on menu. Tests false-positive rejection."
    })
    new_cases.append({
        "id": "SR-031",
        "query": "giá xe máy SH bao nhiêu",
        "expected_relevant": [],
        "expected_irrelevant": [],
        "category": "negative",
        "difficulty": "medium",
        "note": "Out-of-corpus: non-food query. Gatekeeper must block completely."
    })

    # ---- GAP 3: Underrepresented categories (5 cases) ----

    new_cases.append({
        "id": "SR-032",
        "query": "món canh súp nóng",
        "expected_relevant": [
            "Canh Chua Cá Lóc", "Canh Chua Hải Sản",
            "Canh Rong Biển Đậu Hũ", "Canh Cải Thịt Bằm",
            "Canh Bí Đao Tôm Khô",
            "Soup Tomyum Thố Lớn", "Soup Tomyum Thố Nhỏ",
        ],
        "expected_irrelevant": ["Cháo Hàu", "Lẩu Thái"],
        "category": "soup",
        "difficulty": "easy",
        "note": "Category: canh + soup. Rau & Canh category had zero coverage."
    })
    new_cases.append({
        "id": "SR-033",
        "query": "tráng miệng có món gì",
        "expected_relevant": by_cat(menu, "Tráng Miệng"),
        "expected_irrelevant": ["Khoai Tây Lắc Phô Mai", "Bắp Xào"],
        "category": "dessert",
        "difficulty": "easy",
        "note": "Category: Tráng Miệng (8 items). Previously untested."
    })
    new_cases.append({
        "id": "SR-034",
        "query": "tôm thẻ chế biến kiểu gì",
        "expected_relevant": by_name_contains(menu, "Tôm Thẻ"),
        "expected_irrelevant": ["Tôm Chiên Xù", "Tôm Càng Xanh"],
        "category": "shrimp",
        "difficulty": "easy",
        "note": "Category: Tôm. Tôm Thẻ variants (6 items)."
    })
    new_cases.append({
        "id": "SR-035",
        "query": "lẩu chay",
        "expected_relevant": ["Lẩu Nấm Chay"],
        "expected_irrelevant": ["Lẩu Thái", "Lẩu Gà Lá É"],
        "category": "hotpot_veg",
        "difficulty": "easy",
        "note": "Diet + category intersection: chay lẩu. Single item."
    })
    new_cases.append({
        "id": "SR-036",
        "query": "món rau xào chay",
        "expected_relevant": [
            "Rau Muống Xào Tỏi", "Rau Muống Xào Chao",
            "Cải Thìa Xào Nấm Đông Cô", "Bông Bí Xào Tỏi",
            "Đọt Su Su Xào Tỏi", "Nấm Kim Châm Xào Bơ Tỏi",
        ],
        "expected_irrelevant": ["Mì Xào Hải Sản", "Cơm Chiên Hải Sản"],
        "category": "veg_stir_fry",
        "difficulty": "medium",
        "note": "Tag overlap: rau xào + chay. Both BM25 and FAISS must contribute."
    })

    # ---- GAP 4: Tag-based queries (3 cases) ----

    new_cases.append({
        "id": "SR-037",
        "query": "món thanh đạm ít dầu mỡ",
        "expected_relevant": by_tag(menu, "thanh đạm"),
        "expected_irrelevant": ["Ốc Hương Xốt Trứng Muối", "Lẩu Thái"],
        "category": "light",
        "difficulty": "medium",
        "note": "Tag: thanh đạm (14 items). Tests tag-based semantic matching."
    })
    new_cases.append({
        "id": "SR-038",
        "query": "món khai vị ăn trước",
        "expected_relevant": by_tag(menu, "khai vị"),
        "expected_irrelevant": ["Cháo Hàu", "Bia Heineken"],
        "category": "appetizer",
        "difficulty": "medium",
        "note": "Tag: khai vị (15 items, 6 categories). Cross-category tag recall."
    })
    new_cases.append({
        "id": "SR-039",
        "query": "món cao cấp sang trọng đặc biệt",
        "expected_relevant": by_tag(menu, "cao cấp"),
        "expected_irrelevant": ["Trứng Cút Lộn", "Bắp Xào"],
        "category": "premium",
        "difficulty": "medium",
        "note": "Tag: cao cấp (12 items: Bào Ngư + Tôm Càng Xanh). Premium-tier items."
    })

    # ---- GAP 5: Diet and category filter queries (2 cases) ----

    new_cases.append({
        "id": "SR-040",
        "query": "quán có món chay gì không",
        "expected_relevant": by_diet(menu, "chay"),
        "expected_irrelevant": ["Ốc Hương", "Lẩu Thái"],
        "category": "vegetarian",
        "difficulty": "medium",
        "note": "Diet: chay (26 items across 8 categories). Largest expected set."
    })
    new_cases.append({
        "id": "SR-041",
        "query": "đồ uống giải khát có những gì",
        "expected_relevant": by_cat(menu, "Giải Khát"),
        "expected_irrelevant": ["Cháo Hàu", "Gỏi Hải Sản"],
        "category": "beverage",
        "difficulty": "medium",
        "note": "Category: Giải Khát (22 items). Largest single-category set."
    })

    # ---- GAP 6: Harder implicit/vibe queries (3 cases) ----

    new_cases.append({
        "id": "SR-042",
        "query": "ăn gì buổi sáng nhẹ bụng thôi",
        "expected_relevant": [
            "Cháo Hàu", "Cháo Hến", "Cháo Sò Huyết",
            "Cháo Hải Sản", "Cháo Gà Lá Chanh",
            "Bò Bía", "Gỏi Cuốn Tôm Thịt", "Trứng Cút Lộn",
        ],
        "expected_irrelevant": ["Lẩu Thái", "Cơm Chiên Hải Sản"],
        "category": "breakfast",
        "difficulty": "hard",
        "note": "Persona: breakfast, light. Should return cháo + light rolls."
    })
    new_cases.append({
        "id": "SR-043",
        "query": "món hải sản lạ miệng độc đáo quán",
        "expected_relevant": [
            "Bào Ngư Nướng Mỡ Hành", "Bào Ngư Nướng Tiêu Xanh",
            "Bào Ngư Nướng Bơ Tỏi",
            "Vẹm New Zealand Hấp Sả", "Vẹm New Zealand Nướng Mỡ Hành",
            "Vẹm New Zealand Nướng Phô Mai",
            "Hàu Sữa Hấp Sả", "Sò Mai Nướng Mỡ Hành Trứng Cút",
            "Ốc Len Xào Dừa", "Cá Tầm Nướng Sa Tế",
            "Khổ Qua Chà Bông",
        ],
        "expected_irrelevant": ["Khoai Tây Lắc Phô Mai", "Nước Suối"],
        "category": "exotic",
        "difficulty": "hard",
        "note": "Persona: exotic/unique seafood. Purely semantic — no exact keyword match."
    })
    new_cases.append({
        "id": "SR-044",
        "query": "trời nóng, muốn ăn gì đó mát ngọt",
        "expected_relevant": (
            by_cat(menu, "Tráng Miệng") +
            ["Sinh Tố Bơ", "Sinh Tố Xoài", "Trà Tắc", "Trà Ổi",
             "Dừa Tươi", "Nước Ép Cam", "Nước Ép Dưa Hấu",
             "Nước Ép Thơm"]
        ),
        "expected_irrelevant": ["Lẩu Thái", "Ốc Hương Xốt Trứng Muối"],
        "category": "cold_sweet",
        "difficulty": "hard",
        "note": "Persona: hot weather → cold desserts + cold drinks. Multi-category."
    })

    # ---- GAP 7: Fusion edge cases (2 cases) ----

    new_cases.append({
        "id": "SR-045",
        "query": "nước ép trái cây",
        "expected_relevant": ["Nước Ép Cam", "Nước Ép Dưa Hấu", "Nước Ép Thơm", "Dừa Tươi"],
        "expected_irrelevant": ["Nước Suối", "Nước Ngọt"],
        "category": "juice",
        "difficulty": "medium",
        "note": "BM25-strong prefix match on 'Nước Ép'. FAISS adds Dừa Tươi (semantic)."
    })
    new_cases.append({
        "id": "SR-046",
        "query": "món đẹp chụp hình instagram sống ảo",
        "expected_relevant": [
            "Hàu Nướng Phô Mai", "Sò Điệp Nướng Phô Mai",
            "Tôm Càng Xanh Nướng Phô Mai",
            "Chè Khúc Bạch", "Chè Thái Sầu Riêng",
            "Bánh Flan Cà Phê", "Trứng Lòng Đào Me Cay",
            "Sò Mai Nướng Mỡ Hành Trứng Cút",
        ],
        "expected_irrelevant": ["Nước Suối", "Rau Muống Xào Tỏi"],
        "category": "instagram",
        "difficulty": "hard",
        "note": "Purely semantic: instagram/visual appeal. Zero lexical overlap — FAISS must carry."
    })

    # ---- GAP 8: Additional hard queries for depth (4 cases) ----

    new_cases.append({
        "id": "SR-047",
        "query": "nhậu lai rai tối nay ăn gì",
        "expected_relevant": [
            "Ốc Hương Cháy Tỏi", "Ốc Hương Rang Muối",
            "Khô Bò Lá Bông", "Khô Mực Nướng",
            "Khô Mực Khoai Môn Chiên Nước Mắm", "Khô Cá Chỉ Vàng Nướng",
            "Răng Mực Cháy Tỏi", "Chân Gà Xốt Thái", "Chân Gà Nướng",
        ],
        "expected_irrelevant": ["Cháo Hàu", "Nước Suối"],
        "category": "beer_snack",
        "difficulty": "hard",
        "note": "Persona: nhậu/night out. Must surface ốc + khô + mồi nhậu from tag 'nhậu'."
    })
    new_cases.append({
        "id": "SR-048",
        "query": "có món gì từ càng ghẹ không",
        "expected_relevant": by_name_contains(menu, "Càng Ghẹ"),
        "expected_irrelevant": ["Tôm Càng Xanh", "Cá Chim"],
        "category": "crab_claw",
        "difficulty": "easy",
        "note": "Direct ingredient query: Càng Ghẹ (3 items). Món Chính category."
    })
    new_cases.append({
        "id": "SR-049",
        "query": "món nướng phô mai béo ngậy",
        "expected_relevant": [
            "Hàu Nướng Phô Mai", "Sò Điệp Nướng Phô Mai",
            "Tôm Càng Xanh Nướng Phô Mai", "Vẹm New Zealand Nướng Phô Mai",
            "Ốc Hương Xốt Phô Mai", "Tôm Càng Xanh Xốt Phô Mai",
        ],
        "expected_irrelevant": ["Rau Muống Xào Tỏi", "Cơm Chiên Tỏi"],
        "category": "cheesy_grilled",
        "difficulty": "medium",
        "note": "Taste profile: phô mai + béo. BM25 for 'phô mai', FAISS for 'béo ngậy'."
    })
    new_cases.append({
        "id": "SR-050",
        "query": "gia đình có trẻ em nên gọi món gì",
        "expected_relevant": [
            "Tôm Chiên Xù", "Khoai Tây Lắc Phô Mai", "Bánh Mì Bơ Tỏi",
            "Cơm Chiên Hải Sản", "Cơm Chiên Dương Châu",
            "Mì Xào Bò", "Mì Xào Hải Sản",
            "Chả Giò Hải Sản", "Chả Giò Ốc Quậy",
            "Trứng Cút Lộn Chiên Giòn", "Chim Cút Chiên Bơ",
            "Cánh Gà Chiên Nước Mắm",
        ],
        "expected_irrelevant": ["Ốc Hương Xốt Thái Siêu Cay", "Bia Heineken"],
        "category": "family_kids",
        "difficulty": "hard",
        "note": "Persona: family with kids. Kid-friendly fried/rice/noodle items."
    })

    # --- Assemble ---
    all_cases = existing_cases + new_cases

    # --- Cleanup: fix v1 typos and ground-truth errors ---
    _cleanup_cases(all_cases, menu)

    # Difficulty counts
    diff_counts = {"easy": 0, "medium": 0, "hard": 0}
    for c in all_cases:
        diff_counts[c["difficulty"]] = diff_counts.get(c["difficulty"], 0) + 1

    v2 = {
        "dataset": "retrieval_eval",
        "version": "4.0",
        "description": (
            "Đánh giá chất lượng RAG (Hybrid BM25 + FAISS) phiên bản mở rộng 50 case. "
            "Bổ sung info-doc queries, negative queries, underrepresented categories, "
            "tag-based queries, implicit personas, và fusion edge cases. "
            "Tên món khớp chính xác với assets/data/menu.json."
        ),
        "changelog": "+26 cases over v3.0 (24→50). Gaps addressed: info retrieval (4), "
                     "out-of-corpus rejection (3), new categories (5), tag matching (3), "
                     "diet/category filtering (2), implicit vibe (3), fusion edges (2), "
                     "additional hard queries (4).",
        "metrics": ["Recall@5", "Precision@5", "MRR"],
        "k": 5,
        "total_cases": len(all_cases),
        "difficulty_distribution": diff_counts,
        "cases": all_cases,
    }

    return v2


def main():
    v2 = build_v2()
    V2_PATH.write_text(
        json.dumps(v2, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    diff = v2["difficulty_distribution"]
    print(f"Written {len(v2['cases'])} cases to {V2_PATH}")
    print(f"Difficulty: easy={diff['easy']}, medium={diff['medium']}, hard={diff['hard']}")
    print(f"New: {len(v2['cases']) - 24} cases added to existing 24")


if __name__ == "__main__":
    main()
