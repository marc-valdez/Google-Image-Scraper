import os
import io
import time
import hashlib
from PIL import Image
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
import requests
from urllib3 import Retry
from src.logging.logger import logger
from src.utils.cache_utils import load_json_data, save_json_data, remove_file_if_exists

class RateLimiter:
    def __init__(self, min_interval=1.0):
        self.min_interval = min_interval
        self.last_call = 0

    def wait(self):
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()

def verify_image_file(file_path, original_content):
    """Verify downloaded image file integrity"""
    try:
        with open(file_path, 'rb') as f:
            saved_content = f.read()
        return hashlib.md5(saved_content).hexdigest() == hashlib.md5(original_content).hexdigest()
    except Exception:
        return False

class ImageDownloader:
    def __init__(self, config):
        self.config = config
        self.rate_limiter = RateLimiter(min_interval=1.0)  # 1 second between requests
        self.session = self._create_session()
        
        if not os.path.exists(self.config.image_path):
            os.makedirs(self.config.image_path)
            
    def _create_session(self):
        """Create a requests session with retries and pooling"""
        session = requests.Session()
        
        # Configure retry strategy
        retries = Retry(
            total=5,  # Total number of retries
            backoff_factor=0.5,  # Wait 0.5, 1, 2, 4... seconds between retries
            status_forcelist=[408, 429, 500, 502, 503, 504],  # Retry on these status codes
            allowed_methods=["GET"]
        )
        
        # Configure connection pooling
        adapter = HTTPAdapter(
            max_retries=retries,
            pool_connections=10,
            pool_maxsize=50
        )
        
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    @property
    def download_checkpoint_file(self):
        return self.config.get_download_checkpoint_file()

    def save_images(self, image_urls, keep_filenames):
        if not image_urls:
            logger.info("No image URLs provided to save")
            return 0

        logger.start_progress(len(image_urls), f"Downloading images for '{self.config.search_key_for_query}'")

        # Get the path for the ClassName_metadata.json file from config (now in .cache dir)
        metadata_file = self.config.get_image_metadata_file()
        
        loaded_metadata = load_json_data(metadata_file) or {}
        if 'image_cache' not in loaded_metadata:
            loaded_metadata['image_cache'] = {}
        
        all_image_data = loaded_metadata.get('image_cache', {})

        all_urls_verified = True
        if image_urls:
            for url_to_check in image_urls:
                cached_entry = all_image_data.get(url_to_check)
                if not cached_entry or not os.path.exists(cached_entry.get('path', '')):
                    all_urls_verified = False
                    break
                try:
                    with open(cached_entry['path'], 'rb') as f_verify:
                        content = f_verify.read()
                    if hashlib.md5(content).hexdigest() != cached_entry.get('hash', ''):
                        all_urls_verified = False
                        break
                except Exception:
                    all_urls_verified = False
                    break
        else:
            all_urls_verified = True


        if all_urls_verified and image_urls:
            logger.info(f"All {len(image_urls)} provided URLs for '{self.config.search_key_for_query}' are already downloaded and verified.")
            logger.complete_progress()
            return 0

        newly_saved_count = 0
        
        for indx, image_url in enumerate(image_urls):
            image_url = image_urls[indx]
            img_basename_for_file = self.config.clean_base_name

            try:
                self.rate_limiter.wait()
                
                logger.info(f"Downloading {indx+1}/{len(image_urls)}: {logger.truncate_url(image_url)}")
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Referer": image_url
                }
                
                response = self.session.get(image_url, headers=headers, timeout=15)
                if response.status_code != 200:
                    raise Exception(f"HTTP Status code: {response.status_code}")

                try:
                    with Image.open(io.BytesIO(response.content)) as img:
                        image_format = img.format.lower() if img.format else 'jpg'
                except Exception:
                    parsed_url_path = urlparse(image_url).path
                    _, ext_from_url = os.path.splitext(parsed_url_path)
                    if ext_from_url and len(ext_from_url) > 1:
                        image_format = ext_from_url[1:].lower()
                        if image_format not in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff']:
                            image_format = 'jpg'
                    else:
                        image_format = 'jpg'

                if keep_filenames:
                    original_fname_part = os.path.splitext(os.path.basename(urlparse(image_url).path))[0]
                    filename_ext = image_format
                    current_image_count = len(all_image_data)
                    filename = f"{original_fname_part or f'{img_basename_for_file}_{current_image_count + 1:03d}'}.{filename_ext}"
                else:
                    current_image_count = len(all_image_data)
                    filename = f"{img_basename_for_file}_{current_image_count + 1:03d}.{image_format}"

                save_path = os.path.join(self.config.image_path, filename)

                existing_img_info = all_image_data.get(image_url)
                if existing_img_info and os.path.exists(existing_img_info['path']):
                    try:
                        with open(existing_img_info['path'], 'rb') as f_existing:
                            existing_content = f_existing.read()
                        existing_hash = hashlib.md5(existing_content).hexdigest()
                        
                        if existing_hash == existing_img_info['hash']:
                            logger.info(f"Image already in metadata and verified: {os.path.basename(existing_img_info['path'])}")
                            logger.update_progress()
                            continue
                    except Exception as e:
                        logger.warning(f"Metadata cache verification failed for {os.path.basename(existing_img_info['path'])}: {e}. Will re-download.")
                
                image_hash = hashlib.md5(response.content).hexdigest()
                
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                
                if not verify_image_file(save_path, response.content):
                    os.remove(save_path)
                    raise Exception("File integrity check failed")
                
                all_image_data[image_url] = {
                    'filename': filename,
                    'hash': image_hash,
                    'path': save_path,
                    'format': image_format,
                    'size': len(response.content),
                    'download_time': time.time()
                }
                
                loaded_metadata['image_cache'] = all_image_data
                loaded_metadata['search_key'] = self.config.search_key_for_query
                loaded_metadata['download_completed'] = time.time()
                save_json_data(metadata_file, loaded_metadata)
                
                logger.info(f"Saved: {os.path.basename(save_path)} and updated {os.path.basename(metadata_file)}")
                newly_saved_count += 1
                logger.update_progress()

            except requests.exceptions.RequestException as e:
                logger.error(f"Network error downloading image {indx+1} ({logger.truncate_url(image_url)}): {e}")
            except Image.UnidentifiedImageError:
                logger.error(f"Invalid or corrupt image data from {logger.truncate_url(image_url)}")
            except Exception as e:
                logger.error(f"Failed to save image {indx+1} ({logger.truncate_url(image_url)}): {e}")

        logger.complete_progress()
        
        total_images_in_metadata = len(all_image_data)
        if newly_saved_count > 0:
            logger.success(f"Downloaded and added {newly_saved_count} new images to metadata.")
        else:
            logger.warning("No new images added to metadata in this session.")
        logger.info(f"Total images in '{os.path.basename(metadata_file)}': {total_images_in_metadata}")
        
        return newly_saved_count