#!/usr/bin/env python3
"""
Utility script to update existing URL cache files from the old format to the new format.
Changes 'search_url_used' (string) to 'search_urls_used' (array).
"""

import os
import sys
import json
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import config as cfg
from src.utils.cache_utils import load_json_data, save_json_data
from src.logging.logger import logger

def update_cache_file_format(cache_file_path):
    """
    Update a single cache file from old format to new format.
    
    Args:
        cache_file_path (str): Path to the cache file to update
        
    Returns:
        bool: True if file was updated, False if no update needed
    """
    if not os.path.exists(cache_file_path):
        return False
        
    cache_data = load_json_data(cache_file_path)
    if not cache_data:
        return False
    
    # Check if file is already in new format but may need reordering
    if 'search_urls_used' in cache_data:
        # Check if search_urls_used is at the top (first key)
        first_key = next(iter(cache_data))
        if first_key == 'search_urls_used':
            logger.info(f"File already in correct format: {cache_file_path}")
            return False
        else:
            logger.info(f"File has new format but wrong order, fixing: {cache_file_path}")
            # Reorder the existing data
            new_cache_data = {
                'search_urls_used': cache_data.get('search_urls_used', []),
                'search_key': cache_data.get('search_key', ''),
                'last_processed_xpath_index': cache_data.get('last_processed_xpath_index', 0),
                'number_of_images_requested': cache_data.get('number_of_images_requested', 0),
                'number_of_urls_found': cache_data.get('number_of_urls_found', 0),
                'request_efficiency': cache_data.get('request_efficiency', 0.0),
                'urls': cache_data.get('urls', [])
            }
            # Save reordered data
            save_json_data(cache_file_path, new_cache_data)
            logger.success(f"Reordered cache file format: {cache_file_path}")
            return True
    
    # Check if file has old format
    if 'search_url_used' not in cache_data:
        logger.warning(f"File doesn't have expected format: {cache_file_path}")
        return False
    
    # Convert old format to new format with proper ordering
    old_search_url = cache_data['search_url_used']
    
    # Create new ordered data structure with search_urls_used at the top
    new_cache_data = {
        'search_urls_used': [old_search_url],
        'search_key': cache_data.get('search_key', ''),
        'last_processed_xpath_index': cache_data.get('last_processed_xpath_index', 0),
        'number_of_images_requested': cache_data.get('number_of_images_requested', 0),
        'number_of_urls_found': cache_data.get('number_of_urls_found', 0),
        'request_efficiency': cache_data.get('request_efficiency', 0.0),
        'urls': cache_data.get('urls', [])
    }
    
    # Save updated data with proper ordering
    save_json_data(cache_file_path, new_cache_data)
    logger.success(f"Updated cache file format: {cache_file_path}")
    return True

def update_all_cache_files():
    """
    Find and update all cache files in the output directory.
    """
    output_dir = cfg.get_output_dir()
    if not os.path.exists(output_dir):
        logger.warning(f"Output directory doesn't exist: {output_dir}")
        return
    
    updated_count = 0
    total_count = 0
    
    # Walk through all directories looking for cache files
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.endswith('_urls.json'):
                cache_file_path = os.path.join(root, file)
                total_count += 1
                
                if update_cache_file_format(cache_file_path):
                    updated_count += 1
    
    logger.info(f"Cache format update complete. Updated {updated_count}/{total_count} files.")

if __name__ == "__main__":
    logger.info("Starting cache format update...")
    update_all_cache_files()
    logger.info("Cache format update finished.")