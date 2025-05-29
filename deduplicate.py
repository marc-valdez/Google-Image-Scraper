import json
import os
import random
import uuid
from typing import Dict, List, Union
from config import get_image_metadata_file, get_url_cache_file, get_output_dir
from src.logging.logger import logger

def load_duplicates() -> Dict[str, Dict]:
    """Load duplicates.json which contains both inter and intra class duplicates"""
    duplicate_file = os.path.join(get_output_dir(), "duplicates.json")
    try:
        with open(duplicate_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Could not find duplicates file at: {duplicate_file}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in duplicates file: {duplicate_file}")
        raise

def update_json_files(image_path: str) -> None:
    """Update metadata and URL files for an affected class."""
    parts = image_path.split(os.sep)
    
    if len(parts) >= 3:  # Category/Class/filename
        category_dir = parts[0]  # Category directory
        class_name = parts[1]    # Class name
        filename = parts[-1]     # Filename
        
        # Update metadata file
        metadata_file = get_image_metadata_file(category_dir, class_name)
        if os.path.exists(metadata_file):
            try:
                # Read current metadata content
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
                
                if not isinstance(metadata, dict) or "image_cache" not in metadata:
                    logger.error(f"Invalid metadata format in {metadata_file}")
                    return
                
                # Find and remove entry with matching filename
                entries_to_remove = []
                for url, entry in metadata["image_cache"].items():
                    if entry.get("filename") == filename:
                        entries_to_remove.append(url)
                
                if entries_to_remove:
                    for url in entries_to_remove:
                        del metadata["image_cache"][url]
                    with open(metadata_file, "w") as f:
                        json.dump(metadata, f, indent=4)
                    logger.info(f"Updated metadata for {filename} in {class_name}")
                    
            except Exception as e:
                logger.error(f"Error updating metadata file {metadata_file}: {str(e)}")
        
        # Update URLs file
        urls_file = get_url_cache_file(category_dir, class_name)
        if os.path.exists(urls_file):
            try:
                with open(urls_file, "r") as f:
                    urls_data = json.load(f)
                
                if not isinstance(urls_data, dict) or "urls" not in urls_data:
                    logger.error(f"Invalid URLs format in {urls_file}")
                    return
                
                # Remove URLs that were used for this image based on metadata
                if entries_to_remove:
                    original_len = len(urls_data["urls"])
                    urls_data["urls"] = [url for url in urls_data["urls"] if url not in entries_to_remove]
                    
                    if len(urls_data["urls"]) != original_len:
                        with open(urls_file, "w") as f:
                            json.dump(urls_data, f, indent=4)
                        logger.info(f"Updated URLs for {filename} in {class_name}")
                    
            except Exception as e:
                logger.error(f"Error updating URLs file {urls_file}: {str(e)}")

def handle_duplicate_set(files: List[str], worker_id: str) -> None:
    """Handle a set of duplicate files by keeping one randomly and removing others."""
    if not files or len(files) <= 1:
        return

    # Randomly select one file to keep
    keep_index = random.randrange(len(files))
    file_to_keep = files[keep_index]
    logger.status(f"Keeping file: {file_to_keep}")
    
    # Setup progress tracking
    total_files = len(files) - 1  # Exclude the file we're keeping
    logger.start_progress(total_files, "Processing duplicates", worker_id)
    
    # Process all files except the one we're keeping
    for i, file_path in enumerate(files):
        if i != keep_index:
            full_path = os.path.join(get_output_dir(), file_path)
            
            # Extract just the path after 'images/' directory
            relative_path = os.path.normpath(file_path)
            parts = relative_path.split(os.sep)
            if len(parts) >= 3 and parts[0] == "images":
                # Update metadata BEFORE deleting the file
                # Skip 'images' directory and get Category/Class/filename
                subpath = os.path.join(*parts[1:])
                update_json_files(subpath)
                
                # Now delete the file
                if os.path.exists(full_path):
                    try:
                        os.remove(full_path)
                        logger.info(f"Removed duplicate: {file_path}")
                    except Exception as e:
                        logger.error(f"Error removing {file_path}: {str(e)}")
                        raise
                else:
                    logger.info(f"File already removed: {file_path}")
                    
                logger.update_progress(1, worker_id)
            else:
                logger.error(f"Invalid path structure: {file_path}")
    
    logger.complete_progress(worker_id)

def deduplicate_images():
    """Main deduplication function that handles both inter and intra class duplicates."""
    try:
        duplicates = load_duplicates()
        
        # Handle inter-class duplicates
        inter_duplicates = duplicates.get("inter_class_duplicates", {})
        if inter_duplicates:
            logger.status("Processing inter-class duplicates")
            for hash_val, files in inter_duplicates.items():
                worker_id = f"inter_{hash_val[:8]}"
                logger.status(f"Processing duplicate set with hash {hash_val[:8]}")
                handle_duplicate_set(files, worker_id)
        
        # Handle intra-class duplicates
        intra_duplicates = duplicates.get("intra_class_duplicates", {})
        if intra_duplicates:
            logger.status("Processing intra-class duplicates")
            for hash_val, files in intra_duplicates.items():
                worker_id = f"intra_{hash_val[:8]}"
                logger.status(f"Processing duplicate set with hash {hash_val[:8]}")
                handle_duplicate_set(files, worker_id)
        
        # Print summary from the duplicates file
        summary = duplicates.get("duplicate_summary", {})
        logger.success("Deduplication complete!")
        logger.info(f"Processed {summary.get('inter_class_duplicate_hashes', 0)} inter-class duplicate sets")
        logger.info(f"Processed {summary.get('intra_class_duplicate_hashes', 0)} intra-class duplicate sets")
        logger.success(f"Total duplicate files handled: {summary.get('total_duplicate_files', 0)}")
        
    except Exception as e:
        logger.error(f"Deduplication failed: {str(e)}")
        raise

if __name__ == "__main__":
    logger.set_verbose(True)  # Enable detailed logging
    deduplicate_images()