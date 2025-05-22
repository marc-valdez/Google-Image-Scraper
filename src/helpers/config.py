import os

class ScraperConfig:
    """
    Configuration for the Google Image Scraper with sensible defaults
    and automated path generation (pure, no side effects).
    """

    def __init__(self,
                 image_path,
                 search_key,
                 number_of_images=10,
                 headless=True,
                 max_missed=25,
                 webdriver_path=None,
                 chrome_binary_path=None,
                 advanced_suffix='',
                 keep_filenames=False,
                 request_interval=1.0,
                 max_retries=5,
                 retry_backoff=0.5,
                 max_retry_delay=60,
                 connection_timeout=15,
                 page_load_timeout=30,
                 browser_refresh_interval=50,
                 scroll_pause_time=0.5,
                 load_button_wait=3.0):

        self.image_path = image_path
        self.raw_search_key = search_key
        self.number_of_images = number_of_images
        self.headless = headless
        self.max_missed = max_missed
        self.advanced_suffix = advanced_suffix
        self.keep_filenames = keep_filenames

        self.request_interval = request_interval
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.max_retry_delay = max_retry_delay
        self.connection_timeout = connection_timeout

        self.page_load_timeout = page_load_timeout
        self.browser_refresh_interval = browser_refresh_interval
        self.scroll_pause_time = scroll_pause_time
        self.load_button_wait = load_button_wait

        self.webdriver_path = webdriver_path
        self.chrome_binary_path = chrome_binary_path

    @classmethod
    def create_instance(cls, category_dir, search_term, **kwargs):
        clean_base = search_term.replace(" ", "")
        image_path = os.path.join(os.getcwd(), "output", category_dir, clean_base)
        return cls(image_path=image_path, search_key=search_term, **kwargs)

    @property
    def clean_base_name(self):
        return self.raw_search_key.replace(" ", "")

    @property
    def search_key_for_query(self):
        return f"{self.raw_search_key} {self.advanced_suffix}".strip()

    @property
    def cache_dir(self):
        return os.path.join(self.image_path, ".cache")

    def get_url_cache_file(self):
        return os.path.join(self.cache_dir, f"{self.clean_base_name}_urls.json")

    def get_url_checkpoint_file(self):
        return os.path.join(self.cache_dir, f"{self.clean_base_name}_url_checkpoint.json")

    def get_image_metadata_file(self):
        return os.path.join(self.cache_dir, f"{self.clean_base_name or 'generic_metadata'}_metadata.json")
