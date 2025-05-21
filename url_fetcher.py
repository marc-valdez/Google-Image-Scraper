# -*- coding: utf-8 -*-
"""
Handles fetching image URLs from Google Images.
"""
#import selenium drivers
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

#import helper libraries
import time
import os
import re
from cache_utils import ensure_cache_dir, load_json_data, save_json_data, remove_file_if_exists

#custom patch libraries
import patch

class UrlFetcher:
    def __init__(self, webdriver_path, image_path, search_key="cat", advanced_suffix="", number_of_images=1, headless=True, max_missed=10, driver=None):
        self.search_key = f"{search_key}{advanced_suffix}"
        self.number_of_images = number_of_images
        self.webdriver_path = webdriver_path
        self.image_path = image_path
        self.headless = headless
        self.max_missed = max_missed
        self.driver = driver # Can be pre-initialized

        # Cache and Checkpoint setup
        self.cache_dir = os.path.join(self.image_path, ".cache")
        ensure_cache_dir(self.cache_dir)

        self.url_cache_file = os.path.join(self.cache_dir, f"{self.search_key}_urls.json")
        self.url_checkpoint_file = os.path.join(self.cache_dir, f"{self.search_key}_url_checkpoint.json")

        if not self.driver:
            self._initialize_driver()

        self.url = f"https://www.google.com/search?q={self.search_key}&source=lnms&tbm=isch&sa=X&ved=2ahUKEwie44_AnqLpAhUhBWMBHUFGD90Q_AUoAXoECBUQAw&biw=1920&bih=947"


    def _initialize_driver(self):
        #check if chromedriver is installed
        if (not os.path.isfile(self.webdriver_path)):
            is_patched = patch.download_lastest_chromedriver()
            if (not is_patched):
                exit("[ERR] Please update the chromedriver.exe in the webdriver folder according to your chrome version:https://chromedriver.chromium.org/downloads")

        for i in range(1): # Retry logic for driver initialization
            try:
                #try going to www.google.com
                options = Options()
                options.binary_location = r"C:\Users\Marc\AppData\Local\Google\Chrome SxS\Application\chrome.exe" # This might need to be configurable
                if(self.headless):
                    options.add_argument('--headless')
                driver = webdriver.Chrome(executable_path=self.webdriver_path, options=options)
                driver.set_window_size(1400,1050)
                driver.get("https://www.google.com")
                try:
                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "W0wltc"))).click()
                except Exception as e:
                    print(f"[INFO] Cookie consent dialog not found or clickable: {e}") # Changed to print
                    pass # Continue if cookie dialog is not there or fails
                self.driver = driver
                return # Successfully initialized
            except Exception as e:
                #update chromedriver
                pattern = r'(\d+\.\d+\.\d+\.\d+)'
                versions_found = list(set(re.findall(pattern, str(e))))
                if versions_found:
                    version = versions_found[0]
                    print(f"[INFO] Attempting to update ChromeDriver for version {version} based on error: {e}")
                    is_patched = patch.download_lastest_chromedriver(version)
                else:
                    print(f"[WARN] Could not determine Chrome version from error message: {e}")
                    print("[INFO] Attempting to download the latest ChromeDriver as a fallback.")
                    is_patched = patch.download_lastest_chromedriver()

                if not is_patched:
                    # Changed from exit to raise an exception or handle more gracefully
                    raise RuntimeError("[ERR] ChromeDriver update failed. Please ensure Chrome is installed and update the chromedriver.exe in the webdriver folder according to your Chrome version: https://chromedriver.chromium.org/downloads. Also, verify that the Chrome browser binary can be found by Selenium.")
        # If loop finishes without returning, driver initialization failed
        raise RuntimeError("[ERR] Failed to initialize WebDriver after retries.")


    def find_image_urls(self):
        """
            This function search and return a list of image urls based on the search key.
            It incorporates caching for previously fetched URLs and checkpointing to resume interrupted sessions.
        """
        print("[INFO] Attempting to gather image links...")

        image_urls = []
        count = 0
        current_selenium_item_index = 1
        missed_count = 0

        # 1. Try to load from URL cache first (_urls.json)
        cached_urls_data = load_json_data(self.url_cache_file)
        if cached_urls_data and cached_urls_data.get('search_key') == self.search_key:
            loaded_cached_urls = cached_urls_data.get('urls', [])
            for url_item in loaded_cached_urls: # Ensure uniqueness if cache contains duplicates
                if url_item not in image_urls:
                    image_urls.append(url_item)
            count = len(image_urls)
            
            if count >= self.number_of_images:
                print(f"[INFO] Loaded {self.number_of_images} (or more) unique image URLs from cache for '{self.search_key}'.")
                if hasattr(self, 'driver') and self.driver:
                    try: self.driver.quit()
                    except Exception as e: print(f"[WARN] Error quitting WebDriver (cache hit): {e}")
                return image_urls[:self.number_of_images]
            else: # Need to fetch more
                print(f"[INFO] Cache for '{self.search_key}' has {count} unique URLs. Need {self.number_of_images}. Will try to fetch {self.number_of_images - count} more.")
                current_selenium_item_index = cached_urls_data.get('final_selenium_item_index', 0) + 1
                print(f"[INFO] Resuming Selenium iteration from item index {current_selenium_item_index} based on cache state.")

        # 2. Try to load from URL fetching checkpoint (_url_checkpoint.json)
        checkpoint_data = load_json_data(self.url_checkpoint_file)
        if checkpoint_data and checkpoint_data.get('search_key') == self.search_key:
            print(f"[INFO] Resuming URL fetching for '{self.search_key}' from active checkpoint.")
            # Ensure URLs from checkpoint are unique and merged with any from cache
            checkpoint_urls = checkpoint_data.get('image_urls_found', [])
            for url_item in checkpoint_urls:
                if url_item not in image_urls:
                    image_urls.append(url_item)
            count = len(image_urls)
            current_selenium_item_index = checkpoint_data.get('last_selenium_item_index', current_selenium_item_index) # Use checkpoint's index
            missed_count = checkpoint_data.get('missed_count', 0)
            print(f"[INFO] Checkpoint state: {count} URLs found, next Selenium item index {current_selenium_item_index}, missed_count={missed_count}.")
        else:
            missed_count = 0 # Reset if no valid checkpoint

        if not hasattr(self, 'driver') or not self.driver:
            print("[ERROR] WebDriver not initialized before find_image_urls. This should not happen.")
            # Attempt to initialize if not already
            try:
                self._initialize_driver()
            except RuntimeError as e:
                print(f"[ERROR] Failed to initialize driver: {e}")
                return []


        print("[INFO] Gathering image links online (if needed)...")
        if count < self.number_of_images:
            self.driver.get(self.url)
            time.sleep(3) # Consider making this configurable or using WebDriverWait
        
        search_string = '//*[@id="rso"]/div/div/div[1]/div/div/div[%s]/div[2]/h3/a/div/div/div/g-img'

        while count < self.number_of_images and missed_count < self.max_missed:
            try:
                imgurl_element = self.driver.find_element(By.XPATH, search_string % current_selenium_item_index)
                imgurl_element.click()
                missed_count = 0 # Reset on successful click
                
                time.sleep(1) # Wait for popup, consider WebDriverWait
                class_names = ["n3VNCb","iPVvYb","r48jcc","pT0Scc","H8Rx8c"] # Potential for these to change
                found_src_in_popup = False
                # More robust way to find the image source in the popup
                image_elements_in_popup = []
                for class_name in class_names:
                    elements = self.driver.find_elements(By.CLASS_NAME, class_name)
                    if elements:
                        image_elements_in_popup.extend(elements)
                
                for _image_detail_element in image_elements_in_popup:
                    src_link = _image_detail_element.get_attribute("src")
                    if src_link and ("http" in src_link) and ("encrypted" not in src_link): # Basic validation
                        if src_link not in image_urls:
                            image_urls.append(src_link)
                            count = len(image_urls)
                            print(f"[INFO] {self.search_key} \t #{count} (Selenium Idx: {current_selenium_item_index}) \t {src_link}")
                            
                            if count % 5 == 0: # Checkpoint saving logic
                                checkpoint_to_save = {
                                    'search_key': self.search_key,
                                    'last_selenium_item_index': current_selenium_item_index,
                                    'count': count,
                                    'missed_count': missed_count,
                                    'image_urls_found': image_urls
                                }
                                if save_json_data(self.url_checkpoint_file, checkpoint_to_save):
                                    print(f"[INFO] URL fetching checkpoint saved. Total URLs: {count}, at Selenium Idx: {current_selenium_item_index}.")
                                else:
                                    print(f"[WARN] Failed to save URL fetching checkpoint.")
                        else:
                            # print(f"[DEBUG] Duplicate URL found and skipped: {src_link}")
                            pass
                        found_src_in_popup = True
                        break # Found a valid src, move to next Selenium item
                if not found_src_in_popup:
                    # print(f"[DEBUG] No valid src found in popup for Selenium item {current_selenium_item_index}")
                    pass

            except NoSuchElementException:
                # print(f"[DEBUG] Selenium item {current_selenium_item_index} not found (NoSuchElementException).")
                missed_count += 1
            except Exception as e:
                # print(f"[WARN] Error processing Selenium item {current_selenium_item_index}: {e}")
                missed_count += 1

            current_selenium_item_index += 1
                    
            if count < self.number_of_images: # Check if more images are needed
                # Scroll and load more logic
                if missed_count > 5 or (current_selenium_item_index % 15 == 0): # Conditions to try loading more
                    try:
                        self.driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.5) # Give time for new content to load
                        # Attempt to click "Load more results" or similar button
                        # This part is highly dependent on Google's current layout
                        load_more_button_selectors = [
                            (By.CLASS_NAME, "mye4qd"), # Known class
                            (By.XPATH, "//input[@value='Show more results']"), # Another common pattern
                            (By.XPATH, "//*[contains(text(),'Show more results')]") # Text based
                        ]
                        button_clicked = False
                        for by_type, selector_value in load_more_button_selectors:
                            try:
                                load_more_button = self.driver.find_element(by_type, selector_value)
                                if load_more_button.is_displayed() and load_more_button.is_enabled():
                                    print("[INFO] Clicking 'Load more results' button.")
                                    load_more_button.click()
                                    time.sleep(3) # Wait for results to load
                                    button_clicked = True
                                    break # Exit loop once button is clicked
                            except NoSuchElementException:
                                continue # Try next selector
                            except Exception as e_button:
                                print(f"[WARN] Error interacting with load more button ({selector_value}): {e_button}")
                                continue
                        if not button_clicked:
                            # print("[DEBUG] 'Load more results' button not found or not interactable.")
                            pass
                    except Exception as e_load_more:
                        # print(f"[WARN] Error during scroll/load more: {e_load_more}")
                        pass

                if current_selenium_item_index % 5 == 0 : # Periodic scroll
                     self.driver.execute_script(f"window.scrollBy(0, 500);")
                     time.sleep(0.5)

        print(f"[INFO] Total unique image URLs gathered for '{self.search_key}': {len(image_urls)}")
        
        # Save all fetched URLs to cache
        if image_urls: # Only save if there are URLs
            print(f"[INFO] Saving all {len(image_urls)} unique image URLs to cache for '{self.search_key}'.")
            url_cache_data = {
                'search_key': self.search_key,
                'number_of_images_requested': self.number_of_images,
                'urls_found_count': len(image_urls),
                'urls': image_urls,
                'final_selenium_item_index': current_selenium_item_index -1 # The last index processed
            }
            save_json_data(self.url_cache_file, url_cache_data)

        remove_file_if_exists(self.url_checkpoint_file) # Clear checkpoint after successful run or completion
        print(f"[INFO] URL fetching checkpoint cleared for '{self.search_key}'.")

        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
                print("[INFO] WebDriver quit after finding image URLs.")
            except Exception as e:
                print(f"[WARN] Error quitting WebDriver after finding URLs: {e}")
        print("[INFO] Google image URL gathering ended.")
        return image_urls[:self.number_of_images] # Return only the requested number

    def close_driver(self):
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
                print("[INFO] WebDriver explicitly closed.")
            except Exception as e:
                print(f"[WARN] Error quitting WebDriver during explicit close: {e}")
            finally:
                self.driver = None