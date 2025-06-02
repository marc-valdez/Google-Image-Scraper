import json
import pandas as pd
from datetime import datetime
from pathlib import Path

def load_report_data(filepath='sample_report.json'):
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data

def extract_quantitative_stats(data):
    return data.get('quantitative_statistics', {})

def extract_temporal_stats(data):
    return data.get('temporal_statistics', {})

def extract_quality_stats(data):
    return data.get('quality_checks', {})

def create_class_distribution_df(data):
    quant_stats = extract_quantitative_stats(data)
    images_per_class = quant_stats.get('images_per_class', {})
    
    df = pd.DataFrame([
        {'class': class_name, 'count': count}
        for class_name, count in images_per_class.items()
    ])
    return df

def create_category_distribution_df(data):
    quant_stats = extract_quantitative_stats(data)
    images_per_category = quant_stats.get('images_per_category', {})
    
    df = pd.DataFrame([
        {'category': category, 'count': count}
        for category, count in images_per_category.items()
    ])
    return df

def create_format_distribution_df(data):
    quant_stats = extract_quantitative_stats(data)
    formats = quant_stats.get('formats', {})
    
    df = pd.DataFrame([
        {'format': fmt.upper(), 'count': count}
        for fmt, count in formats.items()
    ])
    return df.sort_values('count', ascending=False)

def create_color_mode_df(data):
    quant_stats = extract_quantitative_stats(data)
    color_modes = quant_stats.get('color_modes', {})
    
    df = pd.DataFrame([
        {'color_mode': mode, 'count': count}
        for mode, count in color_modes.items()
    ])
    return df.sort_values('count', ascending=False)

def create_quality_issues_df(data):
    quality_stats = extract_quality_stats(data)
    classes_with_issues = quality_stats.get('classes_with_issues', [])
    
    df = pd.DataFrame(classes_with_issues)
    if not df.empty:
        df['success_rate'] = ((df['urls_downloaded'] / df['urls_found']) * 100).round(2)
    return df

def get_file_size_stats(data):
    quant_stats = extract_quantitative_stats(data)
    return quant_stats.get('file_size', {})

def get_dimension_stats(data):
    quant_stats = extract_quantitative_stats(data)
    return quant_stats.get('dimensions', {})

def get_duplicate_stats(data):
    quant_stats = extract_quantitative_stats(data)
    hashes = quant_stats.get('hashes', {})
    return {
        'unique_count': hashes.get('unique_count', 0),
        'duplicate_count': hashes.get('duplicate_count', 0),
        'total_count': hashes.get('total_count', 0),
        'duplicate_summary': hashes.get('duplicate_summary', {})
    }

def get_temporal_metrics(data):
    temporal_stats = extract_temporal_stats(data)
    time_span = temporal_stats.get('time_span', {})
    average_interval = temporal_stats.get('average_interval', {})
    
    return {
        'duration_hours': time_span.get('duration_hours', 0),
        'earliest': time_span.get('earliest', ''),
        'latest': time_span.get('latest', ''),
        'avg_interval_seconds': average_interval.get('seconds', 0),
        'avg_interval_minutes': average_interval.get('minutes', 0)
    }

def get_overview_metrics(data):
    quant_stats = extract_quantitative_stats(data)
    quality_stats = extract_quality_stats(data)
    
    return {
        'total_images': quant_stats.get('total_image_count', 0),
        'success_rate': quality_stats.get('success_rate', 0),
        'total_urls_found': quality_stats.get('total_urls_found', 0),
        'total_downloaded': quality_stats.get('total_downloaded', 0),
        'total_classes': len(quant_stats.get('images_per_class', {})),
        'total_categories': len(quant_stats.get('images_per_category', {})),
        'total_formats': len(quant_stats.get('formats', {})),
        'avg_file_size_mb': quant_stats.get('file_size', {}).get('average_bytes', 0) / (1024 * 1024)
    }

def format_bytes(bytes_value):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} TB"

def format_duration(hours):
    if hours < 1:
        return f"{hours * 60:.1f} minutes"
    elif hours < 24:
        return f"{hours:.1f} hours"
    else:
        days = hours / 24
        return f"{days:.1f} days"