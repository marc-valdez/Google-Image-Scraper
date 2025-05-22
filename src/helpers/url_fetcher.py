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
from src.helpers import config as cfg
import time
import random

def exponential_backoff(attempt, base=1, max_d=None):
    max_delay = max_d if max_d is not None else cfg.MAX_RETRY_DELAY
    return min(base * (2 ** attempt), max_delay) + random.uniform(0, 0.1)

class UrlFetcher:
    def __init__(self, category_dir: str, search_term: str, worker_id: int):
        self.category_dir = category_dir
        self.search_term_orig = search_term
        self.worker_id = worker_id
        
        self.driver_manager = WebDriverManager()
        self.driver = self.driver_manager.driver

        self.search_key_query = cfg.get_search_key_for_query(search_term, cfg.ADVANCED_SUFFIX)
        self.target_images = cfg.NUM_IMAGES_PER_CLASS
        self.cache_file_path = cfg.get_url_cache_file(self.category_dir, self.search_term_orig)
        
        self.search_url = f"https://www.google.com/search?q={self.search_key_query}&source=lnms&tbm=isch&sa=X&ved=2ahUKEwie44_AnqLpAhUhBWMBHUFGD90Q_AUoAXoECBUQAw&biw=1920&bih=947"


    def find_image_urls(self):
        logger.status(f"[Worker {self.worker_id}] Searching for '{self.search_key_query}'")
        
        found_urls = []
        cache_data = load_json_data(self.cache_file_path)
        
        if cache_data and cache_data.get('search_key') == self.search_key_query:
            found_urls = list(dict.fromkeys(cache_data.get('urls', [])))
            if len(found_urls) >= self.target_images:
                logger.success(f"[Worker {self.worker_id}] Loaded {self.target_images} cached image URLs for '{self.search_key_query}'.")
                return found_urls[:self.target_images]
            logger.info(f"[Worker {self.worker_id}] Found {len(found_urls)} cached URLs for '{self.search_key_query}'. Need {self.target_images - len(found_urls)} more.")

        if not self.driver:
            logger.error(f"[Worker {self.worker_id}] WebDriver not initialized. Cannot fetch URLs for '{self.search_key_query}'.")
            return found_urls

        try:
            self.driver.get(self.search_url)
            WebDriverWait(self.driver, cfg.PAGE_LOAD_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "img"))
            )
        except TimeoutException:
            logger.error(f"[Worker {self.worker_id}] Timeout loading initial image search page for '{self.search_key_query}'.")
            return found_urls
        except WebDriverException as e:
            logger.error(f"[Worker {self.worker_id}] WebDriver error on initial page load for '{self.search_key_query}': {e}")
            return found_urls


        needed_urls = self.target_images - len(found_urls)
        if needed_urls <= 0:
             logger.info(f"[Worker {self.worker_id}] All required images already found for '{self.search_key_query}'.")
             return found_urls[:self.target_images]

        logger.start_progress(needed_urls, f"Finding images for '{self.search_key_query}'", self.worker_id)
        
        high_res_image_selectors = [
            "//img[@class='sFlh5c pT0Scc iPVvYb']",
            "//img[@class='sFlh5c pT0Scc']",
            "//img[contains(@class, 'n3VNCb')]",
        ]

        processed_thumbnails = 0
        consecutive_misses = 0
        
        while len(found_urls) < self.target_images and consecutive_misses < cfg.MAX_MISSED:
            current_thumbnail_index = processed_thumbnails + 1
            thumbnail_clicked = False
            
            try:
                thumbnail_xpath = f"(//div[contains(@class,'isv-r')])[{current_thumbnail_index}]//a[1]"
                
                img_thumbnail_element = WebDriverWait(self.driver, cfg.SCROLL_PAUSE_TIME).until(
                    EC.presence_of_element_located((By.XPATH, thumbnail_xpath))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", img_thumbnail_element)
                time.sleep(cfg.SCROLL_PAUSE_TIME / 2)

                try:
                    WebDriverWait(self.driver, cfg.SCROLL_PAUSE_TIME).until(EC.element_to_be_clickable((By.XPATH, thumbnail_xpath))).click()
                    thumbnail_clicked = True
                except (TimeoutException, StaleElementReferenceException):
                    try: 
                        self.driver.execute_script("arguments[0].click();", img_thumbnail_element)
                        thumbnail_clicked = True
                    except Exception as e_js_click:
                        logger.debug(f"[Worker {self.worker_id}] JS click failed for thumbnail {current_thumbnail_index}: {e_js_click}")
                        processed_thumbnails += 1
                        consecutive_misses +=1
                        continue

                if not thumbnail_clicked:
                    processed_thumbnails += 1
                    consecutive_misses +=1
                    continue

                time.sleep(cfg.SCROLL_PAUSE_TIME)

                extracted_this_round = False
                for selector in high_res_image_selectors:
                    try:
                        img_elements = WebDriverWait(self.driver, cfg.SCROLL_PAUSE_TIME).until(
                            EC.presence_of_all_elements_located((By.XPATH, selector))
                        )
                        for el in img_elements:
                            src = el.get_attribute("src")
                            if src and src.startswith("http") and "encrypted-tbn0.gstatic.com" not in src and src not in found_urls:
                                found_urls.append(src)
                                logger.info(f"[Worker {self.worker_id}] Image {len(found_urls)}/{self.target_images}: {logger.truncate_url(src)}")
                                logger.update_progress(worker_id=self.worker_id)
                                extracted_this_round = True
                                if len(found_urls) >= self.target_images: break
                        if extracted_this_round and len(found_urls) >= self.target_images: break
                    except TimeoutException:
                        logger.debug(f"[Worker {self.worker_id}] Timeout waiting for high-res image with selector: {selector}")
                    except StaleElementReferenceException:
                         logger.debug(f"[Worker {self.worker_id}] Stale element with selector: {selector}")


                if extracted_this_round:
                    save_json_data(self.cache_file_path, {
                        'search_key': self.search_key_query,
                        'number_of_images_requested': self.target_images,
                        'urls_found_count': len(found_urls),
                        'urls': found_urls
                    })
                    consecutive_misses = 0
                else:
                    consecutive_misses += 1
                    logger.debug(f"[Worker {self.worker_id}] No new high-res URL found for thumbnail {current_thumbnail_index}. Misses: {consecutive_misses}")

                processed_thumbnails += 1

                if processed_thumbnails % cfg.BROWSER_REFRESH_INTERVAL == 0 :
                    try:
                        show_more_button = self.driver.find_element(By.XPATH, "//input[@type='button'][@value='Show more results']")
                        if show_more_button.is_displayed() and show_more_button.is_enabled():
                            logger.info(f"[Worker {self.worker_id}] Clicking 'Show more results' button.")
                            self.driver.execute_script("arguments[0].click();", show_more_button)
                            time.sleep(cfg.LOAD_BUTTON_WAIT)
                            consecutive_misses = 0
                    except NoSuchElementException:
                        logger.debug(f"[Worker {self.worker_id}] 'Show more results' button not found or not needed yet.")
                    except Exception as e_sm:
                        logger.warning(f"[Worker {self.worker_id}] Error clicking 'Show more results': {e_sm}")
                
                self.driver.execute_script(f"window.scrollBy(0, {random.randint(600, 900)});")
                time.sleep(cfg.SCROLL_PAUSE_TIME / 2)


            except (NoSuchElementException, StaleElementReferenceException, TimeoutException) as e_thumb:
                logger.warning(f"[Worker {self.worker_id}] Error processing thumbnail {current_thumbnail_index}: {type(e_thumb).__name__}. Misses: {consecutive_misses}")
                consecutive_misses += 1
                self.driver.execute_script(f"window.scrollBy(0, {random.randint(1000, 1500)});")
                time.sleep(exponential_backoff(consecutive_misses, base=0.5, max_d=cfg.SCROLL_PAUSE_TIME * 2))
            except WebDriverException as e_wd:
                logger.error(f"[Worker {self.worker_id}] WebDriverException: {e_wd}. Misses: {consecutive_misses}")
                consecutive_misses += 1
                time.sleep(exponential_backoff(consecutive_misses, base=1, max_d=cfg.MAX_RETRY_DELAY / 2))
            except Exception as e_main:
                logger.error(f"[Worker {self.worker_id}] Unexpected error in main loop: {e_main}. Misses: {consecutive_misses}")
                consecutive_misses += 1
                time.sleep(exponential_backoff(consecutive_misses))

        logger.complete_progress(worker_id=self.worker_id)
        if len(found_urls) >= self.target_images:
            logger.success(f"[Worker {self.worker_id}] Successfully found {self.target_images} image URLs for '{self.search_key_query}'.")
        else:
            logger.warning(f"[Worker {self.worker_id}] Found {len(found_urls)} out of {self.target_images} desired URLs for '{self.search_key_query}' after {cfg.MAX_MISSED} consecutive misses or exhausting content.")
        
        return found_urls[:self.target_images]

    def close(self):
        if hasattr(self, 'driver_manager') and self.driver_manager:
            self.driver_manager.close_driver()
            logger.info(f"[Worker {self.worker_id}] WebDriver closed for UrlFetcher of '{self.search_key_query}'.")
