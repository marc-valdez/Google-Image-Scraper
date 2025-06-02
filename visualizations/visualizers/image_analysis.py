import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from utils import *

def create_file_size_histogram(data):
    file_size_stats = get_file_size_stats(data)
    
    avg_bytes = file_size_stats.get('average_bytes', 0)
    min_bytes = file_size_stats.get('min_bytes', 0)
    max_bytes = file_size_stats.get('max_bytes', 0)
    
    fig = create_figure(title="File Size Distribution")
    
    fig.add_trace(go.Scatter(
        x=['Minimum', 'Average', 'Maximum'],
        y=[min_bytes / (1024 * 1024), avg_bytes / (1024 * 1024), max_bytes / (1024 * 1024)],
        mode='markers+lines',
        marker=dict(size=12, color=theme.colors['primary']),
        line=dict(width=3, color=theme.colors['primary']),
        text=[format_bytes(min_bytes), format_bytes(avg_bytes), format_bytes(max_bytes)],
        textposition='top center'
    ))
    
    fig.update_layout(
        xaxis_title="File Size Metric",
        yaxis_title="Size (MB)",
        height=400
    )
    
    return style_line_chart(fig)

def create_dimension_scatter(data):
    dimension_stats = get_dimension_stats(data)
    
    avg_width = dimension_stats.get('avg_width', 0)
    avg_height = dimension_stats.get('avg_height', 0)
    min_width = dimension_stats.get('min_width', 0)
    max_width = dimension_stats.get('max_width', 0)
    min_height = dimension_stats.get('min_height', 0)
    max_height = dimension_stats.get('max_height', 0)
    
    fig = create_figure(title="Image Dimensions Analysis")
    
    fig.add_trace(go.Scatter(
        x=[min_width, avg_width, max_width],
        y=[min_height, avg_height, max_height],
        mode='markers+text',
        marker=dict(
            size=[20, 30, 20],
            color=[theme.colors['warning'], theme.colors['primary'], theme.colors['accent']],
            opacity=0.7
        ),
        text=['Min', 'Avg', 'Max'],
        textposition='middle center',
        textfont=dict(color='white', size=12),
        hovertemplate='<b>%{text}</b><br>Width: %{x:,.0f}px<br>Height: %{y:,.0f}px<extra></extra>'
    ))
    
    fig.update_layout(
        xaxis_title="Width (pixels)",
        yaxis_title="Height (pixels)",
        height=500
    )
    
    return style_scatter_plot(fig)

def create_color_mode_donut(data):
    df = create_color_mode_df(data)
    
    fig = create_figure(title="Color Mode Distribution")
    
    fig.add_trace(go.Pie(
        labels=df['color_mode'],
        values=df['count'],
        hole=0.5,
        textinfo='label+percent',
        textposition='inside'
    ))
    
    fig.update_layout(height=500)
    
    return style_pie_chart(fig)

def create_format_popularity_chart(data):
    df = create_format_distribution_df(data)
    
    fig = create_figure(title="File Format Popularity")
    
    fig.add_trace(go.Bar(
        y=df['format'],
        x=df['count'],
        orientation='h',
        marker_color=theme.color_palette[:len(df)],
        text=[format_large_numbers(count) for count in df['count']],
        textposition='outside'
    ))
    
    fig.update_layout(
        xaxis_title="Number of Images",
        yaxis_title="File Format",
        height=max(300, len(df) * 50)
    )
    
    return style_bar_chart(fig)

def create_size_vs_format_analysis(data):
    file_size_stats = get_file_size_stats(data)
    format_df = create_format_distribution_df(data)
    
    avg_size_mb = file_size_stats.get('average_bytes', 0) / (1024 * 1024)
    
    fig = create_subplots(
        rows=1, cols=2,
        subplot_titles=['Average File Size', 'Format Distribution'],
        specs=[[{"type": "indicator"}, {"type": "pie"}]]
    )
    
    fig.add_trace(
        go.Indicator(
            mode="number+gauge",
            value=avg_size_mb,
            title={'text': "Average Size (MB)"},
            number={'suffix': " MB", 'font': {'size': 24}},
            gauge={
                'axis': {'range': [0, avg_size_mb * 2]},
                'bar': {'color': theme.colors['primary']},
                'steps': [{'range': [0, avg_size_mb], 'color': "lightgray"}],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': avg_size_mb * 1.5
                }
            }
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Pie(
            labels=format_df['format'][:5],
            values=format_df['count'][:5],
            name="Formats"
        ),
        row=1, col=2
    )
    
    fig.update_layout(
        title="File Size and Format Analysis",
        height=400,
        showlegend=True
    )
    
    return fig

def create_dimension_ranges_chart(data):
    dimension_stats = get_dimension_stats(data)
    
    width_data = [
        dimension_stats.get('min_width', 0),
        dimension_stats.get('avg_width', 0),
        dimension_stats.get('max_width', 0)
    ]
    
    height_data = [
        dimension_stats.get('min_height', 0),
        dimension_stats.get('avg_height', 0),
        dimension_stats.get('max_height', 0)
    ]
    
    fig = create_figure(title="Image Dimension Ranges")
    
    fig.add_trace(go.Bar(
        name='Width',
        x=['Minimum', 'Average', 'Maximum'],
        y=width_data,
        marker_color=theme.colors['primary'],
        text=[f'{w:,.0f}px' for w in width_data],
        textposition='outside'
    ))
    
    fig.add_trace(go.Bar(
        name='Height',
        x=['Minimum', 'Average', 'Maximum'],
        y=height_data,
        marker_color=theme.colors['secondary'],
        text=[f'{h:,.0f}px' for h in height_data],
        textposition='outside'
    ))
    
    fig.update_layout(
        barmode='group',
        xaxis_title="Dimension Metric",
        yaxis_title="Pixels",
        height=500
    )
    
    return style_bar_chart(fig)

def create_combined_image_analysis(data):
    size_hist = create_file_size_histogram(data)
    dimension_scatter = create_dimension_scatter(data)
    color_donut = create_color_mode_donut(data)
    format_chart = create_format_popularity_chart(data)
    size_format = create_size_vs_format_analysis(data)
    dimension_ranges = create_dimension_ranges_chart(data)
    
    return {
        'file_size_histogram': size_hist,
        'dimension_scatter': dimension_scatter,
        'color_mode_distribution': color_donut,
        'format_popularity': format_chart,
        'size_format_analysis': size_format,
        'dimension_ranges': dimension_ranges
    }