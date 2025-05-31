import os
import json
import time
import threading
from typing import Dict, Set, Optional
from src.logging.logger import logger
import config as cfg


class SharedUrlIndex:
    def __init__(self):
        self._index = {
            'categories': {},
            'all_urls': set()
        }
        self._last_updated = {}
        self._lock = threading.RLock()
        self._refresh_interval = 30  # seconds
        
        # Index structure:
        # {
        #   'categories': {
        #     'category_name': {
        #       'class_name': set(['url1', 'url2', ...]),
        #       ...
        #     },
        #     ...
        #   },
        #   'all_urls': set(['url1', 'url2', ...])  # flattened for cross-category checks
        # }
        
    def _get_metadata_timestamp(self, category_dir: str, class_name: str) -> float:
        try:
            metadata_file = cfg.get_image_metadata_file(category_dir, class_name)
            if os.path.exists(metadata_file):
                return os.path.getmtime(metadata_file)
            return 0.0
        except Exception:
            return 0.0
    
    def _load_urls_from_metadata(self, category_dir: str, class_name: str) -> Set[str]:
        try:
            metadata_file = cfg.get_image_metadata_file(category_dir, class_name)
            if not os.path.exists(metadata_file):
                return set()
                
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                
            urls = set()
            images_dict = metadata.get('images', {})
            if isinstance(images_dict, dict):
                for img_data in images_dict.values():
                    if 'fetch_data' in img_data and 'link' in img_data['fetch_data']:
                        urls.add(img_data['fetch_data']['link'])
                        
            return urls
        except Exception as e:
            logger.error(f"Error loading URLs from {category_dir}/{class_name}: {e}")
            return set()
    
    def _needs_refresh(self, category_dir: str, class_name: str) -> bool:
        try:
            key = f"{category_dir}_{class_name}"
            current_time = time.time()
            
            # Check if we have last updated time
            if key not in self._last_updated:
                return True
                
            last_check = self._last_updated[key]
            
            # Check if refresh interval has passed
            if current_time - last_check > self._refresh_interval:
                return True
                
            # Check if metadata file has been modified
            current_timestamp = self._get_metadata_timestamp(category_dir, class_name)
            stored_timestamp = self._last_updated.get(f"{key}_timestamp", 0)
            
            return current_timestamp > stored_timestamp
            
        except Exception:
            return True
    
    def _refresh_class_urls(self, category_dir: str, class_name: str):
        try:
            if not self._needs_refresh(category_dir, class_name):
                return
                
            urls = self._load_urls_from_metadata(category_dir, class_name)
            
            with self._lock:
                # Initialize category if not exists
                if 'categories' not in self._index:
                    self._index['categories'] = {}
                    
                if category_dir not in self._index['categories']:
                    self._index['categories'][category_dir] = {}
                
                # Update class URLs
                self._index['categories'][category_dir][class_name] = urls
                
                # Update timestamps
                key = f"{category_dir}_{class_name}"
                self._last_updated[key] = time.time()
                self._last_updated[f"{key}_timestamp"] = self._get_metadata_timestamp(category_dir, class_name)
                
                logger.debug(f"Refreshed URL index for {category_dir}/{class_name}: {len(urls)} URLs")
                
        except Exception as e:
            logger.error(f"Error refreshing class URLs for {category_dir}/{class_name}: {e}")
    
    def _rebuild_all_urls_cache(self):
        try:
            with self._lock:
                all_urls = set()
                categories = self._index.get('categories', {})
                
                for category_dict in categories.values():
                    for class_urls in category_dict.values():
                        all_urls.update(class_urls)
                
                self._index['all_urls'] = all_urls
                logger.debug(f"Rebuilt all_urls cache: {len(all_urls)} total URLs")
                
        except Exception as e:
            logger.error(f"Error rebuilding all_urls cache: {e}")
    
    def get_category_urls(self, category_dir: str, exclude_class: str = None) -> Set[str]:
        try:
            # Refresh all classes in this category
            metadata_base_dir = os.path.join(cfg.get_output_dir(), "metadata", category_dir)
            if os.path.exists(metadata_base_dir):
                for class_name in os.listdir(metadata_base_dir):
                    class_path = os.path.join(metadata_base_dir, class_name)
                    if os.path.isdir(class_path):
                        self._refresh_class_urls(category_dir, class_name)
            
            # Collect URLs from all classes except excluded
            urls = set()
            with self._lock:
                categories = self._index.get('categories', {})
                category_dict = categories.get(category_dir, {})
                
                for class_name, class_urls in category_dict.items():
                    if exclude_class and class_name == exclude_class:
                        continue
                    urls.update(class_urls)
            
            return urls
            
        except Exception as e:
            logger.error(f"Error getting category URLs for '{category_dir}': {e}")
            return set()
    
    def get_all_urls(self, exclude_category: str = None, exclude_class: str = None) -> Set[str]:
        try:
            # Refresh all categories and classes
            metadata_base_dir = os.path.join(cfg.get_output_dir(), "metadata")
            if os.path.exists(metadata_base_dir):
                for category_dir in os.listdir(metadata_base_dir):
                    if exclude_category and category_dir == exclude_category:
                        continue
                        
                    category_path = os.path.join(metadata_base_dir, category_dir)
                    if os.path.isdir(category_path):
                        for class_name in os.listdir(category_path):
                            if exclude_category == category_dir and exclude_class and class_name == exclude_class:
                                continue
                                
                            class_path = os.path.join(category_path, class_name)
                            if os.path.isdir(class_path):
                                self._refresh_class_urls(category_dir, class_name)
            
            # Collect URLs from all categories except excluded
            urls = set()
            with self._lock:
                categories = self._index.get('categories', {})
                
                for category_name, category_dict in categories.items():
                    if exclude_category and category_name == exclude_category:
                        continue
                        
                    for class_name, class_urls in category_dict.items():
                        if exclude_category == category_name and exclude_class and class_name == exclude_class:
                            continue
                        urls.update(class_urls)
            
            return urls
            
        except Exception as e:
            logger.error(f"Error getting all URLs: {e}")
            return set()
    
    def add_url(self, category_dir: str, class_name: str, url: str):
        try:
            with self._lock:
                # Initialize structure if needed
                if 'categories' not in self._index:
                    self._index['categories'] = {}
                    
                if category_dir not in self._index['categories']:
                    self._index['categories'][category_dir] = {}
                    
                if class_name not in self._index['categories'][category_dir]:
                    self._index['categories'][category_dir][class_name] = set()
                
                # Add URL to class set
                self._index['categories'][category_dir][class_name].add(url)
                
                # Update all_urls cache
                self._index['all_urls'].add(url)
                
                logger.debug(f"Added URL to index: {category_dir}/{class_name}")
                
        except Exception as e:
            logger.error(f"Error adding URL to index: {e}")
    
    def is_url_duplicate_in_category(self, url: str, category_dir: str, current_class: str) -> bool:
        try:
            category_urls = self.get_category_urls(category_dir, exclude_class=current_class)
            return url in category_urls
        except Exception as e:
            logger.error(f"Error checking URL duplication in category '{category_dir}': {e}")
            return False
    
    def is_url_duplicate_across_categories(self, url: str, current_category: str = None, current_class: str = None) -> bool:
        try:
            all_urls = self.get_all_urls(exclude_category=current_category, exclude_class=current_class)
            return url in all_urls
        except Exception as e:
            logger.error(f"Error checking URL duplication across categories: {e}")
            return False
    
    def get_stats(self) -> Dict:
        try:
            with self._lock:
                categories = self._index.get('categories', {})
                stats = {
                    'total_categories': len(categories),
                    'total_classes': sum(len(cat_dict) for cat_dict in categories.values()),
                    'total_urls': len(self._index.get('all_urls', set())),
                    'categories': {}
                }
                
                for cat_name, cat_dict in categories.items():
                    cat_urls = set()
                    for class_urls in cat_dict.values():
                        cat_urls.update(class_urls)
                    
                    stats['categories'][cat_name] = {
                        'classes': len(cat_dict),
                        'urls': len(cat_urls)
                    }
                
                return stats
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {}


# Global shared index instance
_shared_index = None
_index_lock = threading.Lock()

def get_shared_url_index() -> SharedUrlIndex:
    global _shared_index
    if _shared_index is None:
        with _index_lock:
            if _shared_index is None:  # Double-check locking
                _shared_index = SharedUrlIndex()
    return _shared_index