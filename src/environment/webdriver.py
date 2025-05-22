import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from src.logging.logger import logger
from src.environment import patch
import config as cfg

class WebDriverManager:
    def __init__(self):
        self.driver = None
        self._initialize_driver_instance()

    def _initialize_driver_instance(self):
        if not cfg.CHROME_BINARY_PATH:
            raise RuntimeError(
                "Chrome browser binary path not set in config and could not be auto-detected. "
                "Please ensure Chrome is installed and accessible, or explicitly provide 'CHROME_BINARY_PATH' in src/helpers/config.py. "
                "Cannot proceed to download/manage ChromeDriver without a target Chrome browser."
            )
        
        if not os.path.isfile(cfg.CHROME_BINARY_PATH):
            raise RuntimeError(
                f"The configured Chrome browser binary path does not exist or is not a file: '{cfg.CHROME_BINARY_PATH}'. "
                "Please check the path in src/helpers/config.py."
            )
        logger.info(f"Using Chrome browser at: {cfg.CHROME_BINARY_PATH}")

        if not cfg.WEBDRIVER_PATH or not os.path.isfile(cfg.WEBDRIVER_PATH):
            webdriver_path_to_check = cfg.WEBDRIVER_PATH or "./webdriver/chromedriver.exe"
            logger.info(f"ChromeDriver not found at: {webdriver_path_to_check}")
            logger.info("Attempting to download compatible ChromeDriver")
            
            is_patched = patch.download_lastest_chromedriver(chrome_path=cfg.CHROME_BINARY_PATH)
            if not is_patched:
                raise RuntimeError(
                    f"ChromeDriver auto-patching/download failed. Attempted to place/update at '{webdriver_path_to_check}'. "
                    "Ensure the target directory is writable, check network connectivity, and that a suitable ChromeDriver exists for your Chrome version."
                )
            
            if not cfg.WEBDRIVER_PATH or not os.path.isfile(cfg.WEBDRIVER_PATH):
                resolved_webdriver_path = patch.get_expected_chromedriver_path() 
                if not os.path.isfile(resolved_webdriver_path):
                    raise RuntimeError("ChromeDriver still not found after patching attempt.")
                cfg.WEBDRIVER_PATH = resolved_webdriver_path

            logger.success(f"ChromeDriver installed/verified at: {cfg.WEBDRIVER_PATH}")
        else:
            logger.info(f"Found existing ChromeDriver: {cfg.WEBDRIVER_PATH}")

        for attempt in range(2):
            try:
                options = Options()
                options.binary_location = cfg.CHROME_BINARY_PATH
                
                options.add_experimental_option('excludeSwitches', ['enable-logging'])
                options.add_argument('--log-level=3')
                options.add_argument('--silent')
                options.add_argument('--disable-logging')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-extensions')
                options.add_argument('--disable-software-rasterizer')
                options.add_experimental_option('prefs', {
                    'enable_media_stream': False,
                    'enable_logging': False,
                    'profile.default_content_settings.media_stream_mic': 2,
                    'profile.default_content_settings.media_stream_camera': 2
                })
                
                if cfg.HEADLESS_MODE:
                    options.add_argument('--headless')
                
                logger.info(f"Initializing WebDriver (attempt {attempt + 1})")
                logger.info(f"ChromeDriver: {cfg.WEBDRIVER_PATH}")
                logger.info(f"Chrome Browser: {options.binary_location}")

                service = ChromeService(
                    executable_path=cfg.WEBDRIVER_PATH,
                    log_path=os.devnull
                )
                current_driver = webdriver.Chrome(service=service, options=options)
                current_driver.set_window_size(1400, 1050)
                current_driver.get("https://www.google.com")

                try:
                    WebDriverWait(current_driver, 5).until(EC.element_to_be_clickable((By.ID, "W0wltc"))).click()
                except Exception:
                    logger.info("No cookie consent dialog found")
                
                self.driver = current_driver
                logger.info("WebDriver initialized successfully")
                return
            except Exception as e:
                logger.warning(f"WebDriver initialization failed (attempt {attempt + 1}): {e}")
                if attempt == 0:
                    version_hint_from_error = None
                    match = re.search(r"This version of ChromeDriver only supports Chrome version (\d+)", str(e), re.IGNORECASE)
                    if match:
                        version_hint_from_error = match.group(1)
                        logger.info(f"ChromeDriver supports Chrome version {version_hint_from_error}")
                     
                    logger.info(f"Re-patching ChromeDriver to match Chrome version")
                    if patch.download_lastest_chromedriver(
                        chrome_path=cfg.CHROME_BINARY_PATH,
                        required_version=version_hint_from_error
                    ):
                        resolved_webdriver_path = patch.get_expected_chromedriver_path()
                        if os.path.isfile(resolved_webdriver_path):
                            cfg.WEBDRIVER_PATH = resolved_webdriver_path
                        logger.info("ChromeDriver re-patched successfully - retrying")
                        continue
                    else:
                        logger.warning("ChromeDriver re-patch failed")
                        break
        
        raise RuntimeError(
            "[ERR] Failed to initialize WebDriver after all attempts. "
            f"Tried with ChromeDriver: '{cfg.WEBDRIVER_PATH}' and Chrome Browser: '{cfg.CHROME_BINARY_PATH}'. "
            "Common issues: ChromeDriver/Chrome version mismatch, incorrect paths, permissions, or network issues during patching. "
            "Please ensure Chrome is installed correctly and a compatible ChromeDriver is available or can be downloaded."
        )

    def _is_driver_active(self):
        if not self.driver:
            return False
        try:
            _ = self.driver.current_url
            return True
        except Exception:
            return False

    def close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed")
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None
        else:
            logger.info("No active WebDriver to close")