import os
import requests
import io
from PIL import Image
from urllib.parse import urlparse
from cache_utils import load_json_data, save_json_data, remove_file_if_exists

class ImageDownloader:
    def __init__(self, config):
        self.config = config

        if not os.path.exists(self.config.image_path):
            os.makedirs(self.config.image_path)

    @property
    def download_checkpoint_file(self):
        return self.config.get_download_checkpoint_file()

    def save_images(self, image_urls, keep_filenames):
        if not image_urls:
            print("[INFO] No image URLs provided to save.")
            return 0

        effective_search_key = self.config.search_key_for_query or "generic_download"
        print(f"[INFO] Attempting to save {len(image_urls)} images for '{effective_search_key}'...")

        start_index = 0
        # Accessing the property here
        download_checkpoint = load_json_data(self.download_checkpoint_file)
        urls_hash = hash(tuple(sorted(image_urls)))

        if download_checkpoint and \
           download_checkpoint.get('search_key_ref') == effective_search_key and \
           download_checkpoint.get('all_image_urls_hash') == urls_hash:
            start_index = download_checkpoint.get('last_downloaded_index', -1) + 1
            downloaded_previously_count = download_checkpoint.get('saved_count_so_far', 0)
            print(f"[INFO] Resuming download for '{effective_search_key}' from index {start_index}. Previously saved: {downloaded_previously_count}.")
        else:
            # Accessing the property here
            save_json_data(self.download_checkpoint_file, {
                'search_key_ref': effective_search_key,
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
            
            filename_base_key = self.config.raw_search_key
            search_string_for_filename = ''.join(e for e in filename_base_key if e.isalnum())


            try:
                print(f"[INFO] Downloading {indx+1}/{len(image_urls)} for '{effective_search_key}': {image_url}")
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Referer": image_url
                }
                response = requests.get(image_url, headers=headers, timeout=10)
                if response.status_code != 200:
                    raise Exception(f"HTTP Status code: {response.status_code}")

                try:
                    with Image.open(io.BytesIO(response.content)) as img:
                        image_format = img.format.lower() if img.format else 'jpg'
                except Exception as img_err:
                    print(f"[WARN] PIL error determining image format for {image_url}: {img_err}. Guessing from URL.")
                    parsed_url_path = urlparse(image_url).path
                    _, ext_from_url = os.path.splitext(parsed_url_path)
                    if ext_from_url and len(ext_from_url) > 1:
                        image_format = ext_from_url[1:].lower()
                        if image_format not in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff']:
                            print(f"[WARN] Guessed extension '{image_format}' uncommon. Defaulting to 'jpg'.")
                            image_format = 'jpg'
                    else:
                        image_format = 'jpg'

                if keep_filenames:
                    base_name = os.path.basename(urlparse(image_url).path)
                    name_part, ext_part = os.path.splitext(base_name)
                    filename_ext = image_format if not ext_part or ext_part[1:].lower() != image_format else ext_part[1:].lower()
                    filename = f"{name_part or search_string_for_filename + str(indx)}.{filename_ext}"
                else:
                    filename = f"{search_string_for_filename}_{indx}.{image_format}"

                save_path = os.path.join(self.config.image_path, filename)

                if os.path.exists(save_path):
                    print(f"[INFO] File exists, skipping: {save_path}")
                    current_total_saved = downloaded_previously_count + saved_count_this_session
                    save_json_data(self.download_checkpoint_file, {
                        'search_key_ref': effective_search_key,
                        'all_image_urls_hash': urls_hash,
                        'last_downloaded_index': indx,
                        'total_urls_to_download': len(image_urls),
                        'saved_count_so_far': current_total_saved
                    })
                    continue

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
                current_total_saved = downloaded_previously_count + saved_count_this_session
                save_json_data(self.download_checkpoint_file, {
                    'search_key_ref': effective_search_key,
                    'all_image_urls_hash': urls_hash,
                    'last_downloaded_index': indx,
                    'total_urls_to_download': len(image_urls),
                    'saved_count_so_far': current_total_saved
                })

        total_saved_overall = downloaded_previously_count + saved_count_this_session
        print("--------------------------------------------------")
        print(f"[INFO] Download for '{effective_search_key}': {saved_count_this_session} new, {total_saved_overall} total for this set.")

        final_checkpoint_data = load_json_data(self.download_checkpoint_file)
        if final_checkpoint_data and final_checkpoint_data.get('last_downloaded_index', -1) == len(image_urls) - 1:
            remove_file_if_exists(self.download_checkpoint_file)
            print(f"[INFO] All downloads for '{effective_search_key}' complete. Checkpoint cleared.")
        else:
            print(f"[INFO] Download for '{effective_search_key}' may be incomplete. Checkpoint retained.")
            if final_checkpoint_data:
                 print(f"[DEBUG] Final checkpoint: last_idx={final_checkpoint_data.get('last_downloaded_index', -1)}, total_urls={len(image_urls)}")

        return saved_count_this_session