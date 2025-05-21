# -*- coding: utf-8 -*-
"""
Handles downloading and saving images.
"""
import os
import requests
import io
from PIL import Image
from urllib.parse import urlparse
from cache_utils import load_json_data, save_json_data, remove_file_if_exists

class ImageDownloader:
    def __init__(self, image_path, search_key=""): # search_key is used for checkpoint naming
        self.image_path = image_path
        self.search_key = search_key # Used for checkpoint file naming

        if not os.path.exists(self.image_path):
            print(f"[INFO] Image path {self.image_path} not found. Creating a new folder.")
            os.makedirs(self.image_path)

        # Cache and Checkpoint setup (specific to downloads)
        self.cache_dir = os.path.join(self.image_path, ".cache") # Assuming .cache is within image_path
        # ensure_cache_dir(self.cache_dir) # This should be handled by the main class or url_fetcher

        # Checkpoint file name now includes search_key if provided, or a generic name
        checkpoint_suffix = f"{self.search_key}_download_checkpoint.json" if self.search_key else "download_checkpoint.json"
        self.download_checkpoint_file = os.path.join(self.cache_dir, checkpoint_suffix)


    def save_images(self, image_urls, keep_filenames, original_search_key_for_filename=""):
        """
        Download and save images from the given URLs into self.image_path.
        Supports checkpointing and skipping already downloaded files.
        original_search_key_for_filename is the 'filename' part from the main class,
        used if keep_filenames is False.
        """
        if not image_urls:
            print("[INFO] No image URLs provided to save.")
            return 0 # Return count of saved images

        effective_search_key = self.search_key or "generic_download" # Use for logging if main search_key isn't set for downloader
        print(f"[INFO] Attempting to save {len(image_urls)} images for '{effective_search_key}', please wait...")

        start_index = 0
        download_checkpoint = load_json_data(self.download_checkpoint_file)
        # Hash of all URLs to ensure checkpoint validity if the list of URLs changes
        urls_hash = hash(tuple(sorted(image_urls))) # Sort to make hash consistent regardless of order

        if download_checkpoint and \
           download_checkpoint.get('search_key_ref') == effective_search_key and \
           download_checkpoint.get('all_image_urls_hash') == urls_hash:
            start_index = download_checkpoint.get('last_downloaded_index', -1) + 1
            downloaded_previously_count = download_checkpoint.get('saved_count_so_far', 0)
            print(f"[INFO] Resuming download for '{effective_search_key}' from index {start_index}. Previously saved: {downloaded_previously_count}.")
        else:
            # Initialize or reset checkpoint if it's invalid or for a different set of URLs
            save_json_data(self.download_checkpoint_file, {
                'search_key_ref': effective_search_key, # Reference to the search key this checkpoint is for
                'all_image_urls_hash': urls_hash,
                'last_downloaded_index': -1,
                'total_urls_to_download': len(image_urls),
                'saved_count_so_far': 0
            })
            downloaded_previously_count = 0
            print(f"[INFO] Starting new download session or checkpoint reset for '{effective_search_key}'.")


        saved_count_this_session = 0
        for indx in range(start_index, len(image_urls)):
            image_url = image_urls[indx]
            
            # Use the original_search_key_for_filename if provided and not keeping original filenames
            # This ensures filenames are consistent with how GoogleImageScraper originally named them.
            filename_base_key = original_search_key_for_filename or self.search_key # Fallback to downloader's search_key
            search_string_for_filename = ''.join(e for e in filename_base_key if e.isalnum())


            try:
                print(f"[INFO] Downloading {indx+1}/{len(image_urls)} for '{effective_search_key}': {image_url}")
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36" # Consider making this dynamic or configurable
                    ),
                    "Referer": image_url # Some servers might check referer
                }
                response = requests.get(image_url, headers=headers, timeout=10) # Configurable timeout
                if response.status_code != 200:
                    raise Exception(f"HTTP Status code: {response.status_code}")

                # Try to open image and determine format
                try:
                    with Image.open(io.BytesIO(response.content)) as img:
                        image_format = img.format.lower() if img.format else 'jpg' # Default to jpg if format is not detected
                except Exception as img_err:
                    print(f"[WARN] Could not determine image format for {image_url} using PIL: {img_err}. Attempting to guess from URL or use default.")
                    # Fallback: try to guess from URL, or default
                    parsed_url_path = urlparse(image_url).path
                    _, ext_from_url = os.path.splitext(parsed_url_path)
                    if ext_from_url and len(ext_from_url) > 1:
                        image_format = ext_from_url[1:].lower()
                        # Basic validation of common image extensions
                        if image_format not in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff']:
                            print(f"[WARN] Guessed extension '{image_format}' is not common. Defaulting to 'jpg'.")
                            image_format = 'jpg'
                    else:
                        image_format = 'jpg' # Default if no extension found

                if keep_filenames:
                    base_name = os.path.basename(urlparse(image_url).path)
                    name_part, ext_part = os.path.splitext(base_name)
                    # If original extension is missing or different, use the detected/guessed one
                    filename_ext = image_format if not ext_part or ext_part[1:].lower() != image_format else ext_part[1:].lower()
                    filename = f"{name_part or search_string_for_filename + str(indx)}.{filename_ext}"
                else:
                    filename = f"{search_string_for_filename}_{indx}.{image_format}"

                save_path = os.path.join(self.image_path, filename)

                if os.path.exists(save_path):
                    print(f"[INFO] File exists, skipping: {save_path}")
                    # Even if skipped, update checkpoint as this URL is processed
                    current_total_saved = downloaded_previously_count + saved_count_this_session
                    save_json_data(self.download_checkpoint_file, {
                        'search_key_ref': effective_search_key,
                        'all_image_urls_hash': urls_hash,
                        'last_downloaded_index': indx,
                        'total_urls_to_download': len(image_urls),
                        'saved_count_so_far': current_total_saved # This count doesn't increment for skips
                    })
                    # saved_count_this_session += 1 # Do not increment if skipped, but it was "saved" in a previous session
                    continue # Skip to next image

                # Save the raw content if PIL failed but download was successful
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                print(f"[INFO] Saved: {save_path}")
                saved_count_this_session += 1

                current_total_saved = downloaded_previously_count + saved_count_this_session
                save_json_data(self.download_checkpoint_file, {
                    'search_key_ref': effective_search_key,
                    'all_image_urls_hash': urls_hash,
                    'last_downloaded_index': indx,
                    'total_urls_to_download': len(image_urls),
                    'saved_count_so_far': current_total_saved
                })

            except Exception as e:
                print(f"[ERROR] Failed to save image {indx+1} ({image_url}): {e}")
                # Still update checkpoint to reflect this attempt
                current_total_saved = downloaded_previously_count + saved_count_this_session
                save_json_data(self.download_checkpoint_file, {
                    'search_key_ref': effective_search_key,
                    'all_image_urls_hash': urls_hash,
                    'last_downloaded_index': indx, # Mark this index as attempted
                    'total_urls_to_download': len(image_urls),
                    'saved_count_so_far': current_total_saved
                })

        total_saved_overall = downloaded_previously_count + saved_count_this_session
        print("--------------------------------------------------")
        print(f"[INFO] Download session for '{effective_search_key}' finished. New images saved in this session: {saved_count_this_session}. Total saved for this set: {total_saved_overall}.")

        # Check if all images are now "processed" (either downloaded now or skipped because existed)
        final_checkpoint_data = load_json_data(self.download_checkpoint_file)
        if final_checkpoint_data and final_checkpoint_data.get('last_downloaded_index', -1) == len(image_urls) - 1:
            remove_file_if_exists(self.download_checkpoint_file)
            print(f"[INFO] All downloads for '{effective_search_key}' completed or accounted for. Checkpoint cleared.")
        else:
            print(f"[INFO] Download for '{effective_search_key}' may be incomplete or interrupted. Checkpoint retained.")
            if final_checkpoint_data:
                 print(f"[DEBUG] Final checkpoint state: last_downloaded_index={final_checkpoint_data.get('last_downloaded_index', -1)}, total_urls={len(image_urls)}")

        return saved_count_this_session