import os
import io
import time
import hashlib
import random
from PIL import Image, UnidentifiedImageError
from PIL import ExifTags
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3 import Retry
import requests
import certifi
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
        session.verify = certifi.where()
        return session

    def _get_absolute_path_from_metadata(self, entry):
        relative_path = entry.get('relative_path')
        if relative_path:
            return os.path.join(self.base_output_dir, relative_path)
        return None

    def _prepare_download_list(self, image_urls: list, all_image_data: dict) -> list:
        urls_to_download = []
        for url in image_urls:
            entry = all_image_data.get(url)
            if entry:
                abs_path = self._get_absolute_path_from_metadata(entry)
                if abs_path and os.path.exists(abs_path) and \
                   verify_image_file(abs_path, entry.get('hash')):
                    continue
            urls_to_download.append(url)
        return urls_to_download

    def _fetch_image_content(self, url: str) -> tuple[bytes | None, requests.Response | None]:
        default_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        user_agents_to_try = []

        if cfg.ROTATE_USER_AGENT and hasattr(cfg, 'USER_AGENTS') and cfg.USER_AGENTS:
            user_agents_to_try = random.sample(list(cfg.USER_AGENTS), k=len(cfg.USER_AGENTS))
        
        if not user_agents_to_try:
            user_agents_to_try = [default_user_agent]

        last_error_for_url = None
        
        ua_cycle_errors = getattr(cfg, 'USER_AGENT_CYCLE_ON_ERRORS', [403])
        ua_cycle_delay = getattr(cfg, 'RETRY_BACKOFF_FOR_UA_ROTATE', 2.0)

        for i, user_agent in enumerate(user_agents_to_try):
            logger.info(f"[Worker {self.worker_id}] Attempt {i + 1}/{len(user_agents_to_try)} for {logger.truncate_url(url)} with UA: {user_agent}")
            headers = {"User-Agent": user_agent, "Referer": url}
            
            try:
                response = self.session.get(url, headers=headers, timeout=cfg.CONNECTION_TIMEOUT)
                response.raise_for_status()
                return response.content, response
            except requests.exceptions.HTTPError as http_err:
                last_error_for_url = http_err
                status_code = http_err.response.status_code
                if status_code in ua_cycle_errors:
                    logger.warning(f"[Worker {self.worker_id}] HTTP {status_code} for {logger.truncate_url(url)} with UA: {user_agent}.")
                    if i < len(user_agents_to_try) - 1:
                        logger.info(f"Retrying with next User-Agent after {ua_cycle_delay}s delay.")
                        time.sleep(ua_cycle_delay)
                        continue
                    else:
                        logger.error(f"All {len(user_agents_to_try)} User-Agent attempts for {logger.truncate_url(url)} failed with HTTP {status_code}.")
                        break 
                else:
                    logger.error(f"HTTP error {status_code} for {logger.truncate_url(url)} (not in UA cycle list) with UA: {user_agent}: {http_err}")
                    return None, None 
            except requests.exceptions.RequestException as req_err:
                last_error_for_url = req_err
                logger.error(f"Network error for {logger.truncate_url(url)} with UA: {user_agent}: {req_err}")
                return None, None

        if last_error_for_url:
            logger.error(f"Failed to fetch {logger.truncate_url(url)} after {len(user_agents_to_try)} UA attempt(s). Last error: {last_error_for_url}")
        else:
            logger.error(f"Failed to fetch {logger.truncate_url(url)} (no attempts made or no specific last error recorded from loop).")
            
        return None, None

    def _extract_image_details(self, content: bytes, url: str, original_filename_from_url: str, keep_filenames: bool, current_image_count: int) -> tuple[str, str, dict]:
        exif_data = {}
        img_format = 'jpg' 

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
                            if k in ExifTags.TAGS:
                                exif_data[ExifTags.TAGS[k]] = v if isinstance(v, (str, int, float, bool)) else str(v)
        except UnidentifiedImageError:
            logger.warning(f"Could not identify image from URL (falling back to extension): {logger.truncate_url(url)}")
            ext = os.path.splitext(urlparse(url).path)[1][1:].lower()
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff']:
                img_format = ext
        except Exception as e:
            logger.warning(f"Error processing image details for {logger.truncate_url(url)} with PIL: {e}")
            ext = os.path.splitext(urlparse(url).path)[1][1:].lower()
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff']:
                img_format = ext

        if keep_filenames:
            base_from_url = os.path.splitext(original_filename_from_url)[0]
            file_base_name = base_from_url or f"{cfg.sanitize_class_name(self.class_name)}_{current_image_count + 1:03d}"
            filename = f"{file_base_name}.{img_format}"
        else:
            base_name_from_config = cfg.format_filename(self.class_name, current_image_count + 1)
            filename = f"{base_name_from_config}.{img_format}"

        return filename, img_format, exif_data

    def _save_and_verify_image(self, content: bytes, absolute_save_path: str, expected_hash: str) -> bool:
        try:
            with open(absolute_save_path, 'wb') as f:
                f.write(content)

            if not verify_image_file(absolute_save_path, expected_hash):
                if os.path.exists(absolute_save_path):
                    os.remove(absolute_save_path)
                raise Exception("File integrity verification failed after saving.")
            return True
        except Exception as e:
            logger.error(f"Failed to save or verify image {absolute_save_path}: {e}")
            if os.path.exists(absolute_save_path): 
                try:
                    os.remove(absolute_save_path)
                except Exception as rem_e:
                    logger.error(f"Failed to remove corrupted file {absolute_save_path}: {rem_e}")
            return False

    def _update_metadata_entry(self, url: str, filename: str, original_filename: str, image_hash: str, relative_path: str, img_format: str, content_len: int, exif_data: dict, current_time_iso: str) -> dict:
        return {
            'filename': filename,
            'original_filename': original_filename,
            'hash': image_hash,
            'relative_path': relative_path,
            'downloaded_at': current_time_iso,
            'updated_at': current_time_iso,
            'format': img_format,
            'size': content_len,
            'exif': exif_data,
        }

    def _handle_existing_verified_image(self, url: str, existing_entry: dict, new_image_hash: str, metadata_file: str, cache: dict, current_time_iso: str):
        logger.info(f"File {existing_entry.get('filename', 'N/A')} for URL {logger.truncate_url(url)} exists and content matches current download.")
        metadata_updated_this_cycle = False

        if existing_entry.get('hash') != new_image_hash:
            logger.warning(f"Updating stale hash for {existing_entry.get('filename', 'N/A')}. Old: {existing_entry.get('hash')}, New: {new_image_hash}")
            existing_entry['hash'] = new_image_hash
            metadata_updated_this_cycle = True

        if not existing_entry.get('downloaded_at'):
            existing_entry['downloaded_at'] = current_time_iso
            metadata_updated_this_cycle = True

        if metadata_updated_this_cycle:
            existing_entry['updated_at'] = current_time_iso
            cache['updated_at'] = current_time_iso
            save_json_data(metadata_file, cache)
            logger.info(f"Metadata updated for {existing_entry.get('filename', 'N/A')}.")

    def _process_single_image_download(self, url: str, all_image_data: dict, keep_filenames: bool, metadata_file: str, cache: dict) -> bool:
        self.rate_limiter.wait()

        content, _ = self._fetch_image_content(url)
        if not content:
            return False

        original_filename_from_url = os.path.basename(urlparse(url).path)
        image_hash = hashlib.md5(content).hexdigest()
        current_time_iso = datetime.now().isoformat()

        if url in all_image_data:
            existing_entry = all_image_data[url]
            existing_abs_path = self._get_absolute_path_from_metadata(existing_entry)
            if existing_abs_path and os.path.exists(existing_abs_path) and verify_image_file(existing_abs_path, image_hash):
                self._handle_existing_verified_image(url, existing_entry, image_hash, metadata_file, cache, current_time_iso)
                return False 

        filename, img_format, exif_data = self._extract_image_details(content, url, original_filename_from_url, keep_filenames, len(all_image_data))
        absolute_save_path = os.path.join(self.image_path, filename)

        if not self._save_and_verify_image(content, absolute_save_path, image_hash):
            return False 

        relative_image_path = os.path.relpath(absolute_save_path, self.base_output_dir).replace('\\', '/')
        all_image_data[url] = self._update_metadata_entry(
            url, filename, original_filename_from_url, image_hash,
            relative_image_path, img_format, len(content), exif_data, current_time_iso
        )

        cache.update({
            'image_cache': all_image_data,
            'updated_at': current_time_iso
        })
        save_json_data(metadata_file, cache)
        logger.info(f"Saved: {filename}")
        return True


    def save_images(self, image_urls, keep_filenames):
        if not image_urls:
            logger.info("No image URLs provided.")
            return 0

        metadata_file = cfg.get_image_metadata_file(self.category_dir, self.class_name)
        cache = load_json_data(metadata_file) or {}

        cache.setdefault('image_cache', {})
        all_image_data = cache['image_cache']

        urls_to_download = self._prepare_download_list(image_urls, all_image_data)

        if not urls_to_download:
            logger.info(f"All {len(image_urls)} images already downloaded and verified for '{self.class_name}'.")
            if 'class_name' not in cache: cache['class_name'] = self.class_name
            if 'created_at' not in cache: cache['created_at'] = datetime.now().isoformat()
            cache['updated_at'] = datetime.now().isoformat()
            save_json_data(metadata_file, cache)
            return 0

        num_to_download_in_batch = len(urls_to_download)
        logger.start_progress(num_to_download_in_batch, f"Downloading images for '{self.class_name}'", self.worker_id)
        saved_count = 0

        if 'class_name' not in cache: cache['class_name'] = self.class_name
        if 'created_at' not in cache: cache['created_at'] = datetime.now().isoformat()

        for idx, url in enumerate(urls_to_download):
            logger.info(f"Downloading {idx + 1}/{num_to_download_in_batch}: {logger.truncate_url(url)}")
            try:
                if self._process_single_image_download(url, all_image_data, keep_filenames, metadata_file, cache):
                    saved_count += 1
            except Exception as e: 
                logger.error(f"Unexpected error processing {logger.truncate_url(url)}: {e}")
            finally:
                logger.update_progress(worker_id=self.worker_id)

        logger.complete_progress(worker_id=self.worker_id)
        if saved_count > 0:
            logger.success(f"Downloaded {saved_count} new images for '{self.class_name}'.")
        elif num_to_download_in_batch > 0 :
            logger.warning(f"Attempted to download {num_to_download_in_batch} images for '{self.class_name}', but {saved_count} were saved (others may have been verified or failed).")
        else:
            logger.warning(f"No new images were processed for '{self.class_name}'.")

        logger.info(f"Total in metadata for '{self.class_name}': {len(all_image_data)}")

        cache['updated_at'] = datetime.now().isoformat()
        save_json_data(metadata_file, cache)

        return saved_count
