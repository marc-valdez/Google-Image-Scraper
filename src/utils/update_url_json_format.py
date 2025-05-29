#!/usr/bin/env python3
"""
Comprehensive utility script to update existing URL cache files to the latest format.

This script combines the functionality of the original update_url_json_format.py and
update_search_url_format.py scripts to provide a unified solution for:

1. Converting legacy JSON formats to the new ImageScraperLogger structure
2. Converting 'search_url_used' (string) to 'search_urls_used' (array)
3. Ensuring proper field ordering with 'search_urls_used' at the top
4. Handling various fallback scenarios for unrecognized formats

The script processes all *_urls.json files in the output directory and its subdirectories.
"""

import json
import os
import fnmatch
import sys
import uuid
from pathlib import Path

# Add project root to sys.path to allow for src.logging.logger import
project_root_for_import = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root_for_import not in sys.path:
    sys.path.insert(0, project_root_for_import)

import config as cfg
from src.logging.logger import logger
from src.utils.cache_utils import load_json_data, save_json_data

def find_files(directory, pattern):
    """Helper function to find files using os.walk"""
    file_list = []
    if not os.path.isdir(directory):
        logger.error(f"The directory '{os.path.abspath(directory)}' does not exist or is not a directory.")
        return file_list

    for root, _, filenames in os.walk(directory):
        for filename_in_dir in filenames:
            if fnmatch.fnmatch(filename_in_dir, pattern):
                full_path = os.path.join(root, filename_in_dir)
                file_list.append(full_path)
    return file_list

def update_cache_file_format(cache_file_path):
    """
    Update a single cache file from old format to new format.
    Handles both legacy format conversion and search_url_used to search_urls_used conversion.
    
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
    
    # Check if file is already in new format with search_urls_used
    if 'search_urls_used' in cache_data:
        # Check if search_urls_used is at the top (first key) and has all required fields
        expected_keys = ['search_urls_used', 'search_key', 'last_processed_xpath_index',
                        'number_of_images_requested', 'number_of_urls_found', 'request_efficiency', 'urls']
        
        if all(k in cache_data for k in expected_keys):
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
    
    # Handle conversion from search_url_used to search_urls_used
    if 'search_url_used' in cache_data and all(k in cache_data for k in ['search_url_used', 'search_key', 'last_processed_xpath_index', 'number_of_images_requested', 'number_of_urls_found', 'request_efficiency', 'urls']):
        logger.info(f"Converting search_url_used to search_urls_used format: {cache_file_path}")
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
    
    # Handle legacy format conversion (original functionality)
    search_urls_used = ["N/A_migrated"]
    search_key = ""
    last_processed_xpath_index = 0
    number_of_images_requested = 0
    number_of_urls_found = 0
    found_urls = []

    if 'search_url_used' in cache_data and 'search_key' in cache_data and 'urls_found_count' in cache_data:
        logger.info(f"Processing legacy format with recognized old structure: {cache_file_path}")
        old_search_url = cache_data.get('search_url_used', "N/A_migrated")
        search_urls_used = [old_search_url]
        search_key = cache_data.get('search_key', "")
        number_of_images_requested = cache_data.get('number_of_images_requested', 0)
        number_of_urls_found = cache_data.get('urls_found_count', 0)
        found_urls = cache_data.get('urls', [])
        last_processed_xpath_index = cache_data.get('processed_thumbnails_count', 0)
    else:
        logger.info(f"Attempting to process with generic fallback: {cache_file_path}")
        if isinstance(cache_data, list):
            found_urls = cache_data
        elif isinstance(cache_data, dict) and 'urls' in cache_data:
            found_urls = cache_data.get('urls', [])
        elif isinstance(cache_data, dict) and 'results' in cache_data:
            found_urls = cache_data.get('results', [])
        else:
            logger.warning(f"Could not reliably extract URLs or map fields from '{cache_file_path}'. Structure: {list(cache_data.keys()) if isinstance(cache_data, dict) else 'list'}. Skipping.")
            return False

        if not isinstance(found_urls, list):
            logger.warning(f"Extracted 'urls' in '{cache_file_path}' is not a list. Skipping.")
            return False

        number_of_urls_found = len(found_urls)
        number_of_images_requested = cache_data.get('number_of_images_requested',
                                    cache_data.get('limit',
                                                   cache_data.get('count', number_of_urls_found)))
        if number_of_images_requested == 0 and number_of_urls_found > 0:
            number_of_images_requested = number_of_urls_found
        elif number_of_images_requested == 0 and number_of_urls_found == 0:
             number_of_images_requested = 1

        file_name_without_ext = os.path.splitext(os.path.basename(cache_file_path))[0]
        search_key_from_filename = file_name_without_ext.replace("_urls", "")
        search_key = cache_data.get('search_key', search_key_from_filename)
        old_search_url = cache_data.get('search_url_used', "N/A_migrated_fallback")
        search_urls_used = [old_search_url]
        last_processed_xpath_index = cache_data.get('last_processed_xpath_index', cache_data.get('processed_thumbnails_count', 0))

    request_efficiency = number_of_urls_found / number_of_images_requested if number_of_images_requested > 0 else 0

    updated_data = {
        'search_urls_used': search_urls_used,
        'search_key': search_key,
        'last_processed_xpath_index': last_processed_xpath_index,
        'number_of_images_requested': number_of_images_requested,
        'number_of_urls_found': number_of_urls_found,
        'request_efficiency': request_efficiency,
        'urls': found_urls
    }

    save_json_data(cache_file_path, updated_data)
    logger.success(f"Successfully updated '{cache_file_path}' to new format")
    return True

def update_json_files(output_directory_path):
    """
    Updates the format of *_urls.json files in the specified output directory
    to align with the new structure using ImageScraperLogger.
    Also handles conversion from 'search_url_used' (string) to 'search_urls_used' (array).
    """
    file_pattern_to_search = "*_urls.json"
    logger.info(f"Searching for '{file_pattern_to_search}' files in '{os.path.abspath(output_directory_path)}' and its subdirectories...")
    json_files = find_files(output_directory_path, file_pattern_to_search)

    if not json_files:
        logger.warning(f"No '{file_pattern_to_search}' files found in '{os.path.abspath(output_directory_path)}' or its subdirectories.")
        return

    logger.info(f"Found {len(json_files)} JSON files to process.")

    progress_task_id = f"update_json_task_{uuid.uuid4()}"
    logger.start_progress(total=len(json_files), description="Updating JSON files", worker_id=progress_task_id)

    updated_count = 0
    for file_path in json_files:
        try:
            if update_cache_file_format(file_path):
                updated_count += 1
        except Exception as e:
            logger.error(f"An error occurred while processing '{file_path}': {e}. Skipping.")
        finally:
            logger.update_progress(worker_id=progress_task_id)

    logger.complete_progress(worker_id=progress_task_id)
    logger.success(f"Finished processing all files. Updated {updated_count}/{len(json_files)} files.")

def update_all_cache_files():
    """
    Find and update all cache files in the output directory.
    This function provides the same interface as the original update_search_url_format.py
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

if __name__ == '__main__':
    logger.set_verbose(True) # Enable verbose info messages for this script
    
    # Check if user wants to use the new cfg.get_output_dir() method
    # or the old project_root + OUTPUT_DIR_BASE method
    try:
        target_output_directory = cfg.get_output_dir()
        logger.info("Using cfg.get_output_dir() method for output directory")
    except AttributeError:
        # Fallback to old method if get_output_dir() doesn't exist
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        output_dir_name = cfg.OUTPUT_DIR_BASE
        target_output_directory = os.path.join(project_root, output_dir_name)
        logger.info("Using legacy OUTPUT_DIR_BASE method for output directory")

    logger.status(f"Script will search in base directory: {os.path.abspath(target_output_directory)}")

    if not os.path.isdir(target_output_directory):
        logger.error(f"The base directory '{os.path.abspath(target_output_directory)}' does not exist.")
        logger.warning(f"Please ensure the directory exists or modify the output directory configuration.")
    else:
        logger.info("Starting comprehensive URL cache format update...")
        logger.info("This script will:")
        logger.info("1. Convert legacy formats to new format")
        logger.info("2. Convert 'search_url_used' (string) to 'search_urls_used' (array)")
        logger.info("3. Ensure proper field ordering")
        update_json_files(target_output_directory)
        logger.info("URL cache format update finished.")