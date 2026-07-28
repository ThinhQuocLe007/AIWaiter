import os 
import pickle 
import math
from typing import List, Tuple

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
import underthesea

from src.agent_brain.utils import logger


def segment(text: str) -> List[str]:
    """Word-segment one field into BM25 terms.

    Two things this has to get right, both learned the hard way:

    1. Segment each field, and each comma-separated phrase within a field,
       independently. underthesea segments its input as a single sentence, so
       joining fields first merged terms across the boundary: "Chè Khúc Bạch"
       followed by "Mát lạnh" produced the token "bạch_mát", a word that does
       not exist in either field.

    2. Split compounds back into their parts. underthesea's segmentation is
       context-dependent, so the same phrase yields different tokens depending
       on what surrounds it:

           "tráng miệng"                 -> tráng, miệng
           "có món tráng miệng gì không" -> tráng_miệng

       A document and a query naming the same thing therefore need not agree on
       the compound, and "tráng_miệng" matched no document at all. Flattening
       every compound puts both sides in the same token space no matter which
       way the segmenter went. Keeping the compound *alongside* its parts also
       restores the match, but it inflates term frequencies for exactly the
       common words that compounds are built from, which measurably flattened
       the ranking among near-identical dishes ("ốc hấp sả" lost its top hits).

    Used for documents at build time and queries at search time.
    """
    tokens: List[str] = []
    for phrase in text.lower().split(","):
        phrase = phrase.strip()
        if not phrase:
            continue
        for token in underthesea.word_tokenize(phrase, format="text").split():
            tokens.extend(part for part in token.split("_") if part)
    return tokens


class BM25Index:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.bm25 = None
        self.documents = []
        self.tokenized_docs = []
    
    def build(self, documents: List[Document]) -> bool:
        try:
            self.documents = documents
            self.tokenized_docs = []
            for doc in documents:
                components = []
                if doc.metadata.get("name"): components.append(str(doc.metadata.get("name")))
                if doc.metadata.get("title"): components.append(str(doc.metadata.get("title")))
                if doc.metadata.get("taste_profile"): components.append(str(doc.metadata.get("taste_profile")))
                if doc.metadata.get("tags"): components.append(str(doc.metadata.get("tags")))
                
                if not components:
                    components = [doc.page_content]

                tokens = []
                for component in components:
                    tokens.extend(segment(component))
                self.tokenized_docs.append(tokens)
                    
            self.bm25 = BM25Okapi(self.tokenized_docs, k1=1.2, b=0)
            self.save()
            logger.info(f'[INFO] BM25 index built and saved to {self.db_path}')
            return True

        except (pickle.PickleError, OSError) as e:
            logger.error(f'[ERROR] Creating BM25 index: {e}')
            return False
    
    def load(self) -> bool:
        try:
            with open(self.db_path, 'rb') as f:
                data = pickle.load(f)
                self.bm25 = data['bm25']
                self.documents = data['documents']
                self.tokenized_docs = data['tokenized_docs']
            logger.info(f'[INFO] BM25 index loaded from {self.db_path}')
            return True
        except (pickle.PickleError, OSError) as e:
            logger.error(f'[ERROR] Loading BM25 index: {e}')
            return False  
    
    def explain(self, query: str):
        print(f"--- BM25 EXPLAIN: '{query}' ---")
        if not self.bm25:
            print("Error: Index not built or loaded.")
            return

        tokenized_query = segment(query)
        print(f"Tokenized Query: {tokenized_query}")
        
        scores = self.bm25.get_scores(tokenized_query)
        doc_scores = []
        for idx, score in enumerate(scores):
            doc_scores.append((idx, self.documents[idx], float(score)))
        
        doc_scores.sort(key=lambda x: x[2], reverse=True)
        
        for idx, doc, total_score in doc_scores[:3]:
            if total_score == 0:
                continue
            
            name = doc.metadata.get('name') or doc.metadata.get('title') or "Unknown"
            print(f"\nDocument [{idx}]: {name}")
            print(f"Total Score: {total_score:.4f}")
            doc_tokens = self.tokenized_docs[idx]
            
            for q_term in tokenized_query:
                if q_term in self.bm25.idf:
                    idf = self.bm25.idf[q_term]
                    tf = doc_tokens.count(q_term)
                    if tf > 0:
                        k1 = self.bm25.k1
                        b = self.bm25.b
                        doc_len = self.bm25.doc_len[idx]
                        avgdl = self.bm25.avgdl
                        
                        len_norm = 1.0 - b + b * (doc_len / avgdl)
                        term_score = idf * (tf * (k1 + 1)) / (tf + k1 * len_norm)
                        print(f"  Term '{q_term}': tf={tf}, idf={idf:.4f}, length_penalty={len_norm:.4f} => term_score={term_score:.4f}")
        print("-" * 30 + "\n")

    def search(self, query: str, k: int = 4) -> List[Tuple[Document, float]]:
        try:
            tokenized_query = segment(query)
            scores = self.bm25.get_scores(tokenized_query)

            # Zero score means the query shares no term with the document. Those
            # used to be returned anyway (sort-then-slice always yielded k docs),
            # which handed arbitrary documents a top RRF rank on queries with no
            # lexical evidence at all.
            doc_scores = [
                (self.documents[idx], float(score))
                for idx, score in enumerate(scores)
                if score > 0
            ]
            doc_scores.sort(key=lambda x: x[1], reverse=True)

            return doc_scores[:k]
        except (ValueError, RuntimeError) as e:
            logger.error(f'[ERROR] Searching BM25 index: {e}')
            return []

    def save(self) -> bool:
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            data = {
                'bm25': self.bm25,
                'documents': self.documents,
                'tokenized_docs': self.tokenized_docs
            }
            with open(self.db_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f'[INFO] BM25 index saved to {self.db_path}')
            return True
        except (pickle.PickleError, OSError) as e:
            logger.error(f'[ERROR] Saving BM25 index: {e}')
            return False
