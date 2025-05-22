import os
import io
import time
import hashlib
from PIL import Image, UnidentifiedImageError
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3 import Retry
import requests
from datetime import datetime

from src.logging.logger import logger
from src.utils.cache_utils import load_json_data, save_json_data
import config as cfg

class RateLimiter:
    def __init__(self):
        self.min_interval = cfg.REQUEST_INTERVAL
        self.last_call = 0

    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()

def verify_image_file(file_path, content_hash_to_verify):
    try:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest() == content_hash_to_verify
    except Exception:
        return False

class ImageDownloader:
    def __init__(self, category_dir: str, class_name: str, worker_id: int):
        self.category_dir = category_dir
        self.class_name = class_name
        self.worker_id = worker_id
        
        self.image_path = cfg.get_image_path(self.category_dir, self.class_name)
        self.clean_base = cfg.get_clean_base_name(self.class_name) # class_name is already assigned

        self.rate_limiter = RateLimiter()
        self.session = self._create_session()
        os.makedirs(self.image_path, exist_ok=True)

        self.base_output_dir = cfg.get_output_dir() 

    def _create_session(self):
        session = requests.Session()
        retries = Retry(
            total=cfg.MAX_RETRIES, 
            backoff_factor=cfg.RETRY_BACKOFF, 
            status_forcelist=[408, 429, 500, 502, 503, 504], 
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=50)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _get_absolute_path_from_metadata(self, entry):
        relative_path = entry.get('relative_path') # Use .get() for safety
        if relative_path: # Check if it's not None and not empty
            return os.path.join(self.base_output_dir, relative_path)
        return None

    def save_images(self, image_urls, keep_filenames):
        if not image_urls:
            logger.info("No image URLs provided.")
            return 0

        metadata_file = cfg.get_image_metadata_file(self.category_dir, self.class_name)
        cache = load_json_data(metadata_file) or {}
        
        cache.setdefault('image_cache', {})
        all_image_data = cache['image_cache']

        urls_to_download = []
        for url in image_urls:
            entry = all_image_data.get(url)
            if entry:
                abs_path = self._get_absolute_path_from_metadata(entry)
                if abs_path and os.path.exists(abs_path) and \
                   verify_image_file(abs_path, entry.get('hash')):
                    continue 
            urls_to_download.append(url)

        if not urls_to_download:
            logger.info(f"All {len(image_urls)} images already downloaded and verified for '{self.class_name}'.")
            if 'class_name' not in cache: 
                 cache['class_name'] = self.class_name
            if 'created_at' not in cache:
                cache['created_at'] = datetime.now().isoformat()
            cache['updated_at'] = datetime.now().isoformat()
            save_json_data(metadata_file, cache)
            return 0
        
        num_to_download_in_batch = len(urls_to_download)
        logger.start_progress(num_to_download_in_batch, f"Downloading images for '{self.class_name}'", self.worker_id)
        saved_count = 0

        if 'class_name' not in cache: 
            cache['class_name'] = self.class_name
        if 'created_at' not in cache:
            cache['created_at'] = datetime.now().isoformat()

        for idx, url in enumerate(urls_to_download):
            self.rate_limiter.wait()
            
            items_processed_in_batch = idx
            logger.info(f"Downloading {items_processed_in_batch + 1}/{num_to_download_in_batch}: {logger.truncate_url(url)}")
            
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Referer": url 
                }
                response = self.session.get(url, headers=headers, timeout=cfg.CONNECTION_TIMEOUT)
                response.raise_for_status()
                content = response.content
                
                original_filename_from_url = os.path.basename(urlparse(url).path)
                exif_data = {}

                try:
                    with Image.open(io.BytesIO(content)) as img:
                        img_format = img.format.lower() if img.format else 'jpg'
                        exif_data['width'] = img.width
                        exif_data['height'] = img.height
                        exif_data['mode'] = img.mode
                        if hasattr(img, '_getexif'):
                            exif = img._getexif()
                            if exif:
                                for k, v in exif.items():
                                    if k in Image.TAGS:
                                        exif_data[Image.TAGS[k]] = v if isinstance(v, (str, int, float, bool)) else str(v)
                except Exception:
                    ext = os.path.splitext(urlparse(url).path)[1][1:].lower()
                    img_format = ext if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff'] else 'jpg'

                if keep_filenames:
                    base_from_url = os.path.splitext(original_filename_from_url)[0]
                    file_base_name = base_from_url or f"{self.clean_base}_{len(all_image_data)+1:03d}"
                else:
                    file_base_name = f"{self.clean_base}_{len(all_image_data)+1:03d}"
                
                filename = f"{file_base_name}.{img_format}"
                absolute_save_path = os.path.join(self.image_path, filename)

                image_hash = hashlib.md5(content).hexdigest() # Hash of NEWLY downloaded content
                current_time_iso = datetime.now().isoformat()

                if url in all_image_data:
                    existing_entry = all_image_data[url]
                    existing_abs_path = self._get_absolute_path_from_metadata(existing_entry)
                    
                    # If file exists on disk and its content matches the NEWLY downloaded content
                    if existing_abs_path and os.path.exists(existing_abs_path) and verify_image_file(existing_abs_path, image_hash):
                        logger.info(f"File {existing_entry.get('filename', filename)} for URL {logger.truncate_url(url)} exists and content matches current download.")
                        metadata_updated_this_cycle = False
                        
                        if existing_entry.get('hash') != image_hash:
                            logger.warning(f"Updating stale hash for {existing_entry.get('filename', filename)}. Old: {existing_entry.get('hash')}, New: {image_hash}")
                            existing_entry['hash'] = image_hash
                            metadata_updated_this_cycle = True
                        
                        if not existing_entry.get('downloaded_at'): # Ensure downloaded_at is set
                            existing_entry['downloaded_at'] = current_time_iso
                            metadata_updated_this_cycle = True
                        
                        if metadata_updated_this_cycle:
                            existing_entry['updated_at'] = current_time_iso
                            cache['updated_at'] = current_time_iso # Mark the whole cache file as updated
                            save_json_data(metadata_file, cache)
                            logger.info(f"Metadata updated for {existing_entry.get('filename', filename)}.")
                        
                        logger.update_progress(worker_id=self.worker_id)
                        continue 

                # Proceed to save the file (either new or overwriting if stale/different)
                with open(absolute_save_path, 'wb') as f:
                    f.write(content)

                if not verify_image_file(absolute_save_path, image_hash): 
                    if os.path.exists(absolute_save_path):
                        os.remove(absolute_save_path)
                    raise Exception("File integrity verification failed after saving.")
                
                relative_image_path = os.path.relpath(absolute_save_path, self.base_output_dir).replace('\\', '/')
                
                all_image_data[url] = {
                    'filename': filename,
                    'original_filename': original_filename_from_url,
                    'hash': image_hash,
                    'relative_path': relative_image_path,
                    'downloaded_at': current_time_iso,
                    'updated_at': current_time_iso,
                    'format': img_format,
                    'size': len(content),
                    'exif': exif_data,
                }

                cache.update({
                    'image_cache': all_image_data,
                    'updated_at': current_time_iso
                })
                save_json_data(metadata_file, cache)
                logger.info(f"Saved: {filename}")
                saved_count += 1
                logger.update_progress(worker_id=self.worker_id)

            except requests.exceptions.RequestException as e:
                logger.error(f"Network error for {logger.truncate_url(url)}: {e}")
                logger.update_progress(worker_id=self.worker_id) 
            except UnidentifiedImageError:
                logger.error(f"Invalid image data: {logger.truncate_url(url)}")
                logger.update_progress(worker_id=self.worker_id)
            except Exception as e:
                logger.error(f"Failed to save {logger.truncate_url(url)}: {e}")
                logger.update_progress(worker_id=self.worker_id)

        logger.complete_progress(worker_id=self.worker_id)
        if saved_count > 0:
            logger.success(f"Downloaded {saved_count} new images for '{self.class_name}'.")
        elif num_to_download_in_batch > 0 : 
            logger.warning(f"Attempted to download {num_to_download_in_batch} images for '{self.class_name}', but {saved_count} were saved (others may have been verified or failed).")
        else: 
            logger.warning(f"No new images were processed for '{self.class_name}'.")
        
        logger.info(f"Total in metadata for '{self.class_name}': {len(all_image_data)}")
        
        cache['updated_at'] = datetime.now().isoformat() # Final update to overall cache timestamp
        save_json_data(metadata_file, cache)
        
        return saved_count
