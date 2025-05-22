import os
from src.environment.chrome_finder import ChromeFinder
from src.logging.logger import logger

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
            logger.warning(f"Webdriver directory not found, using default: {default_path}")

        # Ensure default directory exists
        if not os.path.exists(default_dir):
            os.makedirs(default_dir, exist_ok=True)
            logger.info(f"Created webdriver directory: {default_dir}")

        return default_path

    def __init__(self,
                 image_path,           # Required: Output path for images
                 search_key,           # Required: Search term
                 number_of_images=10,  # Optional parameters with defaults
                 headless=True,
                 max_missed=25,        # Increased for better resilience
                 webdriver_path=None,
                 chrome_binary_path=None,
                 advanced_suffix='',
                 keep_filenames=False,
                 # Network and rate limiting parameters
                 request_interval=1.0,  # Minimum seconds between requests
                 max_retries=5,        # Maximum number of retries per request
                 retry_backoff=0.5,    # Base delay for exponential backoff
                 max_retry_delay=60,   # Maximum retry delay in seconds
                 connection_timeout=15, # Connection timeout in seconds
                 # Browser parameters
                 page_load_timeout=30,  # Page load timeout in seconds
                 browser_refresh_interval=50,  # Refresh browser every N operations
                 scroll_pause_time=0.5, # Pause between scroll operations
                 load_button_wait=3.0): # Wait after clicking load more
        """Initialize scraper configuration with sensible defaults for long-running operations."""
        
        # Required parameters
        self.image_path = image_path
        self.raw_search_key = search_key
        
        # Create output directory if needed
        if not os.path.exists(self.image_path):
            os.makedirs(self.image_path, exist_ok=True)
            logger.info(f"Created directory: {self.image_path}")
            
        # Optional parameters with defaults
        self.number_of_images = number_of_images
        self.headless = headless
        self.max_missed = max_missed
        self.advanced_suffix = advanced_suffix
        self.keep_filenames = keep_filenames
        
        # Network and rate limiting settings
        self.request_interval = request_interval
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.max_retry_delay = max_retry_delay
        self.connection_timeout = connection_timeout
        
        # Browser behavior settings
        self.page_load_timeout = page_load_timeout
        self.browser_refresh_interval = browser_refresh_interval
        self.scroll_pause_time = scroll_pause_time
        self.load_button_wait = load_button_wait
        
        # Webdriver setup
        self.webdriver_path = self._setup_webdriver_path(webdriver_path)
        
        # Chrome binary path with auto-detection fallback
        if chrome_binary_path:
            self.chrome_binary_path = chrome_binary_path
        else:
            finder = ChromeFinder()
            self.chrome_binary_path = finder.get_chrome_path()
            if self.chrome_binary_path:
                logger.info(f"Auto-detected Chrome at: {self.chrome_binary_path}")
            else:
                logger.warning("Could not detect Chrome path - ensure Chrome is installed")
                self.chrome_binary_path = None

    @classmethod
    def create_instance(cls, category_dir, search_term, **kwargs):
        """Factory method to create a config instance for a category.
        
        Creates folder structure: output/category/CleanBaseName/
        Example: output/Go/ArrozCaldo/ArrozCaldo_0.jpg
        The 'search_term' (e.g., "Arroz Caldo") is used to generate 'CleanBaseName' (e.g., "ArrozCaldo").
        The original 'search_term' is stored as 'raw_search_key' for use in queries.
        """
        # Generate the clean base name for directory and file naming (e.g., "ArrozCaldo" from "Arroz Caldo")
        # by simply removing spaces.
        clean_base = search_term.replace(" ", "")
        
        # Create path: output/category/CleanBaseName/
        image_path = os.path.join(os.getcwd(), "output", category_dir, clean_base)
        
        # The 'search_key' parameter for the constructor will be the original, potentially complex search term.
        # This is stored in self.raw_search_key.
        return cls(image_path=image_path, search_key=search_term, **kwargs)

    @property
    def clean_base_name(self):
        """
        Provides the 'class name' style base for filenames and directories,
        e.g., "ArrozCaldo" from a raw_search_key of "Arroz Caldo".
        This is derived from the raw_search_key (which is the original search_term).
        """
        return self.raw_search_key.replace(" ", "")

    @property
    def search_key_for_query(self):
        """Get the search key with any advanced suffix applied."""
        return f"{self.raw_search_key} {self.advanced_suffix}".strip()

    # No longer need sanitized_query_key as the final cache file will use clean_base_name
    # and store the original search_key_for_query internally.
    # The download_checkpoint_file will also use clean_base_name.

    @property
    def cache_dir(self):
        """Get the cache directory path for this scraper instance.
        e.g., output/Category/ArrozCaldo/.cache/
        """
        # Ensure cache directory exists
        cache_path = os.path.join(self.image_path, ".cache")
        if not os.path.exists(cache_path):
            os.makedirs(cache_path, exist_ok=True)
            logger.info(f"Created cache directory: {cache_path}")
        return cache_path

    def get_url_cache_file(self):
        """Get the path to the URL cache file for this search key.
        e.g., output/Category/ArrozCaldo/.cache/ArrozCaldo_urls.json
        """
        return os.path.join(self.cache_dir, f"{self.clean_base_name}_urls.json")

    def get_url_checkpoint_file(self):
        """Get the path to the URL checkpoint file for this search key.
        e.g., output/Category/ArrozCaldo/.cache/ArrozCaldo_url_checkpoint.json
        """
        return os.path.join(self.cache_dir, f"{self.clean_base_name}_url_checkpoint.json")

    def get_image_metadata_file(self):
        """Get the path to the main image metadata file for this class.
        e.g., output/Category/ArrozCaldo/.cache/ArrozCaldo_metadata.json
        """
        name = self.clean_base_name or "generic_metadata"
        return os.path.join(self.cache_dir, f"{name}_metadata.json")
