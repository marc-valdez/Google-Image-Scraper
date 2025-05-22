from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, StaleElementReferenceException,
    TimeoutException, WebDriverException
)
from src.logging.logger import logger
from src.utils.cache_utils import load_json_data, save_json_data
import time, random

def exponential_backoff(attempt, base=1, max_d=60):
    return min(base * (2 ** attempt), max_d) + random.uniform(0, 0.1)

class UrlFetcher:
    def __init__(self, config, webdriver_manager):
        self.config = config
        self.driver = webdriver_manager.driver
        self.search_key = config.search_key_for_query
        self.target = config.number_of_images
        self.cache_file = config.get_url_cache_file()
        self.search_url = f"https://www.google.com/search?q={self.search_key}&source=lnms&tbm=isch&sa=X&ved=2ahUKEwie44_AnqLpAhUhBWMBHUFGD90Q_AUoAXoECBUQAw&biw=1920&bih=947"

    def find_image_urls(self):
        logger.status(f"Searching '{self.search_key}'")
        urls = []
        cache = load_json_data(self.cache_file)
        if cache and cache.get('search_key') == self.search_key:
            urls = list(dict.fromkeys(cache.get('urls', [])))
            if len(urls) >= self.target:
                logger.success(f"Loaded {self.target} cached images")
                return urls[:self.target]
            logger.info(f"Found {len(urls)} cached - fetching {self.target - len(urls)} more")

        self.driver.get(self.search_url)
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "img")))

        logger.start_progress(self.target - len(urls), f"Finding images for '{self.search_key}'")
        class_names = ["n3VNCb", "iPVvYb", "r48jcc", "pT0Scc", "H8Rx8c"]
        seen = set(urls)
        idx, attempt = 1, 0

        while len(urls) < self.target:
            try:
                xpath = f'//*[@id="rso"]/div/div/div[1]/div/div/div[{idx}]/div[2]/h3/a/div/div/div/g-img'
                try:
                    img = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath)))
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", img)
                    try:
                        WebDriverWait(self.driver, 2).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                        img.click()
                    except WebDriverException:
                        self.driver.execute_script("arguments[0].click();", img)
                except TimeoutException:
                    raise NoSuchElementException()

                time.sleep(random.uniform(1.0, 2.0))
                for cls in class_names:
                    for el in self.driver.find_elements(By.CLASS_NAME, cls):
                        src = el.get_attribute("src")
                        if src and "http" in src and "encrypted" not in src and src not in seen:
                            urls.append(src)
                            seen.add(src)
                            logger.info(f"Image {len(urls)}: {logger.truncate_url(src)}")
                            logger.update_progress()
                            save_json_data(self.cache_file, {
                                'search_key': self.search_key,
                                'number_of_images_requested': self.target,
                                'urls_found_count': len(urls),
                                'urls': urls
                            })
                            break

                idx += 1
                if idx % 5 == 0:
                    self.driver.execute_script(f"window.scrollBy(0, {random.randint(400, 600)});")
                    time.sleep(random.uniform(0.3, 0.7))
                if idx % 15 == 0:
                    try:
                        btn = self.driver.find_element(By.CLASS_NAME, "mye4qd")
                        if btn.is_displayed() and btn.is_enabled():
                            btn.click()
                            time.sleep(3)
                    except: pass

            except (NoSuchElementException, StaleElementReferenceException):
                attempt += 1
                time.sleep(exponential_backoff(attempt))
            except WebDriverException as e:
                logger.warning(f"WebDriver error: {e}")
                attempt += 1
                time.sleep(exponential_backoff(attempt))
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                attempt += 1
                time.sleep(exponential_backoff(attempt))

        logger.complete_progress()
        logger.success(f"Found {len(urls)} images")
        return urls[:self.target]
