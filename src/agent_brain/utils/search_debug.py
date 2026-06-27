import logging
from typing import List
from src.agent_brain.schemas import SearchResult

logger = logging.getLogger(__name__)

def print_database_summary(documents: List):
    """
    Print a summary of the loaded documents.
    """
    total = len(documents)
    menu_count = sum(1 for d in documents if d.metadata.get('type') == 'menu')
    info_count = sum(1 for d in documents if d.metadata.get('type') == 'info')
    best_seller_count = sum(1 for d in documents if d.metadata.get('type') == 'best_seller')
    promo_count = sum(1 for d in documents if d.metadata.get('type') == 'promo')
    customer_count = sum(1 for d in documents if d.metadata.get('type') == 'customer')
    
    logger.info("--- Database Summary ---")
    logger.info(f"Total documents: {total}")
    logger.info(f"Menu items: {menu_count}")
    logger.info(f"Restaurant info docs: {info_count}")
    logger.info(f"Best sellers: {best_seller_count}")
    logger.info(f"Promotions: {promo_count}")
    logger.info(f"Customer profiles: {customer_count}")
    logger.info("------------------------")

def print_search_results(results: List[SearchResult]):
    """
    Print formatted search results.
    """
    if not results:
        logger.info("No results found.")
        return
        
    logger.info(f"--- Search Results ({len(results)}) ---")
    for i, res in enumerate(results):
        logger.info(f"{i+1}. [{res.score:.4f}] {res.document.page_content[:100]}...")
        logger.info(f"   Source: {res.source} | Type: {res.doc_type}")
    logger.info("----------------------------")
