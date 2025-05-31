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
        metadata_file = cfg.get_image_metadata_file(category_dir, class_name)
        base_output_dir = cfg.get_output_dir()
        
        if not os.path.isfile(metadata_file):
            logger.warning(f"Missing metadata file for '{class_name}' in '{category_dir}'.")
            return False

        metadata = load_json_data(metadata_file)
        if not metadata:
            logger.warning(f"Metadata is empty or invalid for '{class_name}' in '{category_dir}'.")
            return False

        images_dict = metadata.get('images', {})
        if not isinstance(images_dict, dict):
            logger.warning(f"Invalid images dict for '{class_name}' in '{category_dir}'.")
            return False

        sorted_keys = sorted(images_dict.keys(), key=lambda k: int(k) if k.isdigit() else 0)
        target_keys = sorted_keys[:cfg.NUM_IMAGES_PER_CLASS]
        
        if len(target_keys) < cfg.NUM_IMAGES_PER_CLASS:
            logger.warning(f"Cache not complete for '{class_name}' in '{category_dir}': Not enough URL records ({len(target_keys)}/{cfg.NUM_IMAGES_PER_CLASS}).")
            return False

        metadata_updated = False
        verified_image_count = 0

        for url_key in target_keys:
            img_data = images_dict[url_key]
            
            if 'download_data' not in img_data:
                logger.info(f"No download_data for key {url_key} in '{class_name}' - needs download.")
                continue
                
            download_data = img_data['download_data']
            relative_path = download_data.get('relative_path')
            expected_hash = download_data.get('hash')
            
            if not relative_path or not expected_hash:
                logger.warning(f"Invalid download_data for key {url_key} - removing download_data only.")
                del img_data['download_data']
                metadata_updated = True
                continue

            absolute_path = os.path.join(base_output_dir, relative_path)

            if os.path.exists(absolute_path):
                try:
                    with open(absolute_path, 'rb') as f_img:
                        content_hash = hashlib.md5(f_img.read()).hexdigest()
                    if content_hash == expected_hash:
                        verified_image_count += 1
                        continue
                    else:
                        logger.warning(f"Hash mismatch for {download_data.get('filename')} - removing download_data only, keeping URL.")
                        try:
                            os.remove(absolute_path)
                            logger.info(f"🗑️ Removed corrupted file: {absolute_path}")
                        except Exception as e:
                            logger.error(f"Failed to remove corrupted file {absolute_path}: {e}")
                        
                        del img_data['download_data']
                        metadata_updated = True
                        logger.info(f"🔄 Removed download_data for {url_key}, keeping URL for redownload")
                        continue
                        
                except Exception as e_hash:
                    logger.error(f"Error verifying hash for {download_data.get('filename')}: {e_hash}")
                    del img_data['download_data']
                    metadata_updated = True
                    continue
            else:
                logger.warning(f"File missing: {absolute_path} - removing download_data only, keeping URL.")
                del img_data['download_data']
                metadata_updated = True
                logger.info(f"🔄 Removed download_data for missing file {url_key}, keeping URL for redownload")

        if metadata_updated:
            save_json_data(metadata_file, metadata)
            logger.info(f"💾 Updated metadata after cleaning corrupted download_data")

        if verified_image_count < cfg.NUM_IMAGES_PER_CLASS:
            logger.warning(f"Cache not complete for '{class_name}' in '{category_dir}': Only {verified_image_count}/{cfg.NUM_IMAGES_PER_CLASS} images verified and downloaded.")
            return False
        
        logger.info(f"✅ Cache is complete for '{class_name}' in '{category_dir}' - {verified_image_count}/{cfg.NUM_IMAGES_PER_CLASS} images verified.")
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
            
        for class_dir in os.listdir(metadata_base_dir):
            class_path = os.path.join(metadata_base_dir, class_dir)
            if not os.path.isdir(class_path):
                continue
                
            if exclude_class and class_dir == exclude_class:
                continue
                
            metadata_file = cfg.get_image_metadata_file(category_dir, class_dir)
            if os.path.exists(metadata_file):
                metadata = load_json_data(metadata_file)
                if metadata and 'images' in metadata:
                    images_dict = metadata['images']
                    if isinstance(images_dict, dict):
                        for img_data in images_dict.values():
                            if 'fetch_data' in img_data and 'link' in img_data['fetch_data']:
                                all_urls.add(img_data['fetch_data']['link'])
                        
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
            
        for category_dir in os.listdir(metadata_base_dir):
            category_path = os.path.join(metadata_base_dir, category_dir)
            if not os.path.isdir(category_path):
                continue
                
            if exclude_category and category_dir == exclude_category:
                continue
                
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