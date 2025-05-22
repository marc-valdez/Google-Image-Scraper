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
    def __init__(self, category_dir: str, search_term: str, worker_id: int):
        self.worker_id = worker_id
        
        self.driver_manager = WebDriverManager()
        self.driver = self.driver_manager.driver
        
        self.search_key_query = cfg.get_search_key_for_query(search_term) 
        self.target_images = cfg.NUM_IMAGES_PER_CLASS
        self.cache_file_path = cfg.get_url_cache_file(category_dir, search_term)
        
        params = {
            "as_st": "y",   # Advanced search type
            "tbm": "isch",  # Crucial for image search
            "sa": "X",      # Action code. X means a search was executed directly.
            "ved": "2ahUKEwie44_AnqLpAhUhBWMBHUFGD90Q_AUoAXoECBUQAw", # A tracking/analytics value.
            "biw": 1280,    # Browser inner width in pixels (e.g. viewport width).
            "bih": 720,     # Browser inner height in pixels (e.g. viewport height).
            "as_q": self.search_key_query,
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
        logger.status(f"[Worker {self.worker_id}] Searching for '{self.search_key_query}' with URL: {self.search_url}")
        
        found_urls = []
        cache_data = load_json_data(self.cache_file_path) 
        
        if cache_data and cache_data.get('search_url_used') == self.search_url:
            found_urls = list(dict.fromkeys(cache_data.get('urls', [])))
            if len(found_urls) >= self.target_images:
                logger.success(f"[Worker {self.worker_id}] Loaded {self.target_images} cached image URLs for '{self.search_key_query}'.")
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

        logger.start_progress(needed_urls, f"Finding images for '{self.search_key_query}'", self.worker_id)
        
        high_res_image_selectors = ["n3VNCb", "iPVvYb", "r48jcc", "pT0Scc", "H8Rx8c"]

        processed_thumbnails = 0
        consecutive_misses = 0
        
        while len(found_urls) < self.target_images and consecutive_misses < cfg.MAX_MISSED:
            current_thumbnail_idx = processed_thumbnails + 1 
            
            try:
                thumbnail_xpath = f'//*[@id="rso"]/div/div/div[1]/div/div/div[{current_thumbnail_idx}]/div[2]/h3/a/div/div/div/g-img'
                
                img_thumbnail_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, thumbnail_xpath))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", img_thumbnail_element)
                try:
                    WebDriverWait(self.driver, 2).until(EC.element_to_be_clickable((By.XPATH, thumbnail_xpath)))
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
                                'search_key': self.search_key_query, 
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
                
                if processed_thumbnails % 15 == 0:
                    try:
                        btn = self.driver.find_element(By.CLASS_NAME, "mye4qd")
                        if btn.is_displayed() and btn.is_enabled():
                            logger.info(f"[Worker {self.worker_id}] Clicking 'Show more results' button.")
                            btn.click()
                            time.sleep(3)
                    except NoSuchElementException:
                        logger.debug(f"[Worker {self.worker_id}] 'Show more results' button (mye4qd) not found.")
                    except Exception as e_sm:
                        logger.warning(f"[Worker {self.worker_id}] Error clicking 'Show more results': {e_sm}")
            
            except TimeoutException: 
                logger.warning(f"[Worker {self.worker_id}] Timeout finding/clicking thumbnail {current_thumbnail_idx}. Misses: {consecutive_misses+1}")
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
            logger.success(f"[Worker {self.worker_id}] Successfully found {self.target_images} image URLs for '{self.search_key_query}'.")
        else:
            logger.warning(f"[Worker {self.worker_id}] Found {len(found_urls)}/{self.target_images} URLs for '{self.search_key_query}' after {cfg.MAX_MISSED} misses or exhausting content.")
        
        return found_urls[:self.target_images]

    def close(self):
        if hasattr(self, 'driver_manager') and self.driver_manager:
            self.driver_manager.close_driver()
            logger.info(f"[Worker {self.worker_id}] WebDriver closed for UrlFetcher of '{self.search_key_query}'.")
