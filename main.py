from absl import app
import os
import json
import concurrent.futures
from src.GoogleImageScraper import GoogleImageScraper
from src.helpers.config import ScraperConfig
from src.logging.logger import logger

# Configuration constants
NUM_WORKERS = 8
NUM_IMAGES_PER_CLASS = 500
SUFFIX = '(filipino OR food OR meal)'
CATEGORIES_FILE = "categories.json"
HEADLESS_MODE = True

def load_categories_from_json(json_file_path):
    """Loads categories and their search terms from a JSON file."""
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
    """Process and validate search tasks from categories data."""
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

def worker_thread(category_name, search_key, suffix, worker_id, num_images=10, headless=True):
    """Worker thread function to scrape images for a given search key within a category."""
    try:
        prefix = f"[Worker {worker_id}]"
        config = ScraperConfig.create_instance(
            category_dir=category_name,
            search_term=search_key,
            advanced_suffix=suffix,
            number_of_images=num_images,
            headless=headless
        )
        
        logger.status(f"{prefix} Starting search for '{search_key}' in category '{category_name}'")
        
        image_scraper = GoogleImageScraper(config=config)
        image_urls = image_scraper.fetch_image_urls()
        
        if image_urls:
            image_scraper.download_images(image_urls)
        else:
            logger.warning(f"{prefix} No images found for '{search_key}' in '{category_name}' - skipping download")
        
        image_scraper.close()
        del image_scraper
        logger.success(f"{prefix} Completed search for '{search_key}' in '{category_name}'")
    except Exception as e:
        logger.error(f"{prefix} Failed processing '{search_key}' in '{category_name}': {e}")

def ensure_output_directory():
    """Ensure the base output directory exists."""
    base_output_dir = os.path.join(os.getcwd(), "output")
    if not os.path.exists(base_output_dir):
        logger.info(f"Creating output directory: {base_output_dir}")
        os.makedirs(base_output_dir, exist_ok=True)
    return base_output_dir

def run_parallel_tasks(tasks):
    """Run scraping tasks in parallel using thread pool."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [
            executor.submit(
                worker_thread,
                task['category'],
                task['search_key'],
                SUFFIX,
                worker_id,  # Add worker ID
                NUM_IMAGES_PER_CLASS,
                HEADLESS_MODE
            ) for worker_id, task in enumerate(tasks)
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Thread executor failed: {e}")

def main(argv):
    """Main entry point for the scraper"""
    logger.set_verbose(False)  # Only show important messages by default
    
    # Load and validate categories
    categories_data = load_categories_from_json(CATEGORIES_FILE)
    if not categories_data:
        logger.error("Failed to load categories - exiting")
        return 1
    
    # Process tasks
    tasks_to_run = process_search_tasks(categories_data)
    if not tasks_to_run:
        logger.warning("No valid search tasks found - exiting")
        return 1

    logger.status(f"Starting image scraping for {len(tasks_to_run)} tasks across {len(categories_data)} categories")
    
    # Setup and run
    ensure_output_directory()
    run_parallel_tasks(tasks_to_run)
    
    logger.success("Image scraping completed successfully")
    return 0

if __name__ == "__main__":
    app.run(main)
