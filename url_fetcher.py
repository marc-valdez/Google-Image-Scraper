from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, StaleElementReferenceException,
    TimeoutException, WebDriverException
)
from cache_utils import load_json_data, save_json_data, remove_file_if_exists
import time
import random

def exponential_backoff(attempt, base_delay=1, max_delay=60):
    """Calculate delay with jitter for exponential backoff"""
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0, 0.1 * delay)
    return delay + jitter

class UrlFetcher:
    def __init__(self, config, webdriver_manager):
        self.config = config
        self.webdriver_manager = webdriver_manager
        self.driver = self.webdriver_manager.driver

    @property
    def search_key(self):
        return self.config.search_key_for_query

    @property
    def number_of_images(self):
        return self.config.number_of_images
        
    @property
    def url_cache_file(self):
        return self.config.get_url_cache_file()

    @property
    def url_checkpoint_file(self):
        return self.config.get_url_checkpoint_file()

    @property
    def google_search_url(self):
        return f"https://www.google.com/search?q={self.search_key}&source=lnms&tbm=isch&sa=X&ved=2ahUKEwie44_AnqLpAhUhBWMBHUFGD90Q_AUoAXoECBUQAw&biw=1920&bih=947"

    def find_image_urls(self):
        print(f"[INFO] Attempting to gather image links for '{self.search_key}'...")

        image_urls = []
        count = 0
        current_selenium_item_index = 1
        missed_count = 0

        cached_urls_data = load_json_data(self.url_cache_file)
        if cached_urls_data and cached_urls_data.get('search_key') == self.search_key:
            loaded_cached_urls = cached_urls_data.get('urls', [])
            for url_item in loaded_cached_urls:
                if url_item not in image_urls:
                    image_urls.append(url_item)
            count = len(image_urls)
            
            if count >= self.number_of_images:
                print(f"[INFO] Loaded {count} (>= requested {self.number_of_images}) unique image URLs from cache for '{self.search_key}'.")
                return image_urls[:self.number_of_images]
            else:
                print(f"[INFO] Cache for '{self.search_key}' has {count} unique URLs. Need {self.number_of_images - count} more.")
                current_selenium_item_index = cached_urls_data.get('final_selenium_item_index', 0) + 1
                print(f"[INFO] Resuming Selenium iteration from item index {current_selenium_item_index} (from cache).")

        checkpoint_data = load_json_data(self.url_checkpoint_file)
        if checkpoint_data and checkpoint_data.get('search_key') == self.search_key:
            print(f"[INFO] Resuming URL fetching for '{self.search_key}' from checkpoint.")
            checkpoint_urls = checkpoint_data.get('image_urls_found', [])
            for url_item in checkpoint_urls:
                if url_item not in image_urls:
                    image_urls.append(url_item)
            count = len(image_urls)
            current_selenium_item_index = max(current_selenium_item_index, checkpoint_data.get('last_selenium_item_index', 1))
            missed_count = checkpoint_data.get('missed_count', 0)
            print(f"[INFO] Checkpoint state: {count} URLs, next Selenium item index {current_selenium_item_index}, missed_count={missed_count}.")
        else:
            missed_count = 0

        # Define search string pattern first
        search_string = '//*[@id="rso"]/div/div/div[1]/div/div/div[%s]/div[2]/h3/a/div/div/div/g-img'
        
        if count < self.number_of_images:
            print(f"[INFO] Gathering remaining image links online for '{self.search_key}'...")
            self.driver.get(self.google_search_url)
            
            # Wait for initial page load with dynamic timeout
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, search_string % 1))
                )
            except TimeoutException:
                print("[WARN] Initial page load timeout - refreshing page...")
                self.driver.refresh()
                time.sleep(5)

        attempt = 0
        page_refresh_counter = 0
        while count < self.number_of_images and missed_count < self.config.max_missed:
            try:
                # Periodic page refresh to prevent stale state
                if page_refresh_counter >= 50:
                    print("[INFO] Performing periodic page refresh...")
                    self.driver.refresh()
                    time.sleep(3)
                    page_refresh_counter = 0
                    continue

                # Try to find and click image with wait
                try:
                    imgurl_element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, search_string % current_selenium_item_index))
                    )
                    imgurl_element.click()
                    missed_count = 0
                    attempt = 0
                except TimeoutException:
                    raise NoSuchElementException("Element not found or not clickable")

                # Dynamic wait after click
                time.sleep(random.uniform(1.0, 2.0))
                class_names = ["n3VNCb","iPVvYb","r48jcc","pT0Scc","H8Rx8c"]
                found_src_in_popup = False
                
                image_elements_in_popup = []
                for class_name in class_names:
                    elements = self.driver.find_elements(By.CLASS_NAME, class_name)
                    if elements: image_elements_in_popup.extend(elements)
                
                for _image_detail_element in image_elements_in_popup:
                    src_link = _image_detail_element.get_attribute("src")
                    if src_link and ("http" in src_link) and ("encrypted" not in src_link):
                        if src_link not in image_urls:
                            image_urls.append(src_link)
                            count = len(image_urls)
                            print(f"[INFO] {self.search_key} | #{count} (Selenium Idx: {current_selenium_item_index}) | {src_link}")
                            
                            if count % 5 == 0:
                                checkpoint_to_save = {
                                    'search_key': self.search_key,
                                    'last_selenium_item_index': current_selenium_item_index,
                                    'count': count, 'missed_count': missed_count,
                                    'image_urls_found': image_urls
                                }
                                if save_json_data(self.url_checkpoint_file, checkpoint_to_save):
                                    print(f"[INFO] URL fetching checkpoint saved. URLs: {count}, Selenium Idx: {current_selenium_item_index}.")
                                else:
                                    print(f"[WARN] Failed to save URL fetching checkpoint.")
                        found_src_in_popup = True
                        break

            except NoSuchElementException:
                missed_count += 1
            except StaleElementReferenceException:
                print("[WARN] Encountered stale element - retrying...")
                attempt += 1
                time.sleep(exponential_backoff(attempt))
                continue
            except WebDriverException as e:
                print(f"[WARN] WebDriver error: {str(e)}")
                missed_count += 1
                attempt += 1
                time.sleep(exponential_backoff(attempt))
            except Exception as e:
                print(f"[ERROR] Unexpected error: {str(e)}")
                missed_count += 1
                attempt += 1
                time.sleep(exponential_backoff(attempt))

            current_selenium_item_index += 1
            page_refresh_counter += 1
                    
            if count < self.number_of_images:
                if missed_count > 5 or (current_selenium_item_index % 15 == 0):
                    try:
                        # Smooth scroll with intermediate stops
                        height = self.driver.execute_script("return document.body.scrollHeight")
                        current_pos = self.driver.execute_script("return window.pageYOffset")
                        scroll_step = height // 4
                        
                        for pos in range(current_pos, height, scroll_step):
                            self.driver.execute_script(f"window.scrollTo(0, {pos});")
                            time.sleep(0.2)
                        
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(random.uniform(0.5, 1.0))
                        load_more_button_selectors = [
                            (By.CLASS_NAME, "mye4qd"),
                            (By.XPATH, "//input[@value='Show more results']"),
                            (By.XPATH, "//*[contains(text(),'Show more results')]")
                        ]
                        button_clicked = False
                        for by_type, selector_value in load_more_button_selectors:
                            try:
                                load_more_button = self.driver.find_element(by_type, selector_value)
                                if load_more_button.is_displayed() and load_more_button.is_enabled():
                                    print("[INFO] Clicking 'Load more results' button.")
                                    load_more_button.click()
                                    time.sleep(3)
                                    button_clicked = True
                                    break
                            except NoSuchElementException: continue
                            except Exception as e_button:
                                print(f"[WARN] Error with load more button ({selector_value}): {e_button}")
                    except Exception as e_load_more:
                        pass

                if current_selenium_item_index % 5 == 0:
                    # Randomized scroll amount
                    scroll_amount = random.randint(400, 600)
                    self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                    time.sleep(random.uniform(0.3, 0.7))
                    
                page_refresh_counter += 1

        print(f"[INFO] Total unique image URLs gathered for '{self.search_key}': {len(image_urls)}")
        
        if image_urls:
            print(f"[INFO] Saving all {len(image_urls)} unique URLs to cache for '{self.search_key}'.")
            url_cache_data = {
                'search_key': self.search_key,
                'number_of_images_requested': self.number_of_images,
                'urls_found_count': len(image_urls),
                'urls': image_urls,
                'final_selenium_item_index': current_selenium_item_index -1
            }
            save_json_data(self.url_cache_file, url_cache_data)

        remove_file_if_exists(self.url_checkpoint_file)
        print(f"[INFO] URL fetching checkpoint cleared for '{self.search_key}'.")

        print("[INFO] Google image URL gathering ended.")
        return image_urls[:self.number_of_images]