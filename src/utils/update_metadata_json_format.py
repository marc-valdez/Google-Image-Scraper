import json
import os
import fnmatch
import sys
import uuid

project_root_for_import = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root_for_import not in sys.path:
    sys.path.insert(0, project_root_for_import)

import config as cfg
from src.logging.logger import logger

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

def update_json_files(output_directory_path):
    """
    Updates *_metadata.json files by moving 'width', 'height', 'mode'
    out of 'exif', removing 'exif', and reordering 'hash' to be the first key.
    Only writes to the file if its content actually changes.
    """
    file_pattern_to_search = "*_metadata.json"
    logger.info(f"Searching for '{file_pattern_to_search}' files in '{os.path.abspath(output_directory_path)}' and its subdirectories...")
    json_files = find_files(output_directory_path, file_pattern_to_search)

    if not json_files:
        logger.warning(f"No '{file_pattern_to_search}' files found in '{os.path.abspath(output_directory_path)}' or its subdirectories.")
        return

    logger.info(f"Found {len(json_files)} JSON files to process.")

    progress_task_id = f"update_metadata_task_{uuid.uuid4()}"
    logger.start_progress(total=len(json_files), description="Updating metadata JSON files", worker_id=progress_task_id)

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_data_from_file = json.load(f)

            if not isinstance(original_data_from_file, dict):
                logger.warning(f"Skipping '{file_path}' as its content is not a dictionary.")
                logger.update_progress(worker_id=progress_task_id)
                continue
            
            processed_data_for_file = {}
            changes_made = False

            # Handle both direct structure and image_cache structure
            data_to_process = original_data_from_file
            if 'image_cache' in original_data_from_file:
                data_to_process = original_data_from_file['image_cache']
                processed_data_for_file['image_cache'] = {}

            for url_key, image_info_entry in data_to_process.items():
                if not isinstance(image_info_entry, dict):
                    if 'image_cache' in processed_data_for_file:
                        processed_data_for_file['image_cache'][url_key] = image_info_entry
                    else:
                        processed_data_for_file[url_key] = image_info_entry
                    continue
                
                # Work on a copy for processing this specific entry
                current_processing_image_info = image_info_entry.copy()
                
                # Check if exif exists - if so, we'll make changes
                if 'exif' in current_processing_image_info:
                    changes_made = True
                
                temp_hash_holder = {}

                # Ensure 'hash' is handled first and removed from its original position
                if 'hash' in current_processing_image_info:
                    temp_hash_holder['hash'] = current_processing_image_info.pop('hash')
                
                # Process 'exif' data
                if 'exif' in current_processing_image_info and isinstance(current_processing_image_info['exif'], dict):
                    exif_data = current_processing_image_info.pop('exif')
                    if 'width' in exif_data:
                        current_processing_image_info['width'] = exif_data['width']
                    if 'height' in exif_data:
                        current_processing_image_info['height'] = exif_data['height']
                    if 'mode' in exif_data:
                        current_processing_image_info['mode'] = exif_data['mode']
                elif 'exif' in current_processing_image_info: # if exif is present but not a dict, remove it
                    current_processing_image_info.pop('exif') 

                # Define the desired order of keys for the final entry
                ordered_keys = [
                    'hash', 'filename', 'original_filename', 'relative_path', 
                    'format', 'size', 'width', 'height', 'mode', 
                    'downloaded_at', 'updated_at'
                ]
                
                final_ordered_entry_for_key = {}
                
                # Add 'hash' if it was extracted
                if 'hash' in temp_hash_holder:
                    final_ordered_entry_for_key['hash'] = temp_hash_holder['hash']
                # If hash was not in temp_hash_holder but somehow still in current_processing_image_info
                elif 'hash' in current_processing_image_info: 
                    final_ordered_entry_for_key['hash'] = current_processing_image_info.pop('hash')

                # Add other keys in the specified order
                for key in ordered_keys:
                    if key == 'hash' and 'hash' in final_ordered_entry_for_key: # Already handled
                        continue
                    if key in current_processing_image_info:
                        final_ordered_entry_for_key[key] = current_processing_image_info.pop(key)
                
                # Add any remaining keys (e.g., new or unexpected fields) to maintain all data
                for remaining_key, remaining_value in current_processing_image_info.items():
                    final_ordered_entry_for_key[remaining_key] = remaining_value
                
                if 'image_cache' in processed_data_for_file:
                    processed_data_for_file['image_cache'][url_key] = final_ordered_entry_for_key
                else:
                    processed_data_for_file[url_key] = final_ordered_entry_for_key
            
            # Use the changes_made flag instead of deep comparison
            if not changes_made:
                logger.info(f"No necessary modifications found for '{file_path}'. File not changed.")
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(processed_data_for_file, f, indent=4)
                logger.success(f"Successfully updated metadata in '{file_path}'")

        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from '{file_path}'. Skipping.")
        except Exception as e:
            logger.error(f"An error occurred while processing '{file_path}': {e}. Skipping.")
        finally:
            logger.update_progress(worker_id=progress_task_id)

    logger.complete_progress(worker_id=progress_task_id)
    logger.success("Finished processing all files.")

if __name__ == '__main__':
    logger.set_verbose(True) 
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    output_dir_name = cfg.OUTPUT_DIR_BASE 
    target_output_directory = os.path.join(project_root, output_dir_name)

    if len(sys.argv) > 1:
        target_output_directory_arg = sys.argv[1]
        if os.path.isdir(target_output_directory_arg):
            target_output_directory = os.path.abspath(target_output_directory_arg)
            logger.info(f"Using command line provided directory: {target_output_directory}")
        else:
            logger.warning(f"Command line directory '{target_output_directory_arg}' not found. Using default: {target_output_directory}")
    
    logger.status(f"Script will search in base directory: {os.path.abspath(target_output_directory)}")

    if not os.path.isdir(target_output_directory):
        logger.error(f"The base directory '{os.path.abspath(target_output_directory)}' does not exist.")
        logger.warning(f"Please ensure the directory exists or modify the 'output_dir_name' variable in the script or provide a valid path as a command line argument.")
    else:
        update_json_files(target_output_directory)