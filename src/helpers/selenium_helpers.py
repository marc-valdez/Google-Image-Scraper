import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, StaleElementReferenceException,
    TimeoutException, WebDriverException
)
from src.logging.logger import logger
import config as cfg


def click_thumbnail_element(driver, item_xpath: str, item_element, img_thumbnail_element, worker_id: int):
    try:
        WebDriverWait(item_element, 3).until(
            EC.element_to_be_clickable((By.XPATH, ".//g-img"))
        ).click()
    except (WebDriverException, StaleElementReferenceException):
        try:
            fresh_element = driver.find_element(By.XPATH, item_xpath)
            fresh_img = fresh_element.find_element(By.XPATH, ".//g-img")
            driver.execute_script("arguments[0].click();", fresh_img)
        except (NoSuchElementException, StaleElementReferenceException):
            driver.execute_script("arguments[0].click();", img_thumbnail_element)


def extract_high_res_urls(driver, high_res_selectors: list):
    found_urls = []
    for cls in high_res_selectors:
        for el in driver.find_elements(By.CLASS_NAME, cls):
            src = el.get_attribute("src")
            if src and "http" in src and "encrypted" not in src:
                found_urls.append(src)
    return found_urls


def perform_periodic_scroll(driver, xpath_index: int):
    if xpath_index % 5 == 0:
        driver.execute_script(f"window.scrollBy(0, {random.randint(400, 600)});")
        time.sleep(random.uniform(0.3, 0.7))


def refresh_page_if_needed(driver, xpath_index: int, worker_id: int):
    if xpath_index > 0 and xpath_index % cfg.BROWSER_REFRESH_INTERVAL == 0:
        logger.info(f"[Worker {worker_id}] Refreshing page at index {xpath_index} to prevent stale elements.")
        driver.refresh()
        WebDriverWait(driver, cfg.PAGE_LOAD_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "img"))
        )
        time.sleep(random.uniform(2.0, 4.0))


def attempt_recovery_scroll(driver, xpath_index: int, worker_id: int):
    try:
        logger.info(f"[Worker {worker_id}] Recovery: Scrolling to bottom to load more images...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(3.0, 5.0))
        
        available_items = driver.find_elements(By.XPATH, '//*[@id="rso"]//g-img')
        if len(available_items) == 0:
            logger.warning(f"[Worker {worker_id}] No more images found in viewport. May have reached end of results.")
            return 2  # Heavy penalty
        else:
            logger.info(f"[Worker {worker_id}] Found {len(available_items)} images in current viewport after recovery scroll.")
            return 0  # No penalty
    except Exception as recovery_e:
        logger.warning(f"[Worker {worker_id}] Recovery attempt failed: {recovery_e}")
        return 1  # Light penalty


def is_related_searches_block(item_element):
    item_classes = item_element.get_attribute("class") or ""
    return "BA0zte" in item_classes.split()


def get_progressive_timeout(xpath_index: int):
    return min(10, 5 + (xpath_index // 100))