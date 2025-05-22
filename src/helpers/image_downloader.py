import os
import io
import time
import hashlib
from PIL import Image, UnidentifiedImageError
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3 import Retry
import requests

from src.logging.logger import logger
from src.utils.cache_utils import load_json_data, save_json_data
from src.helpers import config as cfg

class RateLimiter:
    def __init__(self):
        self.min_interval = cfg.REQUEST_INTERVAL
        self.last_call = 0

    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()

def verify_image_file(file_path, content):
    try:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest() == hashlib.md5(content).hexdigest()
    except Exception:
        return False

class ImageDownloader:
    def __init__(self, category_dir: str, search_term: str, worker_id: int):
        self.category_dir = category_dir
        self.search_term = search_term
        self.worker_id = worker_id
        
        self.image_path = cfg.get_image_path(self.category_dir, self.search_term)
        self.search_key_query = cfg.get_search_key_for_query(self.search_term)
        self.clean_base = cfg.get_clean_base_name(self.search_term)

        self.rate_limiter = RateLimiter()
        self.session = self._create_session()
        os.makedirs(self.image_path, exist_ok=True)

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

    def save_images(self, image_urls, keep_filenames):
        if not image_urls:
            logger.info("No image URLs provided.")
            return 0

        metadata_file = cfg.get_image_metadata_file(self.category_dir, self.search_term)
        cache = load_json_data(metadata_file) or {}
        cache.setdefault('image_cache', {})
        all_image_data = cache['image_cache']

        all_verified = all(
            url in all_image_data and
            os.path.exists(all_image_data[url]['path']) and
            hashlib.md5(open(all_image_data[url]['path'], 'rb').read()).hexdigest() == all_image_data[url]['hash']
            for url in image_urls
        )

        if all_verified and len(image_urls) > 0 :
            logger.info(f"All {len(image_urls)} images already downloaded and verified for '{self.search_key_query}'.")
            return 0

        logger.start_progress(len(image_urls), f"Downloading images for '{self.search_key_query}'", self.worker_id)
        saved_count = 0

        for idx, url in enumerate(image_urls):
            self.rate_limiter.wait()
            logger.info(f"Downloading {idx+1}/{len(image_urls)}: {logger.truncate_url(url)}")

            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Referer": url 
                }
                response = self.session.get(url, headers=headers, timeout=cfg.CONNECTION_TIMEOUT)
                response.raise_for_status()
                content = response.content

                try:
                    with Image.open(io.BytesIO(content)) as img:
                        img_format = img.format.lower() if img.format else 'jpg'
                except Exception:
                    ext = os.path.splitext(urlparse(url).path)[1][1:].lower()
                    img_format = ext if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff'] else 'jpg'

                if keep_filenames:
                    base_from_url = os.path.splitext(os.path.basename(urlparse(url).path))[0]
                    file_base_name = base_from_url or f"{self.clean_base}_{len(all_image_data)+1:03d}"
                else:
                    file_base_name = f"{self.clean_base}_{len(all_image_data)+1:03d}"
                
                filename = f"{file_base_name}.{img_format}"
                path = os.path.join(self.image_path, filename)

                if url in all_image_data and os.path.exists(all_image_data[url]['path']):
                    with open(all_image_data[url]['path'], 'rb') as f_check:
                        if hashlib.md5(f_check.read()).hexdigest() == all_image_data[url]['hash']:
                            logger.info(f"Already downloaded and verified: {filename}")
                            logger.update_progress(worker_id=self.worker_id)
                            continue
                        else:
                            logger.warning(f"Hash mismatch for existing file: {filename}. Re-downloading.")


                image_hash = hashlib.md5(content).hexdigest()
                with open(path, 'wb') as f:
                    f.write(content)

                if not verify_image_file(path, content):
                    if os.path.exists(path):
                        os.remove(path)
                    raise Exception("File integrity verification failed after saving.")

                all_image_data[url] = {
                    'filename': filename,
                    'hash': image_hash,
                    'path': path,
                    'format': img_format,
                    'size': len(content),
                    'download_time': time.time()
                }

                cache.update({
                    'image_cache': all_image_data,
                    'search_key': self.search_key_query,
                    'download_completed': time.time()
                })
                save_json_data(metadata_file, cache)
                logger.info(f"Saved: {filename}")
                saved_count += 1
                logger.update_progress(worker_id=self.worker_id)

            except requests.exceptions.RequestException as e:
                logger.error(f"Network error for {logger.truncate_url(url)}: {e}")
            except UnidentifiedImageError:
                logger.error(f"Invalid image data: {logger.truncate_url(url)}")
            except Exception as e:
                logger.error(f"Failed to save {logger.truncate_url(url)}: {e}")

        logger.complete_progress(worker_id=self.worker_id)
        if saved_count > 0:
            logger.success(f"Downloaded {saved_count} new images for '{self.search_key_query}'.")
        else:
            logger.warning(f"No new images added for '{self.search_key_query}'.")
        logger.info(f"Total in metadata for '{self.search_key_query}': {len(all_image_data)}")
        return saved_count
