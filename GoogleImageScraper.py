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
import urllib.request
from urllib.parse import urlparse
import os
import requests
import io
from PIL import Image
import re
import json # Added import
from cache_utils import ensure_cache_dir, load_json_data, save_json_data, remove_file_if_exists # Added import

#custom patch libraries
import patch

class GoogleImageScraper():
    def __init__(self, webdriver_path, image_path, search_key="cat", number_of_images=1, headless=True, min_resolution=(0, 0), max_resolution=(1920, 1080), max_missed=10):
        #check parameter types
        # image_path is now self.image_path, initialized later
        # original_image_path = image_path # Preserve original for cache structure
        
        if (type(number_of_images)!=int):
            print("[Error] Number of images must be integer value.")
            return
        if not os.path.exists(image_path):
            print("[INFO] Image path not found. Creating a new folder.")
            os.makedirs(os.path.join(image_path, search_key)) # Ensure specific search key folder is made if base path doesn't exist
        
        self.search_key = search_key
        self.number_of_images = number_of_images
        self.webdriver_path = webdriver_path
        # self.image_path is now set after search_key to include it
        self.image_path = os.path.join(image_path, self.search_key)
        if not os.path.exists(self.image_path):
            os.makedirs(self.image_path)

        self.headless=headless
        self.min_resolution = min_resolution
        self.max_resolution = max_resolution
        self.max_missed = max_missed

        # Cache and Checkpoint setup
        self.cache_dir = os.path.join(self.image_path, ".cache")
        ensure_cache_dir(self.cache_dir)
        
        # Sanitize search_key for filenames (though self.search_key is used directly in paths now, good for general cache keys if needed)
        # sanitized_search_key = ''.join(e for e in self.search_key if e.isalnum())
        # Using raw search_key for directory structure, which is fine for OS paths.
        # If search_key could contain problematic characters for filenames (not paths), sanitize then.

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

        # 1. Try to load from URL cache first
        cached_urls_data = load_json_data(self.url_cache_file)
        if cached_urls_data and cached_urls_data.get('search_key') == self.search_key:
            cached_urls = cached_urls_data.get('urls', [])
            if len(cached_urls) >= self.number_of_images:
                print(f"[INFO] Loaded {self.number_of_images} image URLs from cache for '{self.search_key}'.")
                # self.driver might not be initialized if we hit cache directly.
                # Ensure driver is quit if it was initialized in __init__ but not used.
                if hasattr(self, 'driver') and self.driver:
                    try:
                        self.driver.quit()
                        print("[INFO] WebDriver quit as URLs were fully loaded from cache.")
                    except Exception as e:
                        print(f"[WARN] Error quitting WebDriver when loading from cache: {e}")
                return cached_urls[:self.number_of_images]
            else:
                print(f"[INFO] Cache found for '{self.search_key}' but only {len(cached_urls)} URLs. Need {self.number_of_images}. Will try to fetch more.")
        
        # Initialize default values
        image_urls = []
        count = 0
        missed_count = 0
        indx_1 = 0
        indx_2 = 0

        # 2. Try to load from URL fetching checkpoint
        checkpoint_data = load_json_data(self.url_checkpoint_file)
        if checkpoint_data and checkpoint_data.get('search_key') == self.search_key:
            print(f"[INFO] Resuming URL fetching for '{self.search_key}' from checkpoint.")
            image_urls = checkpoint_data.get('image_urls_found', [])
            count = checkpoint_data.get('count', 0)
            indx_1 = checkpoint_data.get('last_indx_1', 0)
            indx_2 = checkpoint_data.get('last_indx_2', 0)
            missed_count = checkpoint_data.get('missed_count', 0)
            print(f"[INFO] Resuming from: count={count}, indx_1={indx_1}, indx_2={indx_2}, missed_count={missed_count}")
        
        if not hasattr(self, 'driver'):
             # This case should ideally not happen if __init__ completes.
             # Re-evaluating __init__ structure for driver initialization.
             # For now, assume driver is available from __init__.
            print("[ERROR] WebDriver not initialized before find_image_urls. This should not happen.")
            return []


        print("[INFO] Gathering image links online...")
        self.driver.get(self.url) # Ensure driver navigates if not loaded from full cache
        
        search_string = '//*[@id="rso"]/div/div/div[1]/div/div/div[%s]/div[2]/h3/a/div/div/div/g-img' # This XPATH might be fragile
        time.sleep(3) # Initial wait for page load

        while self.number_of_images > count and missed_count < self.max_missed:
            if indx_2 > 0:
                try:
                    imgurl = self.driver.find_element(By.XPATH, search_string%(indx_1,indx_2+1))
                    imgurl.click()
                    indx_2 = indx_2 + 1
                    missed_count = 0
                except Exception:
                    try:
                        imgurl = self.driver.find_element(By.XPATH, search_string%(indx_1+1,1))
                        imgurl.click()
                        indx_2 = 1
                        indx_1 = indx_1 + 1
                    except:
                        indx_2 = indx_2 + 1
                        missed_count = missed_count + 1
            else:
                try:
                    imgurl = self.driver.find_element(By.XPATH, search_string%(indx_1+1))
                    imgurl.click()
                    missed_count = 0
                    indx_1 = indx_1 + 1    
                except Exception:
                    try:
                        imgurl = self.driver.find_element(By.XPATH, search_string%(indx_1,indx_2+1))
                        imgurl.click()
                        missed_count = 0
                        indx_2 = indx_2 + 1
                    except Exception:
                        indx_1 = indx_1 + 1
                        missed_count = missed_count + 1
                    
            try:
                #select image from the popup
                time.sleep(1)
                class_names = ["n3VNCb","iPVvYb","r48jcc","pT0Scc","H8Rx8c"]
                images = [self.driver.find_elements(By.CLASS_NAME, class_name) for class_name in class_names if len(self.driver.find_elements(By.CLASS_NAME, class_name)) != 0 ][0]
                for image in images:
                    #only download images that starts with http
                    src_link = image.get_attribute("src")
                    if(("http" in src_link) and (not "encrypted" in src_link)):
                        print(
                            f"[INFO] {self.search_key} \t #{count} \t {src_link}")
                        image_urls.append(src_link)
                        count += 1
                        # Save checkpoint periodically
                        if count % 5 == 0: # Save checkpoint every 5 images found
                            current_checkpoint_data = {
                                'search_key': self.search_key,
                                'last_indx_1': indx_1,
                                'last_indx_2': indx_2,
                                'count': count,
                                'missed_count': missed_count,
                                'image_urls_found': image_urls
                            }
                            if save_json_data(self.url_checkpoint_file, current_checkpoint_data):
                                print(f"[INFO] URL fetching checkpoint saved at image #{count} for '{self.search_key}'.")
                            else:
                                print(f"[WARN] Failed to save URL fetching checkpoint at image #{count}.")
                        break # Found a valid src_link for this image element
            except Exception:
                print("[INFO] Unable to get link")

            try:
                #scroll page to load next image
                if(count%3==0):
                    self.driver.execute_script("window.scrollTo(0, "+str(indx_1*60)+");")
                element = self.driver.find_element(By.CLASS_NAME,"mye4qd")
                element.click()
                print("[INFO] Loading next page")
                time.sleep(3)
            except Exception:
                time.sleep(1)



        # After the loop
        print(f"[INFO] Total image URLs fetched for '{self.search_key}': {len(image_urls)}")
        
        # Save all fetched URLs to cache
        if image_urls: # Only save if some URLs were found
            print(f"[INFO] Saving all {len(image_urls)} fetched image URLs to cache for '{self.search_key}'.")
            url_cache_data = {
                'search_key': self.search_key,
                'number_of_images_requested': self.number_of_images, # Store what was requested
                'urls_found_count': len(image_urls),
                'urls': image_urls
            }
            save_json_data(self.url_cache_file, url_cache_data)
        
        # Remove URL fetching checkpoint as the process is complete for this run
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

    def save_images(self,image_urls, keep_filenames):
        # print(keep_filenames) # Already printed if needed by caller
        #save images into file directory
        """
            This function takes in an array of image urls and save it into the given image path/directory.
            It incorporates checkpointing to resume interrupted downloads and skips already downloaded files.
            Example:
                google_image_scraper = GoogleImageScraper("webdriver_path","image_path","search_key",number_of_photos)
                image_urls=["https://example_1.jpg","https://example_2.jpg"]
                google_image_scraper.save_images(image_urls)

        """
        if not image_urls:
            print("[INFO] No image URLs provided to save.")
            return

        print(f"[INFO] Attempting to save {len(image_urls)} images for '{self.search_key}', please wait...")
        
        start_index = 0
        # Load download checkpoint
        download_checkpoint = load_json_data(self.download_checkpoint_file)
        if download_checkpoint and \
           download_checkpoint.get('search_key') == self.search_key and \
           download_checkpoint.get('all_image_urls_hash') == hash(tuple(image_urls)): # Check if URL list is the same
            
            start_index = download_checkpoint.get('last_downloaded_index', -1) + 1
            if start_index > 0:
                print(f"[INFO] Resuming download for '{self.search_key}' from index {start_index} (out of {len(image_urls)}) based on checkpoint.")
            else: # last_downloaded_index was -1, start from 0
                 print(f"[INFO] Checkpoint found for '{self.search_key}', starting download from beginning (index 0).")
        else:
            if download_checkpoint:
                 print(f"[INFO] Download checkpoint found for '{self.search_key}' but image URL list differs or is missing hash. Starting fresh.")
            else:
                 print(f"[INFO] No valid download checkpoint found for '{self.search_key}'. Starting fresh.")
            # Save initial checkpoint if starting fresh or if checkpoint is invalid for current list
            initial_checkpoint_data = {
                'search_key': self.search_key,
                'all_image_urls_hash': hash(tuple(image_urls)), # Store hash of the list
                'last_downloaded_index': -1,
                'total_urls_to_download': len(image_urls)
            }
            save_json_data(self.download_checkpoint_file, initial_checkpoint_data)

        saved_count = 0
        for indx in range(start_index, len(image_urls)):
            image_url = image_urls[indx]
            # Determine filename first for cache check
            search_string_for_filename = ''.join(e for e in self.search_key if e.isalnum())
            # actual_image_path_to_save will be set after getting image format
            actual_image_path_to_save = ""

            try:
                print(f"[INFO] Downloading image {indx+1}/{len(image_urls)}: {image_url}")
                image_content_response = requests.get(image_url, timeout=10) # Increased timeout
                if image_content_response.status_code == 200:
                    with Image.open(io.BytesIO(image_content_response.content)) as image_from_web:
                        image_format = image_from_web.format.lower() if image_from_web.format else 'jpg' # Default to jpg

                        if keep_filenames:
                            o = urlparse(image_url)
                            base_name = os.path.basename(o.path)
                            name_part, ext_part = os.path.splitext(base_name)
                            # Use actual image format for the extension
                            filename = f"{name_part if name_part else search_string_for_filename + str(indx)}.{image_format}"
                        else:
                            filename = f"{search_string_for_filename}{str(indx)}.{image_format}"
                        
                        actual_image_path_to_save = os.path.join(self.image_path, filename)

                        # Actual cache check with determined filename
                        if os.path.exists(actual_image_path_to_save):
                            print(f"[INFO] Image {actual_image_path_to_save} already exists. Skipping download.")
                            current_dl_checkpoint_data = {
                                'search_key': self.search_key,
                                'all_image_urls_hash': hash(tuple(image_urls)),
                                'last_downloaded_index': indx,
                                'total_urls_to_download': len(image_urls)
                            }
                            save_json_data(self.download_checkpoint_file, current_dl_checkpoint_data)
                            saved_count +=1
                            continue

                        image_resolution = image_from_web.size
                        if image_resolution:
                            if not (self.min_resolution[0] <= image_resolution[0] <= self.max_resolution[0] and \
                                    self.min_resolution[1] <= image_resolution[1] <= self.max_resolution[1]):
                                print(f"[INFO] Image {filename} resolution {image_resolution} out of range ({self.min_resolution}-{self.max_resolution}). Skipping save.")
                                current_dl_checkpoint_data = {
                                    'search_key': self.search_key,
                                    'all_image_urls_hash': hash(tuple(image_urls)),
                                    'last_downloaded_index': indx,
                                    'total_urls_to_download': len(image_urls)
                                }
                                save_json_data(self.download_checkpoint_file, current_dl_checkpoint_data)
                                continue

                        try:
                            image_from_web.save(actual_image_path_to_save)
                            print(f"[INFO] {self.search_key} \t Image {indx+1}/{len(image_urls)} saved at: {actual_image_path_to_save}")
                            saved_count += 1
                        except OSError as e_save:
                            print(f"[WARN] OSError saving {actual_image_path_to_save}. Attempting to convert to RGB. Error: {e_save}")
                            try:
                                rgb_im = image_from_web.convert('RGB')
                                fn, _ = os.path.splitext(actual_image_path_to_save)
                                # Ensure the new path for RGB uses .jpg
                                rgb_save_path = f"{fn}.jpg"
                                if actual_image_path_to_save.lower() == rgb_save_path.lower() and image_format != 'jpeg' and image_format != 'jpg':
                                     # Avoid overwriting if original was already jpg but failed, or if it's a non-jpg format that failed.
                                     # This case might need more specific handling if original was e.g. png and failed, then converting to jpg.
                                     # If original was png, actual_image_path_to_save would be .png. rgb_save_path would be .jpg.
                                     pass # This is fine, different filenames

                                rgb_im.save(rgb_save_path)
                                print(f"[INFO] {self.search_key} \t Image {indx+1}/{len(image_urls)} (converted to RGB) saved at: {rgb_save_path}")
                                saved_count += 1
                            except Exception as e_convert_save:
                                print(f"[ERROR] Failed to convert and save {actual_image_path_to_save} as RGB: {e_convert_save}")
                        
                        # Update download checkpoint
                        current_dl_checkpoint_data = {
                            'search_key': self.search_key,
                            'all_image_urls_hash': hash(tuple(image_urls)),
                            'last_downloaded_index': indx,
                            'total_urls_to_download': len(image_urls)
                        }
                        save_json_data(self.download_checkpoint_file, current_dl_checkpoint_data)

                else: # status_code != 200
                    print(f"[ERROR] Failed to download image {image_url}. Status code: {image_content_response.status_code}")
                    current_dl_checkpoint_data = {
                        'search_key': self.search_key,
                        'all_image_urls_hash': hash(tuple(image_urls)),
                        'last_downloaded_index': indx,
                        'total_urls_to_download': len(image_urls)
                    }
                    save_json_data(self.download_checkpoint_file, current_dl_checkpoint_data)

            except requests.exceptions.RequestException as e_req:
                print(f"[ERROR] Download failed for {image_url} (RequestException): {e_req}")
                current_dl_checkpoint_data = {
                    'search_key': self.search_key,
                    'all_image_urls_hash': hash(tuple(image_urls)),
                    'last_downloaded_index': indx,
                    'total_urls_to_download': len(image_urls)
                }
                save_json_data(self.download_checkpoint_file, current_dl_checkpoint_data)
            except Exception as e:
                print(f"[ERROR] An unexpected error occurred while processing {image_url}: {e}")
                current_dl_checkpoint_data = {
                    'search_key': self.search_key,
                    'all_image_urls_hash': hash(tuple(image_urls)),
                    'last_downloaded_index': indx,
                    'total_urls_to_download': len(image_urls)
                }
                save_json_data(self.download_checkpoint_file, current_dl_checkpoint_data)

        print("--------------------------------------------------")
        if saved_count > 0:
            print(f"[INFO] {saved_count} new images downloaded for '{self.search_key}'.")
        else:
            print(f"[INFO] No new images were downloaded for '{self.search_key}' in this session.")
        
        # Check if all URLs were processed by comparing the last processed index
        all_processed = False
        final_checkpoint = load_json_data(self.download_checkpoint_file)
        if final_checkpoint and final_checkpoint.get('last_downloaded_index', -1) == len(image_urls) - 1:
            all_processed = True
        
        if not image_urls and not os.path.exists(self.download_checkpoint_file): # No URLs and no checkpoint means nothing to do.
            pass # No need to print about clearing checkpoint if it never existed for this run.
        elif all_processed :
            remove_file_if_exists(self.download_checkpoint_file)
            print(f"[INFO] All image downloads processed for '{self.search_key}'. Download checkpoint cleared.")
        else:
            # This case means either not all URLs were processed, or there were no URLs to begin with but a checkpoint might exist.
            if image_urls: # Only print if there were URLs to process
                 print(f"[INFO] Download process for '{self.search_key}' potentially incomplete or interrupted. Checkpoint retained.")
            elif os.path.exists(self.download_checkpoint_file): # No URLs, but an old checkpoint exists
                 remove_file_if_exists(self.download_checkpoint_file) # Clean up old checkpoint if no URLs were given
                 print(f"[INFO] No image URLs provided. Old download checkpoint for '{self.search_key}' cleared.")


        print("[INFO] Image saving process completed. Please note that some photos may not have been downloaded due to errors, format issues, or resolution constraints.")
