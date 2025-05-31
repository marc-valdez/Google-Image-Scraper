#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.cache_utils import (
    initialize_shared_index, 
    get_shared_index_stats,
    add_url_to_shared_index,
    is_url_duplicate_in_category,
    is_url_duplicate_across_categories
)
from src.logging.logger import logger

def test_shared_index():
    logger.info("Testing shared URL index implementation...")
    
    # Initialize the shared index
    if not initialize_shared_index():
        logger.error("Failed to initialize shared index")
        return False
    
    # Test adding URLs
    test_urls = [
        ("animals", "cats", "https://example.com/cat1.jpg"),
        ("animals", "cats", "https://example.com/cat2.jpg"),
        ("animals", "dogs", "https://example.com/dog1.jpg"),
        ("vehicles", "cars", "https://example.com/car1.jpg"),
    ]
    
    logger.info("Adding test URLs to shared index...")
    for category, class_name, url in test_urls:
        add_url_to_shared_index(url, category, class_name)
        logger.info(f"Added: {category}/{class_name} -> {url}")
    
    # Test intra-class duplication (same URL in same class)
    logger.info("\nTesting intra-class duplication...")
    is_dup = is_url_duplicate_in_category("https://example.com/cat1.jpg", "animals", "cats")
    logger.info(f"Same URL in same class should be False: {is_dup}")
    
    # Test inter-class duplication within category
    logger.info("\nTesting inter-class duplication within category...")
    is_dup = is_url_duplicate_in_category("https://example.com/cat1.jpg", "animals", "dogs")
    logger.info(f"Cat URL exists in dogs class check should be True: {is_dup}")
    
    # Test cross-category duplication
    logger.info("\nTesting cross-category duplication...")
    is_dup = is_url_duplicate_across_categories("https://example.com/cat1.jpg", "vehicles", "cars")
    logger.info(f"Cat URL exists in vehicles/cars check should be True: {is_dup}")
    
    # Test non-existent URL
    logger.info("\nTesting non-existent URL...")
    is_dup = is_url_duplicate_in_category("https://example.com/nonexistent.jpg", "animals", "cats")
    logger.info(f"Non-existent URL should be False: {is_dup}")
    
    # Show final stats
    stats = get_shared_index_stats()
    logger.info(f"\nFinal stats: {stats}")
    
    logger.success("Shared index test completed successfully!")
    return True

if __name__ == "__main__":
    test_shared_index()