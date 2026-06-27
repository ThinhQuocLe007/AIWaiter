import json 
import os 
from langchain_core.documents import Document
from src.agent_brain.config import settings
from src.agent_brain.utils import logger


class DocumentLoader: 
    def __init__(self): 
        self.parsers = {
            "menu.json": self._parse_menu_json,
            "restaurant_info.txt": self._parse_info_text,
            "best_seller.json": self._parse_best_seller_json,
            "discounts.json": self._parse_promos_json,
            "customer_info.json": self._parse_customer_json,
        }

    def load(self, file_path): 
        filename = os.path.basename(file_path)
        parser = self.parsers.get(filename)

        if not parser: 
            logger.warning(f"No parser found for {filename}, using default loader")
            return self._default_text_loader(file_path)

        try:
            return parser(file_path)
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return []

    def _parse_menu_json(self, file_path): 
        with open(file_path, 'r', encoding='utf-8') as f: 
            data = json.load(f)

        docs = []
        for item in data: 
            raw_price = item.get("price", "0")
            price_val = 0.0
            if isinstance(raw_price, (int, float)):
                price_val = float(raw_price)
            elif isinstance(raw_price, str):
                cleaned_price = "".join([c for c in raw_price if c.isdigit()])
                if cleaned_price:
                    price_val = float(cleaned_price)

            metadata = {
                "source": "menu.json",
                "type": "menu",
                "name": item.get("name"),
                "taste_profile": item.get("taste_profile"),
                "tags": item.get("tags"),
                "diet_type": item.get("diet_type"),
                "category": item.get("category"),
                "price": price_val,
            }

            page_content = f"""
            Tên món: {item.get('name')}
            Mô tả: {item.get('description')}
            Giá: {item.get('price')}
            Loại món ăn: {item.get('diet_type')}
            Danh mục: {item.get('category')}
            Thành phần: {item.get('ingredients')}
            Hương vị: {item.get('taste_profile')}
            Tags: {item.get('tags')}
            """

            docs.append(
                Document(
                    page_content=page_content,
                    metadata=metadata,
                )
            )

        return docs

    def _parse_info_text(self, file_path): 
        with open(file_path, 'r', encoding='utf-8') as f: 
            content = f.read()

        sections = content.split('##')
        documents = [] 
        for section in sections: 
            if not section.strip(): 
                continue

            parts = section.split('\n', 1)
            if len(parts) < 2: 
                continue

            title = parts[0].strip()
            content = parts[1].strip()

            metadata = {
                "source": "restaurant_info.txt",
                "type": "info",
                "title": title,
            }

            documents.append(
                Document(
                    page_content=content,
                    metadata=metadata,
                )
            )

        return documents

    def _default_text_loader(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f: 
            content = f.read()

        lines = content.split('\n')
        docs = [] 
        for line in lines: 
            if not line.strip(): 
                continue

            metadata = {
                "source": os.path.basename(file_path),
            }

            docs.append(
                Document(
                    page_content=line,
                    metadata=metadata,
                )
            )
        return docs

    def _parse_best_seller_json(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        docs = []
        for item in data:
            name = item.get("dish_name")
            content = f"Món bán chạy: {name}\nLý do yêu thích: {item.get('reason')}"
            docs.append(Document(
                page_content=content,
                metadata={"source": "best_seller.json", "type": "best_seller", "name": name}
            ))
        return docs

    def _parse_promos_json(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        docs = []
        for item in data:
            name = item.get("promo_name")
            content = f"Chương trình: {name}\nChi tiết: {item.get('details')}\nThời gian: {item.get('time')}\nĐiều kiện: {item.get('condition')}"
            docs.append(Document(
                page_content=content,
                metadata={"source": "discounts.json", "type": "promo", "name": name}
            ))
        return docs

    def _parse_customer_json(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        docs = []
        for item in data:
            name = item.get("name")
            content = f"Khách hàng thân thiết: {name} (ID: {item.get('customer_id')})\nHạng thẻ: {item.get('tier')}\nSở thích: {item.get('preferences')}\nMón yêu thích nhất: {item.get('favourite_dish')}\nNgày ghé thăm cuối: {item.get('last_visit')}"
            docs.append(Document(
                page_content=content,
                metadata={"source": "customer_info.json", "type": "customer", "name": name}
            ))
        return docs
