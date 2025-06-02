import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Tuple
import config as cfg
from src.logging.logger import logger

def backup_output_directory():
    """Create a backup of the current output directory"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"output_backup_{timestamp}"
    output_dir = cfg.get_output_dir()
    backup_path = os.path.join(os.path.dirname(output_dir), backup_name)
    
    logger.info(f"Creating backup: {backup_path}")
    shutil.copytree(output_dir, backup_path)
    logger.info(f"Backup created successfully: {backup_path}")
    return backup_path

def get_existing_structure():
    """Scan existing directory structure to find all class directories"""
    output_dir = cfg.get_output_dir()
    images_base = os.path.join(output_dir, "images")
    metadata_base = os.path.join(output_dir, "metadata")
    
    found_classes = {}
    
    if os.path.exists(images_base):
        for category in os.listdir(images_base):
            category_path = os.path.join(images_base, category)
            if os.path.isdir(category_path):
                for class_name in os.listdir(category_path):
                    class_path = os.path.join(category_path, class_name)
                    if os.path.isdir(class_path):
                        found_classes[class_name] = category
    
    logger.info(f"Found {len(found_classes)} classes in existing structure")
    return found_classes

def move_class_directory(old_category: str, class_name: str):
    """Move a single class directory from old to new structure"""
    old_image_dir = cfg.get_legacy_image_dir(old_category, class_name)
    old_metadata_dir = cfg.get_legacy_metadata_dir(old_category, class_name)
    
    new_image_dir = cfg.get_image_dir(class_name)
    new_metadata_base = cfg.get_metadata_dir(class_name)  # This is now just output/metadata/
    
    moved_files = 0
    
    # Move images directory
    if os.path.exists(old_image_dir):
        os.makedirs(os.path.dirname(new_image_dir), exist_ok=True)
        if os.path.exists(new_image_dir):
            logger.warning(f"Target image directory already exists: {new_image_dir}")
        else:
            shutil.move(old_image_dir, new_image_dir)
            moved_files += len(os.listdir(new_image_dir)) if os.path.exists(new_image_dir) else 0
            logger.info(f"Moved images: {old_image_dir} -> {new_image_dir}")
    
    # Move metadata file (not directory)
    if os.path.exists(old_metadata_dir):
        # Find the metadata file in the old directory
        old_metadata_file = os.path.join(old_metadata_dir, f"{cfg.sanitize_class_name(class_name)}_metadata.json")
        new_metadata_file = cfg.get_image_metadata_file(class_name)
        
        if os.path.exists(old_metadata_file):
            os.makedirs(new_metadata_base, exist_ok=True)
            if os.path.exists(new_metadata_file):
                logger.warning(f"Target metadata file already exists: {new_metadata_file}")
            else:
                shutil.move(old_metadata_file, new_metadata_file)
                logger.info(f"Moved metadata file: {old_metadata_file} -> {new_metadata_file}")
                
                # Remove empty old metadata directory
                try:
                    os.rmdir(old_metadata_dir)
                    logger.info(f"Removed empty metadata directory: {old_metadata_dir}")
                except OSError:
                    logger.warning(f"Could not remove metadata directory (not empty): {old_metadata_dir}")
        else:
            logger.warning(f"Metadata file not found: {old_metadata_file}")
    
    return moved_files

def update_metadata_format(class_name: str, nutritional_category: str):
    """Update metadata file to include nutritional_category and fix relative paths"""
    metadata_file = cfg.get_image_metadata_file(class_name)
    
    if not os.path.exists(metadata_file):
        logger.warning(f"Metadata file not found: {metadata_file}")
        return False
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Create new ordered metadata with nutritional_category right after search_key
        new_metadata = {}
        for key, value in metadata.items():
            new_metadata[key] = value
            if key == 'search_key':
                new_metadata['nutritional_category'] = nutritional_category
        
        # If search_key wasn't found, add nutritional_category anyway
        if 'nutritional_category' not in new_metadata:
            new_metadata['nutritional_category'] = nutritional_category
        
        # Update relative paths in download_data
        if 'images' in new_metadata:
            for image_id, image_data in new_metadata['images'].items():
                if 'download_data' in image_data and 'relative_path' in image_data['download_data']:
                    old_path = image_data['download_data']['relative_path']
                    # Replace "images/{category}/{class}/" with "images/{class}/"
                    path_parts = old_path.split('/')
                    if len(path_parts) >= 4 and path_parts[0] == 'images':
                        new_path = f"images/{class_name}/{'/'.join(path_parts[3:])}"
                        image_data['download_data']['relative_path'] = new_path
                        logger.debug(f"Updated path: {old_path} -> {new_path}")
        
        # Write updated metadata
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(new_metadata, f, indent=4, ensure_ascii=False)
        
        logger.info(f"Updated metadata for {class_name}")
        return True
        
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error updating metadata for {class_name}: {e}")
        return False

def cleanup_empty_directories():
    """Remove empty category directories after migration"""
    output_dir = cfg.get_output_dir()
    
    for base_dir in ["images", "metadata"]:
        base_path = os.path.join(output_dir, base_dir)
        if os.path.exists(base_path):
            for item in os.listdir(base_path):
                item_path = os.path.join(base_path, item)
                if os.path.isdir(item_path):
                    try:
                        os.rmdir(item_path)
                        logger.info(f"Removed empty directory: {item_path}")
                    except OSError:
                        # Directory not empty or other error
                        remaining_items = os.listdir(item_path) if os.path.exists(item_path) else []
                        if remaining_items:
                            logger.warning(f"Directory not empty, skipping: {item_path} (contains: {remaining_items})")

def migrate_directory_structure():
    """
    Main migration function that:
    1. Creates backup
    2. Moves directories from category-based to flat structure
    3. Updates metadata files
    4. Cleans up empty directories
    """
    logger.info("Starting directory structure migration")
    
    # Create backup
    backup_path = backup_output_directory()
    
    try:
        # Get existing structure
        existing_classes = get_existing_structure()
        
        if not existing_classes:
            logger.info("No existing class directories found to migrate")
            return
        
        # Get nutritional category mapping
        category_mapping = cfg.get_nutritional_category_mapping()
        
        total_moved_files = 0
        successful_updates = 0
        
        # Process each class
        for class_name, old_category in existing_classes.items():
            logger.info(f"Processing {class_name} (from {old_category})")
            
            # Move directories
            moved_files = move_class_directory(old_category, class_name)
            total_moved_files += moved_files
            
            # Update metadata
            nutritional_category = category_mapping.get(class_name, old_category)
            if update_metadata_format(class_name, nutritional_category):
                successful_updates += 1
        
        # Cleanup empty directories
        cleanup_empty_directories()
        
        logger.info(f"Migration completed successfully!")
        logger.info(f"- Processed {len(existing_classes)} classes")
        logger.info(f"- Moved {total_moved_files} files")
        logger.info(f"- Updated {successful_updates} metadata files")
        logger.info(f"- Backup created at: {backup_path}")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        logger.error(f"Backup available at: {backup_path}")
        raise

def validate_migration():
    """Validate that migration completed successfully"""
    logger.info("Validating migration...")
    
    issues = []
    
    # Check that all classes from categories.json have directories
    all_classes = cfg.get_all_classes_with_categories()
    
    for class_name, nutritional_category in all_classes:
        image_dir = cfg.get_image_dir(class_name)
        metadata_dir = cfg.get_metadata_dir(class_name)
        metadata_file = cfg.get_image_metadata_file(class_name)
        
        # Check directories exist
        if not os.path.exists(image_dir):
            issues.append(f"Missing image directory: {image_dir}")
        
        if not os.path.exists(metadata_dir):
            issues.append(f"Missing metadata directory: {metadata_dir}")
        
        # Check metadata file exists and has correct format
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # Check nutritional_category field
                if 'nutritional_category' not in metadata:
                    issues.append(f"Missing nutritional_category in metadata: {metadata_file}")
                elif metadata['nutritional_category'] != nutritional_category:
                    issues.append(f"Incorrect nutritional_category in {metadata_file}: expected {nutritional_category}, got {metadata.get('nutritional_category')}")
                
                # Check relative paths are updated
                if 'images' in metadata:
                    for image_id, image_data in metadata['images'].items():
                        if 'download_data' in image_data and 'relative_path' in image_data['download_data']:
                            rel_path = image_data['download_data']['relative_path']
                            if rel_path.count('/') > 2:  # Should be images/ClassName/filename
                                issues.append(f"Relative path not updated in {metadata_file}: {rel_path}")
                
            except (json.JSONDecodeError, IOError) as e:
                issues.append(f"Error reading metadata file {metadata_file}: {e}")
    
    if issues:
        logger.error(f"Validation failed with {len(issues)} issues:")
        for issue in issues:
            logger.error(f"  - {issue}")
        return False
    else:
        logger.info("Validation passed - migration completed successfully!")
        return True

if __name__ == "__main__":
    migrate_directory_structure()
    validate_migration()