import os
import configparser
from chrome_finder import ChromeFinder

class ScraperConfig:
    DEFAULT_SETTINGS_FILE = 'settings.ini' # Default INI file name

    def _load_settings_from_ini(self, ini_file_path):
        """Loads configuration from an INI file and returns them as a dictionary."""
        parser = configparser.ConfigParser()
        # Store default values that we expect from INI, helps with type conversion and fallbacks
        # These are string representations as they come from INI
        ini_defaults = {
            'number_of_images': '1', # Default to 1 if not in INI and not overridden
            'max_missed': '10',
            'headless': 'True',
            'webdriver_path': '', # Empty string means "not set in INI"
            'chrome_binary_path': '',
            'advanced_suffix': '',
            # 'base_output_dir': 'output', # This is more of a main.py concern
            # 'categories_file': 'categories.json', # Also main.py concern
            # 'workers': '2', # Also main.py concern
            # 'keep_filenames': 'False' # Also main.py concern
        }
        
        loaded_values = {}
        if not os.path.exists(ini_file_path):
            print(f"[CONFIG_INFO] Settings file '{ini_file_path}' not found. Will rely on constructor arguments and internal defaults.")
            return loaded_values # Return empty dict if file not found

        try:
            parser.read(ini_file_path)
            print(f"[CONFIG_INFO] Successfully read settings from {ini_file_path}")

            if 'General' in parser:
                g = parser['General']
                loaded_values['number_of_images'] = g.getint('number_of_images', fallback=int(ini_defaults['number_of_images']))
                loaded_values['max_missed'] = g.getint('max_missed', fallback=int(ini_defaults['max_missed']))
                loaded_values['advanced_suffix'] = g.get('advanced_suffix', fallback=ini_defaults['advanced_suffix'])
                # Note: 'workers' and 'keep_filenames' are handled by main.py's argparse from INI

            if 'WebDriver' in parser:
                wd = parser['WebDriver']
                # Get path as string, allow empty. If empty, it means "not set by INI".
                loaded_values['webdriver_path'] = wd.get('webdriver_path', fallback=ini_defaults['webdriver_path']).strip()
                loaded_values['chrome_binary_path'] = wd.get('chrome_binary_path', fallback=ini_defaults['chrome_binary_path']).strip()
                loaded_values['headless'] = wd.getboolean('headless', fallback=ini_defaults['headless'].lower() == 'true')
            
            # 'Paths' section from INI is primarily for main.py, not directly consumed by ScraperConfig's core attributes.
            # main.py will read these and pass relevant ones (like base_output_dir to construct image_path)

        except Exception as e:
            print(f"[CONFIG_WARN] Error parsing {ini_file_path}: {e}. Using constructor arguments or internal defaults.")
        
        return loaded_values

    def __init__(self,
                 image_path,                 # Required: Specific path for this scraper instance's output
                 search_key,                 # Required: Specific search key for this instance
                 webdriver_path=None,        # Optional: Can be overridden by INI or constructor
                 number_of_images=None,      # Optional
                 headless=None,              # Optional
                 max_missed=None,            # Optional
                 chrome_binary_path=None,    # Optional
                 advanced_suffix=None,       # Optional
                 settings_file_path=None):   # Optional: Path to INI file

        # Determine the settings file to use
        actual_settings_file = settings_file_path or self.DEFAULT_SETTINGS_FILE
        ini_values = self._load_settings_from_ini(actual_settings_file)

        # --- Resolve parameters with priority: Constructor Arg > INI Value > Internal Default ---

        # webdriver_path
        resolved_webdriver_path = webdriver_path # Constructor arg
        if resolved_webdriver_path is None: # Not given in constructor
            resolved_webdriver_path = ini_values.get('webdriver_path') # Try INI
            if not resolved_webdriver_path: # Empty string from INI means not set
                resolved_webdriver_path = None
        
        default_driver_dir = os.path.join(os.getcwd(), "webdriver")
        default_driver_exe_path = os.path.join(default_driver_dir, "chromedriver.exe")

        if resolved_webdriver_path:
            webdriver_path_dir = os.path.dirname(resolved_webdriver_path)
            if os.path.isdir(webdriver_path_dir):
                self.webdriver_path = resolved_webdriver_path
                source = "Constructor/CLI" if webdriver_path is not None else "INI"
                print(f"[CONFIG_INFO] Using webdriver_path: {self.webdriver_path} (Source: {source})")
            else:
                print(f"[CONFIG_WARN] Provided/INI webdriver_path directory '{webdriver_path_dir}' not found. Defaulting to: {default_driver_exe_path}.")
                self.webdriver_path = default_driver_exe_path
        else: # No constructor arg, no valid INI value
            print(f"[CONFIG_INFO] webdriver_path not set by constructor or INI. Defaulting to: {default_driver_exe_path}.")
            self.webdriver_path = default_driver_exe_path
        
        webdriver_parent_dir = os.path.dirname(self.webdriver_path)
        if not os.path.exists(webdriver_parent_dir):
            try:
                os.makedirs(webdriver_parent_dir, exist_ok=True)
                print(f"[CONFIG_INFO] Created directory for webdriver: {webdriver_parent_dir}")
            except OSError as e:
                print(f"[CONFIG_WARN] Could not create directory {webdriver_parent_dir}: {e}.")

        # image_path (Required, must be passed by caller, e.g., main.py constructs this per category)
        if not image_path:
            # This case should ideally not happen if main.py correctly provides it.
            # Fallback for direct ScraperConfig instantiation without main.py's orchestration.
            self.image_path = os.path.join(os.getcwd(), "images_default_config")
            print(f"[CONFIG_WARN] 'image_path' was not provided to ScraperConfig. Defaulting to {self.image_path}")
        else:
            self.image_path = image_path
            
        # search_key (Required)
        self.raw_search_key = search_key

        # number_of_images: Constructor > INI > Hardcoded Default (1)
        val = number_of_images
        source = "Constructor/CLI"
        if val is None:
            val = ini_values.get('number_of_images')
            source = "INI"
        if val is None: # Still None, use hardcoded default
            val = 1
            source = "Hardcoded Default"
        self.number_of_images = int(val)
        print(f"[CONFIG_INFO] number_of_images: {self.number_of_images} (Source: {source})")

        # headless: Constructor > INI > Hardcoded Default (True)
        val = headless
        source = "Constructor/CLI"
        if val is None:
            val = ini_values.get('headless')
            source = "INI"
        if val is None:
            val = True
            source = "Hardcoded Default"
        self.headless = bool(val)
        print(f"[CONFIG_INFO] headless: {self.headless} (Source: {source})")

        # max_missed: Constructor > INI > Hardcoded Default (10)
        val = max_missed
        source = "Constructor/CLI"
        if val is None:
            val = ini_values.get('max_missed')
            source = "INI"
        if val is None:
            val = 10
            source = "Hardcoded Default"
        self.max_missed = int(val)
        print(f"[CONFIG_INFO] max_missed: {self.max_missed} (Source: {source})")
        
        # advanced_suffix: Constructor > INI > Hardcoded Default ("")
        val = advanced_suffix
        source = "Constructor/CLI"
        if val is None:
            val = ini_values.get('advanced_suffix')
            source = "INI"
        if val is None:
            val = ""
            source = "Hardcoded Default"
        self.advanced_suffix = str(val) # Ensure string
        print(f"[CONFIG_INFO] advanced_suffix: '{self.advanced_suffix}' (Source: {source})")

        # chrome_binary_path: Constructor > INI > ChromeFinder
        resolved_chrome_binary_path = chrome_binary_path # Constructor
        source = "Constructor/CLI"
        if resolved_chrome_binary_path is None:
            resolved_chrome_binary_path = ini_values.get('chrome_binary_path') # INI
            source = "INI"
            if not resolved_chrome_binary_path: # Empty string from INI
                resolved_chrome_binary_path = None
        
        if resolved_chrome_binary_path:
            self.chrome_binary_path = resolved_chrome_binary_path
            print(f"[CONFIG_INFO] Using chrome_binary_path: {self.chrome_binary_path} (Source: {source})")
        else: # Fallback to ChromeFinder
            print("[CONFIG_INFO] chrome_binary_path not set by constructor or INI. Attempting auto-detection via ChromeFinder...")
            finder = ChromeFinder()
            self.chrome_binary_path = finder.get_chrome_path()
            if self.chrome_binary_path:
                print(f"[CONFIG_INFO] Auto-detected chrome_binary_path: {self.chrome_binary_path} (Source: ChromeFinder)")
            else:
                print("[CONFIG_WARN] Chrome binary path could not be auto-detected. WebDriverManager may fail if Chrome not in PATH.")
                self.chrome_binary_path = None # Explicitly None

    @property
    def search_key_for_query(self):
        return f"{self.raw_search_key} {self.advanced_suffix}"

    @property
    def cache_dir(self):
        return os.path.join(self.image_path, ".cache")

    def get_url_cache_file(self):
        return os.path.join(self.cache_dir, f"{self.raw_search_key}_urls.json")

    def get_url_checkpoint_file(self):
        return os.path.join(self.cache_dir, f"{self.raw_search_key}_url_checkpoint.json")

    def get_download_checkpoint_file(self):
        name = self.raw_search_key or "generic_download"
        return os.path.join(self.cache_dir, f"{name}_download_checkpoint.json")