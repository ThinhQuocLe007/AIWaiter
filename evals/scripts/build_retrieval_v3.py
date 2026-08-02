"""Build retrieval_eval_v3.json — stratified by rewriter need.

Adds a `rewrite_stratum` field to every case:
  pass-through      — query already concrete; rewriter should pass unchanged
  category-expand   — benefits from term expansion
  vibe-sensation    — zero lexical overlap; rewriter is essential
  implicit-persona  — situation/occasion mapping
  complex-constraint — multiple constraints (diet + price + taste)
  info              — restaurant info doc queries
  negative          — out-of-corpus; gatekeeper must block

Also adds 10 new vibe/persona queries (SR-051 to SR-060).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

MENU_PATH = PROJECT_ROOT / "assets" / "data" / "menu.json"
V2_PATH = PROJECT_ROOT / "evals" / "data" / "retrieval" / "retrieval_eval_v2.json"
V3_PATH = PROJECT_ROOT / "evals" / "data" / "retrieval" / "retrieval_eval_v3.json"


def load_menu() -> list[dict]:
    return json.loads(MENU_PATH.read_text(encoding="utf-8"))


def _split_tags(item: dict) -> set[str]:
    """Tags are stored as comma-separated strings in menu.json."""
    raw = item.get("tags", "")
    if not raw:
        return set()
    return {t.strip().lower() for t in raw.split(",") if t.strip()}


def by_tag(menu: list[dict], tag: str) -> list[str]:
    return [i["name"] for i in menu if tag in _split_tags(i)]


def by_cat(menu: list[dict], cat: str) -> list[str]:
    return [i["name"] for i in menu if i.get("category") == cat]


def by_diet(menu: list[dict], diet: str) -> list[str]:
    return [i["name"] for i in menu if i.get("diet_type") == diet]


def by_name_contains(menu: list[dict], s: str) -> list[str]:
    return [i["name"] for i in menu if s.lower() in i["name"].lower()]


def by_taste_contains(menu: list[dict], s: str) -> list[str]:
    return [i["name"] for i in menu if s.lower() in (i.get("taste_profile", "") or "").lower()]


def by_tag_or_taste(menu: list[dict], keyword: str) -> list[str]:
    """Match dishes where keyword appears in tags OR taste_profile."""
    results = set()
    for item in menu:
        tags = _split_tags(item)
        taste = (item.get("taste_profile", "") or "").lower()
        if keyword in tags or keyword in taste:
            results.add(item["name"])
    return sorted(results)


# ── Stratum assignment for existing SR-001 to SR-050 ──────────────────

STRATUM_MAP: dict[str, str] = {
    # pass-through: dish name, ingredient, or exact category already in query
    "SR-001": "pass-through",
    "SR-002": "pass-through",
    "SR-003": "pass-through",
    "SR-004": "pass-through",
    "SR-005": "pass-through",
    "SR-006": "pass-through",
    "SR-007": "pass-through",
    "SR-008": "pass-through",
    "SR-012": "pass-through",
    "SR-014": "pass-through",
    "SR-016": "pass-through",
    "SR-024": "pass-through",
    "SR-034": "pass-through",
    "SR-045": "pass-through",
    "SR-048": "pass-through",

    # category-expand: category/tag query that benefits from keyword expansion
    "SR-010": "category-expand",
    "SR-011": "category-expand",
    "SR-013": "category-expand",
    "SR-015": "category-expand",
    "SR-017": "category-expand",
    "SR-032": "category-expand",
    "SR-033": "category-expand",
    "SR-038": "category-expand",
    "SR-040": "category-expand",
    "SR-041": "category-expand",

    # vibe-sensation: zero or minimal lexical overlap with menu
    "SR-019": "vibe-sensation",
    "SR-022": "vibe-sensation",
    "SR-037": "vibe-sensation",
    "SR-039": "vibe-sensation",
    "SR-043": "vibe-sensation",
    "SR-044": "vibe-sensation",
    "SR-046": "vibe-sensation",
    "SR-049": "vibe-sensation",

    # implicit-persona: situation/occasion mapping
    "SR-018": "implicit-persona",
    "SR-020": "implicit-persona",
    "SR-021": "implicit-persona",
    "SR-042": "implicit-persona",
    "SR-047": "implicit-persona",
    "SR-050": "implicit-persona",

    # complex-constraint: multiple intersecting criteria
    "SR-009": "complex-constraint",
    "SR-023": "complex-constraint",
    "SR-035": "complex-constraint",
    "SR-036": "complex-constraint",

    # info / negative
    "SR-025": "info",
    "SR-026": "info",
    "SR-027": "info",
    "SR-028": "info",
    "SR-029": "negative",
    "SR-030": "negative",
    "SR-031": "negative",
}


def build_v3() -> dict:
    menu = load_menu()

    # Load existing v2 cases
    v2 = json.loads(V2_PATH.read_text(encoding="utf-8"))
    existing_cases: list[dict] = v2["cases"]

    # Assign rewrite_stratum to each existing case
    for case in existing_cases:
        cid = case["id"]
        case["rewrite_stratum"] = STRATUM_MAP.get(cid, "pass-through")

    # ── New cases (SR-051 to SR-060) ─────────────────────────────────

    new_cases: list[dict] = []

    # ---- VIBE-SENSATION: queries with zero lexical overlap ----

    new_cases.append({
        "id": "SR-051",
        "query": "món gì the the mát mát giải nhiệt mùa hè",
        "expected_relevant": sorted(set(
            by_cat(menu, "Tráng Miệng") +
            ["Nước Ép Cam", "Nước Ép Dưa Hấu", "Nước Ép Thơm",
             "Sinh Tố Bơ", "Sinh Tố Xoài", "Dừa Tươi",
             "Trà Tắc", "Trà Ổi", "Soda Chanh", "Soda Việt Quất",
             "Nước Suối"]
        )),
        "expected_irrelevant": ["Lẩu Thái", "Ốc Hương Xốt Trứng Muối"],
        "category": "cold_refresh",
        "difficulty": "hard",
        "rewrite_stratum": "vibe-sensation",
        "note": "Vibe: summer heat → cold desserts + cold drinks. Zero dish-name overlap."
    })

    new_cases.append({
        "id": "SR-052",
        "query": "cay xé lưỡi luôn ấy, món nào cay nhất quán",
        "expected_relevant": sorted(set(n for n in [
            i["name"] for i in menu
            if ("cay" in i.get("tags", "").lower()
                or "cay" in i["name"].lower()
                or "sa tế" in i["name"].lower()
                or "siêu cay" in i.get("tags", "").lower()
                or "muối ớt" in i["name"].lower())
        ])),
        "expected_irrelevant": ["Rau Muống Xào Tỏi", "Nước Suối"],
        "category": "spicy",
        "difficulty": "hard",
        "rewrite_stratum": "vibe-sensation",
        "note": "Vibe: maximum spiciness. Curated: cay in name/tags, sa tế, siêu cay, muối ớt."
    })

    new_cases.append({
        "id": "SR-059",
        "query": "ăn gì ấm bụng buổi tối mưa ở Sài Gòn",
        "expected_relevant": sorted(set(
            [i["name"] for i in menu if "cháo" in i["name"].lower() or i.get("category") in ("Món Lẩu", "Rau & Canh")]
        )),
        "expected_irrelevant": ["Bia Heineken", "Kem Dừa"],
        "category": "comfort_food",
        "difficulty": "hard",
        "rewrite_stratum": "vibe-sensation",
        "note": "Vibe: rainy evening → cháo, lẩu, canh súp nóng. 23 items."
    })

    new_cases.append({
        "id": "SR-060",
        "query": "món gì bùi bùi béo béo ăn vặt lai rai",
        "expected_relevant": sorted(set(
            [i["name"] for i in menu
             if (i.get("category") in ("Lặt Vặt Ăn Chơi", "Khô Lai Rai")
                 or "béo" in i.get("tags", "").lower())]
        )),
        "expected_irrelevant": ["Cháo Hàu", "Nước Suối"],
        "category": "snack_rich",
        "difficulty": "hard",
        "rewrite_stratum": "vibe-sensation",
        "note": "Vibe: rich snack. Lặt Vặt Ăn Chơi + Khô Lai Rai categories + 'béo' tag."
    })

    # ---- IMPLICIT-PERSONA: situation/occasion mapping ----

    new_cases.append({
        "id": "SR-053",
        "query": "ăn gì healthy ít calo mà vẫn ngon",
        "expected_relevant": sorted(set(
            by_tag(menu, "thanh đạm") +
            by_tag(menu, "chay")
        )),
        "expected_irrelevant": ["Ốc Hương Xốt Trứng Muối", "Cánh Gà Chiên Nước Mắm"],
        "category": "healthy",
        "difficulty": "hard",
        "rewrite_stratum": "implicit-persona",
        "note": "Persona: health-conscious. Maps to 'thanh đạm' + 'chay' tags."
    })

    new_cases.append({
        "id": "SR-054",
        "query": "tụ tập cuối tuần 8 đứa share được món gì",
        "expected_relevant": sorted(set(
            [i["name"] for i in menu if i.get("category") in ("Món Lẩu", "Gỏi & Trộn")]
            + [i["name"] for i in menu
               if i.get("category") == "Món Nướng"
               and any(kw in i["name"].lower() for kw in
                       ("càng xanh", "cá", "bào ngư", "dê", "gà"))]
        )),
        "expected_irrelevant": ["Trứng Cút Lộn", "Nước Suối"],
        "category": "group_dining",
        "difficulty": "hard",
        "rewrite_stratum": "implicit-persona",
        "note": "Persona: large group. Lẩu + Gỏi + shareable Nướng (cá, gà, dê, bào ngư, tôm càng). 35 items."
    })

    new_cases.append({
        "id": "SR-055",
        "query": "hẹn hò lần đầu nên gọi món gì cho sang",
        "expected_relevant": sorted(set(
            by_tag(menu, "cao cấp")
        )),
        "expected_irrelevant": ["Bắp Xào", "Trứng Cút Lộn"],
        "category": "date_premium",
        "difficulty": "hard",
        "rewrite_stratum": "implicit-persona",
        "note": "Persona: first date → premium/impressive dishes. Maps to 'cao cấp' tag."
    })

    # ---- COMPLEX-CONSTRAINT: multiple intersecting criteria ----

    new_cases.append({
        "id": "SR-056",
        "query": "món chay nào giòn giòn dưới 80k",
        "expected_relevant": sorted(set(
            n for n in by_diet(menu, "chay")
            if n in (set(by_taste_contains(menu, "giòn")))
            and any(int(str(i.get("price", 0))) < 80000 for i in menu if i["name"] == n)
        )),
        "expected_irrelevant": ["Đậu Hũ Mắm Tôm", "Lẩu Nấm Chay"],
        "category": "veg_crispy_budget",
        "difficulty": "hard",
        "rewrite_stratum": "complex-constraint",
        "note": "Complex: chay + giòn + price < 80k. Tests diet + taste + price intersection."
    })

    new_cases.append({
        "id": "SR-057",
        "query": "hải sản sốt bơ tỏi trên 150k có món gì",
        "expected_relevant": [],
        "expected_irrelevant": ["Ốc Hương Xốt Bơ Tỏi Cay", "Tôm Càng Xanh Xốt Bơ Tỏi Cay"],
        "category": "price_ceiling",
        "difficulty": "hard",
        "rewrite_stratum": "complex-constraint",
        "note": "Complex: seafood + butter garlic + above 150k. Max menu price is 99k → empty set. Tests price-filter aware rewriting + correct empty-result handling."
    })

    new_cases.append({
        "id": "SR-058",
        "query": "món nướng không cay cho trẻ em dưới 100k",
        "expected_relevant": sorted(set(
            n for n in by_cat(menu, "Món Nướng")
            if n not in by_taste_contains(menu, "cay")
            and n not in by_tag(menu, "cay")
            and any(int(str(i.get("price", 0))) < 100000 for i in menu if i["name"] == n)
        )),
        "expected_irrelevant": [
            "Ốc Hương Xốt Thái Siêu Cay",
            "Cá Chim Nướng Sa Tế"
        ],
        "category": "grilled_kids",
        "difficulty": "hard",
        "rewrite_stratum": "complex-constraint",
        "note": "Complex: grilled + not spicy + price < 100k. Tests multi-filter rewriting."
    })

    # ── Assemble ──────────────────────────────────────────────────────

    all_cases = existing_cases + new_cases

    # Count per stratum
    stratum_counts: dict[str, int] = {}
    diff_counts: dict[str, int] = {}
    for c in all_cases:
        s = c.get("rewrite_stratum", "pass-through")
        stratum_counts[s] = stratum_counts.get(s, 0) + 1
        d = c["difficulty"]
        diff_counts[d] = diff_counts.get(d, 0) + 1

    v3 = {
        "dataset": "retrieval_eval",
        "version": "5.0",
        "description": (
            "Đánh giá chất lượng RAG + Query Rewriter phiên bản 60 case, "
            "phân tầng theo rewrite_stratum. "
            "Mỗi case được gán nhãn pass-through / category-expand / vibe-sensation / "
            "implicit-persona / complex-constraint / info / negative để đánh giá "
            "đóng góp thực sự của rewriter trên từng loại truy vấn."
        ),
        "changelog": (
            "+10 cases (SR-051 to SR-060) targeting vibe/persona/complex queries. "
            "Added rewrite_stratum field to all 60 cases. "
            "Fixed by_tag() in build script (tags are comma-separated strings)."
        ),
        "metrics": ["Recall@5", "Precision@5", "MRR"],
        "k": 5,
        "total_cases": len(all_cases),
        "difficulty_distribution": diff_counts,
        "rewrite_stratum_distribution": stratum_counts,
        "cases": all_cases,
    }

    return v3


def main():
    v3 = build_v3()
    V3_PATH.write_text(
        json.dumps(v3, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Written {len(v3['cases'])} cases to {V3_PATH}")
    print(f"Difficulty: {v3['difficulty_distribution']}")
    print(f"Stratum:    {v3['rewrite_stratum_distribution']}")


if __name__ == "__main__":
    main()
