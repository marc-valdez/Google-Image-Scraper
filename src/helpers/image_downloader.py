import os, io, time, hashlib, random
from datetime import datetime
from urllib.parse import urlparse
from PIL import Image, UnidentifiedImageError
import requests, certifi
from urllib3 import Retry
from requests.adapters import HTTPAdapter
from requests.exceptions import SSLError
import urllib3

from src.logging.logger import logger
from src.utils.cache_utils import load_json_data, save_json_data
import config as cfg

class RateLimiter:
    def __init__(self):
        self.min_interval, self.last_call = cfg.REQUEST_INTERVAL, 0

    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()


def verify_file(path: str, expected_hash: str | None) -> bool:
    if not expected_hash: return False
    try:
        with open(path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest() == expected_hash
    except: return False


class ImageDownloader:
    def __init__(self, category_dir: str, class_name: str, worker_id: int):
        self.class_name, self.worker_id = class_name, worker_id
        self.category_dir = category_dir
        self.image_path = cfg.get_image_dir(category_dir, class_name)
        self.base_dir = cfg.get_output_dir()
        self.rate_limiter = RateLimiter()
        s = requests.Session()
        retries = Retry(total=cfg.MAX_RETRIES, backoff_factor=cfg.RETRY_BACKOFF, status_forcelist=[408, 429, 500, 502, 503, 504], allowed_methods=["GET"])
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=50)
        s.mount('http://', adapter)
        s.mount('https://', adapter)
        s.verify = certifi.where()
        self.session = s


    def _load_metadata(self) -> dict:
        meta_file = cfg.get_image_metadata_file(self.category_dir, self.class_name)
        return load_json_data(meta_file) or {}

    def _prepare_list(self, images_dict: dict) -> list:
        result = []
        
        for url_key, img_data in images_dict.items():
            needs_download_flag = True
            if 'download_data' in img_data:
                download_data = img_data['download_data']
                rel_path = download_data.get('relative_path')
                expected_hash = download_data.get('hash')
                
                if rel_path and expected_hash:
                    abs_path = os.path.join(self.base_dir, rel_path)
                    
                    if os.path.exists(abs_path) and verify_file(abs_path, expected_hash):
                        needs_download_flag = False
                    else:
                        # File missing or hash mismatch - delete corrupted record and redownload
                        logger.warning(f"❌ File corrupted/missing, deleting record: {os.path.basename(abs_path)}")
                        
                        if os.path.exists(abs_path):
                            try:
                                os.remove(abs_path)
                                logger.info(f"🗑️ Removed corrupted file: {abs_path}")
                            except Exception as e:
                                logger.error(f"Failed to remove corrupted file: {e}")
                        
                        # Delete the download_data record so it gets redownloaded
                        del img_data['download_data']
                        logger.info(f"🔄 Deleted corrupted record, will redownload")
            
            if needs_download_flag:
                result.append(url_key)
        return result

    def _restore_ssl_settings(self, original_verify: bool, ssl_verify: bool):
        """Restore SSL verification settings and warnings"""
        self.session.verify = original_verify
        if not ssl_verify:
            urllib3.warnings.resetwarnings()

    def _fetch(self, url: str) -> bytes | None:
        # Early validation - skip obviously problematic URLs
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            logger.warning(f"[URL Error] Invalid URL format: {url}")
            return None
        
        # Skip domains with known SSL certificate issues
        skip_ssl_domains = getattr(cfg, 'SKIP_SSL_PROBLEMATIC_DOMAINS', [])
        if skip_ssl_domains and any(domain in parsed_url.netloc.lower() for domain in skip_ssl_domains):
            logger.info(f"[URL Skip] Skipping SSL-problematic domain: {parsed_url.netloc}")
            return None
        
        max_ua_attempts = 5 if cfg.ROTATE_USER_AGENT else 1
        
        for i in range(max_ua_attempts):
            ua = cfg.get_random_user_agent() if cfg.ROTATE_USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": url,
                "Connection": "keep-alive",
            }

            # Try with SSL verification first, then without
            for ssl_verify in [True, False]:
                original_verify = self.session.verify
                try:
                    time.sleep(random.uniform(cfg.REQUEST_INTERVAL, cfg.REQUEST_INTERVAL + 1.5))

                    if not ssl_verify:
                        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                        self.session.verify = False
                        logger.warning(f"Retrying {url} with SSL verification disabled")

                    r = self.session.get(url, headers=headers, timeout=cfg.CONNECTION_TIMEOUT)
                    r.raise_for_status()
                    
                    self._restore_ssl_settings(original_verify, ssl_verify)
                    return r.content

                except SSLError as e:
                    self._restore_ssl_settings(original_verify, ssl_verify)
                    error_str = str(e).lower()
                    
                    if ssl_verify and any(term in error_str for term in ['hostname mismatch', 'certificate is not valid', 'certificate verify failed']):
                        logger.warning(f"[SSL Error] Certificate issue for {parsed_url.netloc}: {e}")
                        continue  # Try with SSL disabled
                    else:
                        logger.warning(f"[SSL Error] Skipping problematic URL {url}: {e}")
                        return None
                        
                except requests.exceptions.HTTPError as e:
                    self._restore_ssl_settings(original_verify, ssl_verify)
                    if e.response.status_code == 403 and i + 1 < max_ua_attempts:
                        logger.warning(f"[403] Forbidden for UA attempt {i + 1}, rotating UA...")
                        time.sleep(getattr(cfg, 'RETRY_BACKOFF_FOR_UA_ROTATE', 2.0))
                        break  # Try next user agent
                    return None
                        
                except requests.exceptions.RequestException as e:
                    self._restore_ssl_settings(original_verify, ssl_verify)
                    error_str = str(e).lower()
                    
                    if ssl_verify and any(term in error_str for term in ['ssl', 'certificate', 'hostname', 'timeout', 'timed out']):
                        logger.warning(f"[Request Error] SSL/Timeout issue for {parsed_url.netloc}: {e}")
                        continue  # Try with SSL disabled
                    else:
                        logger.warning(f"[Request Error] Skipping URL due to error: {e}")
                        return None
                
                break  # Success with current SSL setting
                
        return None

    def _image_info(self, content: bytes, url: str, filename: str, url_key: str, keep: bool):
        try:
            with Image.open(io.BytesIO(content)) as img:
                fmt = (img.format or 'jpg').lower()
                w, h, mode = img.width or 0, img.height or 0, img.mode or 'unknown'
        except (UnidentifiedImageError, Exception):
            fmt, w, h, mode = os.path.splitext(urlparse(url).path)[1][1:].lower() or 'jpg', 0, 0, 'unknown'

        if keep:
            # When keeping original names, use the original filename
            name = os.path.splitext(filename)[0] or f"{cfg.sanitize_class_name(self.class_name)}_{url_key}"
        else:
            # Use the key-based naming for consistent filenames
            key_number = int(url_key) if url_key.isdigit() else 1
            name = cfg.format_filename(self.class_name, key_number)
        
        fname = f"{name}.{fmt}"
        return fname, fmt, w, h, mode

    def _save(self, content: bytes, path: str, hash_: str) -> bool:
        try:
            with open(path, 'wb') as f:
                f.write(content)
            return verify_file(path, hash_)
        except:
            return False

    def _create_download_data(self, fname, hash_, rel, fmt, size, w, h, mode, now):
        return {
            "filename": fname,
            "relative_path": rel,
            "hash": hash_,
            "bytes": size,
            "width": w,
            "height": h,
            "mode": mode,
            "format": fmt,
            "downloaded_at": now
        }

    def _download_image(self, url_key: str, img_data: dict, metadata: dict, keep: bool) -> bool:
        self.rate_limiter.wait()
        
        # Extract fetch data early for validation
        fetch_data = img_data.get('fetch_data', {})
        url = fetch_data.get('link')
        orig_fname = fetch_data.get('original_filename', 'unknown')
        
        if not url:
            logger.warning(f"[Worker {self.worker_id}] No URL found for key {url_key}")
            return False

        # Check if already downloaded with same content
        if 'download_data' in img_data:
            download_data = img_data['download_data']
            rel_path = download_data.get('relative_path')
            if rel_path:
                abs_path = os.path.join(self.base_dir, rel_path)
                if os.path.exists(abs_path) and verify_file(abs_path, download_data.get('hash')):
                    return False  # Already have valid file

        content = self._fetch(url)
        if not content:
            return False

        # Process content only after successful fetch
        hash_ = hashlib.md5(content).hexdigest()
        fname, fmt, w, h, mode = self._image_info(content, url, orig_fname, url_key, keep)
        abs_path = os.path.join(self.image_path, fname)
        rel_path = os.path.relpath(abs_path, self.base_dir).replace('\\', '/')

        if not self._save(content, abs_path, hash_):
            return False

        # Update metadata with download data
        metadata['images'][url_key]['download_data'] = self._create_download_data(
            fname, hash_, rel_path, fmt, len(content), w, h, mode, datetime.now().isoformat()
        )
        logger.info(f"Saved: {fname} ({url_key})")
        return True

    def save_images(self, urls: list, keep: bool) -> int:
        if not urls:
            return 0
        
        # Load metadata once and cache file path
        metadata = self._load_metadata()
        images_dict = metadata.get('images', {})
        if not images_dict:
            logger.warning(f"[Worker {self.worker_id}] No images found in metadata for '{self.class_name}'")
            return 0
        
        meta_file = cfg.get_image_metadata_file(self.category_dir, self.class_name)
        to_download = self._prepare_list(images_dict)
        
        # Save metadata after cleaning up corrupted records in _prepare_list
        save_json_data(meta_file, metadata)
        
        if not to_download:
            return 0

        logger.start_progress(len(to_download), f"Downloading '{self.class_name}'", self.worker_id)
        count = 0
        
        # Process downloads and batch save metadata periodically
        for i, url_key in enumerate(to_download):
            img_data = images_dict[url_key]
            if self._download_image(url_key, img_data, metadata, keep):
                count += 1
                
            # Save metadata every 5 images or at the end to reduce I/O
            if (i + 1) % 5 == 0 or i == len(to_download) - 1:
                save_json_data(meta_file, metadata)
                
            logger.update_progress(worker_id=self.worker_id)
            
        logger.complete_progress(worker_id=self.worker_id)
        return count
