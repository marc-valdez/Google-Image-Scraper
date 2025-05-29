import os
import shutil
from pathlib import Path

def restructure_output_folder():
    """
    Restructures the output folder from:
    /output/<category>/<class>/###_image.jpg
    /output/<category>/<class>/.cache/<.json files>
    
    To:
    /output/images/<category>/<class>/###_image.jpg
    /output/metadata/<category>/<class>/<.json files>
    """
    
    output_dir = Path("output")
    
    if not output_dir.exists():
        print("Output directory does not exist!")
        return
    
    # Create new directory structure
    images_dir = output_dir / "images"
    metadata_dir = output_dir / "metadata"
    
    images_dir.mkdir(exist_ok=True)
    metadata_dir.mkdir(exist_ok=True)
    
    moved_files = 0
    moved_metadata = 0
    
    # Iterate through categories
    for category_path in output_dir.iterdir():
        if not category_path.is_dir() or category_path.name in ["images", "metadata"]:
            continue
            
        category_name = category_path.name
        print(f"Processing category: {category_name}")
        
        # Iterate through classes within category
        for class_path in category_path.iterdir():
            if not class_path.is_dir():
                continue
                
            class_name = class_path.name
            print(f"  Processing class: {class_name}")
            
            # Create new directory structure for this category/class
            new_images_path = images_dir / category_name / class_name
            new_metadata_path = metadata_dir / category_name / class_name
            
            new_images_path.mkdir(parents=True, exist_ok=True)
            new_metadata_path.mkdir(parents=True, exist_ok=True)
            
            # Move image files
            for file_path in class_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                    destination = new_images_path / file_path.name
                    print(f"    Moving image: {file_path.name} -> {destination}")
                    shutil.move(str(file_path), str(destination))
                    moved_files += 1
            
            # Move metadata files from .cache folder
            cache_path = class_path / ".cache"
            if cache_path.exists() and cache_path.is_dir():
                for json_file in cache_path.iterdir():
                    if json_file.is_file() and json_file.suffix.lower() == '.json':
                        destination = new_metadata_path / json_file.name
                        print(f"    Moving metadata: {json_file.name} -> {destination}")
                        shutil.move(str(json_file), str(destination))
                        moved_metadata += 1
                
                # Remove empty .cache directory
                try:
                    cache_path.rmdir()
                    print(f"    Removed empty .cache directory")
                except OSError:
                    print(f"    Warning: Could not remove .cache directory (may not be empty)")
            
            # Remove empty class directory
            try:
                if not any(class_path.iterdir()):
                    class_path.rmdir()
                    print(f"    Removed empty class directory: {class_name}")
            except OSError:
                print(f"    Warning: Could not remove class directory {class_name} (may not be empty)")
        
        # Remove empty category directory
        try:
            if not any(category_path.iterdir()):
                category_path.rmdir()
                print(f"  Removed empty category directory: {category_name}")
        except OSError:
            print(f"  Warning: Could not remove category directory {category_name} (may not be empty)")
    
    print(f"\nRestructuring complete!")
    print(f"Moved {moved_files} image files")
    print(f"Moved {moved_metadata} metadata files")
    print(f"\nNew structure:")
    print(f"  Images: /output/images/<category>/<class>/###_image.jpg")
    print(f"  Metadata: /output/metadata/<category>/<class>/<json_files>")

def preview_changes():
    """
    Preview what changes would be made without actually moving files
    """
    output_dir = Path("output")
    
    if not output_dir.exists():
        print("Output directory does not exist!")
        return
    
    print("PREVIEW MODE - No files will be moved")
    print("=" * 50)
    
    image_count = 0
    metadata_count = 0
    
    # Iterate through categories
    for category_path in output_dir.iterdir():
        if not category_path.is_dir() or category_path.name in ["images", "metadata"]:
            continue
            
        category_name = category_path.name
        print(f"Category: {category_name}")
        
        # Iterate through classes within category
        for class_path in category_path.iterdir():
            if not class_path.is_dir():
                continue
                
            class_name = class_path.name
            print(f"  Class: {class_name}")
            
            # Count image files
            for file_path in class_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                    print(f"    IMAGE: {file_path.name} -> /output/images/{category_name}/{class_name}/{file_path.name}")
                    image_count += 1
            
            # Count metadata files from .cache folder
            cache_path = class_path / ".cache"
            if cache_path.exists() and cache_path.is_dir():
                for json_file in cache_path.iterdir():
                    if json_file.is_file() and json_file.suffix.lower() == '.json':
                        print(f"    METADATA: {json_file.name} -> /output/metadata/{category_name}/{class_name}/{json_file.name}")
                        metadata_count += 1
    
    print(f"\nSummary:")
    print(f"  {image_count} image files would be moved")
    print(f"  {metadata_count} metadata files would be moved")

if __name__ == "__main__":
    print("Output Folder Restructuring Tool")
    print("=" * 40)
    
    choice = input("Choose an option:\n1. Preview changes\n2. Execute restructuring\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        preview_changes()
    elif choice == "2":
        confirm = input("Are you sure you want to restructure the output folder? (yes/no): ").strip().lower()
        if confirm in ["yes", "y"]:
            restructure_output_folder()
        else:
            print("Operation cancelled.")
    else:
        print("Invalid choice. Please run the script again and choose 1 or 2.")