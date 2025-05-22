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

        # Log the original search query the user sees/expects
        logger.start_progress(len(image_urls), f"Downloading images for '{self.config.search_key_for_query}'")
        download_checkpoint = load_json_data(self.download_checkpoint_file) or {}
        urls_hash = hash(tuple(sorted(image_urls)))

        # Initialize or get image cache
        image_cache = download_checkpoint.get('image_cache', {})
        
        # Checkpoint uses the original search_key_for_query as the reference
        if (download_checkpoint.get('search_key_ref') == self.config.search_key_for_query and
            download_checkpoint.get('all_image_urls_hash') == urls_hash):
            start_index = download_checkpoint.get('last_downloaded_index', -1) + 1
            downloaded_previously_count = download_checkpoint.get('saved_count_so_far', 0)
            logger.info(f"Resuming from index {start_index} ({downloaded_previously_count} already saved)")
        else:
            # Store the original search_key_for_query in the checkpoint for reference
            save_json_data(self.download_checkpoint_file, {
                'search_key_ref': self.config.search_key_for_query,
                'all_image_urls_hash': urls_hash,
                'last_downloaded_index': -1,
                'total_urls_to_download': len(image_urls),
                'saved_count_so_far': 0,
                'image_cache': {}
            })
            downloaded_previously_count = 0
            image_cache = {}
            start_index = 0
            logger.info("Starting new download session")


        saved_count_this_session = 0
        for indx in range(start_index, len(image_urls)):
            image_url = image_urls[indx]
            
            # Use the clean_base_name for image filenames, e.g., "ArrozCaldo"
            search_string_for_filename = self.config.clean_base_name


            try:
                self.rate_limiter.wait()  # Rate limit requests
                
                logger.info(f"Downloading {indx+1}/{len(image_urls)}: {logger.truncate_url(image_url)}")
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Referer": image_url
                }
                
                # Use session for connection pooling and automatic retries
                response = self.session.get(image_url, headers=headers, timeout=15)
                if response.status_code != 200:
                    raise Exception(f"HTTP Status code: {response.status_code}")

                try:
                    with Image.open(io.BytesIO(response.content)) as img:
                        image_format = img.format.lower() if img.format else 'jpg'
                except Exception as img_err:
                    logger.warning(f"Error determining image format: {img_err}. Guessing from URL")
                    parsed_url_path = urlparse(image_url).path
                    _, ext_from_url = os.path.splitext(parsed_url_path)
                    if ext_from_url and len(ext_from_url) > 1:
                        image_format = ext_from_url[1:].lower()
                        if image_format not in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff']:
                            logger.warning(f"Unknown format '{image_format}' - using jpg")
                            image_format = 'jpg'
                    else:
                        image_format = 'jpg'

                if keep_filenames:
                    base_name = os.path.basename(urlparse(image_url).path)
                    name_part, ext_part = os.path.splitext(base_name)
                    filename_ext = image_format if not ext_part or ext_part[1:].lower() != image_format else ext_part[1:].lower()
                    filename = f"{name_part or search_string_for_filename + str(indx)}.{filename_ext}"
                else:
                    filename = f"{search_string_for_filename}_{indx}.{image_format}"

                save_path = os.path.join(self.config.image_path, filename)

                # Check if URL exists in cache and file exists
                cached_info = image_cache.get(image_url)
                if cached_info and os.path.exists(cached_info['path']):
                    try:
                        with open(cached_info['path'], 'rb') as f:
                            existing_content = f.read()
                            existing_hash = hashlib.md5(existing_content).hexdigest()
                            
                        if existing_hash == cached_info['hash']:
                            logger.info(f"File exists in cache, verified: {os.path.basename(cached_info['path'])}")
                            logger.update_progress()
                            current_total_saved = downloaded_previously_count + saved_count_this_session
                            save_json_data(self.download_checkpoint_file, {
                                'search_key_ref': self.config.search_key_for_query, # Store original query key
                                'all_image_urls_hash': urls_hash,
                                'last_downloaded_index': indx,
                                'total_urls_to_download': len(image_urls),
                                'saved_count_so_far': current_total_saved,
                                'image_cache': image_cache
                            })
                            continue
                    except Exception as e:
                        logger.warning(f"Cache verification failed for {os.path.basename(cached_info['path'])}: {e}")
                        # Continue to download new copy
                
                # Regular file existence check if not in cache
                if os.path.exists(save_path):
                    logger.info(f"File exists but not in cache, will verify: {os.path.basename(save_path)}")

                # Calculate image hash before saving
                image_hash = hashlib.md5(response.content).hexdigest()
                
                # Write content and verify integrity
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                
                if not verify_image_file(save_path, response.content):
                    os.remove(save_path)
                    raise Exception("File integrity check failed")
                
                # Update image cache with successful download
                image_cache[image_url] = {
                    'filename': filename,
                    'hash': image_hash,
                    'path': save_path,
                    'format': image_format,
                    'size': len(response.content),
                    'download_time': time.time()
                }
                
                logger.info(f"Saved: {os.path.basename(save_path)}")
                saved_count_this_session += 1
                logger.update_progress()

                current_total_saved = downloaded_previously_count + saved_count_this_session
                save_json_data(self.download_checkpoint_file, {
                    'search_key_ref': self.config.search_key_for_query, # Store original query key
                    'all_image_urls_hash': urls_hash,
                    'last_downloaded_index': indx,
                    'total_urls_to_download': len(image_urls),
                    'saved_count_so_far': current_total_saved,
                    'image_cache': image_cache
                })

            except requests.exceptions.RequestException as e:
                logger.error(f"Network error downloading image {indx+1}: {e}")
                # Remove from cache if network error to allow retry
                if image_url in image_cache:
                    del image_cache[image_url]
            except Image.UnidentifiedImageError:
                logger.error(f"Invalid or corrupt image data from {logger.truncate_url(image_url)}")
                # Remove from cache if corrupt
                if image_url in image_cache:
                    del image_cache[image_url]
            except Exception as e:
                logger.error(f"Failed to save image {indx+1}: {e}")
                # Remove from cache on general failure
                if image_url in image_cache:
                    del image_cache[image_url]
                current_total_saved = downloaded_previously_count + saved_count_this_session
                save_json_data(self.download_checkpoint_file, {
                    'search_key_ref': self.config.search_key_for_query, # Store original query key
                    'all_image_urls_hash': urls_hash,
                    'last_downloaded_index': indx,
                    'total_urls_to_download': len(image_urls),
                    'saved_count_so_far': current_total_saved,
                    'image_cache': image_cache
                })

        total_saved_overall = downloaded_previously_count + saved_count_this_session
        logger.complete_progress()
        
        if saved_count_this_session > 0:
            logger.success(f"Downloaded {saved_count_this_session} new images ({total_saved_overall} total)")
        else:
            logger.warning("No new images downloaded")

        final_checkpoint_data = load_json_data(self.download_checkpoint_file)
        if final_checkpoint_data and final_checkpoint_data.get('last_downloaded_index', -1) == len(image_urls) - 1:
            cache_filename_base = self.config.clean_base_name or "generic_cache"
            cache_file = os.path.join(self.config.image_path, f"{cache_filename_base}.json")
            
            save_json_data(cache_file, {
                'search_key': self.config.search_key_for_query,
                'download_completed': time.time(),
                'image_cache': image_cache
            })
            remove_file_if_exists(self.download_checkpoint_file)
            logger.info(f"Download complete - Cache saved to {os.path.basename(cache_file)}")
        else:
            logger.warning("Download may be incomplete - checkpoint retained")

        return saved_count_this_session