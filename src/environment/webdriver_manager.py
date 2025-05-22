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

class WebDriverManager:
    def __init__(self, config):
        self.config = config
        self.driver = None
        self._initialize_driver_instance()

    def _initialize_driver_instance(self):
        """
        Initializes the Selenium WebDriver instance.
        Ensures Chrome browser is found, then manages ChromeDriver patching and setup.
        Sets self.driver or raises RuntimeError if unsuccessful.
        """
        # 1. Ensure Chrome Browser itself is found (via ScraperConfig's efforts)
        if not self.config.chrome_binary_path:
            raise RuntimeError(
                "Chrome browser binary path not set in config and could not be auto-detected. "
                "Please ensure Chrome is installed and accessible, or explicitly provide 'chrome_binary_path' in ScraperConfig. "
                "Cannot proceed to download/manage ChromeDriver without a target Chrome browser."
            )
        
        if not os.path.isfile(self.config.chrome_binary_path):
            raise RuntimeError(
                f"The configured Chrome browser binary path does not exist or is not a file: '{self.config.chrome_binary_path}'. "
                "Please check the path in ScraperConfig."
            )
        logger.info(f"Using Chrome browser at: {self.config.chrome_binary_path}")

        # 2. Handle ChromeDriver (chromedriver.exe)
        #    It's expected to be at self.config.webdriver_path (e.g., ./webdriver/chromedriver.exe)
        if not os.path.isfile(self.config.webdriver_path):
            logger.info(f"ChromeDriver not found at: {self.config.webdriver_path}")
            logger.info("Attempting to download compatible ChromeDriver")
            
            # Pass Chrome binary path to help determine correct version
            is_patched = patch.download_lastest_chromedriver(chrome_path=self.config.chrome_binary_path)
            if not is_patched:
                raise RuntimeError(
                    f"ChromeDriver auto-patching/download failed. Attempted to place/update at '{self.config.webdriver_path}'. "
                    "Ensure the target directory is writable, check network connectivity, and that a suitable ChromeDriver exists for your Chrome version."
                )
            logger.success(f"ChromeDriver installed at: {self.config.webdriver_path}")
        else:
            logger.info(f"Found existing ChromeDriver: {self.config.webdriver_path}")

        # 3. Attempt to initialize WebDriver (with retries for version mismatch patching if an existing chromedriver was found but is wrong)
        for attempt in range(2):
            try:
                options = Options()
                # Crucially, set the binary_location for Selenium to use the correct Chrome browser
                options.binary_location = self.config.chrome_binary_path
                
                # Suppress Chrome logging and warnings
                options.add_experimental_option('excludeSwitches', ['enable-logging'])
                options.add_argument('--log-level=3')  # Only show fatal errors
                options.add_argument('--silent')
                options.add_argument('--disable-logging')
                options.add_argument('--disable-dev-shm-usage')
                # Suppress specific warnings
                options.add_argument('--disable-gpu')  # Disables GPU hardware acceleration
                options.add_argument('--no-sandbox')  # Disables the sandbox for all process types
                options.add_argument('--disable-extensions')  # Disables extensions
                options.add_argument('--disable-software-rasterizer')  # Disables software rasterizer
                # Suppress voice transcription warnings
                options.add_experimental_option('prefs', {
                    'enable_media_stream': False,
                    'enable_logging': False,
                    'profile.default_content_settings.media_stream_mic': 2,  # 2=block
                    'profile.default_content_settings.media_stream_camera': 2  # 2=block
                })
                
                if self.config.headless:
                    options.add_argument('--headless')
                
                logger.info(f"Initializing WebDriver (attempt {attempt + 1})")
                logger.info(f"ChromeDriver: {self.config.webdriver_path}")
                logger.info(f"Chrome Browser: {options.binary_location}")

                # Initialize ChromeDriver with proper selenium 4.x syntax
                service = ChromeService(
                    executable_path=self.config.webdriver_path,
                    log_path=os.devnull
                )
                current_driver = webdriver.Chrome(service=service, options=options)
                current_driver.set_window_size(1400, 1050) # Consider making this configurable
                current_driver.get("https://www.google.com") # To accept cookies etc.

                try: # Handle cookie consent dialog
                    WebDriverWait(current_driver, 5).until(EC.element_to_be_clickable((By.ID, "W0wltc"))).click()
                except Exception as e_cookie:
                    logger.info("No cookie consent dialog found")
                
                self.driver = current_driver
                logger.info("WebDriver initialized successfully")
                return # Successfully initialized self.driver
            except Exception as e:
                logger.warning(f"WebDriver initialization failed (attempt {attempt + 1}): {e}")
                if attempt == 0: # Only try specific version patching on the first Selenium instantiation failure
                    # This error often indicates a ChromeDriver/Chrome browser version mismatch.
                    # Try to extract the required Chrome browser version from the error message if possible.
                    version_hint_from_error = None
                    match = re.search(r"This version of ChromeDriver only supports Chrome version (\d+)", str(e), re.IGNORECASE)
                    if match:
                        version_hint_from_error = match.group(1) # e.g., "114"
                        logger.info(f"ChromeDriver supports Chrome version {version_hint_from_error}")
                     
                    logger.info(f"Re-patching ChromeDriver to match Chrome version")
                    # Pass both chrome_path and required_version for more accurate matching
                    if patch.download_lastest_chromedriver(
                        chrome_path=self.config.chrome_binary_path,
                        required_version=version_hint_from_error
                    ):
                        logger.info("ChromeDriver re-patched successfully - retrying")
                        continue # Retry the loop with the (hopefully) corrected ChromeDriver
                    else:
                        logger.warning("ChromeDriver re-patch failed")
                        break # Break from retry loop if re-patch fails
                # If it's the second attempt (attempt == 1) and it failed, or if re-patch failed on first attempt, we fall through.
        
        # If loop completes without returning, initialization has failed
        raise RuntimeError(
            "[ERR] Failed to initialize WebDriver after all attempts. "
            f"Tried with ChromeDriver: '{self.config.webdriver_path}' and Chrome Browser: '{self.config.chrome_binary_path}'. "
            "Common issues: ChromeDriver/Chrome version mismatch, incorrect paths, permissions, or network issues during patching. "
            "Please ensure Chrome is installed correctly and a compatible ChromeDriver is available or can be downloaded."
        )

    def _is_driver_active(self):
        if not self.driver:
            return False
        try:
            # A lightweight way to check if the driver is still responsive
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