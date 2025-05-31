import os
import sys
import json
import concurrent.futures
from src.GoogleImageScraper import GoogleImageScraper
from src.logging.logger import logger
from src.environment.webdriver import WebDriverManager
from src.environment.browser_pool import BrowserPool
from src.environment.manager import EnvironmentResolver
import config as cfg
from src.utils.cache_utils import initialize_shared_index, get_shared_index_stats

cfg.CHROME_BINARY_PATH = EnvironmentResolver.auto_detect_chrome()
cfg.WEBDRIVER_PATH = EnvironmentResolver.resolve_webdriver_path()

def load_categories_from_json(json_file_path):
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Loaded categories from {json_file_path}")
        return data
    except FileNotFoundError:
        logger.error(f"Categories file not found: {json_file_path}")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in {json_file_path}")
    except Exception as e:
        logger.error(f"Failed to load {json_file_path}: {e}")
    return None

def process_search_tasks(categories_data):
    tasks = []
    for category, class_names in categories_data.items():
        if not isinstance(class_names, list):
            logger.warning(f"Skipping category '{category}' - invalid format")
            continue
        for term in class_names:
            if isinstance(term, str) and term.strip():
                tasks.append({
                    'category': category,
                    'search_key': term.strip()
                })
            else:
                logger.warning(f"Skipping invalid search term in category '{category}'")
    return tasks

def worker_thread(category_name, search_key, worker_id, browser_pool):
    prefix = f"[Task {worker_id}]"
    browser_info = None
    
    try:
        logger.status(f"{prefix} Starting search for '{search_key}' in category '{category_name}'")
        
        # Acquire a browser from the pool
        browser_info = browser_pool.acquire_browser(worker_id)
        if not browser_info:
            logger.error(f"{prefix} Failed to acquire browser - aborting task")
            return
        
        logger.info(f"{prefix} Using browser {browser_info['id']} for '{search_key}'")

        image_scraper = GoogleImageScraper(
            category_dir=category_name,
            class_name=search_key,
            worker_id=worker_id,
            driver_instance=browser_info['driver']
        )
        
        if not image_scraper.skip:
            image_urls = image_scraper.fetch_image_urls()

            if image_urls:
                saved_count = image_scraper.download_images(image_urls)
                
                if saved_count > 0:
                    logger.success(f"{prefix} Downloaded {saved_count} images for '{search_key}' in '{category_name}' using browser {browser_info['id']}")
                else:
                    logger.warning(f"{prefix} No new images downloaded for '{search_key}' in '{category_name}'")

        # GoogleImageScraper.close() calls UrlFetcher.close(), which in turn calls
        # WebDriverManager.close_driver(). Since the driver is from an external pool,
        # WebDriverManager (correctly) won't quit it. This ensures any
        # non-driver-related cleanup in GoogleImageScraper/UrlFetcher still occurs.
        image_scraper.close()
        del image_scraper

        logger.success(f"{prefix} Completed search for '{search_key}' in '{category_name}' using browser {browser_info['id']}")

    except Exception as e:
        logger.error(f"{prefix} Failed processing '{search_key}' in '{category_name}': {e}")
    finally:
        # Always release the browser back to the pool
        if browser_info:
            browser_pool.release_browser(browser_info, worker_id)

def ensure_output_directory():
    base_dir, images_dir, metadata_dir = cfg.ensure_base_directories()
    logger.info(f"Ensured directory structure: {images_dir}, {metadata_dir}")
    return base_dir

def initialize_browser_pool(pool_size):
    """Initialize the browser pool with the specified number of browsers."""
    try:
        return BrowserPool(pool_size)
    except Exception as e:
        logger.error(f"Failed to initialize browser pool: {e}")
        sys.exit(1)

def run_parallel_tasks(tasks, browser_pool):
    """Run tasks in parallel using the browser pool."""
    pool_status = browser_pool.get_pool_status()
    logger.info(f"Starting parallel execution with {pool_status['total']} browsers available")

    with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.NUM_WORKERS) as executor:
        futures = []
        for worker_id_offset, task in enumerate(tasks):
            futures.append(
                executor.submit(
                    worker_thread,
                    task['category'],
                    task['search_key'],
                    worker_id_offset + 1,  # Worker ID for logging (1-based)
                    browser_pool
                )
            )
        
        # Monitor progress and log pool status periodically
        completed_count = 0
        total_tasks = len(futures)
        
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
                completed_count += 1
                
                # Log progress every 5 completed tasks or on completion
                if completed_count % 5 == 0 or completed_count == total_tasks:
                    pool_status = browser_pool.get_pool_status()
                    logger.info(f"Progress: {completed_count}/{total_tasks} tasks completed. "
                              f"Browser pool: {pool_status['available']}/{pool_status['total']} available")
                    
            except Exception as e:
                logger.error(f"A worker thread encountered an unhandled error: {e}")
                completed_count += 1
    
    # Wait for all browsers to be released
    logger.info("Waiting for all browsers to be released...")
    browser_pool.wait_for_all_released(timeout=30.0)

def main_app():
    logger.set_verbose(False)
    
    categories_data = load_categories_from_json(cfg.CATEGORIES_FILE)
    if not categories_data:
        logger.error("Failed to load categories - exiting")
        return 1
    
    tasks_to_run = process_search_tasks(categories_data)
    if not tasks_to_run:
        logger.warning("No valid search tasks found - exiting")
        return 1

    logger.status(f"Starting image scraping for {len(tasks_to_run)} tasks across {len(categories_data)} categories using {cfg.NUM_WORKERS} workers.")
    
    ensure_output_directory()
    
    # Initialize shared URL index for efficient duplication checking
    logger.info("Initializing shared URL index for memory-efficient duplication checking...")
    if initialize_shared_index():
        index_stats = get_shared_index_stats()
        logger.info(f"Shared index ready: {index_stats.get('total_urls', 0)} existing URLs loaded")
    else:
        logger.warning("Shared index initialization failed - falling back to file-based checks")

    # Initialize browser pool - use NUM_WORKERS as the pool size for optimal resource use
    browser_pool = initialize_browser_pool(cfg.NUM_WORKERS)
    
    try:
        run_parallel_tasks(tasks_to_run, browser_pool)
    finally:
        # Ensure all browser instances are closed, even if errors occur during task execution
        browser_pool.close_all()
        
        # Log final shared index stats
        try:
            final_stats = get_shared_index_stats()
            logger.info(f"Final shared index stats: {final_stats.get('total_urls', 0)} URLs across {final_stats.get('total_categories', 0)} categories")
        except Exception:
            pass
    
    logger.success("Image scraping completed successfully")
    return 0

if __name__ == "__main__":
    exit_code = main_app()
    sys.exit(exit_code)
