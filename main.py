import os
import json
import concurrent.futures
from GoogleImageScraper import GoogleImageScraper
from config import ScraperConfig
from logger import logger


def worker_thread(category_name, search_key, num_images=10, headless=True):
    """Worker thread function to scrape images for a given search key within a category."""
    try:
        # Use ScraperConfig's factory method to create properly configured instance
        config = ScraperConfig.create_instance(
            category_dir=category_name,
            search_term=search_key,
            number_of_images=num_images,
            headless=headless
        )
        
        logger.status(f"Starting search for '{search_key}' in category '{category_name}'")
        
        image_scraper = GoogleImageScraper(config=config)
        image_urls = image_scraper.fetch_image_urls()
        
        if image_urls:
            image_scraper.download_images(image_urls)
        else:
            logger.warning(f"No images found for '{search_key}' in '{category_name}' - skipping download")
        
        image_scraper.close()
        del image_scraper
        logger.success(f"Completed search for '{search_key}' in '{category_name}'")
    except Exception as e:
        logger.error(f"Failed processing '{search_key}' in '{category_name}': {e}")


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


if __name__ == "__main__":
    # Configuration constants
    NUM_WORKERS = 1
    IMAGES_PER_SEARCH = 2
    CATEGORIES_FILE = "categories.json"
    HEADLESS_MODE = True
    
    # Load categories
    # Configure logging
    logger.set_verbose(False)  # Only show important messages by default
    
    # Load and validate categories
    categories_data = load_categories_from_json(CATEGORIES_FILE)
    if not categories_data:
        logger.error("Failed to load categories - exiting")
        exit(1)
    
    # Prepare tasks
    tasks_to_run = []
    for category, search_terms in categories_data.items():
        if not isinstance(search_terms, list):
            logger.warning(f"Skipping category '{category}' - invalid format")
            continue
        for term in search_terms:
            if isinstance(term, str) and term.strip():
                tasks_to_run.append({'category': category, 'search_key': term.strip()})
            else:
                logger.warning(f"Skipping invalid search term in category '{category}'")
    
    if not tasks_to_run:
        logger.warning("No valid search tasks found - exiting")
        exit(0)

    logger.status(f"Starting image scraping for {len(tasks_to_run)} tasks across {len(categories_data)} categories")
    
    # Create base output directory
    base_output_dir = os.path.join(os.getcwd(), "output")
    if not os.path.exists(base_output_dir):
        logger.info(f"Creating output directory: {base_output_dir}")
        os.makedirs(base_output_dir, exist_ok=True)
    
    # Run tasks in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [
            executor.submit(
                worker_thread,
                task['category'],
                task['search_key'],
                IMAGES_PER_SEARCH,
                HEADLESS_MODE
            ) for task in tasks_to_run
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Thread executor failed: {e}")
    
    logger.success("Image scraping completed successfully")
