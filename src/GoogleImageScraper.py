import os
from src.utils.cache_utils import ensure_cache_dir, is_cache_complete
from src.helpers.config import ScraperConfig
from src.helpers.url_fetcher import UrlFetcher
from src.helpers.image_downloader import ImageDownloader
from src.environment.webdriver import WebDriverManager
from src.logging.logger import logger

class GoogleImageScraper:
    def __init__(self, config: ScraperConfig, worker_id):
        self.config = config

        if is_cache_complete(config):
            logger.info(f"Skipping scraper for '{config.search_key_for_query}' — already completed")
            self.skip = True
            return
        self.skip = False

        os.makedirs(config.image_path, exist_ok=True)
        ensure_cache_dir(config.cache_dir)

        self.url_fetcher = UrlFetcher(config, worker_id)
        self.image_downloader = ImageDownloader(config, worker_id)
        logger.info(f"Initialized scraper for '{config.search_key_for_query}'")

    def fetch_image_urls(self):
        if self.skip:
            logger.info(f"Skipping URL fetch — already done for '{self.config.search_key_for_query}'")
            return []

        logger.status(f"Searching for '{self.config.search_key_for_query}' images")
        try:
            image_urls = self.url_fetcher.find_image_urls()
            if image_urls:
                logger.success(f"Found {len(image_urls)} images for '{self.config.search_key_for_query}'")
            else:
                logger.warning(f"No images found for '{self.config.search_key_for_query}'")
            return image_urls
        except Exception as e:
            logger.error(f"Failed to fetch URLs for '{self.config.search_key_for_query}': {e}")
            return []

    def download_images(self, image_urls, keep_filenames=False):
        if self.skip:
            logger.info(f"Skipping download — already done for '{self.config.search_key_for_query}'")
            return 0

        if not image_urls:
            logger.info("No URLs provided for download")
            return 0

        logger.status(f"Downloading {len(image_urls)} images for '{self.config.search_key_for_query}'")
        saved_count = self.image_downloader.save_images(
            image_urls=image_urls,
            keep_filenames=keep_filenames
        )
        if saved_count > 0:
            logger.success(f"Downloaded {saved_count} new images for '{self.config.search_key_for_query}'")
        else:
            logger.warning(f"No new images downloaded for '{self.config.search_key_for_query}'")
        return saved_count

    def close(self):
        if self.skip:
            return
        logger.info(f"Cleaning up resources for '{self.config.search_key_for_query}'")
        if hasattr(self, 'webdriver') and self.webdriver:
            self.webdriver.close_driver()
