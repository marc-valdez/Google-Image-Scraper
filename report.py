#!/usr/bin/env python3
"""
Image Download Report Generator

Analyzes unified metadata files to generate comprehensive statistics.
Optimized for the new unified metadata structure with improved performance.
"""

import os
import json
import glob
import sys
from datetime import datetime
from collections import defaultdict, Counter
import statistics
from pathlib import Path

# Add project root to sys.path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import config as cfg
from src.logging.logger import logger

class ImageDownloadReport:
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or cfg.get_output_dir()
        self.image_data = []
        self.categories = ["Go", "Grow", "Glow"]
        
    def load_metadata(self):
        """Load all unified metadata files from metadata directories"""
        logger.status("Loading unified metadata files...")
        
        # Use config function to construct metadata pattern
        metadata_pattern = os.path.join(self.output_dir, "metadata", "*", "*", "*_metadata.json")
        json_files = glob.glob(metadata_pattern)
        
        logger.info(f"Found {len(json_files)} unified metadata files")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Validate unified format
                if 'images' not in data or 'search_key' not in data:
                    logger.warning(f"Skipping non-unified format file: {Path(json_file).name}")
                    continue
                
                # Extract category and class from path
                path_parts = Path(json_file).parts
                data['category'] = path_parts[-3]  # output/metadata/<Category>/<Class>/file.json
                data['class_name'] = path_parts[-2]
                data['file_path'] = json_file
                
                # Single unified data structure
                self.image_data.append(data)
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {Path(json_file).name}: {e}")
            except Exception as e:
                logger.error(f"Error reading {Path(json_file).name}: {e}")
                
        logger.success(f"Loaded {len(self.image_data)} unified metadata files")
    
    def _extract_metadata_values(self, metadata, category, class_name, file_sizes, widths, heights, color_modes, formats, hashes, hash_to_files, hash_per_class):
        """Extract and collect metadata values for statistics"""
        # File size
        size = metadata.get('bytes', 0)
        if size > 0:
            file_sizes.append(size)
        
        # Dimensions
        width = metadata.get('width', 0)
        height = metadata.get('height', 0)
        if width > 0:
            widths.append(width)
        if height > 0:
            heights.append(height)
        
        # Color mode and format
        mode = metadata.get('mode', 'unknown')
        if mode:
            color_modes.append(mode)
        
        fmt = metadata.get('format', 'unknown')
        if fmt:
            formats.append(fmt.lower())
        
        # Hash for duplicate detection
        hash_val = metadata.get('hash')
        if hash_val:
            hashes.append(hash_val)
            file_path = metadata.get('relative_path', 'unknown')
            class_key = f"{category}/{class_name}"
            
            hash_to_files[hash_val].append(file_path)
            hash_per_class[class_key][hash_val].append(file_path)

    def calculate_quantitative_stats(self):
        """Calculate quantitative statistics from unified metadata"""
        # Initialize collections
        total_images = 0
        images_per_class = defaultdict(int)
        images_per_category = defaultdict(int)
        file_sizes, widths, heights, color_modes, formats, hashes = [], [], [], [], [], []
        hash_to_files = defaultdict(list)
        hash_per_class = defaultdict(lambda: defaultdict(list))
        
        # Process unified metadata
        for img_data in self.image_data:
            category = img_data['category']
            class_name = img_data['class_name']
            images_dict = img_data.get('images', {})
            
            # Count images
            class_image_count = len(images_dict)
            total_images += class_image_count
            images_per_class[class_name] += class_image_count
            images_per_category[category] += class_image_count
            
            # Process each image's download metadata
            for img_key, img_entry in images_dict.items():
                if isinstance(img_entry, dict) and 'download_data' in img_entry:
                    self._extract_metadata_values(
                        img_entry['download_data'], category, class_name,
                        file_sizes, widths, heights, color_modes, formats, hashes,
                        hash_to_files, hash_per_class
                    )
        
        # Calculate and return statistics
        return {
            'total_image_count': total_images,
            'images_per_class': dict(images_per_class),
            'images_per_category': dict(images_per_category),
            'file_size': self._calculate_file_size_stats(file_sizes),
            'dimensions': self._calculate_dimension_stats(widths, heights),
            'color_modes': dict(Counter(color_modes)),
            'formats': dict(Counter(formats)),
            'hashes': self._calculate_hash_stats(hashes, hash_to_files, hash_per_class)
        }

    def _calculate_file_size_stats(self, file_sizes):
        """Calculate file size statistics"""
        if not file_sizes:
            return {'average_bytes': 0, 'min_bytes': 0, 'max_bytes': 0, 'total_bytes': 0}
        
        return {
            'average_bytes': statistics.mean(file_sizes),
            'min_bytes': min(file_sizes),
            'max_bytes': max(file_sizes),
            'total_bytes': sum(file_sizes)
        }

    def _calculate_dimension_stats(self, widths, heights):
        """Calculate dimension statistics"""
        if not widths:
            return {
                'avg_width': 0, 'avg_height': 0,
                'min_width': 0, 'max_width': 0,
                'min_height': 0, 'max_height': 0
            }
        
        return {
            'avg_width': statistics.mean(widths),
            'avg_height': statistics.mean(heights),
            'min_width': min(widths),
            'max_width': max(widths),
            'min_height': min(heights),
            'max_height': max(heights)
        }

    def _calculate_hash_stats(self, hashes, hash_to_files, hash_per_class):
        """Calculate hash and duplicate statistics"""
        unique_hashes = len(set(hashes))
        total_hashes = len(hashes)
        inter_class_duplicates = {}
        intra_class_duplicates = {}
        
        for hash_val, files in hash_to_files.items():
            if len(files) > 1:
                classes_with_hash = {class_key for class_key, class_hashes in hash_per_class.items() if hash_val in class_hashes}
                
                if len(classes_with_hash) > 1:
                    inter_class_duplicates[hash_val] = files
                else:
                    intra_class_duplicates[hash_val] = files
        
        return {
            'unique_count': unique_hashes,
            'duplicate_count': total_hashes - unique_hashes,
            'total_count': total_hashes,
            'inter_class_duplicates': inter_class_duplicates,
            'intra_class_duplicates': intra_class_duplicates,
            'duplicate_summary': {
                'inter_class_duplicate_hashes': len(inter_class_duplicates),
                'intra_class_duplicate_hashes': len(intra_class_duplicates),
                'total_duplicate_hashes': len(inter_class_duplicates) + len(intra_class_duplicates),
                'total_duplicate_files': sum(len(files) for files in inter_class_duplicates.values()) + sum(len(files) for files in intra_class_duplicates.values())
            }
        }
    
    def calculate_temporal_stats(self):
        """Calculate temporal statistics from unified metadata"""
        download_times = []
        
        # Extract download timestamps from unified format
        for img_data in self.image_data:
            images_dict = img_data.get('images', {})
            for img_key, img_entry in images_dict.items():
                if isinstance(img_entry, dict) and 'download_data' in img_entry:
                    downloaded_at = img_entry['download_data'].get('downloaded_at')
                    if downloaded_at:
                        try:
                            dt = datetime.fromisoformat(downloaded_at.replace('Z', '+00:00'))
                            download_times.append(dt)
                        except (ValueError, TypeError):
                            continue
        
        if not download_times:
            return {
                'time_span': {'earliest': None, 'latest': None, 'duration_hours': 0},
                'average_interval': {'seconds': 0, 'minutes': 0}
            }
        
        download_times.sort()
        
        # Calculate time span
        time_span = {
            'earliest': download_times[0].isoformat(),
            'latest': download_times[-1].isoformat(),
            'duration_hours': (download_times[-1] - download_times[0]).total_seconds() / 3600
        }
        
        # Calculate average interval between downloads
        if len(download_times) > 1:
            intervals = [(download_times[i] - download_times[i-1]).total_seconds()
                        for i in range(1, len(download_times))]
            avg_seconds = statistics.mean(intervals)
            average_interval = {
                'seconds': avg_seconds,
                'minutes': avg_seconds / 60
            }
        else:
            average_interval = {'seconds': 0, 'minutes': 0}
        
        return {
            'time_span': time_span,
            'average_interval': average_interval
        }
    
    def calculate_quality_checks(self):
        """Calculate quality check statistics from unified metadata"""
        total_urls_found = 0
        total_downloaded = 0
        classes_with_issues = []
        
        for img_data in self.image_data:
            class_key = f"{img_data['category']}/{img_data['class_name']}"
            images_dict = img_data.get('images', {})
            
            # Count URLs found and successfully downloaded
            urls_found = len(images_dict)
            urls_downloaded = sum(1 for img_entry in images_dict.values()
                                if isinstance(img_entry, dict) and 'download_data' in img_entry)
            
            total_urls_found += urls_found
            total_downloaded += urls_downloaded
            
            # Track classes with download issues
            missing_downloads = urls_found - urls_downloaded
            if missing_downloads > 0:
                classes_with_issues.append({
                    'class': class_key,
                    'urls_found': urls_found,
                    'urls_downloaded': urls_downloaded,
                    'missing_downloads': missing_downloads
                })
        
        urls_missing_downloads = total_urls_found - total_downloaded
        success_rate = (total_downloaded / total_urls_found * 100) if total_urls_found > 0 else 0
        
        return {
            'urls_found_but_missing_metadata': urls_missing_downloads,
            'total_urls_found': total_urls_found,
            'total_downloaded': total_downloaded,
            'classes_with_issues': classes_with_issues,
            'success_rate': success_rate
        }
    
    def _get_output_path(self, filename, default_name):
        """Get absolute output path for report files"""
        if filename is None:
            return os.path.join(self.output_dir, default_name)
        elif not os.path.isabs(filename):
            return os.path.join(self.output_dir, filename)
        return filename

    def generate_report_json(self, output_file=None, duplicates_file=None):
        """Generate JSON report file and separate duplicates file"""
        # Resolve output paths
        output_file = self._get_output_path(output_file, "report.json")
        duplicates_file = self._get_output_path(duplicates_file, "duplicates.json")
        
        # Ensure output directories exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        os.makedirs(os.path.dirname(duplicates_file), exist_ok=True)
        
        # Calculate all statistics with progress logging
        logger.status("Calculating quantitative statistics...")
        quant_stats = self.calculate_quantitative_stats()
        
        logger.status("Calculating temporal statistics...")
        temp_stats = self.calculate_temporal_stats()
        
        logger.status("Calculating quality check statistics...")
        quality_stats = self.calculate_quality_checks()
        
        generation_time = datetime.now().isoformat()
        
        # Create main report (without detailed duplicate lists)
        hash_stats = quant_stats['hashes']
        simplified_hash_analysis = {
            'unique_count': hash_stats['unique_count'],
            'duplicate_count': hash_stats['duplicate_count'],
            'total_count': hash_stats['total_count'],
            'duplicate_summary': hash_stats['duplicate_summary']
        }
        
        report = {
            "generated_at": generation_time,
            "quantitative_statistics": quant_stats,
            "temporal_statistics": temp_stats,
            "quality_checks": quality_stats
        }
        
        # Replace detailed hash data with simplified version
        report["quantitative_statistics"]["hashes"] = simplified_hash_analysis
        
        # Create detailed duplicates report
        duplicates_data = {
            "generated_at": generation_time,
            "inter_class_duplicates": hash_stats['inter_class_duplicates'],
            "intra_class_duplicates": hash_stats['intra_class_duplicates'],
            "duplicate_summary": hash_stats['duplicate_summary']
        }
        
        # Write reports with progress logging
        logger.status("Writing report files...")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.success(f"Main report generated: {Path(output_file).name}")
            
            with open(duplicates_file, 'w', encoding='utf-8') as f:
                json.dump(duplicates_data, f, indent=2, ensure_ascii=False)
            logger.success(f"Duplicates report generated: {Path(duplicates_file).name}")
            
        except Exception as e:
            logger.error(f"Failed to write report files: {e}")
            raise
        
        return report, duplicates_data


def main(output_dir=None):
    """Main function to generate the report"""
    try:
        logger.status("Starting image download report generation...")
        
        # Initialize report generator
        report = ImageDownloadReport(output_dir or cfg.get_output_dir())
        
        # Load and validate metadata
        report.load_metadata()
        if not report.image_data:
            logger.error("No unified metadata files found. Please ensure data exists in unified format.")
            logger.info("Expected format: output/metadata/<Category>/<Class>/*_metadata.json")
            return 1
        
        # Generate reports
        main_report, duplicates_report = report.generate_report_json()
        
        # Display comprehensive summary
        qs = main_report['quantitative_statistics']
        
        # File size calculations
        file_size = qs['file_size']
        avg_size_mb = file_size['average_bytes'] / 1048576 if file_size['average_bytes'] > 0 else 0
        total_size_mb = file_size['total_bytes'] / 1048576 if file_size['total_bytes'] > 0 else 0
        
        # Category summary
        categories = ', '.join(f"{k}: {v}" for k, v in qs['images_per_category'].items())
        
        logger.success("Report generation completed successfully!")
        logger.info(f"📊 Report Summary:")
        logger.info(f"   📸 Total Images: {qs['total_image_count']:,}")
        logger.info(f"   📁 Total Classes: {len(qs['images_per_class'])}")
        logger.info(f"   📂 Categories: {categories}")
        logger.info(f"   ✅ Download Success Rate: {main_report['quality_checks']['success_rate']:.1f}%")
        logger.info(f"   🔄 Duplicate Images: {qs['hashes']['duplicate_count']:,}")
        logger.info(f"   💾 Average Size: {avg_size_mb:.1f} MB")
        logger.info(f"   📦 Total Size: {total_size_mb:.1f} MB")
        
        # Time span info if available
        if main_report['temporal_statistics']['time_span']['earliest']:
            duration_hours = main_report['temporal_statistics']['time_span']['duration_hours']
            logger.info(f"   ⏱️  Collection Duration: {duration_hours:.1f} hours")
        
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in metadata file: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error generating report: {e}")
        import traceback
        logger.error("Full traceback:")
        for line in traceback.format_exc().splitlines():
            logger.error(f"  {line}")
        return 1


if __name__ == "__main__":
    # Support command line argument for custom output directory
    output_dir = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Enable verbose logging for better user experience
    logger.set_verbose(True)
    
    try:
        exit_code = main(output_dir)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("Report generation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Critical error: {e}")
        sys.exit(1)