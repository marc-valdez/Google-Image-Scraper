import os
import sys
import json
import concurrent.futures
from src.GoogleImageScraper import GoogleImageScraper
from src.logging.logger import logger
from src.environment.webdriver import WebDriverManager

from src.environment.manager import EnvironmentResolver
import config as cfg

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

def worker_thread(category_name, search_key, worker_id, driver_instance):
    prefix = f"[Task {worker_id}]"
    try:
        logger.status(f"{prefix} Starting search for '{search_key}' in category '{category_name}'")

        image_scraper = GoogleImageScraper(
            category_dir=category_name,
            class_name=search_key,
            worker_id=worker_id,
            driver_instance=driver_instance
        )
        
        if not image_scraper.skip:
            image_urls = image_scraper.fetch_image_urls()

            if image_urls:
                saved_count = image_scraper.download_images(image_urls)
                
                if saved_count > 0:
                    logger.success(f"{prefix} Downloaded {saved_count} images for '{search_key}' in '{category_name}'")
                else:
                    logger.warning(f"{prefix} No new images downloaded for '{search_key}' in '{category_name}'")

        # GoogleImageScraper.close() calls UrlFetcher.close(), which in turn calls
        # WebDriverManager.close_driver(). Since the driver is from an external pool,
        # WebDriverManager (correctly) won't quit it. This ensures any
        # non-driver-related cleanup in GoogleImageScraper/UrlFetcher still occurs.
        image_scraper.close()
        del image_scraper

        logger.success(f"{prefix} Completed search for '{search_key}' in '{category_name}'")

    except Exception as e:
        logger.error(f"{prefix} Failed processing '{search_key}' in '{category_name}': {e}")

def ensure_output_directory():
    base_output_dir = cfg.get_output_dir()
    if not os.path.exists(base_output_dir):
        logger.info(f"Creating output directory: {base_output_dir}")
        os.makedirs(base_output_dir, exist_ok=True)
    return base_output_dir

def initialize_driver_pool(num_drivers):
    driver_managers = []
    logger.info(f"Initializing {num_drivers} WebDriver instances for the pool...")
    for i in range(num_drivers):
        try:
            manager = WebDriverManager() # Each manager creates and owns one driver
            driver_managers.append(manager)
            logger.info(f"WebDriver instance {i+1}/{num_drivers} initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver instance {i+1}: {e}")
    
    if not driver_managers:
        logger.error("Failed to initialize any WebDriver instances for the pool. Exiting.")
        sys.exit(1)
    logger.success(f"Successfully initialized {len(driver_managers)} WebDriver instances.")
    return driver_managers

def close_driver_pool(driver_managers):
    logger.info("Closing all WebDriver instances in the pool...")
    for manager in driver_managers:
        try:
            # WebDriverManager will quit the driver because it created it (self.managed_driver is True)
            manager.close_driver()
        except Exception as e:
            logger.error(f"Error closing a WebDriver instance: {e}")
    logger.success("All WebDriver instances in the pool have been closed.")

def run_parallel_tasks(tasks, driver_managers):
    num_managers = len(driver_managers)
    if num_managers == 0:
        logger.error("No WebDriver instances available in the pool. Cannot run tasks.")
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.NUM_WORKERS) as executor:
        futures = []
        for worker_id_offset, task in enumerate(tasks):
            # Assign a driver instance to the worker thread
            # The worker_id for logging is 1-based, offset is 0-based
            driver_manager_for_task = driver_managers[worker_id_offset % num_managers]
            actual_driver_instance = driver_manager_for_task.driver 
            
            futures.append(
                executor.submit(
                    worker_thread,
                    task['category'],
                    task['search_key'],
                    worker_id_offset + 1, # Worker ID for logging
                    actual_driver_instance
                )
            )
        
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result() 
            except Exception as e:
                logger.error(f"A worker thread encountered an unhandled error: {e}")

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

    # The number of WebDriver instances in the pool should match NUM_WORKERS for optimal resource use.
    driver_managers_pool = initialize_driver_pool(cfg.NUM_WORKERS)
    if len(driver_managers_pool) < cfg.NUM_WORKERS:
        logger.warning(f"Could not initialize the desired number of WebDrivers ({cfg.NUM_WORKERS}). Proceeding with {len(driver_managers_pool)} drivers.")
        if not driver_managers_pool: # Still no drivers after warning
            return 1 

    try:
        run_parallel_tasks(tasks_to_run, driver_managers_pool)
    finally:
        # Ensure all WebDriver instances are closed, even if errors occur during task execution.
        close_driver_pool(driver_managers_pool)
    
    logger.success("Image scraping completed successfully")
    return 0 

if __name__ == "__main__":
    exit_code = main_app()
    sys.exit(exit_code)
