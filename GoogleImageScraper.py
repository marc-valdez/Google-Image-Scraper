import os
from cache_utils import ensure_cache_dir
from config import ScraperConfig
from url_fetcher import UrlFetcher
from image_downloader import ImageDownloader

class GoogleImageScraper():
    def __init__(self, webdriver_path, image_path, search_key="cat", advanced_suffix="", number_of_images=1, headless=True, max_missed=10):
        if not isinstance(number_of_images, int):
            raise ValueError("Number of images must be an integer value.")
        
        self.config = ScraperConfig(
            webdriver_path=webdriver_path,
            image_path=image_path,
            search_key=search_key,
            advanced_suffix=advanced_suffix,
            number_of_images=number_of_images,
            headless=headless,
            max_missed=max_missed
        )

        if not os.path.exists(self.config.image_path):
            print(f"[INFO] Image path {self.config.image_path} not found. Creating a new folder.")
            os.makedirs(self.config.image_path)
        
        ensure_cache_dir(self.config.cache_dir)

        self.url_fetcher = UrlFetcher(config=self.config)
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
        if hasattr(self, 'url_fetcher') and self.url_fetcher:
            self.url_fetcher.close_driver()
