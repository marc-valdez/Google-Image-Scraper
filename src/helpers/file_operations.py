import os
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from src.logging.logger import logger
from src.helpers.image_processor import verify_file_cached, invalidate_file_cache


def save_file_with_verification(content: bytes, path: str, expected_hash: str) -> bool:
    """
    Save file and verify it was written correctly
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Write file
        with open(path, 'wb') as f:
            f.write(content)
        
        # Verify the file was written correctly
        return verify_file_cached(path, expected_hash)
        
    except Exception as e:
        logger.error(f"Failed to save file {path}: {e}")
        return False


def remove_corrupted_file(path: str) -> bool:
    """
    Remove a corrupted file and invalidate its cache
    """
    try:
        if os.path.exists(path):
            os.remove(path)
            invalidate_file_cache(path)
            logger.info(f"🗑️ Removed corrupted file: {path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to remove corrupted file {path}: {e}")
        return False


def create_download_metadata(filename: str, relative_path: str, content_hash: str,
                           content_size: int, width: int, height: int, 
                           mode: str, format_name: str) -> Dict[str, Any]:
    """
    Create standardized download metadata
    """
    return {
        "filename": filename,
        "relative_path": relative_path,
        "hash": content_hash,
        "bytes": content_size,
        "width": width,
        "height": height,
        "mode": mode,
        "format": format_name,
        "downloaded_at": datetime.now().isoformat()
    }


def check_existing_download(img_data: dict, base_dir: str) -> bool:
    """
    Check if file is already downloaded and valid
    Returns True if file exists and is valid
    """
    if 'download_data' not in img_data:
        return False
    
    download_data = img_data['download_data']
    rel_path = download_data.get('relative_path')
    expected_hash = download_data.get('hash')
    
    if not rel_path or not expected_hash:
        return False
    
    abs_path = os.path.join(base_dir, rel_path)
    return os.path.exists(abs_path) and verify_file_cached(abs_path, expected_hash)


def cleanup_corrupted_download(img_data: dict, base_dir: str, url_key: str) -> bool:
    """
    Clean up corrupted download data and files
    Returns True if cleanup was performed
    """
    if 'download_data' not in img_data:
        return False
    
    download_data = img_data['download_data']
    rel_path = download_data.get('relative_path')
    
    if rel_path:
        abs_path = os.path.join(base_dir, rel_path)
        filename = os.path.basename(abs_path)
        
        logger.warning(f"❌ File corrupted/missing, deleting record: {filename}")
        
        # Remove physical file if it exists
        remove_corrupted_file(abs_path)
        
        # Remove download_data from metadata
        del img_data['download_data']
        logger.info(f"🔄 Deleted corrupted record for {url_key}, will redownload")
        return True
    
    return False


def get_relative_path(abs_path: str, base_dir: str) -> str:
    """
    Get relative path with consistent separators
    """
    return os.path.relpath(abs_path, base_dir).replace('\\', '/')


def ensure_directory_exists(path: str) -> bool:
    """
    Ensure directory exists for given file path
    """
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory for {path}: {e}")
        return False