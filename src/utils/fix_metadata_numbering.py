import os
import sys

if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from src.utils.cache_utils import load_json_data, save_json_data
from src.logging.logger import logger
import config as cfg

def fix_metadata_numbering(category_dir: str, class_name: str, max_images: int = None):
    cache_file_path = cfg.get_image_metadata_file(category_dir, class_name)
    
    if not os.path.exists(cache_file_path):
        logger.warning(f"Metadata file not found: {cache_file_path}")
        return False
    
    cache_data = load_json_data(cache_file_path)
    if not cache_data or 'images' not in cache_data:
        logger.warning(f"No images data found in metadata: {cache_file_path}")
        return False
    
    images_dict = cache_data['images']
    if not images_dict:
        logger.info(f"No images to fix for {class_name}")
        return True
    
    if max_images is None:
        max_images = cache_data.get('number_of_images_requested', cfg.NUM_IMAGES_PER_CLASS)
    
    existing_indices = []
    for key in images_dict.keys():
        try:
            index = int(key)
            existing_indices.append(index)
        except ValueError:
            continue
    
    if not existing_indices:
        logger.warning(f"No valid numeric indices found for {class_name}")
        return False
    
    existing_indices.sort()
    
    logger.info(f"Fixing numbering for {class_name}: found {len(existing_indices)} images, target limit: {max_images}")
    
    new_images_dict = {}
    images_to_rename = []
    
    limited_indices = existing_indices[:max_images]
    
    for new_index, old_index in enumerate(limited_indices, 1):
        old_key = f"{old_index:03d}"
        new_key = f"{new_index:03d}"
        
        if old_key in images_dict:
            new_images_dict[new_key] = images_dict[old_key]
            
            if old_index != new_index:
                images_to_rename.append((old_index, new_index))
    
    excess_count = len(existing_indices) - len(limited_indices)
    if excess_count > 0:
        logger.info(f"Removing {excess_count} excess images (beyond limit of {max_images})")
        excess_indices = existing_indices[max_images:]
        for excess_index in excess_indices:
            _delete_image_file(category_dir, class_name, excess_index)
    
    cache_data['images'] = new_images_dict
    cache_data['number_of_urls_found'] = len(new_images_dict)
    
    save_json_data(cache_file_path, cache_data)
    
    _rename_image_files(category_dir, class_name, images_to_rename)
    
    gaps_filled = len([i for i, old_i in enumerate(limited_indices, 1) if i != old_i])
    
    logger.success(f"Fixed numbering for {class_name}: {gaps_filled} gaps filled, {excess_count} excess removed, final count: {len(new_images_dict)}")
    
    return True

def _rename_image_files(category_dir: str, class_name: str, rename_list: list):
    class_dir = cfg.get_image_dir(category_dir, class_name)
    
    if not os.path.exists(class_dir):
        logger.warning(f"Class directory not found: {class_dir}")
        return
    
    temp_suffix = "_temp_rename"
    
    for old_index, new_index in rename_list:
        old_pattern = f"{old_index:03d}"
        new_pattern = f"{new_index:03d}"
        temp_pattern = f"{old_index:03d}{temp_suffix}"
        
        for filename in os.listdir(class_dir):
            if filename.startswith(old_pattern + "."):
                old_path = os.path.join(class_dir, filename)
                extension = os.path.splitext(filename)[1]
                temp_path = os.path.join(class_dir, temp_pattern + extension)
                
                try:
                    os.rename(old_path, temp_path)
                    logger.info(f"Temp renamed: {filename} -> {temp_pattern + extension}")
                except OSError as e:
                    logger.error(f"Failed to temp rename {old_path}: {e}")
    
    for old_index, new_index in rename_list:
        old_pattern = f"{old_index:03d}"
        new_pattern = f"{new_index:03d}"
        temp_pattern = f"{old_index:03d}{temp_suffix}"
        
        for filename in os.listdir(class_dir):
            if filename.startswith(temp_pattern):
                temp_path = os.path.join(class_dir, filename)
                extension = os.path.splitext(filename)[1]
                new_filename = new_pattern + extension
                new_path = os.path.join(class_dir, new_filename)
                
                try:
                    os.rename(temp_path, new_path)
                    logger.info(f"Final renamed: {filename} -> {new_filename}")
                except OSError as e:
                    logger.error(f"Failed to final rename {temp_path}: {e}")

def _delete_image_file(category_dir: str, class_name: str, index: int):
    class_dir = cfg.get_image_dir(category_dir, class_name)
    
    if not os.path.exists(class_dir):
        return
    
    pattern = f"{index:03d}"
    
    for filename in os.listdir(class_dir):
        if filename.startswith(pattern + "."):
            file_path = os.path.join(class_dir, filename)
            try:
                os.remove(file_path)
                logger.info(f"Deleted excess file: {filename}")
            except OSError as e:
                logger.error(f"Failed to delete {file_path}: {e}")

def fix_all_metadata_numbering(target_category: str = None, target_class: str = None, max_images: int = None):
    output_dir = cfg.get_output_dir()
    images_base_dir = os.path.join(output_dir, "images")
    
    if not os.path.exists(images_base_dir):
        logger.error(f"Images directory not found: {images_base_dir}")
        return
    
    categories_to_process = []
    
    if target_category:
        category_path = os.path.join(images_base_dir, target_category)
        if os.path.exists(category_path):
            categories_to_process.append(target_category)
        else:
            logger.error(f"Category not found: {target_category}")
            return
    else:
        for item in os.listdir(images_base_dir):
            item_path = os.path.join(images_base_dir, item)
            if os.path.isdir(item_path):
                categories_to_process.append(item)
    
    total_fixed = 0
    
    for category in categories_to_process:
        category_path = os.path.join(images_base_dir, category)
        
        classes_to_process = []
        
        if target_class:
            class_path = os.path.join(category_path, target_class)
            if os.path.exists(class_path):
                classes_to_process.append(target_class)
            else:
                logger.warning(f"Class not found in {category}: {target_class}")
                continue
        else:
            for item in os.listdir(category_path):
                item_path = os.path.join(category_path, item)
                if os.path.isdir(item_path):
                    classes_to_process.append(item)
        
        for class_name in classes_to_process:
            if fix_metadata_numbering(category, class_name, max_images):
                total_fixed += 1
    
    logger.success(f"Fixed numbering for {total_fixed} classes total")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 1:
        fix_all_metadata_numbering()
    elif len(sys.argv) == 2:
        fix_all_metadata_numbering(target_category=sys.argv[1])
    elif len(sys.argv) == 3:
        fix_all_metadata_numbering(target_category=sys.argv[1], target_class=sys.argv[2])
    elif len(sys.argv) == 4:
        fix_all_metadata_numbering(target_category=sys.argv[1], target_class=sys.argv[2], max_images=int(sys.argv[3]))
    else:
        print("Usage:")
        print("  python -m src.utils.fix_metadata_numbering")
        print("  python -m src.utils.fix_metadata_numbering <category>")
        print("  python -m src.utils.fix_metadata_numbering <category> <class>")
        print("  python -m src.utils.fix_metadata_numbering <category> <class> <max_images>")