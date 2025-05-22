import os
from src.utils.cache_utils import ensure_cache_dir
from src.helpers.config import ScraperConfig
from src.helpers.url_fetcher import UrlFetcher
from src.helpers.image_downloader import ImageDownloader
from src.environment.webdriver_manager import WebDriverManager
from src.logging.logger import logger

class GoogleImageScraper():
    def __init__(self, config: ScraperConfig):
        self.config = config

        if not os.path.exists(self.config.image_path):
            logger.info(f"Creating output directory: {self.config.image_path}")
            os.makedirs(self.config.image_path)
        
        ensure_cache_dir(self.config.cache_dir)

        self.webdriver_manager = WebDriverManager(config=self.config)
        self.url_fetcher = UrlFetcher(config=self.config, webdriver_manager=self.webdriver_manager)
        self.image_downloader = ImageDownloader(config=self.config)
        logger.info(f"Initialized scraper for '{self.config.search_key_for_query}'")

    def fetch_image_urls(self):
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
        logger.info(f"Cleaning up resources for '{self.config.search_key_for_query}'")
        if hasattr(self, 'webdriver_manager') and self.webdriver_manager:
            self.webdriver_manager.close_driver()
