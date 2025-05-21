import os

class ScraperConfig:
    def __init__(self, webdriver_path, image_path, search_key, advanced_suffix,
                 number_of_images, headless, max_missed):
        self.webdriver_path = webdriver_path
        self.image_path = image_path
        self.raw_search_key = search_key
        self.advanced_suffix = advanced_suffix
        self.number_of_images = number_of_images
        self.headless = headless
        self.max_missed = max_missed

    @property
    def search_key_for_query(self):
        return f"{self.raw_search_key}{self.advanced_suffix}"

    @property
    def cache_dir(self):
        return os.path.join(self.image_path, ".cache")

    def get_url_cache_file(self):
        return os.path.join(self.cache_dir, f"{self.raw_search_key}_urls.json")

    def get_url_checkpoint_file(self):
        return os.path.join(self.cache_dir, f"{self.raw_search_key}_url_checkpoint.json")

    def get_download_checkpoint_file(self):
        name = self.raw_search_key or "generic_download"
        return os.path.join(self.cache_dir, f"{name}_download_checkpoint.json")