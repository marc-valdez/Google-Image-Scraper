import os
from cache_utils import ensure_cache_dir
from config import ScraperConfig
from url_fetcher import UrlFetcher
from image_downloader import ImageDownloader
from webdriver_manager import WebDriverManager

class GoogleImageScraper():
    def __init__(self, config: ScraperConfig):
        self.config = config

        if not os.path.exists(self.config.image_path):
            print(f"[INFO] Image path {self.config.image_path} not found. Creating a new folder.")
            os.makedirs(self.config.image_path)
        
        ensure_cache_dir(self.config.cache_dir)

        self.webdriver_manager = WebDriverManager(config=self.config)
        self.url_fetcher = UrlFetcher(config=self.config, webdriver_manager=self.webdriver_manager)
        self.image_downloader = ImageDownloader(config=self.config)
        print(f"[INFO] GoogleImageScraper initialized for search: '{self.config.search_key_for_query}'")

    def fetch_image_urls(self):
        print(f"[INFO] Starting URL fetching process for '{self.config.search_key_for_query}' via GoogleImageScraper.")
        try:
            image_urls = self.url_fetcher.find_image_urls()
            print(f"[INFO] URL fetching process completed for '{self.config.search_key_for_query}'. Found {len(image_urls)} URLs.")
            return image_urls
        except Exception as e:
            print(f"[ERROR] An error occurred during URL fetching for '{self.config.search_key_for_query}': {e}")
            return []

    def download_images(self, image_urls, keep_filenames=False):
        if not image_urls:
            print("[INFO] No image URLs provided to download_images method.")
            return 0
        
        print(f"[INFO] Starting image download process for '{self.config.search_key_for_query}' via GoogleImageScraper.")
        saved_count = self.image_downloader.save_images(
            image_urls=image_urls,
            keep_filenames=keep_filenames
        )
        print(f"[INFO] Image download process completed for '{self.config.search_key_for_query}'. Saved {saved_count} new images.")
        return saved_count

    def close(self):
        print(f"[INFO] Closing GoogleImageScraper for '{self.config.search_key_for_query}'.")
        if hasattr(self, 'webdriver_manager') and self.webdriver_manager:
            self.webdriver_manager.close_driver()
