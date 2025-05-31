import os
import hashlib
from src.logging.logger import logger
from src.utils.cache_utils import load_json_data, save_json_data
from src.helpers.http_client import OptimizedHTTPClient
from src.helpers.image_processor import (
    analyze_image_optimized, generate_filename, deduplicate_urls
)
from src.helpers.file_operations import (
    save_file_with_verification, check_existing_download,
    cleanup_corrupted_download, create_download_metadata, get_relative_path
)
import config as cfg


class ImageDownloader:
    def __init__(self, category_dir: str, class_name: str, worker_id: int):
        self.class_name = class_name
        self.worker_id = worker_id
        self.category_dir = category_dir
        self.image_path = cfg.get_image_dir(category_dir, class_name)
        self.base_dir = cfg.get_output_dir()
        self.http_client = OptimizedHTTPClient()


    def _load_metadata(self) -> dict:
        meta_file = cfg.get_image_metadata_file(self.category_dir, self.class_name)
        return load_json_data(meta_file) or {}

    def _prepare_download_list(self, images_dict: dict) -> list:
        """
        Prepare list of URLs that need downloading, cleaning up corrupted files
        """
        # First, deduplicate URLs to avoid redundant downloads
        images_dict = deduplicate_urls(images_dict)
        
        result = []
        
        for url_key, img_data in images_dict.items():
            # Check if already downloaded and valid
            if check_existing_download(img_data, self.base_dir):
                continue
            
            # Clean up any corrupted download data
            cleanup_corrupted_download(img_data, self.base_dir, url_key)
            
            # Mark for download
            result.append(url_key)
        
        return result


    def _download_image(self, url_key: str, img_data: dict, metadata: dict, keep: bool) -> bool:
        """Download a single image with optimized processing"""
        
        # Extract fetch data early for validation
        fetch_data = img_data.get('fetch_data', {})
        url = fetch_data.get('link')
        orig_fname = fetch_data.get('original_filename', 'unknown')
        
        if not url:
            logger.warning(f"[Worker {self.worker_id}] ❌ Download failed for key {url_key}: No URL found")
            return False

        # Skip if already downloaded (double-check with caching)
        if check_existing_download(img_data, self.base_dir):
            return False  # Already have valid file

        # Fetch content using optimized HTTP client
        content, error_msg = self.http_client.fetch_content(url)
        if not content:
            logger.error(f"[Worker {self.worker_id}] ❌ Download failed for key {url_key} ({orig_fname}): {error_msg or 'Unknown fetch error'}")
            logger.error(f"[Worker {self.worker_id}]    URL: {url}")
            return False

        # Process image with optimized analysis
        content_hash = hashlib.md5(content).hexdigest()
        fmt, width, height, mode = analyze_image_optimized(content, url, orig_fname)
        
        # Generate filename
        filename = generate_filename(self.class_name, url_key, orig_fname, fmt, keep)
        abs_path = os.path.join(self.image_path, filename)
        rel_path = get_relative_path(abs_path, self.base_dir)

        # Save file with verification
        if not save_file_with_verification(content, abs_path, content_hash):
            logger.error(f"[Worker {self.worker_id}] ❌ Save failed for key {url_key} ({filename}): File write or verification error")
            logger.error(f"[Worker {self.worker_id}]    Path: {abs_path}")
            return False

        # Update metadata with download data
        metadata['images'][url_key]['download_data'] = create_download_metadata(
            filename, rel_path, content_hash, len(content), width, height, mode, fmt
        )
        
        logger.info(f"Saved: {filename} ({url_key})")
        return True

    def save_images(self, urls: list, keep: bool) -> int:
        """
        Download images with optimized processing and error handling
        """
        if not urls:
            return 0
        
        # Load metadata once and cache file path
        metadata = self._load_metadata()
        images_dict = metadata.get('images', {})
        if not images_dict:
            logger.warning(f"[Worker {self.worker_id}] No images found in metadata for '{self.class_name}'")
            return 0
        
        meta_file = cfg.get_image_metadata_file(self.category_dir, self.class_name)
        to_download = self._prepare_download_list(images_dict)
        
        # Save metadata after cleaning up corrupted records
        save_json_data(meta_file, metadata)
        
        if not to_download:
            logger.info(f"[Worker {self.worker_id}] All images already downloaded for '{self.class_name}'")
            return 0

        logger.start_progress(len(to_download), f"Downloading '{self.class_name}'", self.worker_id)
        count = 0
        failed_count = 0
        
        # Process downloads with per-file metadata saves for safety
        for url_key in to_download:
            img_data = images_dict[url_key]
            
            if self._download_image(url_key, img_data, metadata, keep):
                count += 1
            else:
                failed_count += 1
            
            # Save metadata after each download for safety (as requested)
            save_json_data(meta_file, metadata)
            logger.update_progress(worker_id=self.worker_id)
            
        logger.complete_progress(worker_id=self.worker_id)
        
        # Report final statistics
        if failed_count > 0:
            logger.warning(f"[Worker {self.worker_id}] Download summary for '{self.class_name}': {count} successful, {failed_count} failed out of {len(to_download)} total")
        else:
            logger.info(f"[Worker {self.worker_id}] Download summary for '{self.class_name}': All {count} images downloaded successfully")
            
        return count
