import os
from src.utils.cache_utils import ensure_cache_dir, is_cache_complete
import config as cfg
from src.helpers.url_fetcher import UrlFetcher
from src.helpers.image_downloader import ImageDownloader
from src.logging.logger import logger

class GoogleImageScraper:
    def __init__(self, category_dir: str, search_term: str, worker_id: int):
        self.category_dir = category_dir
        self.search_term = search_term
        self.worker_id = worker_id

        self.search_key_for_query = cfg.get_search_key_for_query(self.search_term)
        self.image_path = cfg.get_image_path(self.category_dir, self.search_term)
        self.cache_dir = cfg.get_cache_dir(self.category_dir, self.search_term)

        if is_cache_complete(self.category_dir, self.search_term):
            logger.info(f"Skipping scraper for '{self.search_key_for_query}' — already completed")
            self.skip = True
            return
        self.skip = False

        os.makedirs(self.image_path, exist_ok=True)
        ensure_cache_dir(self.cache_dir)

        self.url_fetcher = UrlFetcher(self.category_dir, self.search_term, self.worker_id)
        self.image_downloader = ImageDownloader(self.category_dir, self.search_term, self.worker_id)
        logger.info(f"Initialized scraper for '{self.search_key_for_query}'")

    def fetch_image_urls(self):
        if self.skip:
            logger.info(f"Skipping URL fetch — already done for '{self.search_key_for_query}'")
            return []

        logger.status(f"Searching for '{self.search_key_for_query}' images")
        try:
            image_urls = self.url_fetcher.find_image_urls()
            if image_urls:
                logger.success(f"Found {len(image_urls)} images for '{self.search_key_for_query}'")
            else:
                logger.warning(f"No images found for '{self.search_key_for_query}'")
            return image_urls
        except Exception as e:
            logger.error(f"Failed to fetch URLs for '{self.search_key_for_query}': {e}")
            return []

    def download_images(self, image_urls):
        if self.skip:
            logger.info(f"Skipping download — already done for '{self.search_key_for_query}'")
            return 0

        if not image_urls:
            logger.info("No URLs provided for download")
            return 0

        logger.status(f"Downloading {len(image_urls)} images for '{self.search_key_for_query}'")
        saved_count = self.image_downloader.save_images(
            image_urls=image_urls,
            keep_filenames=cfg.KEEP_FILENAMES
        )
        if saved_count > 0:
            logger.success(f"Downloaded {saved_count} new images for '{self.search_key_for_query}'")
        else:
            logger.warning(f"No new images downloaded for '{self.search_key_for_query}'")
        return saved_count

    def close(self):
        if self.skip:
            return
        logger.info(f"Cleaning up resources for '{self.search_key_for_query}'")
        if hasattr(self, 'url_fetcher') and self.url_fetcher:
            self.url_fetcher.close()
