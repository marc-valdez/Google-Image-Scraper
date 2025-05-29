import os
import sys
import json
from urllib.parse import urlparse

# Add project root to path for standalone execution
if __name__ == "__main__":
    # Get the project root directory (two levels up from this file)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    sys.path.insert(0, project_root)

from src.utils.cache_utils import load_json_data, save_json_data
from src.logging.logger import logger
import config as cfg

def migrate_legacy_files(category_dir: str, class_name: str) -> bool:
    """
    Migrates old format (_urls.json + _metadata.json) to new unified format.
    
    Args:
        category_dir: Category directory name
        class_name: Class name
        
    Returns:
        bool: True if migration was successful or no migration needed
    """
    try:
        # Get file paths
        metadata_dir = cfg.get_metadata_dir(category_dir, class_name)
        sanitized_name = cfg.sanitize_class_name(class_name)
        
        old_url_file = os.path.join(metadata_dir, f"{sanitized_name}_urls.json")
        old_metadata_file = os.path.join(metadata_dir, f"{sanitized_name}_metadata.json")
        new_metadata_file = cfg.get_image_metadata_file(category_dir, class_name)
        
        # Check if old files exist
        has_old_url_file = os.path.exists(old_url_file)
        has_old_metadata_file = os.path.exists(old_metadata_file)
        has_new_file = os.path.exists(new_metadata_file)
        
        # If new format already exists and is complete, no migration needed
        if has_new_file:
            new_data = load_json_data(new_metadata_file)
            if new_data and 'images' in new_data and new_data['images']:
                logger.info(f"New format already exists for '{class_name}' - skipping migration")
                return True
        
        # If no old files exist, no migration needed
        if not has_old_url_file and not has_old_metadata_file:
            logger.info(f"No legacy files found for '{class_name}' - no migration needed")
            return True
            
        logger.info(f"Migrating legacy format to unified format for '{class_name}'")
        
        # Load old data
        old_url_data = load_json_data(old_url_file) if has_old_url_file else {}
        old_metadata_data = load_json_data(old_metadata_file) if has_old_metadata_file else {}
        
        # Create new unified structure
        unified_data = {
            "search_urls_used": old_url_data.get('search_urls_used', []),
            "search_key": old_url_data.get('search_key', class_name),
            "last_xpath_index": old_url_data.get('last_processed_xpath_index', 1),
            "number_of_images_requested": old_url_data.get('number_of_images_requested', cfg.NUM_IMAGES_PER_CLASS),
            "number_of_urls_found": old_url_data.get('number_of_urls_found', 0),
            "images": {}
        }
        
        # Handle different old URL formats
        old_urls = old_url_data.get('urls', [])
        
        # Handle URLs as list (new old format) vs dict (older format)
        if isinstance(old_urls, list):
            # URLs are in a list: ["url1", "url2", "url3"]
            url_list = old_urls
        elif isinstance(old_urls, dict):
            # URLs are in a dict: {"img_001": "url1", "img_002": "url2"}
            url_list = list(old_urls.values())
        else:
            logger.warning(f"Unexpected URLs format for '{class_name}': {type(old_urls)}")
            url_list = []
        
        # Get image_cache for download metadata (keyed by URL)
        image_cache = old_metadata_data.get('image_cache', {})
        
        # Process each URL with index
        for index, url in enumerate(url_list, 1):
            new_key = f"{index:03d}"  # 001, 002, 003, etc.
            
            # Create fetch_data
            parsed_url = urlparse(url)
            original_filename = os.path.basename(parsed_url.path) or "unknown"
            domain = parsed_url.netloc
            
            unified_data["images"][new_key] = {
                "fetch_data": {
                    "link": url,
                    "domain": domain,
                    "original_filename": original_filename,
                    "xpath_index": index  # Use index as xpath_index
                }
            }
            
            # Add download_data if URL exists in image_cache
            if url in image_cache:
                cache_entry = image_cache[url]
                unified_data["images"][new_key]["download_data"] = {
                    "filename": cache_entry.get("filename", ""),
                    "relative_path": cache_entry.get("relative_path", ""),
                    "hash": cache_entry.get("hash", ""),
                    "bytes": cache_entry.get("size", 0),
                    "width": cache_entry.get("width", 0),
                    "height": cache_entry.get("height", 0),
                    "mode": cache_entry.get("mode", ""),
                    "format": cache_entry.get("format", ""),
                    "downloaded_at": cache_entry.get("downloaded_at", "")
                }
        
        # Save unified format
        if save_json_data(new_metadata_file, unified_data):
            logger.success(f"Successfully migrated '{class_name}' to unified format")
            
            # Optionally backup old files before removal
            if has_old_url_file:
                backup_path = old_url_file + ".backup"
                os.rename(old_url_file, backup_path)
                logger.info(f"Backed up old URL file to {backup_path}")
                
            if has_old_metadata_file and old_metadata_file != new_metadata_file:
                backup_path = old_metadata_file + ".backup"
                os.rename(old_metadata_file, backup_path)
                logger.info(f"Backed up old metadata file to {backup_path}")
                
            return True
        else:
            logger.error(f"Failed to save unified metadata for '{class_name}'")
            return False
            
    except Exception as e:
        logger.error(f"Error migrating '{class_name}': {e}")
        return False

def discover_and_migrate_all_legacy_files(output_dir_base: str = None) -> int:
    """
    Discovers and migrates all legacy files by scanning the output directory.
    
    Args:
        output_dir_base: Base output directory to scan (uses cfg.OUTPUT_DIR_BASE if None)
        
    Returns:
        int: Number of successfully migrated classes
    """
    if output_dir_base is None:
        output_dir_base = cfg.OUTPUT_DIR_BASE
        
    output_dir = os.path.join(os.getcwd(), output_dir_base)
    metadata_dir = os.path.join(output_dir, "metadata")
    
    if not os.path.exists(metadata_dir):
        logger.warning(f"Metadata directory not found: {metadata_dir}")
        return 0
    
    migrated_count = 0
    total_count = 0
    legacy_files_found = []
    
    # Scan for legacy files
    for root, dirs, files in os.walk(metadata_dir):
        for file in files:
            if file.endswith('_urls.json') and not file.endswith('.backup'):
                legacy_files_found.append(os.path.join(root, file))
    
    logger.info(f"Found {len(legacy_files_found)} legacy _urls.json files to process")
    
    # Process each legacy file
    for url_file_path in legacy_files_found:
        try:
            # Extract category and class from path
            rel_path = os.path.relpath(url_file_path, metadata_dir)
            path_parts = rel_path.split(os.sep)
            
            if len(path_parts) >= 2:
                category_dir = path_parts[0]
                class_dir = path_parts[1]
                filename = path_parts[-1]
                
                # Extract class name from filename (remove _urls.json suffix)
                if filename.endswith('_urls.json'):
                    sanitized_class_name = filename[:-10]  # Remove '_urls.json'
                    
                    # Try to reverse sanitize to get original class name
                    # This is best effort - may not be perfect for all cases
                    class_name = class_dir  # Use directory name as fallback
                    
                    total_count += 1
                    logger.info(f"Processing: {category_dir}/{class_name}")
                    
                    if migrate_legacy_files(category_dir, class_name):
                        migrated_count += 1
                        logger.success(f"✓ Migrated {category_dir}/{class_name}")
                    else:
                        logger.error(f"✗ Failed to migrate {category_dir}/{class_name}")
                        
        except Exception as e:
            logger.error(f"Error processing {url_file_path}: {e}")
    
    logger.info(f"Migration complete: {migrated_count}/{total_count} classes migrated successfully")
    
    # Report remaining legacy files
    remaining_legacy = []
    for root, dirs, files in os.walk(metadata_dir):
        for file in files:
            if file.endswith('_urls.json') and not file.endswith('.backup'):
                remaining_legacy.append(os.path.join(root, file))
    
    if remaining_legacy:
        logger.warning(f"{len(remaining_legacy)} legacy files still remain:")
        for file in remaining_legacy:
            logger.warning(f"  - {file}")
    else:
        logger.success("All legacy files have been migrated!")
    
    return migrated_count

def migrate_all_legacy_files(categories_data: dict) -> int:
    """
    Migrates all legacy files based on categories data.
    
    Args:
        categories_data: Dictionary of categories and their classes
        
    Returns:
        int: Number of successfully migrated classes
    """
    migrated_count = 0
    total_count = 0
    
    for category, class_names in categories_data.items():
        if not isinstance(class_names, list):
            continue
            
        for class_name in class_names:
            if isinstance(class_name, str) and class_name.strip():
                total_count += 1
                if migrate_legacy_files(category, class_name.strip()):
                    migrated_count += 1
                    
    logger.info(f"Migration complete: {migrated_count}/{total_count} classes migrated successfully")
    return migrated_count

if __name__ == "__main__":
    """
    Standalone migration script.
    Usage: python src/utils/migrate_metadata.py [output_dir_base]
    """
    import sys
    
    # Get output directory from command line or use default
    output_dir_base = sys.argv[1] if len(sys.argv) > 1 else cfg.OUTPUT_DIR_BASE
    
    logger.info(f"Starting migration for output directory: {output_dir_base}")
    logger.info("This will convert all legacy _urls.json + _metadata.json files to unified format")
    
    try:
        migrated_count = discover_and_migrate_all_legacy_files(output_dir_base)
        
        if migrated_count > 0:
            logger.success(f"Successfully migrated {migrated_count} classes to unified format!")
        else:
            logger.info("No legacy files found or all files already migrated.")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
