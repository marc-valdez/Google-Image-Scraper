# -*- coding: utf-8 -*-
"""
Created on Sat Jul 18 13:01:02 2020

@author: OHyic
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
from urllib.parse import urlparse
import os
import requests
import io
from PIL import Image
import re
from cache_utils import ensure_cache_dir, load_json_data, save_json_data, remove_file_if_exists # Added import

#custom patch libraries
import patch

class GoogleImageScraper():
    def __init__(self, webdriver_path, image_path, search_key="cat", number_of_images=1, headless=True, min_resolution=(0, 0), max_resolution=(1920, 1080), max_missed=10):
        #check parameter types
        if (type(number_of_images)!=int):
            print("[Error] Number of images must be integer value.")
            return
        self.search_key = search_key
        self.number_of_images = number_of_images
        self.webdriver_path = webdriver_path
        self.image_path = image_path

        if not os.path.exists(self.image_path):
            print(f"[INFO] Image path {self.image_path} not found. Creating a new folder.")
            os.makedirs(self.image_path)

        self.headless=headless
        self.min_resolution = min_resolution
        self.max_resolution = max_resolution
        self.max_missed = max_missed

        # Cache and Checkpoint setup
        self.cache_dir = os.path.join(self.image_path, ".cache")
        ensure_cache_dir(self.cache_dir)

        self.url_cache_file = os.path.join(self.cache_dir, f"{self.search_key}_urls.json")
        self.url_checkpoint_file = os.path.join(self.cache_dir, f"{self.search_key}_url_checkpoint.json")
        self.download_checkpoint_file = os.path.join(self.cache_dir, f"{self.search_key}_download_checkpoint.json")
            
        #check if chromedriver is installed
        if (not os.path.isfile(webdriver_path)):
            is_patched = patch.download_lastest_chromedriver()
            if (not is_patched):
                exit("[ERR] Please update the chromedriver.exe in the webdriver folder according to your chrome version:https://chromedriver.chromium.org/downloads")

        for i in range(1):
            try:
                #try going to www.google.com
                options = Options()
                options.binary_location = r"C:\Users\Marc\AppData\Local\Google\Chrome SxS\Application\chrome.exe"
                if(headless):
                    options.add_argument('--headless')
                driver = webdriver.Chrome(executable_path=webdriver_path, options=options)
                driver.set_window_size(1400,1050)
                driver.get("https://www.google.com")
                try:
                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "W0wltc"))).click()
                except Exception as e:
                    continue
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
                    is_patched = patch.download_lastest_chromedriver() # Attempt to download latest if version unknown
                
                if not is_patched:
                    exit("[ERR] ChromeDriver update failed. Please ensure Chrome is installed and update the chromedriver.exe in the webdriver folder according to your Chrome version: https://chromedriver.chromium.org/downloads. Also, verify that the Chrome browser binary can be found by Selenium.")

        self.driver = driver # driver is initialized in the loop above
        self.url = "https://www.google.com/search?q=%s&source=lnms&tbm=isch&sa=X&ved=2ahUKEwie44_AnqLpAhUhBWMBHUFGD90Q_AUoAXoECBUQAw&biw=1920&bih=947"%(self.search_key)
        # Other self attributes already set above

    def find_image_urls(self):
        """
            This function search and return a list of image urls based on the search key.
            It incorporates caching for previously fetched URLs and checkpointing to resume interrupted sessions.
            Example:
                google_image_scraper = GoogleImageScraper("webdriver_path","image_path","search_key",number_of_photos)
                image_urls = google_image_scraper.find_image_urls()

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
            for url in loaded_cached_urls:
                if url not in image_urls:
                    image_urls.append(url)
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
            image_urls = checkpoint_data.get('image_urls_found', [])
            count = len(image_urls)
            current_selenium_item_index = checkpoint_data.get('last_selenium_item_index', current_selenium_item_index) # Use checkpoint's index
            missed_count = checkpoint_data.get('missed_count', 0)
            print(f"[INFO] Checkpoint state: {count} URLs found, next Selenium item index {current_selenium_item_index}, missed_count={missed_count}.")
        else:
            missed_count = 0

        if not hasattr(self, 'driver'):
            print("[ERROR] WebDriver not initialized before find_image_urls. This should not happen.")
            return []


        print("[INFO] Gathering image links online (if needed)...")
        if count < self.number_of_images:
            self.driver.get(self.url)
            time.sleep(3)
        
        search_string = '//*[@id="rso"]/div/div/div[1]/div/div/div[%s]/div[2]/h3/a/div/div/div/g-img'

        while count < self.number_of_images and missed_count < self.max_missed:
            try:
                imgurl_element = self.driver.find_element(By.XPATH, search_string % current_selenium_item_index)
                imgurl_element.click()
                missed_count = 0
                
                time.sleep(1)
                class_names = ["n3VNCb","iPVvYb","r48jcc","pT0Scc","H8Rx8c"]
                found_src_in_popup = False
                for _image_detail_element in [self.driver.find_elements(By.CLASS_NAME, class_name) for class_name in class_names if len(self.driver.find_elements(By.CLASS_NAME, class_name)) != 0 ][0]:
                    src_link = _image_detail_element.get_attribute("src")
                    if src_link and ("http" in src_link) and ("encrypted" not in src_link):
                        if src_link not in image_urls:
                            image_urls.append(src_link)
                            count = len(image_urls)
                            print(f"[INFO] {self.search_key} \t #{count} (Selenium Idx: {current_selenium_item_index}) \t {src_link}")
                            
                            if count % 5 == 0:
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
                            pass
                        found_src_in_popup = True
                        break
                if not found_src_in_popup:
                    pass

            except NoSuchElementException:
                missed_count += 1
            except Exception as e:
                missed_count += 1

            current_selenium_item_index += 1
                    
            if count < self.number_of_images:
                if missed_count > 5 or (current_selenium_item_index % 15 == 0):
                    try:
                        self.driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.5)
                        load_more_button = self.driver.find_element(By.CLASS_NAME, "mye4qd")
                        if load_more_button.is_displayed() and load_more_button.is_enabled():
                            print("[INFO] Clicking 'Load more results' button.")
                            load_more_button.click()
                            time.sleep(3)
                        else:
                            pass
                    except Exception as e_load_more:
                        pass

                if current_selenium_item_index % 5 == 0 :
                     self.driver.execute_script(f"window.scrollBy(0, 500);")
                     time.sleep(0.5)

        print(f"[INFO] Total unique image URLs gathered for '{self.search_key}': {len(image_urls)}")
        
        # Save all fetched URLs to cache
        if image_urls:
            print(f"[INFO] Saving all {len(image_urls)} unique image URLs to cache for '{self.search_key}'.")
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

        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
                print("[INFO] WebDriver quit after finding image URLs.")
            except Exception as e:
                print(f"[WARN] Error quitting WebDriver after finding URLs: {e}")
        print("[INFO] Google image URL gathering ended.")
        return image_urls

    def save_images(self, image_urls, keep_filenames):
        """
        Download and save images from the given URLs into self.image_path.
        Supports checkpointing and skipping already downloaded files.
        """
        if not image_urls:
            print("[INFO] No image URLs provided to save.")
            return

        print(f"[INFO] Attempting to save {len(image_urls)} images for '{self.search_key}', please wait...")

        start_index = 0
        download_checkpoint = load_json_data(self.download_checkpoint_file)
        urls_hash = hash(tuple(image_urls))

        if download_checkpoint and \
        download_checkpoint.get('search_key') == self.search_key and \
        download_checkpoint.get('all_image_urls_hash') == urls_hash:
            start_index = download_checkpoint.get('last_downloaded_index', -1) + 1
            print(f"[INFO] Resuming from index {start_index}.")
        else:
            save_json_data(self.download_checkpoint_file, {
                'search_key': self.search_key,
                'all_image_urls_hash': urls_hash,
                'last_downloaded_index': -1,
                'total_urls_to_download': len(image_urls)
            })

        saved_count = 0
        for indx in range(start_index, len(image_urls)):
            image_url = image_urls[indx]
            search_string_for_filename = ''.join(e for e in self.search_key if e.isalnum())

            try:
                print(f"[INFO] Downloading {indx+1}/{len(image_urls)}: {image_url}")
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Referer": image_url
                }
                response = requests.get(image_url, headers=headers, timeout=10)
                if response.status_code != 200:
                    raise Exception(f"Status code: {response.status_code}")

                with Image.open(io.BytesIO(response.content)) as img:
                    image_format = img.format.lower() if img.format else 'jpg'

                    if keep_filenames:
                        base_name = os.path.basename(urlparse(image_url).path)
                        name_part, _ = os.path.splitext(base_name)
                        filename = f"{name_part or search_string_for_filename + str(indx)}.{image_format}"
                    else:
                        filename = f"{search_string_for_filename}{indx}.{image_format}"

                    save_path = os.path.join(self.image_path, filename)

                    if os.path.exists(save_path):
                        print(f"[INFO] File exists, skipping: {save_path}")
                        save_json_data(self.download_checkpoint_file, {
                            'search_key': self.search_key,
                            'all_image_urls_hash': urls_hash,
                            'last_downloaded_index': indx,
                            'total_urls_to_download': len(image_urls)
                        })
                        saved_count += 1
                        continue

                    img.save(save_path)
                    print(f"[INFO] Saved: {save_path}")
                    saved_count += 1

                save_json_data(self.download_checkpoint_file, {
                    'search_key': self.search_key,
                    'all_image_urls_hash': urls_hash,
                    'last_downloaded_index': indx,
                    'total_urls_to_download': len(image_urls)
                })

            except Exception as e:
                print(f"[ERROR] Failed to save image {indx+1}: {e}")
                save_json_data(self.download_checkpoint_file, {
                    'search_key': self.search_key,
                    'all_image_urls_hash': urls_hash,
                    'last_downloaded_index': indx,
                    'total_urls_to_download': len(image_urls)
                })

        print("--------------------------------------------------")
        print(f"[INFO] Downloaded {saved_count} new image(s).")

        if saved_count and os.path.exists(self.download_checkpoint_file):
            final_checkpoint = load_json_data(self.download_checkpoint_file)
            if final_checkpoint.get('last_downloaded_index', -1) == len(image_urls) - 1:
                remove_file_if_exists(self.download_checkpoint_file)
                print(f"[INFO] All downloads completed. Checkpoint cleared.")
            else:
                print(f"[INFO] Download incomplete. Checkpoint retained.")
        elif not saved_count:
            print(f"[INFO] No new images were downloaded.")
