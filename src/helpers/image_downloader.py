import os, io, time, hashlib, random
from datetime import datetime
from urllib.parse import urlparse
from PIL import Image, UnidentifiedImageError
import requests, certifi
from urllib3 import Retry
from requests.adapters import HTTPAdapter

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
        self.image_path = cfg.get_image_path(category_dir, class_name)
        self.base_dir = cfg.get_output_dir()
        os.makedirs(self.image_path, exist_ok=True)
        self.rate_limiter = RateLimiter()
        s = requests.Session()
        retries = Retry(total=cfg.MAX_RETRIES, backoff_factor=cfg.RETRY_BACKOFF, status_forcelist=[408, 429, 500, 502, 503, 504], allowed_methods=["GET"])
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=50)
        s.mount('http://', adapter)
        s.mount('https://', adapter)
        s.verify = certifi.where()
        self.session = s

    def _get_abs_path(self, entry: dict | None) -> str | None:
        if not entry: return None
        rel_path = entry.get('relative_path')
        return os.path.join(self.base_dir, rel_path) if rel_path else None

    def _prepare_list(self, urls: list, data: dict) -> list:
        result = []
        for url_item in urls: 
            entry = data.get(url_item)
            path = self._get_abs_path(entry)
            
            needs_download_flag = True 
            if entry and path and os.path.exists(path):
                if verify_file(path, entry.get("hash")):
                    needs_download_flag = False
            
            if needs_download_flag:
                result.append(url_item)
        return result

    def _fetch(self, url: str) -> bytes | None:
        uas = getattr(cfg, 'USER_AGENTS', []) or []
        try_uas = random.sample(uas, len(uas)) if cfg.ROTATE_USER_AGENT else uas
        try_uas = try_uas or ["Mozilla/5.0"]

        for i, ua in enumerate(try_uas):
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": url,
                "Connection": "keep-alive",
            }

            try:
                delay = random.uniform(cfg.REQUEST_INTERVAL, cfg.REQUEST_INTERVAL + 1.5)
                time.sleep(delay)

                r = self.session.get(url, headers=headers, timeout=cfg.CONNECTION_TIMEOUT)
                r.raise_for_status()
                return r.content

            except requests.exceptions.HTTPError as e:
                code = e.response.status_code
                if code == 403 and i + 1 < len(try_uas):
                    logger.warning(f"[403] Forbidden for UA index {i}, rotating UA...")
                    time.sleep(getattr(cfg, 'RETRY_BACKOFF_FOR_UA_ROTATE', 2.0))
                    continue
                break 
            except requests.exceptions.RequestException as e:
                logger.warning(f"[Request Error] {e}")
                break
        return None

    def _image_info(self, content: bytes, url: str, filename: str, idx: int, keep: bool):
        try:
            with Image.open(io.BytesIO(content)) as img:
                fmt = (img.format or 'jpg').lower()
                w, h, mode = img.width or 0, img.height or 0, img.mode or 'unknown'
        except (UnidentifiedImageError, Exception):
            fmt, w, h, mode = os.path.splitext(urlparse(url).path)[1][1:].lower() or 'jpg', 0, 0, 'unknown'

        name = os.path.splitext(filename)[0] or f"{cfg.sanitize_class_name(self.class_name)}_{idx + 1:03d}"
        fname = f"{cfg.format_filename(self.class_name, idx + 1) if not keep else name}.{fmt}"
        return fname, fmt, w, h, mode

    def _save(self, content: bytes, path: str, hash_: str) -> bool:
        try:
            with open(path, 'wb') as f:
                f.write(content)
            return verify_file(path, hash_)
        except:
            return False

    def _metadata(self, fname, orig, hash_, rel, fmt, size, w, h, mode, now):
        return dict(
            filename=fname, original_filename=orig, hash=hash_, relative_path=rel,
            format=fmt, size=size, width=w, height=h, mode=mode,
            downloaded_at=now, updated_at=now
        )

    def _download_image(self, url: str, data: dict, keep: bool, meta_file: str, cache: dict) -> bool:
        self.rate_limiter.wait()
        content = self._fetch(url)
        if not content: return False

        hash_ = hashlib.md5(content).hexdigest()
        now = datetime.now().isoformat()
        orig_fname = os.path.basename(urlparse(url).path)
        existing = data.get(url)

        if existing and existing.get('hash') == hash_:
            path = self._get_abs_path(existing)
            if path and os.path.exists(path) and verify_file(path, hash_):
                existing['updated_at'] = now
                cache['updated_at'] = now
                save_json_data(meta_file, cache)
                return False

        fname, fmt, w, h, mode = self._image_info(content, url, orig_fname, len(data), keep)
        abs_path = os.path.join(self.image_path, fname)
        rel_path = os.path.relpath(abs_path, self.base_dir).replace('\\', '/')

        if not self._save(content, abs_path, hash_):
            return False

        data[url] = self._metadata(fname, orig_fname, hash_, rel_path, fmt, len(content), w, h, mode, now)
        cache['image_cache'], cache['updated_at'] = data, now
        save_json_data(meta_file, cache)
        logger.info(f"Saved: {fname}")
        return True

    def save_images(self, urls: list, keep: bool) -> int:
        if not urls: return 0
        category_output_path = os.path.join(self.base_dir, self.category_dir)
        meta_file = cfg.get_image_metadata_file(category_output_path, self.class_name)
        
        cache = load_json_data(meta_file) or {}
        cache.setdefault('image_cache', {})
        cache.setdefault('class_name', self.class_name)
        cache.setdefault('created_at', datetime.now().isoformat())
        data = cache['image_cache']

        to_download = self._prepare_list(urls, data)
        if not to_download:
            return 0

        logger.start_progress(len(to_download), f"Downloading '{self.class_name}'", self.worker_id)
        count = 0
        for i, url_item in enumerate(to_download): 
            if self._download_image(url_item, data, keep, meta_file, cache):
                count += 1
            logger.update_progress(worker_id=self.worker_id)
        logger.complete_progress(worker_id=self.worker_id)
        return count
