from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, StaleElementReferenceException,
    TimeoutException, WebDriverException
)
from src.environment.webdriver import WebDriverManager
from src.logging.logger import logger
from src.utils.cache_utils import load_json_data, save_json_data
import config as cfg
import time
import random
import urllib.parse

def exponential_backoff(attempt, base=1, max_d=None):
    max_delay = max_d if max_d is not None else cfg.MAX_RETRY_DELAY
    return min(base * (2 ** attempt), max_delay) + random.uniform(0, 0.1)

class UrlFetcher:
    def __init__(self, category_dir: str, class_name: str, worker_id: int, driver_instance=None):
        self.worker_id = worker_id
        
        self.driver_manager = WebDriverManager(existing_driver=driver_instance)
        self.driver = self.driver_manager.driver
        
        self.query = class_name
        self.images_requested = cfg.NUM_IMAGES_PER_CLASS
        self.cache_file_path = cfg.get_url_cache_file(category_dir, class_name)
        
        self.current_xpath_index = 1 
        self.consecutive_misses = 0
        self.consecutive_high_res_failures = 0
        
        params = {
            "as_st": "y",   # Advanced search type
            "tbm": "isch",  # Crucial for image search
            "sa": "X",      # Action code. X means a search was executed directly.
            "as_q": self.query,
            "as_epq": cfg.SEARCH_QUERY_EXACT_PHRASE,
            "as_oq": cfg.SEARCH_QUERY_ANY_OF_THESE_WORDS,
            "as_eq": cfg.SEARCH_QUERY_EXCLUDE_THESE_WORDS,
            "imgsz": cfg.SEARCH_QUERY_IMAGE_SIZE,
            "imgar": cfg.SEARCH_QUERY_ASPECT_RATIO,
            "imgc": cfg.SEARCH_QUERY_IMAGE_COLOR_TYPE,
            "imgcolor": cfg.SEARCH_QUERY_SPECIFIC_COLOR,
            "imgtype": cfg.SEARCH_QUERY_IMAGE_TYPE,
            "cr": cfg.SEARCH_QUERY_COUNTRY_RESTRICTION,
            "as_sitesearch": cfg.SEARCH_QUERY_SITE_SEARCH,
            "as_filetype": cfg.SEARCH_QUERY_FILE_TYPE,
        }
        params = {k: v for k, v in params.items() if v != ""}
        self.search_url = f"https://www.google.com/search?{urllib.parse.urlencode(params)}"

    def _handle_item_error(self, message: str, scroll_min=200, scroll_max=400, backoff_base=0.5, backoff_max_d_mult=1):
        """Handles logging, miss counting, scrolling, and delay for item processing errors."""
        logger.warning(message)
        self.consecutive_misses += 1
        self.driver.execute_script(f"window.scrollBy(0, {random.randint(scroll_min, scroll_max)});")
        time.sleep(exponential_backoff(self.consecutive_misses, base=backoff_base, max_d=cfg.SCROLL_PAUSE_TIME * backoff_max_d_mult))

    def find_image_urls(self):
        logger.status(f"[Worker {self.worker_id}] Searching for '{self.query}' with URL: {self.search_url}")
        
        found_urls = []
        cache_data = load_json_data(self.cache_file_path)
        
        if cache_data and cache_data.get('search_url_used') == self.search_url:
            found_urls = list(dict.fromkeys(cache_data.get('urls', [])))
            last_processed_index = cache_data.get('last_processed_xpath_index', 0)
            self.current_xpath_index = last_processed_index + 1
            if self.current_xpath_index > 1:
                logger.info(f"[Worker {self.worker_id}] Resuming. Last processed XPath index was {last_processed_index}. Next to try: {self.current_xpath_index}.")
        else:
            self.current_xpath_index = 1

        if len(found_urls) >= self.images_requested:
            logger.success(f"[Worker {self.worker_id}] Loaded {self.images_requested} cached image URLs for '{self.query}'.")
            return found_urls[:self.images_requested]

        needed_count = self.images_requested - len(found_urls)
        logger.info(f"[Worker {self.worker_id}] Need {needed_count} more image URLs for '{self.query}'. Starting at XPath index {self.current_xpath_index}.")

        if not self.driver:
            logger.error(f"[Worker {self.worker_id}] WebDriver not initialized.")
            return found_urls 

        try:
            self.driver.get(self.search_url)
            WebDriverWait(self.driver, cfg.PAGE_LOAD_TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "img")))
        except (TimeoutException, WebDriverException) as e:
            logger.error(f"[Worker {self.worker_id}] Error on initial page load for {self.search_url}: {e}")
            return found_urls

        logger.start_progress(self.images_requested, f"Finding images for '{self.query}'", self.worker_id)
        if len(found_urls) > 0:
            logger.update_progress(advance=len(found_urls), worker_id=self.worker_id)
        
        self.consecutive_misses = 0
        self.consecutive_high_res_failures = 0
        high_res_image_selectors = ["n3VNCb", "iPVvYb", "r48jcc", "pT0Scc", "H8Rx8c"]
        
        while len(found_urls) < self.images_requested and self.consecutive_misses < cfg.MAX_MISSED:
            item_xpath = f'//*[@id="rso"]/div/div/div[1]/div/div/div[{self.current_xpath_index}]'
            try:
                item_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, item_xpath))
                )

                # Skip if this is a related searches block
                item_classes = item_element.get_attribute("class") or ""
                if "BA0zte" in item_classes.split():
                    logger.info(f"[Worker {self.worker_id}] Skipping related searches block at index {self.current_xpath_index}.")
                    self.driver.execute_script(f"window.scrollBy(0, {random.randint(50, 150)});") 
                    time.sleep(random.uniform(0.1, 0.3))
                    self.current_xpath_index += 1
                    continue

                # Skip if this item does not contain a g-img
                try:
                    img_thumbnail_element = item_element.find_element(By.XPATH, ".//g-img")
                except NoSuchElementException:
                    raise NoSuchElementException("No g-img found in item")

                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", img_thumbnail_element)

                # Try clicking the thumbnail
                try:
                    WebDriverWait(item_element, 2).until(
                        EC.element_to_be_clickable((By.XPATH, ".//g-img"))
                    ).click()
                except WebDriverException:
                    self.driver.execute_script("arguments[0].click();", img_thumbnail_element)

                time.sleep(random.uniform(1.0, 3.0))  # Wait for high-res image panel

                image_found_this_iteration = False
                for cls in high_res_image_selectors:
                    for el in self.driver.find_elements(By.CLASS_NAME, cls):
                        src = el.get_attribute("src")
                        if src and "http" in src and "encrypted" not in src and src not in found_urls:
                            found_urls.append(src)
                            logger.info(
                                f"[Worker {self.worker_id}] Image {len(found_urls)}/{self.images_requested}: {logger.truncate_url(src)}"
                            )
                            logger.update_progress(worker_id=self.worker_id)

                            self.consecutive_misses = 0
                            self.consecutive_high_res_failures = 0
                            image_found_this_iteration = True

                            save_json_data(self.cache_file_path, {
                                'search_url_used': self.search_url,
                                'search_key': self.query,
                                'last_processed_xpath_index': self.current_xpath_index,
                                'number_of_images_requested': self.images_requested,
                                'number_of_urls_found': len(found_urls),
                                'request_efficiency': len(found_urls) / self.images_requested,
                                'urls': found_urls
                            })

                            if len(found_urls) >= self.images_requested:
                                break
                    if image_found_this_iteration:
                        break

                if not image_found_this_iteration:
                    self.consecutive_high_res_failures += 1
                    logger.warning(
                        f"[Worker {self.worker_id}] No valid high-res URL from item at index {self.current_xpath_index}. "
                        f"Consecutive high-res failures: {self.consecutive_high_res_failures}/{cfg.MAX_CONSECUTIVE_HIGH_RES_FAILURES}."
                    )
                    if self.consecutive_high_res_failures >= cfg.MAX_CONSECUTIVE_HIGH_RES_FAILURES:
                        logger.warning(
                            f"[Worker {self.worker_id}] Reached max ({cfg.MAX_CONSECUTIVE_HIGH_RES_FAILURES}) "
                            f"consecutive high-res URL failures. Stopping URL search for '{self.query}'."
                        )
                        break
                    else:
                        self.driver.execute_script(f"window.scrollBy(0, {random.randint(100, 200)});")
                        time.sleep(exponential_backoff(self.consecutive_high_res_failures, base=0.2, max_d=cfg.SCROLL_PAUSE_TIME * 0.5))

                if self.current_xpath_index % 5 == 0:
                    self.driver.execute_script(f"window.scrollBy(0, {random.randint(400, 600)});")
                    time.sleep(random.uniform(0.3, 0.7))

            except (TimeoutException, NoSuchElementException, StaleElementReferenceException, WebDriverException) as e:
                self._handle_item_error(
                    f"[Worker {self.worker_id}] {type(e).__name__} at index {self.current_xpath_index}: {str(e)}. Misses: {self.consecutive_misses + 1}",
                    scroll_min=300, scroll_max=800, backoff_base=0.5, backoff_max_d_mult=1.5
                )
            except Exception as e_main:
                self._handle_item_error(
                    f"[Worker {self.worker_id}] Unexpected error at index {self.current_xpath_index}: {str(e_main)}. Misses: {self.consecutive_misses + 1}",
                    scroll_min=300, scroll_max=600, backoff_base=0.8, backoff_max_d_mult=1.5
                )
            finally:
                self.current_xpath_index += 1

        logger.complete_progress(worker_id=self.worker_id)
        if len(found_urls) >= self.images_requested:
            logger.success(f"[Worker {self.worker_id}] Successfully found {self.images_requested} image URLs for '{self.query}'.")
        else:
            logger.warning(f"[Worker {self.worker_id}] Found {len(found_urls)}/{self.images_requested} URLs for '{self.query}' after {self.consecutive_misses} general misses or {self.consecutive_high_res_failures} high-res misses, or exhausting content.")
        
        return found_urls[:self.images_requested]

    def close(self):
        if hasattr(self, 'driver_manager') and self.driver_manager:
            self.driver_manager.close_driver()
            logger.info(f"[Worker {self.worker_id}] UrlFetcher for '{self.query}' signaled WebDriverManager to close if managed.")
