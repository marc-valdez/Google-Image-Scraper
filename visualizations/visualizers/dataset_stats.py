import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import plotly.graph_objects as go
import plotly.express as px
from utils import *

def create_overview_dashboard(data):
    metrics = get_overview_metrics(data)
    
    fig = create_subplots(
        rows=2, cols=4,
        subplot_titles=[
            'Total Images', 'Success Rate (%)', 'Total Classes', 'Total Categories',
            'Total Formats', 'Avg File Size (MB)', 'URLs Found', 'Downloaded'
        ],
        specs=[[{"type": "indicator"}] * 4, [{"type": "indicator"}] * 4]
    )
    
    indicators = [
        (metrics['total_images'], 1, 1),
        (metrics['success_rate'], 1, 2),
        (metrics['total_classes'], 1, 3),
        (metrics['total_categories'], 1, 4),
        (metrics['total_formats'], 2, 1),
        (metrics['avg_file_size_mb'], 2, 2),
        (metrics['total_urls_found'], 2, 3),
        (metrics['total_downloaded'], 2, 4)
    ]
    
    for value, row, col in indicators:
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=value,
                number={"font": {"size": 24, "color": theme.colors['primary']}},
                domain={'row': row-1, 'column': col-1}
            ),
            row=row, col=col
        )
    
    fig.update_layout(
        title="Dataset Overview Dashboard",
        height=400,
        showlegend=False
    )
    
    return fig

def create_class_distribution_chart(data):
    df = create_class_distribution_df(data)
    
    fig = create_figure(title="Images per Class Distribution")
    
    fig.add_trace(go.Bar(
        x=df['class'],
        y=df['count'],
        marker_color=theme.color_palette[:len(df)],
        text=df['count'],
        textposition='outside'
    ))
    
    fig.update_layout(
        xaxis_title="Class",
        yaxis_title="Number of Images",
        height=500
    )
    
    return style_bar_chart(fig)

def create_category_pie_chart(data):
    df = create_category_distribution_df(data)
    
    fig = create_figure(title="Images per Category Distribution")
    
    fig.add_trace(go.Pie(
        labels=df['category'],
        values=df['count'],
        hole=0.4
    ))
    
    fig.update_layout(height=500)
    
    return style_pie_chart(fig)

def create_success_rate_gauge(data):
    quality_stats = extract_quality_stats(data)
    success_rate = quality_stats.get('success_rate', 0)
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = success_rate,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Download Success Rate (%)"},
        delta = {'reference': 100},
        gauge = {
            'axis': {'range': [None, 100]},
            'bar': {'color': theme.colors['primary']},
            'steps': [
                {'range': [0, 50], 'color': theme.colors['warning']},
                {'range': [50, 80], 'color': theme.colors['info']},
                {'range': [80, 100], 'color': theme.colors['success']}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    
    fig.update_layout(
        height=400,
        **theme.layout_config
    )
    
    return fig

def create_format_distribution_chart(data):
    df = create_format_distribution_df(data)
    
    fig = create_figure(title="File Format Distribution")
    
    fig.add_trace(go.Bar(
        x=df['format'],
        y=df['count'],
        marker_color=theme.color_palette[:len(df)],
        text=[format_large_numbers(count) for count in df['count']],
        textposition='outside'
    ))
    
    fig.update_layout(
        xaxis_title="File Format",
        yaxis_title="Number of Images",
        height=500
    )
    
    return style_bar_chart(fig)

def create_combined_overview(data):
    overview_fig = create_overview_dashboard(data)
    class_fig = create_class_distribution_chart(data)
    category_fig = create_category_pie_chart(data)
    success_fig = create_success_rate_gauge(data)
    
    return {
        'overview': overview_fig,
        'class_distribution': class_fig,
        'category_distribution': category_fig,
        'success_rate': success_fig
    }