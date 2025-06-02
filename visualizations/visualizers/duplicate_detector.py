import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import plotly.graph_objects as go
import plotly.express as px
from utils import *

def create_duplicate_overview(data):
    duplicate_stats = get_duplicate_stats(data)
    
    unique_count = duplicate_stats['unique_count']
    duplicate_count = duplicate_stats['duplicate_count']
    total_count = duplicate_stats['total_count']
    
    fig = create_figure(title="Duplicate Detection Overview")
    
    fig.add_trace(go.Pie(
        labels=['Unique Images', 'Duplicate Hashes'],
        values=[unique_count, duplicate_count],
        hole=0.4,
        marker_colors=[theme.colors['success'], theme.colors['warning']]
    ))
    
    fig.add_annotation(
        text=f"Total:<br>{total_count:,}",
        x=0.5, y=0.5,
        font_size=16,
        showarrow=False
    )
    
    fig.update_layout(height=500)
    
    return style_pie_chart(fig)

def create_duplicate_breakdown(data):
    duplicate_stats = get_duplicate_stats(data)
    duplicate_summary = duplicate_stats['duplicate_summary']
    
    inter_class = duplicate_summary.get('inter_class_duplicate_hashes', 0)
    intra_class = duplicate_summary.get('intra_class_duplicate_hashes', 0)
    total_dup_hashes = duplicate_summary.get('total_duplicate_hashes', 0)
    total_dup_files = duplicate_summary.get('total_duplicate_files', 0)
    
    fig = create_figure(title="Duplicate Type Analysis")
    
    fig.add_trace(go.Bar(
        x=['Inter-Class\nDuplicates', 'Intra-Class\nDuplicates', 'Total Duplicate\nHashes', 'Total Duplicate\nFiles'],
        y=[inter_class, intra_class, total_dup_hashes, total_dup_files],
        marker_color=[theme.colors['accent'], theme.colors['warning'], theme.colors['info'], theme.colors['secondary']],
        text=[inter_class, intra_class, total_dup_hashes, total_dup_files],
        textposition='outside'
    ))
    
    fig.update_layout(
        xaxis_title="Duplicate Type",
        yaxis_title="Count",
        height=500
    )
    
    return style_bar_chart(fig)

def create_hash_efficiency_metrics(data):
    duplicate_stats = get_duplicate_stats(data)
    
    unique_count = duplicate_stats['unique_count']
    total_count = duplicate_stats['total_count']
    duplicate_count = duplicate_stats['duplicate_count']
    
    uniqueness_rate = (unique_count / total_count * 100) if total_count > 0 else 0
    duplicate_rate = (duplicate_count / total_count * 100) if total_count > 0 else 0
    
    fig = create_subplots(
        rows=1, cols=3,
        subplot_titles=['Uniqueness Rate (%)', 'Duplicate Rate (%)', 'Hash Efficiency'],
        specs=[[{"type": "indicator"}] * 3]
    )
    
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=uniqueness_rate,
            title={'text': "Uniqueness"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': theme.colors['success']},
                'steps': [
                    {'range': [0, 80], 'color': theme.colors['warning']},
                    {'range': [80, 95], 'color': theme.colors['info']},
                    {'range': [95, 100], 'color': theme.colors['success']}
                ]
            }
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=duplicate_rate,
            title={'text': "Duplicates"},
            gauge={
                'axis': {'range': [0, 20]},
                'bar': {'color': theme.colors['warning']},
                'steps': [
                    {'range': [0, 5], 'color': theme.colors['success']},
                    {'range': [5, 10], 'color': theme.colors['info']},
                    {'range': [10, 20], 'color': theme.colors['warning']}
                ]
            }
        ),
        row=1, col=2
    )
    
    efficiency_score = 100 - duplicate_rate
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=efficiency_score,
            title={'text': "Efficiency Score"},
            number={'suffix': "%", 'font': {'size': 32, 'color': theme.colors['primary']}}
        ),
        row=1, col=3
    )
    
    fig.update_layout(
        title="Hash Detection Efficiency Metrics",
        height=400,
        showlegend=False
    )
    
    return fig

def create_duplicate_impact_analysis(data):
    duplicate_stats = get_duplicate_stats(data)
    duplicate_summary = duplicate_stats['duplicate_summary']
    
    total_dup_files = duplicate_summary.get('total_duplicate_files', 0)
    total_dup_hashes = duplicate_summary.get('total_duplicate_hashes', 0)
    
    overview_metrics = get_overview_metrics(data)
    total_images = overview_metrics['total_images']
    
    storage_saved_estimate = total_dup_files / total_images * 100 if total_images > 0 else 0
    
    fig = create_figure(title="Duplicate Detection Impact")
    
    categories = ['Total Images', 'Duplicate Files Found', 'Unique Hashes Affected', 'Estimated Storage Saved (%)']
    values = [total_images, total_dup_files, total_dup_hashes, storage_saved_estimate]
    colors = [theme.colors['primary'], theme.colors['warning'], theme.colors['accent'], theme.colors['success']]
    
    fig.add_trace(go.Bar(
        x=categories,
        y=values,
        marker_color=colors,
        text=[format_large_numbers(v) if i < 3 else f'{v:.2f}%' for i, v in enumerate(values)],
        textposition='outside'
    ))
    
    fig.update_layout(
        xaxis_title="Metric",
        yaxis_title="Count / Percentage",
        height=500
    )
    
    return style_bar_chart(fig)

def create_duplicate_distribution_funnel(data):
    duplicate_stats = get_duplicate_stats(data)
    
    total_count = duplicate_stats['total_count']
    unique_count = duplicate_stats['unique_count']
    duplicate_count = duplicate_stats['duplicate_count']
    
    duplicate_summary = duplicate_stats['duplicate_summary']
    total_dup_files = duplicate_summary.get('total_duplicate_files', 0)
    
    fig = create_figure(title="Duplicate Detection Funnel")
    
    fig.add_trace(go.Funnel(
        y=['Total Images Processed', 'Unique Images', 'Duplicate Hashes', 'Duplicate Files'],
        x=[total_count, unique_count, duplicate_count, total_dup_files],
        textinfo="value+percent initial",
        marker=dict(
            color=[theme.colors['primary'], theme.colors['success'], theme.colors['warning'], theme.colors['accent']]
        )
    ))
    
    fig.update_layout(height=500)
    
    return fig

def create_class_duplicate_comparison(data):
    duplicate_stats = get_duplicate_stats(data)
    duplicate_summary = duplicate_stats['duplicate_summary']
    
    inter_class = duplicate_summary.get('inter_class_duplicate_hashes', 0)
    intra_class = duplicate_summary.get('intra_class_duplicate_hashes', 0)
    
    fig = create_figure(title="Inter-Class vs Intra-Class Duplicates")
    
    fig.add_trace(go.Pie(
        labels=['Intra-Class Duplicates', 'Inter-Class Duplicates'],
        values=[intra_class, inter_class],
        hole=0.3,
        marker_colors=[theme.colors['info'], theme.colors['accent']],
        textinfo='label+value+percent'
    ))
    
    fig.update_layout(height=400)
    
    return style_pie_chart(fig)

def create_duplicate_summary_cards(data):
    duplicate_stats = get_duplicate_stats(data)
    duplicate_summary = duplicate_stats['duplicate_summary']
    
    total_dup_hashes = duplicate_summary.get('total_duplicate_hashes', 0)
    total_dup_files = duplicate_summary.get('total_duplicate_files', 0)
    inter_class = duplicate_summary.get('inter_class_duplicate_hashes', 0)
    intra_class = duplicate_summary.get('intra_class_duplicate_hashes', 0)
    
    fig = create_subplots(
        rows=1, cols=4,
        subplot_titles=['Duplicate Hashes', 'Duplicate Files', 'Inter-Class', 'Intra-Class'],
        specs=[[{"type": "indicator"}] * 4]
    )
    
    indicators = [
        (total_dup_hashes, theme.colors['warning'], 1),
        (total_dup_files, theme.colors['accent'], 2),
        (inter_class, theme.colors['secondary'], 3),
        (intra_class, theme.colors['info'], 4)
    ]
    
    for value, color, col in indicators:
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=value,
                number={"font": {"size": 28, "color": color}},
                domain={'row': 0, 'column': col-1}
            ),
            row=1, col=col
        )
    
    fig.update_layout(
        title="Duplicate Detection Summary",
        height=300,
        showlegend=False
    )
    
    return fig

def create_combined_duplicate_analysis(data):
    overview = create_duplicate_overview(data)
    breakdown = create_duplicate_breakdown(data)
    efficiency = create_hash_efficiency_metrics(data)
    impact = create_duplicate_impact_analysis(data)
    funnel = create_duplicate_distribution_funnel(data)
    comparison = create_class_duplicate_comparison(data)
    summary = create_duplicate_summary_cards(data)
    
    return {
        'duplicate_overview': overview,
        'duplicate_breakdown': breakdown,
        'efficiency_metrics': efficiency,
        'impact_analysis': impact,
        'distribution_funnel': funnel,
        'class_comparison': comparison,
        'summary_cards': summary
    }