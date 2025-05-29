import os
from src.utils.cache_utils import ensure_cache_dir, is_cache_complete
import config as cfg
from src.helpers.url_fetcher import UrlFetcher
from src.helpers.image_downloader import ImageDownloader
from src.logging.logger import logger

class GoogleImageScraper:
    def __init__(self, category_dir: str, class_name: str, worker_id: int, driver_instance=None):
        self.category_dir = category_dir
        self.worker_id = worker_id

        self.query = class_name
        
        if is_cache_complete(self.category_dir, class_name):
            logger.info(f"[Worker {self.worker_id}] Skipping scraper for '{self.query}' — already completed")
            self.skip = True
            return
        self.skip = False

        self.image_path, self.metadata_dir = cfg.ensure_class_directories(self.category_dir, class_name)

        # Pass the driver_instance to UrlFetcher
        self.url_fetcher = UrlFetcher(self.category_dir, class_name, self.worker_id, driver_instance=driver_instance)
        self.image_downloader = ImageDownloader(self.category_dir, class_name, self.worker_id)
        logger.info(f"[Worker {self.worker_id}] Initialized scraper for '{self.query}'")

    def fetch_image_urls(self):
        if self.skip:
            logger.info(f"[Worker {self.worker_id}] Skipping URL fetch — already done for '{self.query}'")
            return []

        logger.status(f"[Worker {self.worker_id}] Searching for '{self.query}' images")
        try:
            image_urls = self.url_fetcher.find_image_urls()
            if image_urls:
                logger.success(f"[Worker {self.worker_id}] Found {len(image_urls)} images for '{self.query}'")
            else:
                logger.warning(f"[Worker {self.worker_id}] No images found for '{self.query}'")
            return image_urls
        except Exception as e:
            logger.error(f"[Worker {self.worker_id}] Failed to fetch URLs for '{self.query}': {e}")
            return []

    def download_images(self, image_urls):
        if self.skip:
            logger.info(f"[Worker {self.worker_id}] Skipping download — already done for '{self.query}'")
            return 0

        if not image_urls:
            logger.info(f"[Worker {self.worker_id}] No URLs provided for download")
            return 0

        logger.status(f"[Worker {self.worker_id}] Downloading {len(image_urls)} images for '{self.query}'")
        saved_count = self.image_downloader.save_images(
            image_urls,
            cfg.KEEP_FILENAMES
        )
        if saved_count > 0:
            logger.success(f"[Worker {self.worker_id}] Downloaded {saved_count} new images for '{self.query}'")
        else:
            logger.warning(f"[Worker {self.worker_id}] No new images downloaded for '{self.query}'")
        return saved_count

    def close(self):
        if self.skip:
            return
        logger.info(f"[Worker {self.worker_id}] Cleaning up resources for '{self.query}'")
        if hasattr(self, 'url_fetcher') and self.url_fetcher:
            self.url_fetcher.close() # UrlFetcher will now handle its WebDriverManager appropriately
