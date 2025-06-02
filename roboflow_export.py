import zipfile
from pathlib import Path
import sys
from typing import Optional, Set

def create_roboflow_zip(
    output_dir: Path = Path("output"),
    include_metadata: bool = False,
    overwrite: bool = False
) -> Optional[Path]:
    """
    Create a zip file containing images (and optionally metadata) for Roboflow export.
    
    Args:
        output_dir: Base output directory containing images and metadata
        include_metadata: Whether to include metadata files in the zip
        overwrite: Whether to overwrite existing zip file
    
    Returns:
        Path to created zip file, or None if failed
    """
    
    # Define paths
    images_dir = output_dir / "images"
    metadata_dir = output_dir / "metadata"
    zip_path = output_dir / "roboflow_dataset.zip"
    
    # Validation
    if not output_dir.exists():
        print(f"❌ Output directory not found: {output_dir}")
        return None
    
    if not images_dir.exists():
        print(f"❌ Images directory not found: {images_dir}")
        return None
    
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
    # Default execution
    result = create_roboflow_zip(
        output_dir=Path("output"),
        include_metadata=False,
        overwrite=True
    )
    
    if result is None:
        sys.exit(1)