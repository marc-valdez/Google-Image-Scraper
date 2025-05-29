import os
import re
from fake_useragent import UserAgent

NUM_WORKERS = 4
NUM_IMAGES_PER_CLASS = 500
HEADLESS_MODE = True
MAX_MISSED = 5
MAX_CONSECUTIVE_HIGH_RES_FAILURES = 30
KEEP_FILENAMES = False

REQUEST_INTERVAL = 1.0
MAX_RETRIES = 5
RETRY_BACKOFF = 0.5
MAX_RETRY_DELAY = 60
CONNECTION_TIMEOUT = 15

PAGE_LOAD_TIMEOUT = 30
BROWSER_REFRESH_INTERVAL = 60
SCROLL_PAUSE_TIME = 0.5
LOAD_BUTTON_WAIT = 3.0

CATEGORIES_FILE = "categories.json"
OUTPUT_DIR_BASE = "output"

WEBDRIVER_PATH = ""
CHROME_BINARY_PATH = ""

_ua = UserAgent()
def get_random_user_agent():
    try:
        return _ua.random
    except Exception:
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
ROTATE_USER_AGENT = True
USER_AGENT_CYCLE_ON_ERRORS = [403, 429] # Define which HTTP status codes should trigger a User-Agent cycle attempt
RETRY_BACKOFF_FOR_UA_ROTATE = 2.0 # Delay in seconds before retrying with a new User-Agent after an error in USER_AGENT_CYCLE_ON_ERRORS

# Google Search Query Parameters:
SEARCH_QUERY_EXACT_PHRASE = ""            # as_epq
SEARCH_QUERY_ANY_OF_THESE_WORDS = ""      # as_oq
SEARCH_QUERY_EXCLUDE_THESE_WORDS = ""     # as_eq
SEARCH_QUERY_IMAGE_SIZE = ""              # imgsz (l: large)
SEARCH_QUERY_ASPECT_RATIO = ""            # imgar
SEARCH_QUERY_IMAGE_COLOR_TYPE = ""        # imgc (color)
SEARCH_QUERY_SPECIFIC_COLOR = ""          # imgcolor
SEARCH_QUERY_IMAGE_TYPE = "photo"         # imgtype (photo)
SEARCH_QUERY_COUNTRY_RESTRICTION = ""     # cr (countryPH)
SEARCH_QUERY_SITE_SEARCH = ""             # as_sitesearch
SEARCH_QUERY_FILE_TYPE = ""               # as_filetype (jpg)

def get_output_dir() -> str:
    return os.path.join(os.getcwd(), OUTPUT_DIR_BASE)

def get_image_path(category_dir: str, class_name: str) -> str:
    return os.path.join(get_output_dir(), category_dir, class_name)

def get_cache_dir(category_dir: str, class_name: str) -> str:
    return os.path.join(get_image_path(category_dir, class_name), ".cache")

def sanitize_class_name(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9]', '', name.title())

def format_filename(class_name: str, index: int) -> str:
    sanitized = sanitize_class_name(class_name)
    return f"{index:03}_{sanitized}"

def get_url_cache_file(category_dir: str, class_name: str) -> str:
    return os.path.join(get_cache_dir(category_dir, class_name),
                        f"{sanitize_class_name(class_name)}_urls.json")

def get_image_metadata_file(category_dir: str, class_name: str) -> str:
    return os.path.join(get_cache_dir(category_dir, class_name),
                        f"{sanitize_class_name(class_name)}_metadata.json")
