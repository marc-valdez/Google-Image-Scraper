"""
Plotting functions for image scraper data visualization
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# Set default style
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")


def plot_category_distribution(summary_df: pd.DataFrame, use_plotly: bool = True):
    """
    Plot distribution of images across categories
    
    Args:
        summary_df: Summary DataFrame
        use_plotly: Whether to use Plotly (True) or Matplotlib (False)
    """
    category_counts = summary_df.groupby('category')['downloaded_images'].sum()
    
    if use_plotly:
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Images by Category', 'Classes by Category'),
            specs=[[{"type": "pie"}, {"type": "bar"}]]
        )
        
        # Pie chart for image counts
        fig.add_trace(
            go.Pie(
                labels=category_counts.index,
                values=category_counts.values,
                name="Images",
                hole=0.4
            ),
            row=1, col=1
        )
        
        # Bar chart for class counts
        class_counts = summary_df.groupby('category').size()
        fig.add_trace(
            go.Bar(
                x=class_counts.index,
                y=class_counts.values,
                name="Classes",
                text=class_counts.values,
                textposition='auto'
            ),
            row=1, col=2
        )
        
        fig.update_layout(
            title_text="📊 Category Distribution",
            title_x=0.5,
            height=400,
            showlegend=False
        )
        
        fig.show()
    
    else:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # Pie chart
        ax1.pie(category_counts.values, labels=category_counts.index, autopct='%1.1f%%')
        ax1.set_title('Images by Category')
        
        # Bar chart
        class_counts = summary_df.groupby('category').size()
        ax2.bar(class_counts.index, class_counts.values)
        ax2.set_title('Classes by Category')
        ax2.set_ylabel('Number of Classes')
        
        plt.tight_layout()
        plt.show()


def plot_class_distribution(summary_df: pd.DataFrame, top_n: int = 20, use_plotly: bool = True):
    """
    Plot distribution of images across classes
    
    Args:
        summary_df: Summary DataFrame
        top_n: Number of top classes to show
        use_plotly: Whether to use Plotly (True) or Matplotlib (False)
    """
    class_counts = summary_df.set_index('class_name')['downloaded_images'].sort_values(ascending=False)
    top_classes = class_counts.head(top_n)
    
    if use_plotly:
        fig = go.Figure(data=go.Bar(
            x=top_classes.values,
            y=top_classes.index,
            orientation='h',
            text=top_classes.values,
            textposition='auto'
        ))
        
        fig.update_layout(
            title=f"📈 Top {top_n} Classes by Image Count",
            xaxis_title="Number of Images",
            yaxis_title="Class Name",
            height=max(400, top_n * 25),
            yaxis={'categoryorder': 'total ascending'}
        )
        
        fig.show()
    
    else:
        plt.figure(figsize=(10, max(6, top_n * 0.3)))
        plt.barh(range(len(top_classes)), top_classes.values)
        plt.yticks(range(len(top_classes)), top_classes.index)
        plt.xlabel('Number of Images')
        plt.title(f'Top {top_n} Classes by Image Count')
        plt.gca().invert_yaxis()
        plt.tight_layout()
        plt.show()


def plot_success_rates(summary_df: pd.DataFrame, use_plotly: bool = True):
    """
    Plot download success rates
    
    Args:
        summary_df: Summary DataFrame
        use_plotly: Whether to use Plotly (True) or Matplotlib (False)
    """
    if use_plotly:
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Overall Success Rate Distribution',
                'Success Rate by Category',
                'Success Rate vs Images Downloaded',
                'Classes with Low Success Rates'
            )
        )
        
        # Histogram of success rates
        fig.add_trace(
            go.Histogram(
                x=summary_df['download_success_rate'],
                nbinsx=20,
                name="Success Rate Distribution"
            ),
            row=1, col=1
        )
        
        # Success rate by category
        category_success = summary_df.groupby('category')['download_success_rate'].mean()
        fig.add_trace(
            go.Bar(
                x=category_success.index,
                y=category_success.values,
                text=[f"{v:.1f}%" for v in category_success.values],
                textposition='auto',
                name="Category Success Rate"
            ),
            row=1, col=2
        )
        
        # Scatter plot: success rate vs images downloaded
        fig.add_trace(
            go.Scatter(
                x=summary_df['downloaded_images'],
                y=summary_df['download_success_rate'],
                mode='markers',
                text=summary_df['class_name'],
                name="Success vs Count"
            ),
            row=2, col=1
        )
        
        # Classes with low success rates (< 80%)
        low_success = summary_df[summary_df['download_success_rate'] < 80].sort_values('download_success_rate')
        if len(low_success) > 0:
            fig.add_trace(
                go.Bar(
                    x=low_success['download_success_rate'],
                    y=low_success['class_name'],
                    orientation='h',
                    text=[f"{v:.1f}%" for v in low_success['download_success_rate']],
                    textposition='auto',
                    name="Low Success Classes"
                ),
                row=2, col=2
            )
        
        fig.update_layout(
            title_text="📊 Download Success Analysis",
            title_x=0.5,
            height=800,
            showlegend=False
        )
        
        fig.show()
    
    else:
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Histogram
        axes[0, 0].hist(summary_df['download_success_rate'], bins=20, alpha=0.7)
        axes[0, 0].set_title('Success Rate Distribution')
        axes[0, 0].set_xlabel('Success Rate (%)')
        
        # Category success rates
        category_success = summary_df.groupby('category')['download_success_rate'].mean()
        axes[0, 1].bar(category_success.index, category_success.values)
        axes[0, 1].set_title('Success Rate by Category')
        axes[0, 1].set_ylabel('Average Success Rate (%)')
        
        # Scatter plot
        axes[1, 0].scatter(summary_df['downloaded_images'], summary_df['download_success_rate'])
        axes[1, 0].set_xlabel('Images Downloaded')
        axes[1, 0].set_ylabel('Success Rate (%)')
        axes[1, 0].set_title('Success Rate vs Downloaded Count')
        
        # Low success rates
        low_success = summary_df[summary_df['download_success_rate'] < 80].sort_values('download_success_rate')
        if len(low_success) > 0:
            axes[1, 1].barh(range(len(low_success)), low_success['download_success_rate'])
            axes[1, 1].set_yticks(range(len(low_success)))
            axes[1, 1].set_yticklabels(low_success['class_name'])
            axes[1, 1].set_title('Classes with Low Success Rates')
        
        plt.tight_layout()
        plt.show()


def plot_file_characteristics(image_df: pd.DataFrame, use_plotly: bool = True):
    """
    Plot file characteristics (size, dimensions, format, etc.)
    
    Args:
        image_df: Detailed image DataFrame
        use_plotly: Whether to use Plotly (True) or Matplotlib (False)
    """
    # Filter to downloaded images only
    downloaded_df = image_df[image_df['has_download_data'] == True].copy()
    
    if len(downloaded_df) == 0:
        print("No downloaded images found for analysis")
        return
    
    if use_plotly:
        fig = make_subplots(
            rows=2, cols=3,
            subplot_titles=(
                'File Size Distribution',
                'Image Dimensions',
                'Format Distribution',
                'Aspect Ratio Distribution',
                'File Size by Format',
                'Resolution Categories'
            ),
            specs=[[{"type": "histogram"}, {"type": "scatter"}, {"type": "pie"}],
                   [{"type": "histogram"}, {"type": "box"}, {"type": "bar"}]]
        )
        
        # File size distribution (MB)
        file_sizes_mb = downloaded_df['bytes'] / 1048576
        fig.add_trace(
            go.Histogram(x=file_sizes_mb, nbinsx=30, name="File Size"),
            row=1, col=1
        )
        
        # Dimensions scatter plot
        fig.add_trace(
            go.Scatter(
                x=downloaded_df['width'],
                y=downloaded_df['height'],
                mode='markers',
                text=downloaded_df['filename'],
                name="Dimensions",
                opacity=0.6
            ),
            row=1, col=2
        )
        
        # Format distribution
        format_counts = downloaded_df['format'].value_counts()
        fig.add_trace(
            go.Pie(
                labels=format_counts.index,
                values=format_counts.values,
                name="Formats"
            ),
            row=1, col=3
        )
        
        # Aspect ratio distribution
        aspect_ratios = downloaded_df[downloaded_df['aspect_ratio'] > 0]['aspect_ratio']
        fig.add_trace(
            go.Histogram(x=aspect_ratios, nbinsx=25, name="Aspect Ratio"),
            row=2, col=1
        )
        
        # File size by format
        for fmt in downloaded_df['format'].unique():
            if pd.notna(fmt):
                fmt_sizes = downloaded_df[downloaded_df['format'] == fmt]['bytes'] / 1048576
                fig.add_trace(
                    go.Box(y=fmt_sizes, name=fmt),
                    row=2, col=2
                )
        
        # Resolution categories
        def categorize_resolution(row):
            if row['width'] >= 1920 or row['height'] >= 1080:
                return 'HD+'
            elif row['width'] >= 1280 or row['height'] >= 720:
                return 'HD'
            elif row['width'] >= 640 or row['height'] >= 480:
                return 'SD'
            else:
                return 'Low'
        
        downloaded_df['resolution_category'] = downloaded_df.apply(categorize_resolution, axis=1)
        res_counts = downloaded_df['resolution_category'].value_counts()
        
        fig.add_trace(
            go.Bar(
                x=res_counts.index,
                y=res_counts.values,
                text=res_counts.values,
                textposition='auto',
                name="Resolution"
            ),
            row=2, col=3
        )
        
        fig.update_layout(
            title_text="📱 File Characteristics Analysis",
            title_x=0.5,
            height=800,
            showlegend=False
        )
        
        # Update axis labels
        fig.update_xaxes(title_text="Size (MB)", row=1, col=1)
        fig.update_xaxes(title_text="Width", row=1, col=2)
        fig.update_yaxes(title_text="Height", row=1, col=2)
        fig.update_xaxes(title_text="Aspect Ratio", row=2, col=1)
        fig.update_yaxes(title_text="Size (MB)", row=2, col=2)
        fig.update_xaxes(title_text="Resolution Category", row=2, col=3)
        
        fig.show()


def plot_temporal_analysis(image_df: pd.DataFrame, use_plotly: bool = True):
    """
    Plot temporal analysis of downloads
    
    Args:
        image_df: Detailed image DataFrame
        use_plotly: Whether to use Plotly (True) or Matplotlib (False)
    """
    # Filter to images with valid timestamps
    temporal_df = image_df[
        (image_df['has_download_data'] == True) & 
        (image_df['download_timestamp'].notna())
    ].copy()
    
    if len(temporal_df) == 0:
        print("No temporal data available for analysis")
        return
    
    temporal_df = temporal_df.sort_values('download_timestamp')
    
    if use_plotly:
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Downloads Over Time',
                'Downloads by Hour of Day',
                'Downloads by Date',
                'Download Rate Analysis'
            )
        )
        
        # Cumulative downloads over time
        temporal_df['cumulative_count'] = range(1, len(temporal_df) + 1)
        fig.add_trace(
            go.Scatter(
                x=temporal_df['download_timestamp'],
                y=temporal_df['cumulative_count'],
                mode='lines+markers',
                name="Cumulative Downloads"
            ),
            row=1, col=1
        )
        
        # Downloads by hour
        hourly_counts = temporal_df.groupby('download_hour').size()
        fig.add_trace(
            go.Bar(
                x=hourly_counts.index,
                y=hourly_counts.values,
                text=hourly_counts.values,
                textposition='auto',
                name="Hourly Downloads"
            ),
            row=1, col=2
        )
        
        # Downloads by date
        daily_counts = temporal_df.groupby('download_date').size()
        fig.add_trace(
            go.Bar(
                x=daily_counts.index,
                y=daily_counts.values,
                text=daily_counts.values,
                textposition='auto',
                name="Daily Downloads"
            ),
            row=2, col=1
        )
        
        # Download intervals
        if len(temporal_df) > 1:
            intervals = []
            for i in range(1, len(temporal_df)):
                interval = (temporal_df.iloc[i]['download_timestamp'] - 
                           temporal_df.iloc[i-1]['download_timestamp']).total_seconds()
                intervals.append(interval)
            
            fig.add_trace(
                go.Histogram(
                    x=intervals,
                    nbinsx=25,
                    name="Download Intervals"
                ),
                row=2, col=2
            )
        
        fig.update_layout(
            title_text="⏱️ Temporal Analysis",
            title_x=0.5,
            height=800,
            showlegend=False
        )
        
        fig.show()


def plot_duplicate_analysis(duplicate_stats: Dict[str, Any], use_plotly: bool = True):
    """
    Plot duplicate analysis
    
    Args:
        duplicate_stats: Dictionary with duplicate analysis results
        use_plotly: Whether to use Plotly (True) or Matplotlib (False)
    """
    if duplicate_stats['total_images'] == 0:
        print("No images available for duplicate analysis")
        return
    
    if use_plotly:
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Unique vs Duplicate Images',
                'Duplicate Type Distribution',
                'Duplicate Impact',
                'Top Duplicate Hashes'
            ),
            specs=[[{"type": "pie"}, {"type": "bar"}],
                   [{"type": "bar"}, {"type": "bar"}]]
        )
        
        # Unique vs duplicate pie chart
        unique_count = duplicate_stats['unique_hashes']
        duplicate_count = duplicate_stats['duplicate_count']
        
        fig.add_trace(
            go.Pie(
                labels=['Unique', 'Duplicate'],
                values=[unique_count, duplicate_count],
                hole=0.4,
                name="Image Status"
            ),
            row=1, col=1
        )
        
        # Duplicate types
        inter_count = len(duplicate_stats['inter_class_duplicates'])
        intra_count = len(duplicate_stats['intra_class_duplicates'])
        
        fig.add_trace(
            go.Bar(
                x=['Inter-Class', 'Intra-Class'],
                y=[inter_count, intra_count],
                text=[inter_count, intra_count],
                textposition='auto',
                name="Duplicate Types"
            ),
            row=1, col=2
        )
        
        # Duplicate impact metrics
        total_images = duplicate_stats['total_images']
        duplicate_rate = duplicate_stats['duplicate_rate']
        
        impact_metrics = {
            'Total Images': total_images,
            'Unique Images': unique_count,
            'Duplicate Images': duplicate_count,
            'Duplicate Rate (%)': duplicate_rate
        }
        
        fig.add_trace(
            go.Bar(
                x=list(impact_metrics.keys()),
                y=list(impact_metrics.values()),
                text=[f"{v:.1f}" for v in impact_metrics.values()],
                textposition='auto',
                name="Impact Metrics"
            ),
            row=2, col=1
        )
        
        # Top duplicate hashes by occurrence
        if duplicate_stats['inter_class_duplicates'] or duplicate_stats['intra_class_duplicates']:
            all_duplicates = {}
            
            for hash_val, info in duplicate_stats['inter_class_duplicates'].items():
                all_duplicates[hash_val] = info['count']
            
            for hash_val, info in duplicate_stats['intra_class_duplicates'].items():
                all_duplicates[hash_val] = info['count']
            
            if all_duplicates:
                top_duplicates = sorted(all_duplicates.items(), key=lambda x: x[1], reverse=True)[:10]
                
                fig.add_trace(
                    go.Bar(
                        x=[f"Hash {i+1}" for i in range(len(top_duplicates))],
                        y=[count for _, count in top_duplicates],
                        text=[f"{count} copies" for _, count in top_duplicates],
                        textposition='auto',
                        name="Top Duplicates"
                    ),
                    row=2, col=2
                )
        
        fig.update_layout(
            title_text="🔄 Duplicate Analysis",
            title_x=0.5,
            height=800,
            showlegend=False
        )
        
        fig.show()


def create_summary_dashboard(summary_df: pd.DataFrame, image_df: pd.DataFrame, duplicate_stats: Dict[str, Any]):
    """
    Create a comprehensive summary dashboard
    
    Args:
        summary_df: Summary DataFrame
        image_df: Detailed image DataFrame
        duplicate_stats: Duplicate analysis results
    """
    # Calculate key metrics
    total_classes = len(summary_df)
    total_images = summary_df['downloaded_images'].sum()
    avg_success_rate = summary_df['download_success_rate'].mean()
    
    downloaded_df = image_df[image_df['has_download_data'] == True]
    if len(downloaded_df) > 0:
        avg_file_size_mb = downloaded_df['bytes'].mean() / 1048576
        total_storage_mb = downloaded_df['bytes'].sum() / 1048576
    else:
        avg_file_size_mb = 0
        total_storage_mb = 0
    
    # Create dashboard
    fig = make_subplots(
        rows=3, cols=3,
        subplot_titles=(
            'Dataset Overview', 'Category Distribution', 'Success Rates',
            'File Size Distribution', 'Format Distribution', 'Duplicate Analysis',
            'Top Classes', 'Resolution Quality', 'Storage Analysis'
        ),
        specs=[[{"type": "indicator"}, {"type": "pie"}, {"type": "bar"}],
               [{"type": "histogram"}, {"type": "pie"}, {"type": "pie"}],
               [{"type": "bar"}, {"type": "bar"}, {"type": "bar"}]]
    )
    
    # Dataset overview indicator
    fig.add_trace(
        go.Indicator(
            mode="number+gauge+delta",
            value=total_images,
            delta={'reference': total_classes * 50},
            gauge={'axis': {'range': [None, total_classes * 100]},
                   'bar': {'color': "darkblue"},
                   'steps': [{'range': [0, total_classes * 25], 'color': "lightgray"},
                            {'range': [total_classes * 25, total_classes * 75], 'color': "gray"}],
                   'threshold': {'line': {'color': "red", 'width': 4},
                                'thickness': 0.75, 'value': total_classes * 90}},
            title={'text': f"Total Images<br>{total_classes} Classes"}
        ),
        row=1, col=1
    )
    
    # Category distribution
    category_counts = summary_df.groupby('category')['downloaded_images'].sum()
    fig.add_trace(
        go.Pie(labels=category_counts.index, values=category_counts.values, hole=0.3),
        row=1, col=2
    )
    
    # Success rates by category
    category_success = summary_df.groupby('category')['download_success_rate'].mean()
    fig.add_trace(
        go.Bar(x=category_success.index, y=category_success.values,
               text=[f"{v:.1f}%" for v in category_success.values], textposition='auto'),
        row=1, col=3
    )
    
    # File size distribution
    if len(downloaded_df) > 0:
        file_sizes_mb = downloaded_df['bytes'] / 1048576
        fig.add_trace(go.Histogram(x=file_sizes_mb, nbinsx=20), row=2, col=1)
        
        # Format distribution
        format_counts = downloaded_df['format'].value_counts()
        fig.add_trace(
            go.Pie(labels=format_counts.index, values=format_counts.values),
            row=2, col=2
        )
    
    # Duplicate analysis
    if duplicate_stats['total_images'] > 0:
        fig.add_trace(
            go.Pie(
                labels=['Unique', 'Duplicate'],
                values=[duplicate_stats['unique_hashes'], duplicate_stats['duplicate_count']],
                hole=0.3
            ),
            row=2, col=3
        )
    
    # Top classes
    top_classes = summary_df.nlargest(10, 'downloaded_images')
    fig.add_trace(
        go.Bar(
            x=top_classes['downloaded_images'],
            y=top_classes['class_name'],
            orientation='h',
            text=top_classes['downloaded_images'],
            textposition='auto'
        ),
        row=3, col=1
    )
    
    # Resolution quality
    if len(downloaded_df) > 0:
        def categorize_resolution(row):
            if row['width'] >= 1920 or row['height'] >= 1080:
                return 'HD+'
            elif row['width'] >= 1280 or row['height'] >= 720:
                return 'HD'
            elif row['width'] >= 640 or row['height'] >= 480:
                return 'SD'
            else:
                return 'Low'
        
        downloaded_df['resolution_category'] = downloaded_df.apply(categorize_resolution, axis=1)
        res_counts = downloaded_df['resolution_category'].value_counts()
        
        fig.add_trace(
            go.Bar(x=res_counts.index, y=res_counts.values,
                   text=res_counts.values, textposition='auto'),
            row=3, col=2
        )
    
    # Storage analysis
    if len(downloaded_df) > 0:
        storage_by_category = downloaded_df.groupby('category')['bytes'].sum() / 1048576
        fig.add_trace(
            go.Bar(x=storage_by_category.index, y=storage_by_category.values,
                   text=[f"{v:.1f}MB" for v in storage_by_category.values], textposition='auto'),
            row=3, col=3
        )
    
    fig.update_layout(
        title_text="📊 Image Scraper Dashboard",
        title_x=0.5,
        height=1200,
        showlegend=False
    )
    
    fig.show()
    
    # Print summary statistics
    print("📊 DATASET SUMMARY")
    print("=" * 50)
    print(f"📁 Total Classes: {total_classes}")
    print(f"📸 Total Images: {total_images:,}")
    print(f"✅ Average Success Rate: {avg_success_rate:.1f}%")
    print(f"💾 Average File Size: {avg_file_size_mb:.1f} MB")
    print(f"📦 Total Storage: {total_storage_mb:.1f} MB")
    print(f"🔄 Duplicate Rate: {duplicate_stats.get('duplicate_rate', 0):.1f}%")