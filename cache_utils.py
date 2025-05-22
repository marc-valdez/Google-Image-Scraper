import os
import json
from logger import logger

def ensure_cache_dir(cache_path):
    """Ensures that the cache directory exists."""
    try:
        os.makedirs(cache_path, exist_ok=True)
        # print(f"[DEBUG] Ensured cache directory exists: {cache_path}")
    except Exception as e:
        logger.error(f"Could not create cache directory {cache_path}: {e}")
        raise

def load_json_data(file_path):
    """Loads data from a JSON file.
    Returns None if the file is not found or if there's a JSON decoding error.
    """
    # print(f"[DEBUG] Attempting to load JSON from: {file_path}")
    if not os.path.exists(file_path):
        # print(f"[DEBUG] File not found: {file_path}")
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # print(f"[DEBUG] Successfully loaded JSON from: {file_path}")
            return data
    except FileNotFoundError:
        # print(f"[DEBUG] FileNotFoundError (should have been caught by os.path.exists): {file_path}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in file {file_path}: {e}")
        # Optionally, could delete or rename the corrupted file here
        # os.rename(file_path, file_path + ".corrupted")
        return None
    except Exception as e:
        logger.error(f"Could not load JSON from {file_path}: {e}")
        return None

def save_json_data(file_path, data):
    """Saves data to a JSON file."""
    # print(f"[DEBUG] Attempting to save JSON to: {file_path}")
    try:
        # Ensure the directory for the file_path exists
        parent_dir = os.path.dirname(file_path)
        if parent_dir: # Ensure parent_dir is not an empty string (e.g. for files in current dir)
            os.makedirs(parent_dir, exist_ok=True)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        # print(f"[DEBUG] Successfully saved JSON to: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Could not save JSON to {file_path}: {e}")
        return False

def remove_file_if_exists(file_path):
    """Removes a file if it exists."""
    # print(f"[DEBUG] Attempting to remove file: {file_path}")
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            # print(f"[DEBUG] Successfully removed file: {file_path}")
            return True
        # print(f"[DEBUG] File not found, no removal needed: {file_path}")
        return False # Or True, depending on desired semantics (True if state is "file does not exist")
    except Exception as e:
        logger.error(f"Could not remove file {file_path}: {e}")
        return False