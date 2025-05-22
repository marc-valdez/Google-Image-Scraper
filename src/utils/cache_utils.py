import os
import json
import hashlib
from src.logging.logger import logger
from src.helpers import config as cfg

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
    
def is_cache_complete(category_dir: str, search_term: str):
    try:
        url_cache_file = cfg.get_url_cache_file(category_dir, search_term)
        image_metadata_file = cfg.get_image_metadata_file(category_dir, search_term)
        
        if not os.path.isfile(url_cache_file) or not os.path.isfile(image_metadata_file):
            logger.debug(f"Cache not complete for '{search_term}' in '{category_dir}': Missing cache files.")
            return False

        url_data = load_json_data(url_cache_file)
        image_metadata = load_json_data(image_metadata_file)

        if not url_data or not image_metadata:
            logger.debug(f"Cache not complete for '{search_term}' in '{category_dir}': Corrupted or empty cache files.")
            return False

        urls_found = url_data.get('urls', [])
        if not isinstance(urls_found, list) or len(urls_found) < cfg.NUM_IMAGES_PER_CLASS:
            logger.debug(f"Cache not complete for '{search_term}' in '{category_dir}': Not enough URLs in cache ({len(urls_found)}/{cfg.NUM_IMAGES_PER_CLASS}).")
            return False

        images_in_metadata = image_metadata.get('image_cache', {})
        if not isinstance(images_in_metadata, dict):
            logger.debug(f"Cache not complete for '{search_term}' in '{category_dir}': Invalid image_cache format.")
            return False

        verified_image_count = 0
        target_urls_from_cache = urls_found[:cfg.NUM_IMAGES_PER_CLASS]

        for url in target_urls_from_cache:
            if url in images_in_metadata:
                img_entry = images_in_metadata[url]
                if os.path.exists(img_entry.get('path', '')):
                    try:
                        with open(img_entry['path'], 'rb') as f_img:
                            content_hash = hashlib.md5(f_img.read()).hexdigest()
                        if content_hash == img_entry.get('hash'):
                            verified_image_count += 1
                        else:
                            logger.debug(f"Hash mismatch for cached image: {img_entry.get('filename')}")
                    except Exception as e_hash:
                        logger.debug(f"Error verifying hash for {img_entry.get('filename')}: {e_hash}")
                else:
                    logger.debug(f"Cached image file missing: {img_entry.get('path')}")
            else:
                logger.debug(f"URL {logger.truncate_url(url)} not found in image metadata.")


        if verified_image_count < cfg.NUM_IMAGES_PER_CLASS:
            logger.debug(f"Cache not complete for '{search_term}' in '{category_dir}': Not enough verified images in metadata ({verified_image_count}/{cfg.NUM_IMAGES_PER_CLASS}).")
            return False
        
        logger.info(f"Cache is complete for '{search_term}' in '{category_dir}'.")
        return True
        
    except Exception as e:
        logger.error(f"Error checking cache completeness for '{search_term}' in '{category_dir}': {e}")
        return False