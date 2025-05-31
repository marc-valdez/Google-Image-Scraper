from src.utils.cache_utils import (
    is_url_duplicate_in_category, 
    is_url_duplicate_across_categories,
    add_url_to_shared_index
)
from src.logging.logger import logger


class DuplicationChecker:
    def __init__(self, category_dir: str, class_name: str, worker_id: int):
        self.category_dir = category_dir
        self.class_name = class_name
        self.worker_id = worker_id
    
    def check_url_duplicates(self, url: str, found_urls: list):
        if url in found_urls:
            logger.info(f"[Worker {self.worker_id}] URL already fetched in current class, moving to next item")
            return "intra_class_duplicate"
        
        if is_url_duplicate_in_category(url, self.category_dir, self.class_name):
            logger.info(f"[Worker {self.worker_id}] URL already exists in another class within category '{self.category_dir}': {logger.truncate_url(url)}")
            return "inter_class_duplicate"
        
        if is_url_duplicate_across_categories(url, self.category_dir, self.class_name):
            logger.info(f"[Worker {self.worker_id}] URL already exists in another category: {logger.truncate_url(url)}")
            return "cross_category_duplicate"
        
        return "unique"
    
    def add_unique_url(self, url: str):
        add_url_to_shared_index(url, self.category_dir, self.class_name)