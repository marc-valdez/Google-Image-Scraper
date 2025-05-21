import os
import json
import concurrent.futures
from GoogleImageScraper import GoogleImageScraper
from config import ScraperConfig


def worker_thread(category_name, search_key, settings_file='settings.ini'):
    """Worker thread function to scrape images for a given search key within a category."""
    
    try:
        # Create ScraperConfig instance - it will load its own settings from settings.ini
        config = ScraperConfig(
            image_path=os.path.join(os.getcwd(), "output", category_name),  # Dynamic path per category
            search_key=search_key,                                          # Dynamic per task
            settings_file_path=settings_file                               # Use the same settings file
        )
        
        print(f"[INFO] Worker starting for Category: '{category_name}', Search Key: '{search_key}', Output Path: '{config.image_path}'")
        
        # Ensure category directory exists
        if not os.path.exists(config.image_path):
            print(f"[INFO] Creating category directory: {config.image_path}")
            os.makedirs(config.image_path, exist_ok=True)
            
        image_scraper = GoogleImageScraper(config=config)
        
        image_urls = image_scraper.fetch_image_urls()
        if image_urls:
            # Let ScraperConfig determine keep_filenames setting from settings.ini
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
    # Let ScraperConfig handle all configuration from settings.ini
    config = ScraperConfig(
        image_path="output",  # Temporary config just to read settings
        search_key="temp",    # Temporary config just to read settings
    )
    
    # Load categories from the path specified in settings.ini
    categories_data = load_categories_from_json(os.path.join(os.getcwd(), "categories.json"))
    if not categories_data:
        print("[FATAL] Could not load categories. Exiting.")
        exit(1)
    
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
    
    # Let ScraperConfig determine number of workers from settings.ini
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                worker_thread,
                task['category'],
                task['search_key']
            ) for task in tasks_to_run
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"[ERROR] A thread executor task raised an unhandled exception: {e}")
    
    print("[INFO] All scraping tasks completed.")
