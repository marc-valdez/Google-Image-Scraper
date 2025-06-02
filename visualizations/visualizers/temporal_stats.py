import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from utils import *

def create_scraping_timeline(data):
    temporal_metrics = get_temporal_metrics(data)
    
    earliest = temporal_metrics['earliest']
    latest = temporal_metrics['latest']
    duration_hours = temporal_metrics['duration_hours']
    
    fig = create_figure(title="Scraping Timeline")
    
    fig.add_trace(go.Scatter(
        x=[earliest, latest],
        y=[0, 0],
        mode='markers+lines+text',
        marker=dict(size=[15, 15], color=[theme.colors['success'], theme.colors['accent']]),
        line=dict(width=4, color=theme.colors['primary']),
        text=['Start', 'End'],
        textposition='top center',
        hovertemplate='<b>%{text}</b><br>Time: %{x}<extra></extra>'
    ))
    
    fig.add_annotation(
        x=earliest,
        y=0.1,
        text=f"Duration: {format_duration(duration_hours)}",
        showarrow=True,
        arrowhead=2,
        arrowcolor=theme.colors['primary'],
        bgcolor=theme.colors['light'],
        bordercolor=theme.colors['primary']
    )
    
    fig.update_layout(
        xaxis_title="Time",
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        height=300
    )
    
    return fig

def create_interval_analysis(data):
    temporal_metrics = get_temporal_metrics(data)
    
    avg_seconds = temporal_metrics['avg_interval_seconds']
    avg_minutes = temporal_metrics['avg_interval_minutes']
    
    fig = create_figure(title="Average Download Intervals")
    
    fig.add_trace(go.Bar(
        x=['Seconds', 'Minutes'],
        y=[avg_seconds, avg_minutes],
        marker_color=[theme.colors['primary'], theme.colors['secondary']],
        text=[f'{avg_seconds:.2f}s', f'{avg_minutes:.3f}m'],
        textposition='outside'
    ))
    
    fig.update_layout(
        xaxis_title="Time Unit",
        yaxis_title="Average Interval",
        height=400
    )
    
    return style_bar_chart(fig)

def create_performance_metrics(data):
    temporal_metrics = get_temporal_metrics(data)
    overview_metrics = get_overview_metrics(data)
    
    duration_hours = temporal_metrics['duration_hours']
    total_images = overview_metrics['total_images']
    
    images_per_hour = total_images / duration_hours if duration_hours > 0 else 0
    images_per_minute = images_per_hour / 60 if images_per_hour > 0 else 0
    
    fig = create_subplots(
        rows=1, cols=3,
        subplot_titles=['Images per Hour', 'Images per Minute', 'Total Duration (hrs)'],
        specs=[[{"type": "indicator"}] * 3]
    )
    
    metrics = [
        (images_per_hour, 1),
        (images_per_minute, 2),
        (duration_hours, 3)
    ]
    
    for value, col in metrics:
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=value,
                number={"font": {"size": 24, "color": theme.colors['primary']}},
                domain={'row': 0, 'column': col-1}
            ),
            row=1, col=col
        )
    
    fig.update_layout(
        title="Scraping Performance Metrics",
        height=300,
        showlegend=False
    )
    
    return fig

def create_efficiency_gauge(data):
    temporal_metrics = get_temporal_metrics(data)
    overview_metrics = get_overview_metrics(data)
    
    avg_interval_seconds = temporal_metrics['avg_interval_seconds']
    total_images = overview_metrics['total_images']
    duration_hours = temporal_metrics['duration_hours']
    
    theoretical_max_rate = 3600 / avg_interval_seconds if avg_interval_seconds > 0 else 0
    actual_rate = total_images / duration_hours if duration_hours > 0 else 0
    efficiency = (actual_rate / theoretical_max_rate * 100) if theoretical_max_rate > 0 else 0
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=efficiency,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Scraping Efficiency (%)"},
        gauge={
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

def create_time_breakdown_chart(data):
    temporal_metrics = get_temporal_metrics(data)
    
    duration_hours = temporal_metrics['duration_hours']
    duration_days = duration_hours / 24
    duration_minutes = duration_hours * 60
    
    fig = create_figure(title="Time Duration Breakdown")
    
    fig.add_trace(go.Bar(
        x=['Minutes', 'Hours', 'Days'],
        y=[duration_minutes, duration_hours, duration_days],
        marker_color=[theme.colors['info'], theme.colors['primary'], theme.colors['secondary']],
        text=[f'{duration_minutes:.1f}', f'{duration_hours:.1f}', f'{duration_days:.1f}'],
        textposition='outside'
    ))
    
    fig.update_layout(
        xaxis_title="Time Unit",
        yaxis_title="Duration",
        height=400
    )
    
    return style_bar_chart(fig)

def create_rate_comparison(data):
    temporal_metrics = get_temporal_metrics(data)
    overview_metrics = get_overview_metrics(data)
    
    duration_hours = temporal_metrics['duration_hours']
    total_images = overview_metrics['total_images']
    avg_interval_seconds = temporal_metrics['avg_interval_seconds']
    
    actual_rate_per_hour = total_images / duration_hours if duration_hours > 0 else 0
    theoretical_rate_per_hour = 3600 / avg_interval_seconds if avg_interval_seconds > 0 else 0
    
    fig = create_figure(title="Actual vs Theoretical Download Rates")
    
    fig.add_trace(go.Bar(
        name='Actual Rate',
        x=['Downloads per Hour'],
        y=[actual_rate_per_hour],
        marker_color=theme.colors['primary'],
        text=f'{actual_rate_per_hour:.1f}',
        textposition='outside'
    ))
    
    fig.add_trace(go.Bar(
        name='Theoretical Max Rate',
        x=['Downloads per Hour'],
        y=[theoretical_rate_per_hour],
        marker_color=theme.colors['secondary'],
        text=f'{theoretical_rate_per_hour:.1f}',
        textposition='outside'
    ))
    
    fig.update_layout(
        barmode='group',
        xaxis_title="Rate Type",
        yaxis_title="Images per Hour",
        height=400
    )
    
    return style_bar_chart(fig)

def create_combined_temporal_analysis(data):
    timeline = create_scraping_timeline(data)
    interval_analysis = create_interval_analysis(data)
    performance_metrics = create_performance_metrics(data)
    efficiency_gauge = create_efficiency_gauge(data)
    time_breakdown = create_time_breakdown_chart(data)
    rate_comparison = create_rate_comparison(data)
    
    return {
        'scraping_timeline': timeline,
        'interval_analysis': interval_analysis,
        'performance_metrics': performance_metrics,
        'efficiency_gauge': efficiency_gauge,
        'time_breakdown': time_breakdown,
        'rate_comparison': rate_comparison
    }