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