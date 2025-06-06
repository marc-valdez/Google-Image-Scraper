import os
import time
import random
import urllib.parse
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
from src.helpers.selenium_helpers import (
    click_thumbnail_element, extract_high_res_urls, perform_periodic_scroll,
    refresh_page_if_needed, attempt_recovery_scroll, is_related_searches_block,
    get_progressive_timeout
)
from src.helpers.duplication_checker import DuplicationChecker
import config as cfg
def exponential_backoff(attempt, base=1, max_d=None):
    max_delay = max_d if max_d is not None else cfg.MAX_RETRY_DELAY
    return min(base * (2 ** attempt), max_delay) + random.uniform(0, 0.1)

class UrlFetcher:
    def __init__(self, class_name: str, nutritional_category: str, worker_id: int, driver_instance=None):
        self.worker_id = worker_id
        self.class_name = class_name
        self.nutritional_category = nutritional_category
        
        self.driver_manager = WebDriverManager(existing_driver=driver_instance)
        self.driver = self.driver_manager.driver
        
        self.query = class_name
        self.images_requested = cfg.NUM_IMAGES_PER_CLASS
        self.cache_file_path = cfg.get_image_metadata_file(class_name)
        
        self.current_xpath_index = 1
        self.consecutive_misses = 0
        self.consecutive_high_res_failures = 0
        
        self.duplication_checker = DuplicationChecker(class_name, nutritional_category, worker_id)
        
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
        
        # Scroll to bottom to trigger more content loading
        logger.info(f"[Worker {self.worker_id}] Scrolling to bottom to load more images...")
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(2.0, 3.0))  # Wait for new content to load
        
        # Additional scroll to ensure we trigger infinite scroll
        self.driver.execute_script(f"window.scrollBy(0, {random.randint(scroll_min, scroll_max)});")
        time.sleep(exponential_backoff(self.consecutive_misses, base=backoff_base, max_d=cfg.SCROLL_PAUSE_TIME * backoff_max_d_mult))

    def _generate_url_key(self, index: int) -> str:
        return f"{index:03d}"


    def _get_next_available_key(self, images_dict: dict) -> str:
        if not images_dict:
            return self._generate_url_key(1)
        
        existing_indices = []
        for key in images_dict.keys():
            try:
                index = int(key)
                existing_indices.append(index)
            except ValueError:
                continue
        
        if not existing_indices:
            return self._generate_url_key(1)
        
        # Sort indices to find gaps
        existing_indices.sort()
        
        # Look for the first gap in the sequence
        for i in range(len(existing_indices)):
            expected_index = i + 1
            if existing_indices[i] != expected_index:
                # Found a gap, return the missing index
                return self._generate_url_key(expected_index)
        
        # No gaps found, append after the last index
        next_index = max(existing_indices) + 1
        return self._generate_url_key(next_index)

    def _create_fetch_metadata(self, url: str, xpath_index: int) -> dict:
        parsed = urllib.parse.urlparse(url)
        original_filename = os.path.basename(parsed.path) or "unknown"
        domain = parsed.netloc
        
        return {
            "fetch_data": {
                "link": url,
                "domain": domain,
                "original_filename": original_filename,
                "xpath_index": xpath_index
            }
        }

    def find_image_urls(self):
        logger.status(f"[Worker {self.worker_id}] Searching for '{self.query}' with URL: {self.search_url}")
        
        cache_data = load_json_data(self.cache_file_path)
        
        images_dict = cache_data.get('images', {}) if cache_data else {}
        found_urls = [img['fetch_data']['link'] for img in images_dict.values() if img.get('fetch_data', {}).get('link')]
        
        # Check if current search URL is in the array of used URLs
        search_urls_used = cache_data.get('search_urls_used', []) if cache_data else []
        
        if cache_data and self.search_url in search_urls_used:
            last_processed_index = cache_data.get('last_xpath_index', 0)
            self.current_xpath_index = last_processed_index + 1
            if self.current_xpath_index > 1:
                logger.info(f"[Worker {self.worker_id}] Resuming. Last processed XPath index was {last_processed_index}. Next to try: {self.current_xpath_index}.")
        else:
            self.current_xpath_index = 1
            # Add current search URL to the array if it's not already there
            if self.search_url not in search_urls_used:
                search_urls_used.append(self.search_url)
                logger.info(f"[Worker {self.worker_id}] Adding new search URL to cache. Will append to existing {len(found_urls)} URLs. Total URLs used: {len(search_urls_used)}")

        if len(found_urls) >= self.images_requested:
            logger.success(f"[Worker {self.worker_id}] Loaded {self.images_requested} cached image URLs for '{self.query}'.")
            return self._get_ordered_urls(images_dict, self.images_requested)

        needed_count = self.images_requested - len(found_urls)
        logger.info(f"[Worker {self.worker_id}] Need {needed_count} more image URLs for '{self.query}'. Starting at XPath index {self.current_xpath_index}.")

        if not self.driver:
            logger.error(f"[Worker {self.worker_id}] WebDriver not initialized.")
            return self._get_ordered_urls(images_dict, self.images_requested)

        try:
            self.driver.get(self.search_url)
            WebDriverWait(self.driver, cfg.PAGE_LOAD_TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "img")))
        except (TimeoutException, WebDriverException) as e:
            logger.error(f"[Worker {self.worker_id}] Error on initial page load for {self.search_url}: {e}")
            return self._get_ordered_urls(images_dict, self.images_requested)

        logger.start_progress(self.images_requested, f"Finding images for '{self.query}'", self.worker_id)
        if len(found_urls) > 0:
            logger.update_progress(advance=len(found_urls), worker_id=self.worker_id)
        
        self.consecutive_misses = 0
        self.consecutive_high_res_failures = 0
        high_res_image_selectors = ["n3VNCb", "iPVvYb", "r48jcc", "pT0Scc", "H8Rx8c"]
        
        while len(found_urls) < self.images_requested and self.consecutive_misses < cfg.MAX_MISSED and self.current_xpath_index < 1000:
            item_xpath = f'//*[@id="rso"]/div/div/div[1]/div/div/div[{self.current_xpath_index}]'
            try:
                timeout = get_progressive_timeout(self.current_xpath_index)
                item_element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, item_xpath))
                )

                if is_related_searches_block(item_element):
                    logger.info(f"[Worker {self.worker_id}] Skipping related searches block at index {self.current_xpath_index}.")
                    self.driver.execute_script(f"window.scrollBy(0, {random.randint(50, 150)});")
                    time.sleep(random.uniform(0.1, 0.3))
                    self.current_xpath_index += 1
                    continue

                try:
                    img_thumbnail_element = item_element.find_element(By.XPATH, ".//g-img")
                except NoSuchElementException:
                    raise NoSuchElementException("No g-img found in item")

                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", img_thumbnail_element)
                click_thumbnail_element(self.driver, item_xpath, item_element, img_thumbnail_element, self.worker_id)
                time.sleep(random.uniform(1.0, 3.0))

                image_found_this_iteration = False
                url_already_exists = False
                
                high_res_urls = extract_high_res_urls(self.driver, high_res_image_selectors)
                
                for src in high_res_urls:
                    duplicate_status = self.duplication_checker.check_url_duplicates(src, found_urls)
                    
                    if duplicate_status == "unique":
                        url_key = self._get_next_available_key(images_dict)
                        images_dict[url_key] = self._create_fetch_metadata(src, self.current_xpath_index)
                        found_urls = [img['fetch_data']['link'] for img in images_dict.values() if img.get('fetch_data', {}).get('link')]
                        
                        self.duplication_checker.add_unique_url(src)
                        
                        logger.info(
                            f"[Worker {self.worker_id}] Image {len(found_urls)}/{self.images_requested} ({url_key}): {logger.truncate_url(src)}"
                        )
                        logger.update_progress(worker_id=self.worker_id)

                        self.consecutive_misses = 0
                        self.consecutive_high_res_failures = 0
                        image_found_this_iteration = True

                        save_json_data(self.cache_file_path, {
                            'search_urls_used': search_urls_used,
                            'search_key': self.query,
                            'nutritional_category': self.nutritional_category,
                            'last_xpath_index': self.current_xpath_index,
                            'number_of_images_requested': self.images_requested,
                            'number_of_urls_found': len(found_urls),
                            'images': images_dict
                        })

                        if len(found_urls) >= self.images_requested:
                            break
                    else:
                        url_already_exists = True
                        image_found_this_iteration = True
                        break
                    
                    if image_found_this_iteration:
                        break

                if not image_found_this_iteration:
                    # Only count as failure if it wasn't a duplicate URL
                    if not url_already_exists:
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

                perform_periodic_scroll(self.driver, self.current_xpath_index)
                refresh_page_if_needed(self.driver, self.current_xpath_index, self.worker_id)

            except (TimeoutException, NoSuchElementException, StaleElementReferenceException, WebDriverException) as e:
                error_type = type(e).__name__
                error_msg = f"[Worker {self.worker_id}] {error_type} at index {self.current_xpath_index}. Misses: {self.consecutive_misses + 1}"
                
                if isinstance(e, TimeoutException) and self.current_xpath_index > 100:
                    logger.warning(f"{error_msg} - Attempting recovery...")
                    penalty = attempt_recovery_scroll(self.driver, self.current_xpath_index, self.worker_id)
                    self.consecutive_misses += penalty
                
                self._handle_item_error(error_msg, scroll_min=300, scroll_max=800, backoff_base=0.5, backoff_max_d_mult=1.5)
            except Exception as e_main:
                self._handle_item_error(
                    f"[Worker {self.worker_id}] Unexpected error at index {self.current_xpath_index}. Misses: {self.consecutive_misses + 1}",
                    scroll_min=300, scroll_max=600, backoff_base=0.8, backoff_max_d_mult=1.5
                )
            finally:
                self.current_xpath_index += 1

        logger.complete_progress(worker_id=self.worker_id)
        
        # Reset last_processed_xpath_index to 1 when process completes normally
        # This ensures values > 1 only indicate an abrupt exit occurred
        final_cache_data = {
            'search_urls_used': search_urls_used,
            'search_key': self.query,
            'nutritional_category': self.nutritional_category,
            'last_xpath_index': 1,
            'number_of_images_requested': self.images_requested,
            'number_of_urls_found': len(found_urls),
            'images': images_dict
        }
        save_json_data(self.cache_file_path, final_cache_data)
        
        if len(found_urls) >= self.images_requested:
            logger.success(f"[Worker {self.worker_id}] Successfully found {self.images_requested} image URLs for '{self.query}'.")
        else:
            stop_reason = ""
            if self.consecutive_misses >= cfg.MAX_MISSED:
                stop_reason = f"reached max misses ({cfg.MAX_MISSED})"
            elif self.consecutive_high_res_failures >= cfg.MAX_CONSECUTIVE_HIGH_RES_FAILURES:
                stop_reason = f"reached max high-res failures ({cfg.MAX_CONSECUTIVE_HIGH_RES_FAILURES})"
            elif self.current_xpath_index >= 1000:
                stop_reason = "reached maximum index limit (1000)"
            else:
                stop_reason = "unknown reason"
            
            logger.warning(f"[Worker {self.worker_id}] Found {len(found_urls)}/{self.images_requested} URLs for '{self.query}'. Stopped at index {self.current_xpath_index} - {stop_reason}.")
        
        return self._get_ordered_urls(images_dict, self.images_requested)

    def _get_ordered_urls(self, images_dict: dict, limit: int) -> list:
        if not images_dict:
            return []
        
        # Sort keys to maintain order: 001, 002, etc.
        sorted_keys = sorted(images_dict.keys(), key=lambda k: int(k) if k.isdigit() else 0)
        return [images_dict[key]['fetch_data']['link'] for key in sorted_keys[:limit] if images_dict[key].get('fetch_data', {}).get('link')]

    def close(self):
        if hasattr(self, 'driver_manager') and self.driver_manager:
            self.driver_manager.close_driver()
            logger.info(f"[Worker {self.worker_id}] UrlFetcher for '{self.query}' signaled WebDriverManager to close if managed.")
