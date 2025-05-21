# -*- coding: utf-8 -*-
"""
Created on Sat Jul 18 13:01:02 2020

@author: OHyic
"""
#import helper libraries
import os
from cache_utils import ensure_cache_dir

# Import new classes
from url_fetcher import UrlFetcher
from image_downloader import ImageDownloader

class GoogleImageScraper():
    def __init__(self, webdriver_path, image_path, search_key="cat", advanced_suffix="", number_of_images=1, headless=True, max_missed=10):
        #check parameter types
        if (type(number_of_images)!=int):
            print("[Error] Number of images must be integer value.")
            # Consider raising an error instead of just returning
            raise ValueError("Number of images must be an integer value.")
        
        self.raw_search_key = search_key # Keep the original search key for filename generation if needed
        self.search_key_with_suffix = f"{search_key}{advanced_suffix}" # Used for actual searching and cache naming
        self.number_of_images = number_of_images
        self.webdriver_path = webdriver_path
        self.image_path = image_path
        self.headless = headless
        self.max_missed = max_missed # Passed to UrlFetcher

        if not os.path.exists(self.image_path):
            print(f"[INFO] Image path {self.image_path} not found. Creating a new folder.")
            os.makedirs(self.image_path)
        
        # Ensure cache directory exists (can be called multiple times safely)
        self.cache_dir = os.path.join(self.image_path, ".cache")
        ensure_cache_dir(self.cache_dir)

        self.url_fetcher = UrlFetcher(
            webdriver_path=self.webdriver_path,
            image_path=self.image_path, # For cache path consistency
            search_key=search_key, # Pass the original search key
            advanced_suffix=advanced_suffix,
            number_of_images=self.number_of_images,
            headless=self.headless,
            max_missed=self.max_missed
        )

        self.image_downloader = ImageDownloader(
            image_path=self.image_path,
            search_key=self.search_key_with_suffix
        )
        print(f"[INFO] GoogleImageScraper initialized for search: '{self.search_key_with_suffix}'")

    def fetch_image_urls(self):
        """
        Fetches image URLs using the UrlFetcher instance.
        """
        print(f"[INFO] Starting URL fetching process for '{self.search_key_with_suffix}' via GoogleImageScraper.")
        try:
            image_urls = self.url_fetcher.find_image_urls()
            print(f"[INFO] URL fetching process completed for '{self.search_key_with_suffix}'. Found {len(image_urls)} URLs.")
            return image_urls
        except Exception as e:
            print(f"[ERROR] An error occurred during URL fetching for '{self.search_key_with_suffix}': {e}")
            return []

    def download_images(self, image_urls, keep_filenames=False):
        """
        Downloads images using the ImageDownloader instance.
        'keep_filenames' determines if original filenames from URLs are used.
        """
        if not image_urls:
            print("[INFO] No image URLs provided to download_images method.")
            return 0
        
        print(f"[INFO] Starting image download process for '{self.search_key_with_suffix}' via GoogleImageScraper.")
        # Pass the original search key (self.raw_search_key) for consistent filename generation
        # if keep_filenames is False, as per original logic.
        saved_count = self.image_downloader.save_images(
            image_urls=image_urls,
            keep_filenames=keep_filenames,
            original_search_key_for_filename=self.raw_search_key
        )
        print(f"[INFO] Image download process completed for '{self.search_key_with_suffix}'. Saved {saved_count} new images.")
        return saved_count

    def close(self):
        """
        Clean up resources, primarily by ensuring the UrlFetcher's WebDriver is closed.
        """
        print(f"[INFO] Closing GoogleImageScraper for '{self.search_key_with_suffix}'.")
        if hasattr(self, 'url_fetcher') and self.url_fetcher:
            self.url_fetcher.close_driver() # UrlFetcher has its own method to close driver
