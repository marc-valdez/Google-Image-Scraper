import os
import json
import concurrent.futures
from GoogleImageScraper import GoogleImageScraper
from config import ScraperConfig


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
        
        print(f"[INFO] Worker starting for Category: '{category_name}', Search Key: '{search_key}'")
        
        image_scraper = GoogleImageScraper(config=config)
        image_urls = image_scraper.fetch_image_urls()
        
        if image_urls:
            image_scraper.download_images(image_urls)
        else:
            print(f"[INFO] No image URLs found for '{search_key}' in category '{category_name}'. Skipping download.")
        
        image_scraper.close()
        del image_scraper
        print(f"[INFO] Worker finished for Category: '{category_name}', Search Key: '{search_key}'")
    except Exception as e:
        print(f"[ERROR] Worker for Category: '{category_name}', Search Key: '{search_key}' encountered an error: {e}")


def load_categories_from_json(json_file_path):
    """Loads categories and their search terms from a JSON file."""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[INFO] Successfully loaded categories from {json_file_path}")
        return data
    except FileNotFoundError:
        print(f"[ERROR] Categories JSON file not found: {json_file_path}")
    except json.JSONDecodeError:
        print(f"[ERROR] Error decoding JSON from file: {json_file_path}")
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred while loading {json_file_path}: {e}")
    return None


if __name__ == "__main__":
    # Configuration constants
    NUM_WORKERS = 1
    IMAGES_PER_SEARCH = 2
    CATEGORIES_FILE = "categories.json"
    HEADLESS_MODE = True
    
    # Load categories
    categories_data = load_categories_from_json(CATEGORIES_FILE)
    if not categories_data:
        print("[FATAL] Could not load categories. Exiting.")
        exit(1)
    
    # Prepare tasks
    tasks_to_run = []
    for category, search_terms in categories_data.items():
        if not isinstance(search_terms, list):
            print(f"[WARN] Category '{category}' in JSON does not have a list of search terms. Skipping.")
            continue
        for term in search_terms:
            if isinstance(term, str) and term.strip():
                tasks_to_run.append({'category': category, 'search_key': term.strip()})
            else:
                print(f"[WARN] Invalid search term '{term}' in category '{category}'. Skipping.")
    
    if not tasks_to_run:
        print("[INFO] No valid search tasks to run based on the categories file.")
        exit(0)

    print(f"[INFO] Starting image scraping for {len(tasks_to_run)} total search tasks across {len(categories_data)} categories.")
    
    # Create base output directory
    base_output_dir = os.path.join(os.getcwd(), "output")
    if not os.path.exists(base_output_dir):
        print(f"[INFO] Creating base output directory: {base_output_dir}")
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
                print(f"[ERROR] A thread executor task raised an unhandled exception: {e}")
    
    print("[INFO] All scraping tasks completed.")
