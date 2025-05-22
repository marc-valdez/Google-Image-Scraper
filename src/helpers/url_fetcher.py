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
    def __init__(self, category_dir: str, class_name: str, worker_id: int):
        self.worker_id = worker_id
        
        self.driver_manager = WebDriverManager()
        self.driver = self.driver_manager.driver
        
        self.query = class_name
        self.target_images = cfg.NUM_IMAGES_PER_CLASS
        self.cache_file_path = cfg.get_url_cache_file(category_dir, class_name)
        
        params = {
            "as_st": "y",   # Advanced search type
            "tbm": "isch",  # Crucial for image search
            "sa": "X",      # Action code. X means a search was executed directly.
            "ved": "2ahUKEwie44_AnqLpAhUhBWMBHUFGD90Q_AUoAXoECBUQAw", # A tracking/analytics value.
            "biw": 1280,    # Browser inner width in pixels (e.g. viewport width).
            "bih": 720,     # Browser inner height in pixels (e.g. viewport height).
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
        params = {k: v for k, v in params.items() if v != ""} # Strip out empty values
        self.search_url = f"https://www.google.com/search?{urllib.parse.urlencode(params)}"

    def find_image_urls(self):
        logger.status(f"[Worker {self.worker_id}] Searching for '{self.query}' with URL: {self.search_url}")
        
        found_urls = []
        cache_data = load_json_data(self.cache_file_path) 
        
        if cache_data and cache_data.get('search_url_used') == self.search_url:
            found_urls = list(dict.fromkeys(cache_data.get('urls', [])))
            if len(found_urls) >= self.target_images:
                logger.success(f"[Worker {self.worker_id}] Loaded {self.target_images} cached image URLs for '{self.query}'.")
                return found_urls[:self.target_images]
            logger.info(f"[Worker {self.worker_id}] Found {len(found_urls)} cached URLs. Need {self.target_images - len(found_urls)} more.")

        if not self.driver:
            logger.error(f"[Worker {self.worker_id}] WebDriver not initialized.")
            return found_urls

        try:
            self.driver.get(self.search_url)
            WebDriverWait(self.driver, cfg.PAGE_LOAD_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "img"))
            )
        except TimeoutException:
            logger.error(f"[Worker {self.worker_id}] Timeout loading initial image search page. URL: {self.search_url}")
            return found_urls
        except WebDriverException as e:
            logger.error(f"[Worker {self.worker_id}] WebDriver error on initial page load: {e}. URL: {self.search_url}")
            return found_urls

        needed_urls = self.target_images - len(found_urls)
        if needed_urls <= 0:
             logger.info(f"[Worker {self.worker_id}] All required images already found.")
             return found_urls[:self.target_images]

        logger.start_progress(needed_urls, f"Finding images for '{self.query}'", self.worker_id)
        
        high_res_image_selectors = ["n3VNCb", "iPVvYb", "r48jcc", "pT0Scc", "H8Rx8c"]

        processed_thumbnails = 0
        consecutive_misses = 0
        
        while len(found_urls) < self.target_images and consecutive_misses < cfg.MAX_MISSED:
            current_thumbnail_idx = processed_thumbnails + 1 
            
            try:
                item_xpath_base = f'//*[@id="rso"]/div/div/div[1]/div/div/div[{current_thumbnail_idx}]'
                
                try:
                    item_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, item_xpath_base))
                    )
                except TimeoutException:
                    logger.warning(f"[Worker {self.worker_id}] Timeout waiting for item (thumbnail or other) at index {current_thumbnail_idx}. Misses: {consecutive_misses+1}")
                    consecutive_misses += 1
                    self.driver.execute_script(f"window.scrollBy(0, {random.randint(500, 800)});")
                    time.sleep(exponential_backoff(consecutive_misses, base=0.5, max_d=cfg.SCROLL_PAUSE_TIME))
                    continue

                is_related_block = False
                try:
                    if "BA0zte" in item_element.get_attribute("class").split():
                        is_related_block = True
                    else:
                        item_element.find_element(By.CLASS_NAME, "BA0zte")
                        is_related_block = True
                except NoSuchElementException:
                    is_related_block = False
                except Exception: 
                    is_related_block = False

                if is_related_block:
                    logger.info(f"[Worker {self.worker_id}] Identified 'Related searches' block at index {current_thumbnail_idx}. Skipping.")
                    processed_thumbnails += 1
                    self.driver.execute_script(f"window.scrollBy(0, {random.randint(50, 150)});") 
                    time.sleep(random.uniform(0.1, 0.3))
                    continue

                try:
                    img_thumbnail_element = item_element.find_element(By.XPATH, "./div[2]/h3/a/div/div/div/g-img")
                except NoSuchElementException:
                    logger.warning(f"[Worker {self.worker_id}] Item at index {current_thumbnail_idx} not 'Related searches' but no g-img found. Misses: {consecutive_misses+1}")
                    processed_thumbnails += 1 
                    consecutive_misses += 1
                    self.driver.execute_script(f"window.scrollBy(0, {random.randint(200, 400)});")
                    time.sleep(random.uniform(0.2, 0.4))
                    continue
                
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", img_thumbnail_element)
                try:
                    # Use relative XPath from item_element to ensure we click the correct thumbnail
                    clickable_thumbnail_xpath = "./div[2]/h3/a/div/div/div/g-img"
                    WebDriverWait(item_element, 2).until(EC.element_to_be_clickable((By.XPATH, clickable_thumbnail_xpath)))
                    img_thumbnail_element.click()
                except WebDriverException:
                    self.driver.execute_script("arguments[0].click();", img_thumbnail_element)
                
                time.sleep(random.uniform(1.0, 2.0))

                image_found_this_iteration = False
                for cls in high_res_image_selectors:
                    for el in self.driver.find_elements(By.CLASS_NAME, cls):
                        src = el.get_attribute("src")
                        if src and "http" in src and "encrypted" not in src and src not in found_urls:
                            found_urls.append(src)
                            logger.info(f"[Worker {self.worker_id}] Image {len(found_urls)}/{self.target_images}: {logger.truncate_url(src)}")
                            logger.update_progress(worker_id=self.worker_id)
                            
                            save_json_data(self.cache_file_path, {
                                'search_url_used': self.search_url, 
                                'search_key': self.query, 
                                'number_of_images_requested': self.target_images,
                                'urls_found_count': len(found_urls),
                                'urls': found_urls
                            })
                            image_found_this_iteration = True
                            if len(found_urls) >= self.target_images: break
                    if image_found_this_iteration and len(found_urls) >= self.target_images: break
                
                if image_found_this_iteration:
                    consecutive_misses = 0
                processed_thumbnails += 1

                if processed_thumbnails % 5 == 0:
                    self.driver.execute_script(f"window.scrollBy(0, {random.randint(400, 600)});")
                    time.sleep(random.uniform(0.3, 0.7))
                
            except TimeoutException: 
                logger.warning(f"[Worker {self.worker_id}] Outer Timeout in main loop for thumbnail {current_thumbnail_idx}. Misses: {consecutive_misses+1}")
                consecutive_misses += 1
                self.driver.execute_script(f"window.scrollBy(0, {random.randint(1000, 1500)});")
                time.sleep(exponential_backoff(consecutive_misses, base=0.5, max_d=cfg.SCROLL_PAUSE_TIME * 2))
            except (NoSuchElementException, StaleElementReferenceException) as e_thumb:
                logger.warning(f"[Worker {self.worker_id}] Error processing thumbnail {current_thumbnail_idx}: {type(e_thumb).__name__}. Misses: {consecutive_misses+1}")
                consecutive_misses += 1
                self.driver.execute_script(f"window.scrollBy(0, {random.randint(1000, 1500)});")
                time.sleep(exponential_backoff(consecutive_misses, base=0.5, max_d=cfg.SCROLL_PAUSE_TIME * 2))
            except WebDriverException as e_wd:
                logger.error(f"[Worker {self.worker_id}] WebDriverException: {e_wd}. Misses: {consecutive_misses+1}")
                consecutive_misses += 1
                time.sleep(exponential_backoff(consecutive_misses, base=1, max_d=cfg.MAX_RETRY_DELAY / 2))
            except Exception as e_main:
                logger.error(f"[Worker {self.worker_id}] Unexpected error in main loop: {e_main}. Misses: {consecutive_misses+1}")
                consecutive_misses += 1
                time.sleep(exponential_backoff(consecutive_misses))

        logger.complete_progress(worker_id=self.worker_id)
        if len(found_urls) >= self.target_images:
            logger.success(f"[Worker {self.worker_id}] Successfully found {self.target_images} image URLs for '{self.query}'.")
        else:
            logger.warning(f"[Worker {self.worker_id}] Found {len(found_urls)}/{self.target_images} URLs for '{self.query}' after {cfg.MAX_MISSED} misses or exhausting content.")
        
        return found_urls[:self.target_images]

    def close(self):
        if hasattr(self, 'driver_manager') and self.driver_manager:
            self.driver_manager.close_driver()
            logger.info(f"[Worker {self.worker_id}] WebDriver closed for UrlFetcher of '{self.query}'.")
