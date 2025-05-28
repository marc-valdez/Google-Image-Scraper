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

def update_json_files(output_directory_path):
    """
    Updates the format of *_urls.json files in the specified output directory
    to align with the new structure using ImageScraperLogger.
    """
    file_pattern_to_search = "*_urls.json"
    logger.info(f"Searching for '{file_pattern_to_search}' files in '{os.path.abspath(output_directory_path)}' and its subdirectories...")
    json_files = find_files(output_directory_path, file_pattern_to_search)

    if not json_files:
        logger.warning(f"No '{file_pattern_to_search}' files found in '{os.path.abspath(output_directory_path)}' or its subdirectories.")
        return

    logger.info(f"Found {len(json_files)} JSON files to process.")

    progress_task_id = f"update_json_task_{uuid.uuid4()}"
    logger.start_progress(total=len(json_files), description="Updating JSON files", worker_id=progress_task_id)

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if all(k in data for k in ['search_url_used', 'search_key', 'last_processed_xpath_index', 'number_of_images_requested', 'number_of_urls_found', 'request_efficiency', 'urls']):
                logger.info(f"Skipping '{file_path}' as it already appears to be in the new format.")
                logger.update_progress(worker_id=progress_task_id)
                continue

            search_url_used = "N/A_migrated"
            search_key = ""
            last_processed_xpath_index = 0
            number_of_images_requested = 0
            number_of_urls_found = 0
            found_urls = []

            if 'search_url_used' in data and 'search_key' in data and 'urls_found_count' in data:
                logger.info(f"Processing '{file_path}' with recognized old format...")
                search_url_used = data.get('search_url_used', "N/A_migrated")
                search_key = data.get('search_key', "")
                number_of_images_requested = data.get('number_of_images_requested', 0)
                number_of_urls_found = data.get('urls_found_count', 0)
                found_urls = data.get('urls', [])
                last_processed_xpath_index = data.get('processed_thumbnails_count', 0)
            else:
                logger.info(f"Attempting to process '{file_path}' with generic fallback...")
                if isinstance(data, list):
                    found_urls = data
                elif isinstance(data, dict) and 'urls' in data:
                    found_urls = data.get('urls', [])
                elif isinstance(data, dict) and 'results' in data:
                    found_urls = data.get('results', [])
                else:
                    logger.warning(f"Could not reliably extract URLs or map fields from '{file_path}'. Structure: {list(data.keys()) if isinstance(data, dict) else 'list'}. Skipping.")
                    logger.update_progress(worker_id=progress_task_id)
                    continue

                if not isinstance(found_urls, list):
                    logger.warning(f"Extracted 'urls' in '{file_path}' is not a list. Skipping.")
                    logger.update_progress(worker_id=progress_task_id)
                    continue

                number_of_urls_found = len(found_urls)
                number_of_images_requested = data.get('number_of_images_requested',
                                            data.get('limit',
                                                     data.get('count', number_of_urls_found)))
                if number_of_images_requested == 0 and number_of_urls_found > 0:
                    number_of_images_requested = number_of_urls_found
                elif number_of_images_requested == 0 and number_of_urls_found == 0:
                     number_of_images_requested = 1

                file_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
                search_key_from_filename = file_name_without_ext.replace("_urls", "")
                search_key = data.get('search_key', search_key_from_filename)
                search_url_used = data.get('search_url_used', "N/A_migrated_fallback")
                last_processed_xpath_index = data.get('last_processed_xpath_index', data.get('processed_thumbnails_count', 0))

            request_efficiency = number_of_urls_found / number_of_images_requested if number_of_images_requested > 0 else 0

            updated_data = {
                'search_url_used': search_url_used,
                'search_key': search_key,
                'last_processed_xpath_index': last_processed_xpath_index,
                'number_of_images_requested': number_of_images_requested,
                'number_of_urls_found': number_of_urls_found,
                'request_efficiency': request_efficiency,
                'urls': found_urls
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(updated_data, f, indent=4)

            logger.success(f"Successfully updated '{file_path}'")

        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from '{file_path}'. Skipping.")
        except Exception as e:
            logger.error(f"An error occurred while processing '{file_path}': {e}. Skipping.")
        finally:
            logger.update_progress(worker_id=progress_task_id)

    logger.complete_progress(worker_id=progress_task_id)
    logger.success("Finished processing all files.")

if __name__ == '__main__':
    logger.set_verbose(True) # Enable verbose info messages for this script
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    output_dir_name = cfg.OUTPUT_DIR_BASE
    target_output_directory = os.path.join(project_root, output_dir_name)

    logger.status(f"Script will search in base directory: {os.path.abspath(target_output_directory)}")

    if not os.path.isdir(target_output_directory):
        logger.error(f"The base directory '{os.path.abspath(target_output_directory)}' does not exist.")
        logger.warning(f"Please ensure the directory exists or modify the 'output_dir_name' variable in the script.")
    else:
        update_json_files(target_output_directory)