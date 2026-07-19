from typing import List, Tuple, Optional
from langchain_core.documents import Document


def by_menu_metadata(
    results: List[Tuple[Document, float]],
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    diet_type: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Tuple[Document, float]]:
    filtered = []
    for doc, score in results:
        doc_type = doc.metadata.get("type", "")
        if doc_type == "menu":
            doc_price = doc.metadata.get("price", 0.0)
            doc_diet = doc.metadata.get("diet_type", "")
            doc_cat = doc.metadata.get("category", "")

            if max_price is not None and doc_price > max_price:
                continue
            if min_price is not None and doc_price < min_price:
                continue
            if diet_type is not None and diet_type.lower() not in doc_diet.lower():
                continue
            if category is not None and category.lower() not in doc_cat.lower():
                continue
            filtered.append((doc, score))
        elif doc_type == "info":
            filtered.append((doc, score))
        # drop customer, best_seller, promo — not searchable content
    return filtered
