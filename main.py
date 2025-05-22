import os
import sys
import json
import concurrent.futures
from src.GoogleImageScraper import GoogleImageScraper
from src.logging.logger import logger

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
    for category, search_terms in categories_data.items():
        if not isinstance(search_terms, list):
            logger.warning(f"Skipping category '{category}' - invalid format")
            continue
        for term in search_terms:
            if isinstance(term, str) and term.strip():
                tasks.append({
                    'category': category,
                    'search_key': term.strip()
                })
            else:
                logger.warning(f"Skipping invalid search term in category '{category}'")
    return tasks

def worker_thread(category_name, search_key, worker_id):
    prefix = f"[Worker {worker_id}]"
    try:
        logger.status(f"{prefix} Starting search for '{search_key}' in category '{category_name}'")

        image_scraper = GoogleImageScraper(
            category_dir=category_name,
            search_term=search_key,
            worker_id=worker_id
        )
        
        image_urls = image_scraper.fetch_image_urls()

        if image_urls:
            saved_count = image_scraper.download_images(image_urls)
            
            if saved_count > 0:
                logger.success(f"{prefix} Downloaded {saved_count} images for '{search_key}' in '{category_name}'")
            else:
                logger.warning(f"{prefix} No new images downloaded for '{search_key}' in '{category_name}'")
        else:
            logger.warning(f"{prefix} No images found for '{search_key}' in '{category_name}' - skipping download")

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

def run_parallel_tasks(tasks):
    with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.NUM_WORKERS) as executor:
        futures = [
            executor.submit(
                worker_thread,
                task['category'],
                task['search_key'],
                worker_id + 1 
            ) for worker_id, task in enumerate(tasks)
        ]
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

    logger.status(f"Starting image scraping for {len(tasks_to_run)} tasks across {len(categories_data)} categories")
    
    ensure_output_directory()
    run_parallel_tasks(tasks_to_run)
    
    logger.success("Image scraping completed successfully")
    return 0 

if __name__ == "__main__":
    exit_code = main_app()
    sys.exit(exit_code)
