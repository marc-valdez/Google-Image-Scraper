import os

NUM_WORKERS = 1
NUM_IMAGES_PER_CLASS = 10
HEADLESS_MODE = False
MAX_MISSED = 25
KEEP_FILENAMES = False

REQUEST_INTERVAL = 1.0
MAX_RETRIES = 5
RETRY_BACKOFF = 0.5
MAX_RETRY_DELAY = 60
CONNECTION_TIMEOUT = 15

PAGE_LOAD_TIMEOUT = 30
BROWSER_REFRESH_INTERVAL = 50
SCROLL_PAUSE_TIME = 0.5
LOAD_BUTTON_WAIT = 3.0

CATEGORIES_FILE = "categories.json"
OUTPUT_DIR_BASE = "output"

WEBDRIVER_PATH = ""
CHROME_BINARY_PATH = ""

# Google Search Query Parameters:
SEARCH_QUERY_EXACT_PHRASE = ""                  # as_epq
SEARCH_QUERY_ANY_OF_THESE_WORDS = "cooked"      # as_oq
SEARCH_QUERY_EXCLUDE_THESE_WORDS = "raw"        # as_eq
SEARCH_QUERY_IMAGE_SIZE = "l"                   # imgsz (l: large)
SEARCH_QUERY_ASPECT_RATIO = ""                  # imgar
SEARCH_QUERY_IMAGE_COLOR_TYPE = "color"         # imgc (color)
SEARCH_QUERY_SPECIFIC_COLOR = ""                # imgcolor
SEARCH_QUERY_IMAGE_TYPE = "photo"               # imgtype (photo)
SEARCH_QUERY_COUNTRY_RESTRICTION = "countryPH"  # cr (countryPH)
SEARCH_QUERY_SITE_SEARCH = ""                   # as_sitesearch
SEARCH_QUERY_FILE_TYPE = "jpg"                  # as_filetype (jpg)

def get_output_dir() -> str:
    return os.path.join(os.getcwd(), OUTPUT_DIR_BASE)

def get_image_path(category_dir: str, search_term: str) -> str:
    clean_base = search_term.replace(" ", "")
    return os.path.join(get_output_dir(), category_dir, clean_base)

def get_cache_dir(category_dir: str, search_term: str) -> str:
    return os.path.join(get_image_path(category_dir, search_term), ".cache")

def get_clean_base_name(search_term: str) -> str:
    return search_term.replace(" ", "") or "Unnamed"

def get_search_key_for_query(search_term: str) -> str:
    return search_term.strip()

def get_url_cache_file(category_dir: str, search_term: str) -> str:
    return os.path.join(get_cache_dir(category_dir, search_term),
                        f"{get_clean_base_name(search_term)}_urls.json")

def get_image_metadata_file(category_dir: str, search_term: str) -> str:
    return os.path.join(get_cache_dir(category_dir, search_term),
                        f"{get_clean_base_name(search_term)}_metadata.json")
