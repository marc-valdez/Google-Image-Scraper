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
    def __init__(self, existing_driver=None):
        self.driver = existing_driver
        # self.managed_driver is True if this instance is responsible for creating and quitting the driver.
        self.managed_driver = False 

        if self.driver:
            logger.info("WebDriverManager is using an existing WebDriver instance.")
        else:
            self._initialize_driver_instance()
            self.managed_driver = True

    def _initialize_driver_instance(self):
        if not cfg.CHROME_BINARY_PATH or not os.path.isfile(cfg.CHROME_BINARY_PATH):
            raise RuntimeError(
                f"Chrome browser binary path ('{cfg.CHROME_BINARY_PATH}') is not configured or invalid. "
                "Ensure Chrome is installed and CHROME_BINARY_PATH is correctly set."
            )
        logger.info(f"Using Chrome browser at: {cfg.CHROME_BINARY_PATH}")

        # Ensure ChromeDriver is available, attempting to patch/download if not found.
        if not cfg.WEBDRIVER_PATH or not os.path.isfile(cfg.WEBDRIVER_PATH):
            original_webdriver_path_cfg = cfg.WEBDRIVER_PATH # Store for logging/error messages
            logger.info(f"ChromeDriver not found at configured path: {original_webdriver_path_cfg}. Attempting download.")
            
            if not patch.download_lastest_chromedriver(chrome_path=cfg.CHROME_BINARY_PATH):
                raise RuntimeError(
                    f"ChromeDriver auto-patching/download failed. Attempted for path: '{original_webdriver_path_cfg}'. "
                    "Check permissions, network, and Chrome/ChromeDriver compatibility."
                )
            
            # After patching, patch.py should ideally update cfg.WEBDRIVER_PATH or return the new path.
            # If not, we construct an expected path.
            expected_path_after_patch = os.path.join(os.getcwd(), "webdriver", patch.webdriver_executable())
            if os.path.isfile(expected_path_after_patch):
                cfg.WEBDRIVER_PATH = expected_path_after_patch
            elif not cfg.WEBDRIVER_PATH or not os.path.isfile(cfg.WEBDRIVER_PATH): # If still not valid
                raise RuntimeError(f"ChromeDriver still not found at '{cfg.WEBDRIVER_PATH}' or '{expected_path_after_patch}' after patching attempt.")
            logger.success(f"ChromeDriver installed/verified at: {cfg.WEBDRIVER_PATH}")
        else:
            logger.info(f"Found existing ChromeDriver: {cfg.WEBDRIVER_PATH}")

        # Attempt to initialize WebDriver, with one retry if the first attempt fails due to version mismatch.
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
                
                logger.info(f"Initializing WebDriver (attempt {attempt + 1}) with ChromeDriver: {cfg.WEBDRIVER_PATH}")

                service = ChromeService(
                    executable_path=cfg.WEBDRIVER_PATH,
                    log_path=os.devnull # Suppress verbose chromedriver console output
                )
                current_driver = webdriver.Chrome(service=service, options=options)
                current_driver.set_window_size(1400, 1050)
                current_driver.get("https://www.google.com") # Initial navigation to verify and handle cookies

                # Attempt to dismiss cookie consent dialog if it appears
                try:
                    WebDriverWait(current_driver, 5).until(EC.element_to_be_clickable((By.ID, "W0wltc"))).click()
                except Exception:
                    logger.info("No cookie consent dialog found or interaction failed (this is often OK).")
                
                self.driver = current_driver
                logger.info("WebDriver initialized successfully")
                return 
            except Exception as e:
                logger.warning(f"WebDriver initialization failed (attempt {attempt + 1}): {e}")
                if attempt == 0: # Only re-patch on the first failed attempt
                    version_hint_from_error = None
                    match = re.search(r"This version of ChromeDriver only supports Chrome version (\d+)", str(e), re.IGNORECASE)
                    if match:
                        version_hint_from_error = match.group(1)
                        logger.info(f"Error suggests ChromeDriver needs Chrome version {version_hint_from_error}")
                     
                    logger.info(f"Attempting to re-patch ChromeDriver (target version hint: {version_hint_from_error or 'latest'})")
                    if patch.download_lastest_chromedriver(
                        chrome_path=cfg.CHROME_BINARY_PATH,
                        required_version=version_hint_from_error
                    ):
                        # Re-verify path after re-patch, similar to initial check
                        expected_path_after_repatch = os.path.join(os.getcwd(), "webdriver", patch.webdriver_executable())
                        if os.path.isfile(expected_path_after_repatch):
                            cfg.WEBDRIVER_PATH = expected_path_after_repatch
                        logger.info("ChromeDriver re-patched. Retrying WebDriver initialization.")
                        continue 
                    else:
                        logger.warning("ChromeDriver re-patch failed. Further attempts may also fail.")
                        break # Stop if re-patch itself fails
        
        raise RuntimeError(
            f"Failed to initialize WebDriver after all attempts. Last tried ChromeDriver: '{cfg.WEBDRIVER_PATH}'. "
            "Check Chrome/ChromeDriver compatibility, paths, and permissions."
        )

    def _is_driver_active(self):
        if not self.driver:
            return False
        try:
            _ = self.driver.current_url # A simple check to see if the driver session is responsive
            return True
        except Exception: 
            return False

    def close_driver(self):
        # Only quit the driver if this WebDriverManager instance created it.
        # If an existing_driver was passed in, this instance does not own it.
        if self.managed_driver and self.driver: 
            try:
                self.driver.quit()
                logger.info("WebDriver instance (managed by this manager) has been closed.")
            except Exception as e:
                logger.warning(f"Error closing managed WebDriver: {e}")
            finally:
                self.driver = None # Ensure driver attribute is cleared
        elif self.driver:
            logger.info("WebDriverManager is using an externally managed driver. It will not be closed by this instance.")
        else:
            logger.info("No active WebDriver to close, or it was not managed by this instance.")