import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import patch

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
        print(f"[INFO] Using Chrome browser binary at: {self.config.chrome_binary_path}")

        # 2. Handle ChromeDriver (chromedriver.exe)
        #    It's expected to be at self.config.webdriver_path (e.g., ./webdriver/chromedriver.exe)
        if not os.path.isfile(self.config.webdriver_path):
            print(f"[INFO] ChromeDriver executable not found at the configured path: {self.config.webdriver_path}.")
            print(f"[INFO] Attempting to download/patch ChromeDriver suitable for Chrome at '{self.config.chrome_binary_path}'.")
            
            # Assuming patch.py's download_lastest_chromedriver can take chrome_exe_path
            # to determine the correct browser version for which to download chromedriver.
            # If patch.py is simpler, it might just download the "latest stable" chromedriver.
            is_patched = patch.download_lastest_chromedriver(chrome_exe_path=self.config.chrome_binary_path)
            if not is_patched:
                raise RuntimeError(
                    f"ChromeDriver auto-patching/download failed. Attempted to place/update at '{self.config.webdriver_path}'. "
                    "Ensure the target directory is writable, check network connectivity, and that a suitable ChromeDriver exists for your Chrome version."
                )
            print(f"[INFO] ChromeDriver patched/downloaded to: {self.config.webdriver_path}")
        else:
            print(f"[INFO] Found existing ChromeDriver at: {self.config.webdriver_path}")


        # 3. Attempt to initialize WebDriver (with retries for version mismatch patching if an existing chromedriver was found but is wrong)
        for attempt in range(2):
            try:
                options = Options()
                # Crucially, set the binary_location for Selenium to use the correct Chrome browser
                options.binary_location = self.config.chrome_binary_path
                
                if self.config.headless:
                    options.add_argument('--headless')
                
                print(f"[INFO] Attempting to launch WebDriver (attempt {attempt + 1})...")
                print(f"       Using ChromeDriver: {self.config.webdriver_path}")
                print(f"       Targeting Chrome Browser: {options.binary_location}")

                current_driver = webdriver.Chrome(executable_path=self.config.webdriver_path, options=options)
                current_driver.set_window_size(1400, 1050) # Consider making this configurable
                current_driver.get("https://www.google.com") # To accept cookies etc.

                try: # Handle cookie consent dialog
                    WebDriverWait(current_driver, 5).until(EC.element_to_be_clickable((By.ID, "W0wltc"))).click()
                except Exception as e_cookie:
                    print(f"[INFO] Cookie consent dialog not found/clickable on google.com: {e_cookie}")
                
                self.driver = current_driver
                print("[INFO] WebDriver initialized successfully by WebDriverManager.")
                return # Successfully initialized self.driver
            except Exception as e:
                print(f"[WARN] Error initializing WebDriver (attempt {attempt + 1}): {e}")
                if attempt == 0: # Only try specific version patching on the first Selenium instantiation failure
                    # This error often indicates a ChromeDriver/Chrome browser version mismatch.
                    # Try to extract the required Chrome browser version from the error message if possible.
                    version_hint_from_error = None
                    match = re.search(r"This version of ChromeDriver only supports Chrome version (\d+)", str(e), re.IGNORECASE)
                    if match:
                        version_hint_from_error = match.group(1) # e.g., "114"
                        print(f"[INFO] Error suggests ChromeDriver supports Chrome version {version_hint_from_error}.")
                    
                    print(f"[INFO] Attempting to re-patch ChromeDriver. This will try to match Chrome at '{self.config.chrome_binary_path}' or use hint '{version_hint_from_error}'.")
                    # Pass chrome_exe_path for primary version detection, and version_hint_from_error as a secondary hint.
                    if patch.download_lastest_chromedriver(chrome_exe_path=self.config.chrome_binary_path, required_version=version_hint_from_error):
                        print("[INFO] ChromeDriver re-patched after error, retrying WebDriver initialization...")
                        continue # Retry the loop with the (hopefully) corrected ChromeDriver
                    else:
                        print("[WARN] ChromeDriver re-patch attempt after error failed. Will not retry patch.")
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
                print("[INFO] WebDriver closed by WebDriverManager.")
            except Exception as e:
                print(f"[WARN] Error quitting WebDriver in WebDriverManager: {e}")
            finally:
                self.driver = None
        else:
            print("[INFO] No active WebDriver instance to close in WebDriverManager.")