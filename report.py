#!/usr/bin/env python3
"""
Image Download Report Generator

Analyzes metadata from URL fetcher and image downloader to generate comprehensive statistics.
Reads JSON files from /output/<Category>/<Class>/.cache/<.json>
"""

import os
import json
import glob
from datetime import datetime
from collections import defaultdict, Counter
import statistics
from pathlib import Path

class ImageDownloadReport:
    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        self.url_data = []
        self.image_data = []
        self.categories = ["Go", "Grow", "Glow"]
        
    def load_metadata(self):
        """Load all JSON metadata files from cache directories"""
        print("Loading metadata files...")
        
        # Pattern: output/<Category>/<Class>/.cache/*.json
        cache_pattern = os.path.join(self.output_dir, "*", "*", ".cache", "*.json")
        json_files = glob.glob(cache_pattern)
        
        print(f"Found {len(json_files)} JSON files")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract category and class from path
                path_parts = Path(json_file).parts
                category = path_parts[-4]  # output/<Category>/<Class>/.cache/file.json
                class_name = path_parts[-3]
                
                # Determine if this is URL data or image metadata
                if 'urls' in data and 'search_key' in data:
                    # URL fetcher data
                    data['category'] = category
                    data['class_name'] = class_name
                    data['file_path'] = json_file
                    self.url_data.append(data)
                elif 'image_cache' in data:
                    # Image downloader data
                    data['category'] = category
                    data['class_name'] = class_name
                    data['file_path'] = json_file
                    self.image_data.append(data)
                    
            except Exception as e:
                print(f"Error reading {json_file}: {e}")
                
        print(f"Loaded {len(self.url_data)} URL cache files")
        print(f"Loaded {len(self.image_data)} image metadata files")
    
    def calculate_quantitative_stats(self):
        """Calculate quantitative statistics"""
        stats = {}
        
        # Total images across all metadata
        total_images = 0
        images_per_class = defaultdict(int)
        images_per_category = defaultdict(int)
        
        file_sizes = []
        widths = []
        heights = []
        color_modes = []
        formats = []
        hashes = []
        
        # Enhanced hash tracking with file locations
        hash_to_files = defaultdict(list)
        hash_per_class = defaultdict(lambda: defaultdict(list))
        
        for img_data in self.image_data:
            category = img_data['category']
            class_name = img_data['class_name']
            image_cache = img_data.get('image_cache', {})
            
            class_image_count = len(image_cache)
            total_images += class_image_count
            images_per_class[class_name] += class_image_count
            images_per_category[category] += class_image_count
            
            # Process each image's metadata
            for url, metadata in image_cache.items():
                if isinstance(metadata, dict):
                    # File size
                    size = metadata.get('size', 0)
                    if size > 0:
                        file_sizes.append(size)
                    
                    # Dimensions
                    width = metadata.get('width', 0)
                    height = metadata.get('height', 0)
                    if width > 0:
                        widths.append(width)
                    if height > 0:
                        heights.append(height)
                    
                    # Color mode
                    mode = metadata.get('mode', 'unknown')
                    if mode:
                        color_modes.append(mode)
                    
                    # Format
                    fmt = metadata.get('format', 'unknown')
                    if fmt:
                        formats.append(fmt.lower())
                    
                    # Hash for duplicate detection
                    hash_val = metadata.get('hash')
                    if hash_val:
                        hashes.append(hash_val)
                        
                        # Track file location for this hash
                        file_path = metadata.get('relative_path', 'unknown')
                        class_key = f"{category}/{class_name}"
                        
                        hash_to_files[hash_val].append(file_path)
                        hash_per_class[class_key][hash_val].append(file_path)
        
        # Calculate statistics
        stats['total_image_count'] = total_images
        stats['images_per_class'] = dict(images_per_class)
        stats['images_per_category'] = dict(images_per_category)
        
        # File size statistics (in bytes)
        if file_sizes:
            stats['file_size'] = {
                'average_bytes': statistics.mean(file_sizes),
                'min_bytes': min(file_sizes),
                'max_bytes': max(file_sizes),
                'total_bytes': sum(file_sizes)
            }
        else:
            stats['file_size'] = {'average_bytes': 0, 'min_bytes': 0, 'max_bytes': 0, 'total_bytes': 0}
        
        # Dimension statistics
        if widths:
            stats['dimensions'] = {
                'avg_width': statistics.mean(widths),
                'avg_height': statistics.mean(heights),
                'min_width': min(widths),
                'max_width': max(widths),
                'min_height': min(heights),
                'max_height': max(heights)
            }
        else:
            stats['dimensions'] = {
                'avg_width': 0, 'avg_height': 0,
                'min_width': 0, 'max_width': 0,
                'min_height': 0, 'max_height': 0
            }
        
        # Color mode distribution
        stats['color_modes'] = dict(Counter(color_modes))
        
        # Format distribution
        stats['formats'] = dict(Counter(formats))
        
        # Enhanced hash statistics with inter/intra class analysis
        unique_hashes = len(set(hashes))
        total_hashes = len(hashes)
        
        # Find inter-class duplicates (same hash across different classes)
        inter_class_duplicates = {}
        # Find intra-class duplicates (same hash within same class)
        intra_class_duplicates = {}
        
        for hash_val, files in hash_to_files.items():
            if len(files) > 1:
                # Check which classes this hash appears in
                classes_with_hash = set()
                for class_key, class_hashes in hash_per_class.items():
                    if hash_val in class_hashes:
                        classes_with_hash.add(class_key)
                
                if len(classes_with_hash) > 1:
                    # Inter-class duplicate (appears in multiple classes)
                    inter_class_duplicates[hash_val] = files
                else:
                    # Intra-class duplicate (appears multiple times in same class)
                    intra_class_duplicates[hash_val] = files
        
        stats['hashes'] = {
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
        
        return stats
    
    def calculate_temporal_stats(self):
        """Calculate temporal statistics"""
        stats = {}
        download_times = []
        
        for img_data in self.image_data:
            image_cache = img_data.get('image_cache', {})
            
            for url, metadata in image_cache.items():
                if isinstance(metadata, dict):
                    downloaded_at = metadata.get('downloaded_at')
                    if downloaded_at:
                        try:
                            dt = datetime.fromisoformat(downloaded_at.replace('Z', '+00:00'))
                            download_times.append(dt)
                        except:
                            continue
        
        if download_times:
            download_times.sort()
            stats['time_span'] = {
                'earliest': download_times[0].isoformat(),
                'latest': download_times[-1].isoformat(),
                'duration_hours': (download_times[-1] - download_times[0]).total_seconds() / 3600
            }
            
            # Calculate average time between downloads
            if len(download_times) > 1:
                intervals = []
                for i in range(1, len(download_times)):
                    interval = (download_times[i] - download_times[i-1]).total_seconds()
                    intervals.append(interval)
                
                stats['average_interval'] = {
                    'seconds': statistics.mean(intervals),
                    'minutes': statistics.mean(intervals) / 60
                }
            else:
                stats['average_interval'] = {'seconds': 0, 'minutes': 0}
        else:
            stats['time_span'] = {'earliest': None, 'latest': None, 'duration_hours': 0}
            stats['average_interval'] = {'seconds': 0, 'minutes': 0}
        
        return stats
    
    def calculate_quality_checks(self):
        """Calculate quality check statistics"""
        stats = {}
        
        urls_found_but_missing_metadata = 0
        total_urls_found = 0
        classes_with_issues = []
        
        # Create a mapping of URLs to image metadata for each class
        image_metadata_by_class = {}
        for img_data in self.image_data:
            class_key = f"{img_data['category']}/{img_data['class_name']}"
            image_metadata_by_class[class_key] = set(img_data.get('image_cache', {}).keys())
        
        # Check URL data against image metadata
        for url_data in self.url_data:
            class_key = f"{url_data['category']}/{url_data['class_name']}"
            urls = url_data.get('urls', [])
            total_urls_found += len(urls)
            
            # Get corresponding image metadata
            downloaded_urls = image_metadata_by_class.get(class_key, set())
            
            missing_count = 0
            for url in urls:
                if url not in downloaded_urls:
                    missing_count += 1
            
            urls_found_but_missing_metadata += missing_count
            
            if missing_count > 0:
                classes_with_issues.append({
                    'class': class_key,
                    'urls_found': len(urls),
                    'urls_downloaded': len(downloaded_urls),
                    'missing_downloads': missing_count
                })
        
        stats['urls_found_but_missing_metadata'] = urls_found_but_missing_metadata
        stats['total_urls_found'] = total_urls_found
        stats['classes_with_issues'] = classes_with_issues
        stats['success_rate'] = ((total_urls_found - urls_found_but_missing_metadata) / total_urls_found * 100) if total_urls_found > 0 else 0
        
        return stats
    
    def generate_report_json(self, output_file="report.json", duplicates_file="duplicates.json"):
        """Generate JSON report file and separate duplicates file"""
        quant_stats = self.calculate_quantitative_stats()
        temp_stats = self.calculate_temporal_stats()
        quality_stats = self.calculate_quality_checks()
        
        # Extract duplicates data for separate file
        duplicates_data = {
            "generated_at": datetime.now().isoformat(),
            "inter_class_duplicates": quant_stats['hashes']['inter_class_duplicates'],
            "intra_class_duplicates": quant_stats['hashes']['intra_class_duplicates'],
            "duplicate_summary": quant_stats['hashes']['duplicate_summary']
        }
        
        # Create simplified hash analysis for main report
        simplified_hash_analysis = {
            'unique_count': quant_stats['hashes']['unique_count'],
            'duplicate_count': quant_stats['hashes']['duplicate_count'],
            'total_count': quant_stats['hashes']['total_count'],
            'duplicate_summary': quant_stats['hashes']['duplicate_summary']
        }
        
        # Main report without detailed duplicates
        report = {
            "generated_at": datetime.now().isoformat(),
            "quantitative_statistics": {
                "total_image_count": quant_stats['total_image_count'],
                "images_per_category": quant_stats['images_per_category'],
                "images_per_class": quant_stats['images_per_class'],
                "file_size_bytes": quant_stats['file_size'],
                "dimensions": quant_stats['dimensions'],
                "color_modes": quant_stats['color_modes'],
                "formats": quant_stats['formats'],
                "hash_analysis": simplified_hash_analysis
            },
            "temporal_statistics": temp_stats,
            "quality_checks": quality_stats
        }
        
        # Write main report
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Write duplicates report
        with open(duplicates_file, 'w', encoding='utf-8') as f:
            json.dump(duplicates_data, f, indent=2, ensure_ascii=False)
        
        print(f"Report generated: {output_file}")
        print(f"Duplicates report generated: {duplicates_file}")
        return report, duplicates_data


def main():
    """Main function to generate the report"""
    try:
        report = ImageDownloadReport()
        report.load_metadata()
        report.generate_report_json()
    except Exception as e:
        print(f"Error generating report: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()