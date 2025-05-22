import os

NUM_IMAGES_PER_CLASS = 10
HEADLESS_MODE = True
MAX_MISSED = 25
ADVANCED_SUFFIX = ''
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

NUM_WORKERS = 4
CATEGORIES_FILE = "categories.json"
OUTPUT_DIR_BASE = "output"

WEBDRIVER_PATH = None
CHROME_BINARY_PATH = None


def get_output_dir() -> str:
    return os.path.join(os.getcwd(), OUTPUT_DIR_BASE)

def get_image_path(category_dir: str, search_term: str) -> str:
    clean_base = search_term.replace(" ", "")
    return os.path.join(get_output_dir(), category_dir, clean_base)


def get_cache_dir(category_dir: str, search_term: str) -> str:
    return os.path.join(get_image_path(category_dir, search_term), ".cache")


def get_clean_base_name(search_term: str) -> str:
    return search_term.replace(" ", "") or "Unnamed"


def get_search_key_for_query(search_term: str, suffix: str = "") -> str:
    return f"{search_term} {suffix}".strip()


def get_url_cache_file(category_dir: str, search_term: str) -> str:
    return os.path.join(get_cache_dir(category_dir, search_term),
                        f"{get_clean_base_name(search_term)}_urls.json")


def get_image_metadata_file(category_dir: str, search_term: str) -> str:
    return os.path.join(get_cache_dir(category_dir, search_term),
                        f"{get_clean_base_name(search_term)}_metadata.json")
