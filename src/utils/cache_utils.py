import os
import json
import hashlib
from src.logging.logger import logger
import config as cfg

def ensure_cache_dir(cache_path):
    try:
        os.makedirs(cache_path, exist_ok=True)
    except Exception as e:
        logger.error(f"Could not create cache directory {cache_path}: {e}")
        raise

def load_json_data(file_path):
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in file {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Could not load JSON from {file_path}: {e}")
        return None

def save_json_data(file_path, data):
    try:
        parent_dir = os.path.dirname(file_path)
        if parent_dir: 
            os.makedirs(parent_dir, exist_ok=True)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Could not save JSON to {file_path}: {e}")
        return False

def remove_file_if_exists(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False 
    except Exception as e:
        logger.error(f"Could not remove file {file_path}: {e}")
        return False
    
def is_cache_complete(category_dir: str, class_name: str):
    try:
        url_cache_file = cfg.get_url_cache_file(category_dir, class_name)
        image_metadata_file = cfg.get_image_metadata_file(category_dir, class_name)
        base_output_dir = cfg.get_output_dir() # Get base output directory
        
        if not os.path.isfile(url_cache_file):
            logger.warning(f"Missing URL cache file for '{class_name}' in '{category_dir}'.")
            return False
            
        if not os.path.isfile(image_metadata_file):
            logger.warning(f"Missing image metadata file for '{class_name}' in '{category_dir}'.")
            return False

        url_data = load_json_data(url_cache_file)
        image_metadata = load_json_data(image_metadata_file)

        if not url_data: # Handle case where url_data is None
            logger.warning(f"URL cache data is empty or invalid for '{class_name}' in '{category_dir}'.")
            return False
        if not image_metadata: # Handle case where image_metadata is None
            logger.warning(f"Image metadata is empty or invalid for '{class_name}' in '{category_dir}'.")
            return False

        urls_found = url_data.get('urls', [])
        if not isinstance(urls_found, list) or len(urls_found) < cfg.NUM_IMAGES_PER_CLASS:
            logger.warning(f"Cache not complete for '{class_name}' in '{category_dir}': Not enough URLs in cache ({len(urls_found)}/{cfg.NUM_IMAGES_PER_CLASS}).")
            return False

        images_in_metadata = image_metadata.get('image_cache', {})
        if not isinstance(images_in_metadata, dict):
            logger.error(f"Cache not complete for '{class_name}' in '{category_dir}': Invalid image_cache format.")
            return False

        verified_image_count = 0
        target_urls_from_cache = urls_found[:cfg.NUM_IMAGES_PER_CLASS]

        for url in target_urls_from_cache:
            if url in images_in_metadata:
                img_entry = images_in_metadata[url]
                relative_path = img_entry.get('relative_path')
                
                if not relative_path:
                    logger.error(f"Missing 'relative_path' for URL {logger.truncate_url(url)} in metadata for '{class_name}'.")
                    continue

                absolute_path = os.path.join(base_output_dir, relative_path)

                if os.path.exists(absolute_path):
                    try:
                        with open(absolute_path, 'rb') as f_img:
                            content_hash = hashlib.md5(f_img.read()).hexdigest()
                        if content_hash == img_entry.get('hash'):
                            verified_image_count += 1
                        else:
                            logger.error(f"Hash mismatch for cached image: {img_entry.get('filename')} (Path: {absolute_path})")
                    except Exception as e_hash:
                        logger.error(f"Error verifying hash for {img_entry.get('filename')} (Path: {absolute_path}): {e_hash}")
                else:
                    logger.error(f"Cached image file missing: {absolute_path} (Filename: {img_entry.get('filename')})")
            else:
                logger.warning(f"URL {logger.truncate_url(url)} not found in image metadata.")


        if verified_image_count < cfg.NUM_IMAGES_PER_CLASS:
            logger.warning(f"Cache not complete for '{class_name}' in '{category_dir}': Not enough verified images in metadata ({verified_image_count}/{cfg.NUM_IMAGES_PER_CLASS}).")
            return False
        
        logger.info(f"Cache is complete for '{class_name}' in '{category_dir}'.")
        return True
        
    except Exception as e:
        logger.error(f"Error checking cache completeness for '{class_name}' in '{category_dir}': {e}")
        return False

def get_all_urls_in_category(category_dir: str, exclude_class: str = None):
    try:
        all_urls = set()
        metadata_base_dir = os.path.join(cfg.get_output_dir(), "metadata", category_dir)
        
        if not os.path.exists(metadata_base_dir):
            return all_urls
            
        # Iterate through all class directories in the category
        for class_dir in os.listdir(metadata_base_dir):
            class_path = os.path.join(metadata_base_dir, class_dir)
            if not os.path.isdir(class_path):
                continue
                
            # Skip the excluded class
            if exclude_class and class_dir == exclude_class:
                continue
                
            # Look for URL cache files in this class directory
            url_cache_file = cfg.get_url_cache_file(category_dir, class_dir)
            if os.path.exists(url_cache_file):
                cache_data = load_json_data(url_cache_file)
                if cache_data and 'urls' in cache_data:
                    urls = cache_data['urls']
                    if isinstance(urls, list):
                        all_urls.update(urls)
                        
        return all_urls
        
    except Exception as e:
        logger.error(f"Error getting all URLs in category '{category_dir}': {e}")
        return set()

def get_all_urls_across_categories(exclude_category: str = None, exclude_class: str = None):
    try:
        all_urls = set()
        metadata_base_dir = os.path.join(cfg.get_output_dir(), "metadata")
        
        if not os.path.exists(metadata_base_dir):
            return all_urls
            
        # Iterate through all category directories
        for category_dir in os.listdir(metadata_base_dir):
            category_path = os.path.join(metadata_base_dir, category_dir)
            if not os.path.isdir(category_path):
                continue
                
            # Skip the excluded category
            if exclude_category and category_dir == exclude_category:
                continue
                
            # Get URLs from this category
            category_urls = get_all_urls_in_category(category_dir, exclude_class if category_dir == exclude_category else None)
            all_urls.update(category_urls)
                        
        return all_urls
        
    except Exception as e:
        logger.error(f"Error getting all URLs across categories: {e}")
        return set()

def is_url_duplicate_in_category(url: str, category_dir: str, current_class: str):
    try:
        existing_urls = get_all_urls_in_category(category_dir, exclude_class=current_class)
        return url in existing_urls
    except Exception as e:
        logger.error(f"Error checking URL duplication in category '{category_dir}': {e}")
        return False

def is_url_duplicate_across_categories(url: str, current_category: str = None, current_class: str = None):
    try:
        existing_urls = get_all_urls_across_categories(exclude_category=current_category, exclude_class=current_class)
        return url in existing_urls
    except Exception as e:
        logger.error(f"Error checking URL duplication across categories: {e}")
        return False