import zipfile
from pathlib import Path
import sys
import json
from typing import Optional, Set, List, Union

def create_roboflow_zip(
    output_dir: Path = Path("output"),
    include_metadata: bool = False,
    overwrite: bool = False,
    categories: Optional[Union[str, List[str]]] = None
) -> Optional[Path]:
    """
    Create a zip file containing images (and optionally metadata) for Roboflow export.
    
    Args:
        output_dir: Base output directory containing images and metadata
        include_metadata: Whether to include metadata files in the zip
        overwrite: Whether to overwrite existing zip file
        categories: Categories to include. Can be:
                   - None: Include all categories
                   - String: Single category ("Go", "Grow", or "Glow")
                   - List: Multiple categories (["Go", "Grow"])
    
    Returns:
        Path to created zip file, or None if failed
    """
    
    # Define paths
    images_dir = output_dir / "images"
    metadata_dir = output_dir / "metadata"
    categories_file = Path("categories.json")
    
    # Determine zip file name based on categories
    if categories is None:
        zip_name = "roboflow_dataset.zip"
    elif isinstance(categories, str):
        zip_name = f"roboflow_dataset_{categories.lower()}.zip"
    else:
        categories_str = "_".join(sorted([cat.lower() for cat in categories]))
        zip_name = f"roboflow_dataset_{categories_str}.zip"
    
    zip_path = output_dir / zip_name
    
    # Validation
    if not output_dir.exists():
        print(f"❌ Output directory not found: {output_dir}")
        return None
    
    if not images_dir.exists():
        print(f"❌ Images directory not found: {images_dir}")
        return None
    
    # Load and validate categories
    allowed_food_items = set()
    if categories is not None:
        if not categories_file.exists():
            print(f"❌ Categories file not found: {categories_file}")
            return None
        
        try:
            with open(categories_file, 'r', encoding='utf-8') as f:
                categories_data = json.load(f)
        except Exception as e:
            print(f"❌ Error reading categories file: {e}")
            return None
        
        # Normalize categories input
        if isinstance(categories, str):
            categories = [categories]
        
        # Validate category names
        valid_categories = set(categories_data.keys())
        for cat in categories:
            if cat not in valid_categories:
                print(f"❌ Invalid category: {cat}")
                print(f"   Valid categories: {', '.join(sorted(valid_categories))}")
                return None
        
        # Collect food items for selected categories
        for cat in categories:
            allowed_food_items.update(categories_data[cat])
        
        print(f"📋 Filtering by categories: {', '.join(categories)}")
        print(f"   Including {len(allowed_food_items)} food items")
    
    # Check if images directory has any files
    image_files = list(images_dir.rglob("*"))
    image_files = [f for f in image_files if f.is_file()]
    
    if not image_files:
        print(f"❌ No image files found in: {images_dir}")
        return None
    
    # Check for existing zip file
    if zip_path.exists() and not overwrite:
        print(f"❌ Zip file already exists: {zip_path}")
        print("   Use overwrite=True to replace it")
        return None
    
    # Valid image extensions
    valid_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'}
    
    try:
        # Create zip
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
            files_added = 0
            
            # Add images
            print(f"📦 Adding images from: {images_dir}")
            for image_path in images_dir.rglob("*"):
                if image_path.is_file():
                    # Filter by extension
                    if image_path.suffix.lower() in valid_extensions:
                        # Filter by category if specified
                        if allowed_food_items:
                            # Get the food item name from the directory structure
                            # Path structure: images/FoodItemName/filename.ext
                            try:
                                food_item = image_path.parent.name
                                if food_item not in allowed_food_items:
                                    continue
                            except (IndexError, AttributeError):
                                continue
                        
                        arcname = image_path.relative_to(output_dir)
                        zipf.write(image_path, arcname=arcname)
                        files_added += 1
                        
                        if files_added % 10 == 0:
                            print(f"   Added {files_added} images...")
            
            # Add metadata if requested
            if include_metadata and metadata_dir.exists():
                print(f"📋 Adding metadata from: {metadata_dir}")
                metadata_files = 0
                for metadata_path in metadata_dir.rglob("*.json"):
                    if metadata_path.is_file():
                        # Filter metadata by category if specified
                        if allowed_food_items:
                            # Convert filename to food item name
                            # Metadata filename format: FoodItemName.json (with spaces removed)
                            metadata_basename = metadata_path.stem
                            # Check if this metadata file corresponds to an allowed food item
                            matching_item = None
                            for item in allowed_food_items:
                                # Remove spaces and convert to match metadata filename format
                                item_normalized = item.replace(" ", "").replace("-", "")
                                if metadata_basename.lower() == item_normalized.lower():
                                    matching_item = item
                                    break
                            
                            if not matching_item:
                                continue
                        
                        arcname = metadata_path.relative_to(output_dir)
                        zipf.write(metadata_path, arcname=arcname)
                        metadata_files += 1
                
                print(f"   Added {metadata_files} metadata files")
            
            print(f"✅ Dataset zipped successfully!")
            print(f"   📁 Location: {zip_path}")
            print(f"   📊 Total images: {files_added}")
            print(f"   💾 File size: {zip_path.stat().st_size / (1024*1024):.1f} MB")
            
            return zip_path
            
    except Exception as e:
        print(f"❌ Error creating zip file: {e}")
        # Clean up partial zip file
        if zip_path.exists():
            zip_path.unlink()
        return None

if __name__ == "__main__":
    # Parse command line arguments for category filtering
    import argparse
    
    parser = argparse.ArgumentParser(description="Export dataset for Roboflow by category")
    parser.add_argument("--categories", "-c", nargs="+",
                       help="Categories to include (Go, Grow, Glow). If not specified, includes all.")
    parser.add_argument("--include-metadata", "-m", action="store_true",
                       help="Include metadata files in the export")
    parser.add_argument("--output-dir", "-o", type=Path, default=Path("output"),
                       help="Output directory path (default: output)")
    parser.add_argument("--overwrite", action="store_true",
                       help="Overwrite existing zip file")
    
    args = parser.parse_args()
    
    # Default execution with parsed arguments
    result = create_roboflow_zip(
        output_dir=args.output_dir,
        include_metadata=args.include_metadata,
        overwrite=args.overwrite,
        categories=args.categories
    )
    
    if result is None:
        sys.exit(1)