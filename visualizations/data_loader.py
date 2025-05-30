"""
Data loading and processing utilities for image scraper metadata
"""

import json
import glob
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple
import numpy as np


def load_all_metadata(output_dir="../output") -> List[Dict[str, Any]]:
    """
    Load all metadata files from the output directory
    
    Args:
        output_dir: Path to the output directory containing metadata
        
    Returns:
        List of metadata dictionaries
    """
    metadata_pattern = os.path.join(output_dir, "metadata", "*", "*", "*_metadata.json")
    json_files = glob.glob(metadata_pattern)
    
    print(f"Found {len(json_files)} metadata files")
    
    all_metadata = []
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate unified format
            if 'images' not in data or 'search_key' not in data:
                print(f"⚠️ Skipping non-unified format file: {Path(json_file).name}")
                continue
            
            # Extract category and class from path
            path_parts = Path(json_file).parts
            data['category'] = path_parts[-3]
            data['class_name'] = path_parts[-2]
            data['file_path'] = json_file
            
            all_metadata.append(data)
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {Path(json_file).name}: {e}")
        except Exception as e:
            print(f"❌ Error reading {Path(json_file).name}: {e}")
    
    print(f"✅ Successfully loaded {len(all_metadata)} metadata files")
    return all_metadata


def create_summary_dataframe(metadata_list: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Create a summary DataFrame from the metadata
    
    Args:
        metadata_list: List of metadata dictionaries
        
    Returns:
        DataFrame with summary statistics per class
    """
    summary_data = []
    
    for metadata in metadata_list:
        category = metadata['category']
        class_name = metadata['class_name']
        search_key = metadata['search_key']
        images = metadata.get('images', {})
        
        # Count total images and successfully downloaded images
        total_images = len(images)
        downloaded_images = sum(1 for img in images.values() 
                               if isinstance(img, dict) and 'download_data' in img)
        
        # URLs info
        urls_requested = metadata.get('number_of_images_requested', 0)
        urls_found = metadata.get('number_of_urls_found', 0)
        
        summary_data.append({
            'category': category,
            'class_name': class_name,
            'search_key': search_key,
            'urls_requested': urls_requested,
            'urls_found': urls_found,
            'total_images': total_images,
            'downloaded_images': downloaded_images,
            'download_success_rate': (downloaded_images / total_images * 100) if total_images > 0 else 0,
            'file_path': metadata['file_path']
        })
    
    return pd.DataFrame(summary_data)


def create_image_details_dataframe(metadata_list: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Create a detailed DataFrame with one row per image
    
    Args:
        metadata_list: List of metadata dictionaries
        
    Returns:
        DataFrame with detailed information per image
    """
    image_data = []
    
    for metadata in metadata_list:
        category = metadata['category']
        class_name = metadata['class_name']
        search_key = metadata['search_key']
        images = metadata.get('images', {})
        
        for img_id, img_info in images.items():
            if not isinstance(img_info, dict):
                continue
                
            # Basic info
            row = {
                'category': category,
                'class_name': class_name,
                'search_key': search_key,
                'image_id': img_id,
                'has_fetch_data': 'fetch_data' in img_info,
                'has_download_data': 'download_data' in img_info
            }
            
            # Fetch data
            if 'fetch_data' in img_info:
                fetch_data = img_info['fetch_data']
                row.update({
                    'source_url': fetch_data.get('link', ''),
                    'domain': fetch_data.get('domain', ''),
                    'original_filename': fetch_data.get('original_filename', ''),
                    'xpath_index': fetch_data.get('xpath_index', 0)
                })
            
            # Download data
            if 'download_data' in img_info:
                download_data = img_info['download_data']
                row.update({
                    'filename': download_data.get('filename', ''),
                    'relative_path': download_data.get('relative_path', ''),
                    'hash': download_data.get('hash', ''),
                    'bytes': download_data.get('bytes', 0),
                    'width': download_data.get('width', 0),
                    'height': download_data.get('height', 0),
                    'mode': download_data.get('mode', ''),
                    'format': download_data.get('format', ''),
                    'downloaded_at': download_data.get('downloaded_at', '')
                })
                
                # Calculate derived fields
                if row['width'] > 0 and row['height'] > 0:
                    row['aspect_ratio'] = row['width'] / row['height']
                    row['pixel_count'] = row['width'] * row['height']
                else:
                    row['aspect_ratio'] = 0
                    row['pixel_count'] = 0
                
                # Parse download timestamp
                if row['downloaded_at']:
                    try:
                        dt = datetime.fromisoformat(row['downloaded_at'].replace('Z', '+00:00'))
                        row['download_timestamp'] = dt
                        row['download_date'] = dt.date()
                        row['download_hour'] = dt.hour
                    except:
                        row['download_timestamp'] = None
                        row['download_date'] = None
                        row['download_hour'] = None
            
            image_data.append(row)
    
    return pd.DataFrame(image_data)


def get_duplicate_analysis(image_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze duplicates in the image dataset
    
    Args:
        image_df: DataFrame with image details
        
    Returns:
        Dictionary with duplicate analysis results
    """
    # Filter to only downloaded images with hashes
    downloaded_df = image_df[
        (image_df['has_download_data'] == True) & 
        (image_df['hash'].notna()) & 
        (image_df['hash'] != '')
    ].copy()
    
    if len(downloaded_df) == 0:
        return {
            'total_images': 0,
            'unique_hashes': 0,
            'duplicate_count': 0,
            'duplicate_hashes': [],
            'inter_class_duplicates': {},
            'intra_class_duplicates': {}
        }
    
    # Count hash occurrences
    hash_counts = downloaded_df['hash'].value_counts()
    duplicate_hashes = hash_counts[hash_counts > 1].index.tolist()
    
    # Analyze duplicate types
    inter_class_duplicates = {}
    intra_class_duplicates = {}
    
    for hash_val in duplicate_hashes:
        hash_images = downloaded_df[downloaded_df['hash'] == hash_val]
        classes = hash_images['class_name'].unique()
        
        if len(classes) > 1:
            # Inter-class duplicates (same image in different classes)
            inter_class_duplicates[hash_val] = {
                'classes': classes.tolist(),
                'files': hash_images['relative_path'].tolist(),
                'count': len(hash_images)
            }
        else:
            # Intra-class duplicates (same image multiple times in same class)
            intra_class_duplicates[hash_val] = {
                'class': classes[0],
                'files': hash_images['relative_path'].tolist(),
                'count': len(hash_images)
            }
    
    return {
        'total_images': len(downloaded_df),
        'unique_hashes': len(hash_counts),
        'duplicate_count': len(downloaded_df) - len(hash_counts),
        'duplicate_hashes': duplicate_hashes,
        'inter_class_duplicates': inter_class_duplicates,
        'intra_class_duplicates': intra_class_duplicates,
        'duplicate_rate': (len(downloaded_df) - len(hash_counts)) / len(downloaded_df) * 100 if len(downloaded_df) > 0 else 0
    }


def get_category_stats(summary_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Get statistics by category
    
    Args:
        summary_df: Summary DataFrame
        
    Returns:
        Dictionary with category statistics
    """
    category_stats = {}
    
    for category in summary_df['category'].unique():
        cat_data = summary_df[summary_df['category'] == category]
        
        category_stats[category] = {
            'total_classes': len(cat_data),
            'total_images': cat_data['downloaded_images'].sum(),
            'avg_images_per_class': cat_data['downloaded_images'].mean(),
            'min_images_per_class': cat_data['downloaded_images'].min(),
            'max_images_per_class': cat_data['downloaded_images'].max(),
            'avg_success_rate': cat_data['download_success_rate'].mean(),
            'classes': cat_data['class_name'].tolist()
        }
    
    return category_stats


def get_temporal_stats(image_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Get temporal statistics from image download timestamps
    
    Args:
        image_df: DataFrame with image details
        
    Returns:
        Dictionary with temporal statistics
    """
    # Filter to downloaded images with timestamps
    temporal_df = image_df[
        (image_df['has_download_data'] == True) & 
        (image_df['download_timestamp'].notna())
    ].copy()
    
    if len(temporal_df) == 0:
        return {
            'has_temporal_data': False,
            'total_images': 0
        }
    
    timestamps = temporal_df['download_timestamp'].sort_values()
    
    # Calculate intervals between downloads
    intervals = []
    if len(timestamps) > 1:
        for i in range(1, len(timestamps)):
            interval = (timestamps.iloc[i] - timestamps.iloc[i-1]).total_seconds()
            intervals.append(interval)
    
    return {
        'has_temporal_data': True,
        'total_images': len(temporal_df),
        'earliest_download': timestamps.min(),
        'latest_download': timestamps.max(),
        'duration_hours': (timestamps.max() - timestamps.min()).total_seconds() / 3600,
        'avg_interval_seconds': np.mean(intervals) if intervals else 0,
        'median_interval_seconds': np.median(intervals) if intervals else 0,
        'downloads_by_hour': temporal_df.groupby('download_hour').size().to_dict(),
        'downloads_by_date': temporal_df.groupby('download_date').size().to_dict()
    }