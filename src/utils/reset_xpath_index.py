import json
import os
import fnmatch
import sys
import uuid

# Add project root to sys.path to allow for src.logging.logger import
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

def reset_xpath_index(output_directory_path):
    """
    Resets the last_processed_xpath_index to 1 in all *_urls.json files
    in the specified output directory.
    """
    file_pattern_to_search = "*_urls.json"
    logger.info(f"Searching for '{file_pattern_to_search}' files in '{os.path.abspath(output_directory_path)}' and its subdirectories...")
    json_files = find_files(output_directory_path, file_pattern_to_search)

    if not json_files:
        logger.warning(f"No '{file_pattern_to_search}' files found in '{os.path.abspath(output_directory_path)}' or its subdirectories.")
        return

    logger.info(f"Found {len(json_files)} JSON files to process.")

    progress_task_id = f"reset_xpath_task_{uuid.uuid4()}"
    logger.start_progress(total=len(json_files), description="Resetting xpath index", worker_id=progress_task_id)

    updated_count = 0
    skipped_count = 0

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check if the file has the expected structure
            if not isinstance(data, dict) or 'last_processed_xpath_index' not in data:
                logger.warning(f"File '{file_path}' does not contain 'last_processed_xpath_index' field. Skipping.")
                skipped_count += 1
                logger.update_progress(worker_id=progress_task_id)
                continue

            # Check if already set to 1
            if data['last_processed_xpath_index'] == 1:
                logger.info(f"File '{file_path}' already has last_processed_xpath_index set to 1. Skipping.")
                skipped_count += 1
                logger.update_progress(worker_id=progress_task_id)
                continue

            # Update the xpath index to 1
            old_value = data['last_processed_xpath_index']
            data['last_processed_xpath_index'] = 1

            # Write the updated data back to the file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)

            logger.success(f"Updated '{file_path}': last_processed_xpath_index changed from {old_value} to 1")
            updated_count += 1

        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from '{file_path}'. Skipping.")
            skipped_count += 1
        except Exception as e:
            logger.error(f"An error occurred while processing '{file_path}': {e}. Skipping.")
            skipped_count += 1
        finally:
            logger.update_progress(worker_id=progress_task_id)

    logger.complete_progress(worker_id=progress_task_id)
    logger.success(f"Finished processing all files. Updated: {updated_count}, Skipped: {skipped_count}")

if __name__ == '__main__':
    logger.set_verbose(True)  # Enable verbose info messages for this script
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    output_dir_name = cfg.OUTPUT_DIR_BASE
    target_output_directory = os.path.join(project_root, output_dir_name)

    logger.status(f"Script will search in base directory: {os.path.abspath(target_output_directory)}")

    if not os.path.isdir(target_output_directory):
        logger.error(f"The base directory '{os.path.abspath(target_output_directory)}' does not exist.")
        logger.warning(f"Please ensure the directory exists or modify the 'output_dir_name' variable in the script.")
    else:
        reset_xpath_index(target_output_directory)