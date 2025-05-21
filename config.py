import os
from chrome_finder import ChromeFinder

class ScraperConfig:
    """Configuration for the Google Image Scraper.
    
    Provides a simple interface for configuring the scraper with reasonable defaults.
    """
    
    def _setup_webdriver_path(self, webdriver_path=None):
        """Sets up and validates the webdriver path."""
        default_dir = os.path.join(os.getcwd(), "webdriver")
        default_path = os.path.join(default_dir, "chromedriver.exe")

        # Use provided path if it exists and is valid
        if webdriver_path:
            driver_dir = os.path.dirname(webdriver_path)
            if os.path.isdir(driver_dir):
                return webdriver_path
            print(f"[CONFIG_WARN] Webdriver directory '{driver_dir}' not found. Using default: {default_path}")

        # Ensure default directory exists
        if not os.path.exists(default_dir):
            os.makedirs(default_dir, exist_ok=True)
            print(f"[CONFIG_INFO] Created webdriver directory: {default_dir}")

        return default_path

    def __init__(self, 
                 image_path,           # Required: Output path for images
                 search_key,           # Required: Search term
                 number_of_images=10,  # Optional parameters with defaults
                 headless=True,
                 max_missed=10,
                 webdriver_path=None,
                 chrome_binary_path=None,
                 advanced_suffix='',
                 keep_filenames=False):
        """Initialize scraper configuration with sensible defaults."""
        
        # Required parameters
        self.image_path = image_path
        self.raw_search_key = search_key
        
        # Create output directory if needed
        if not os.path.exists(self.image_path):
            os.makedirs(self.image_path, exist_ok=True)
            print(f"[CONFIG_INFO] Created directory: {self.image_path}")
            
        # Optional parameters with defaults
        self.number_of_images = number_of_images
        self.headless = headless
        self.max_missed = max_missed
        self.advanced_suffix = advanced_suffix
        self.keep_filenames = keep_filenames
        
        # Webdriver setup
        self.webdriver_path = self._setup_webdriver_path(webdriver_path)
        
        # Chrome binary path with auto-detection fallback
        if chrome_binary_path:
            self.chrome_binary_path = chrome_binary_path
        else:
            finder = ChromeFinder()
            self.chrome_binary_path = finder.get_chrome_path()
            if self.chrome_binary_path:
                print(f"[CONFIG_INFO] Auto-detected Chrome path: {self.chrome_binary_path}")
            else:
                print("[CONFIG_WARN] Could not auto-detect Chrome path. WebDriverManager may fail if Chrome is not in PATH.")
                self.chrome_binary_path = None

    @classmethod
    def create_instance(cls, category_dir, search_term, **kwargs):
        """Factory method to create a config instance for a category.
        
        Creates folder structure: output/category/search_term/
        Example: output/Go/Sinangag/Sinangag_0.jpg
        """
        # Create path: output/category/search_term/
        image_path = os.path.join(os.getcwd(), "output", category_dir, search_term)
        return cls(image_path=image_path, search_key=search_term, **kwargs)
    
    @property
    def search_key_for_query(self):
        """Get the search key with any advanced suffix applied."""
        return f"{self.raw_search_key} {self.advanced_suffix}".strip()

    @property
    def cache_dir(self):
        """Get the cache directory path for this scraper instance."""
        return os.path.join(self.image_path, ".cache")

    def get_url_cache_file(self):
        """Get the path to the URL cache file for this search key."""
        return os.path.join(self.cache_dir, f"{self.raw_search_key}_urls.json")

    def get_url_checkpoint_file(self):
        """Get the path to the URL checkpoint file for this search key."""
        return os.path.join(self.cache_dir, f"{self.raw_search_key}_url_checkpoint.json")

    def get_download_checkpoint_file(self):
        """Get the path to the download checkpoint file for this search key."""
        name = self.raw_search_key or "generic_download"
        return os.path.join(self.cache_dir, f"{name}_download_checkpoint.json")