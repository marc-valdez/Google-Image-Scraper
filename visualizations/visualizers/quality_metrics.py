import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import plotly.graph_objects as go
import plotly.express as px
from utils import *

def create_success_rate_breakdown(data):
    quality_stats = extract_quality_stats(data)
    overall_success = quality_stats.get('success_rate', 0)
    
    fig = create_figure(title="Download Success Rate Analysis")
    
    fig.add_trace(go.Indicator(
        mode="gauge+number+delta",
        value=overall_success,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Overall Success Rate (%)"},
        delta={'reference': 100, 'position': "top"},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': theme.colors['primary']},
            'steps': [
                {'range': [0, 70], 'color': theme.colors['warning']},
                {'range': [70, 90], 'color': theme.colors['info']},
                {'range': [90, 100], 'color': theme.colors['success']}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 95
            }
        }
    ))
    
    fig.update_layout(height=400)
    return fig

def create_class_success_rates(data):
    df = create_quality_issues_df(data)
    
    if df.empty:
        fig = create_figure(title="Class Success Rates - No Issues Found")
        fig.add_annotation(
            text="All classes downloaded successfully!",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False,
            font=dict(size=20, color=theme.colors['success'])
        )
        return fig
    
    fig = create_figure(title="Success Rate by Class")
    
    fig.add_trace(go.Bar(
        x=df['class'],
        y=df['success_rate'],
        marker_color=[
            theme.colors['success'] if rate >= 95 else 
            theme.colors['warning'] if rate >= 85 else 
            theme.colors['accent'] 
            for rate in df['success_rate']
        ],
        text=[f'{rate:.1f}%' for rate in df['success_rate']],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>Success Rate: %{y:.1f}%<br>Downloaded: %{customdata[0]}<br>Found: %{customdata[1]}<extra></extra>',
        customdata=df[['urls_downloaded', 'urls_found']].values
    ))
    
    fig.update_layout(
        xaxis_title="Class",
        yaxis_title="Success Rate (%)",
        yaxis=dict(range=[0, 100]),
        height=500
    )
    
    return style_bar_chart(fig)

def create_download_comparison(data):
    quality_stats = extract_quality_stats(data)
    
    total_found = quality_stats.get('total_urls_found', 0)
    total_downloaded = quality_stats.get('total_downloaded', 0)
    missing = quality_stats.get('urls_found_but_missing_metadata', 0)
    
    fig = create_figure(title="URL Discovery vs Download Success")
    
    categories = ['URLs Found', 'Successfully Downloaded', 'Missing/Failed']
    values = [total_found, total_downloaded, missing]
    colors = [theme.colors['info'], theme.colors['success'], theme.colors['warning']]
    
    fig.add_trace(go.Bar(
        x=categories,
        y=values,
        marker_color=colors,
        text=[format_large_numbers(v) for v in values],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>Count: %{y:,.0f}<extra></extra>'
    ))
    
    fig.update_layout(
        xaxis_title="Category",
        yaxis_title="Count",
        height=400
    )
    
    return style_bar_chart(fig)

def create_quality_issues_detailed(data):
    df = create_quality_issues_df(data)
    
    if df.empty:
        fig = create_figure(title="Quality Issues - Detailed View")
        fig.add_annotation(
            text="No quality issues detected!",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False,
            font=dict(size=18, color=theme.colors['success'])
        )
        return fig
    
    fig = create_subplots(
        rows=1, cols=2,
        subplot_titles=['Missing Downloads per Class', 'Download Success Rate'],
        specs=[[{"type": "bar"}, {"type": "bar"}]]
    )
    
    fig.add_trace(
        go.Bar(
            name='Missing Downloads',
            x=df['class'],
            y=df['missing_downloads'],
            marker_color=theme.colors['accent'],
            text=df['missing_downloads'],
            textposition='outside'
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(
            name='Success Rate (%)',
            x=df['class'],
            y=df['success_rate'],
            marker_color=theme.colors['primary'],
            text=[f'{rate:.1f}%' for rate in df['success_rate']],
            textposition='outside'
        ),
        row=1, col=2
    )
    
    fig.update_layout(
        title="Quality Issues - Detailed Analysis",
        height=500,
        showlegend=False
    )
    
    fig.update_xaxes(title_text="Class", row=1, col=1)
    fig.update_xaxes(title_text="Class", row=1, col=2)
    fig.update_yaxes(title_text="Missing Count", row=1, col=1)
    fig.update_yaxes(title_text="Success Rate (%)", row=1, col=2)
    
    return fig

def create_quality_summary_cards(data):
    quality_stats = extract_quality_stats(data)
    
    success_rate = quality_stats.get('success_rate', 0)
    total_found = quality_stats.get('total_urls_found', 0)
    total_downloaded = quality_stats.get('total_downloaded', 0)
    missing = quality_stats.get('urls_found_but_missing_metadata', 0)
    
    fig = create_subplots(
        rows=1, cols=4,
        subplot_titles=['Success Rate (%)', 'URLs Found', 'Downloaded', 'Missing'],
        specs=[[{"type": "indicator"}] * 4]
    )
    
    indicators = [
        (success_rate, theme.colors['primary'], 1),
        (total_found, theme.colors['info'], 2),
        (total_downloaded, theme.colors['success'], 3),
        (missing, theme.colors['warning'], 4)
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
        title="Quality Metrics Summary",
        height=300,
        showlegend=False
    )
    
    return fig

def create_download_efficiency_chart(data):
    quality_stats = extract_quality_stats(data)
    
    total_found = quality_stats.get('total_urls_found', 0)
    total_downloaded = quality_stats.get('total_downloaded', 0)
    success_rate = quality_stats.get('success_rate', 0)
    
    fig = create_figure(title="Download Efficiency Analysis")
    
    efficiency_data = [
        {'metric': 'URLs Found', 'value': total_found, 'percentage': 100},
        {'metric': 'Successfully Downloaded', 'value': total_downloaded, 'percentage': success_rate},
        {'metric': 'Failed/Missing', 'value': total_found - total_downloaded, 'percentage': 100 - success_rate}
    ]
    
    fig.add_trace(go.Funnel(
        y=[d['metric'] for d in efficiency_data],
        x=[d['value'] for d in efficiency_data],
        textinfo="value+percent initial",
        marker=dict(color=[theme.colors['info'], theme.colors['success'], theme.colors['warning']])
    ))
    
    fig.update_layout(height=400)
    
    return fig

def create_combined_quality_analysis(data):
    success_breakdown = create_success_rate_breakdown(data)
    class_success = create_class_success_rates(data)
    download_comparison = create_download_comparison(data)
    quality_detailed = create_quality_issues_detailed(data)
    summary_cards = create_quality_summary_cards(data)
    efficiency_chart = create_download_efficiency_chart(data)
    
    return {
        'success_rate_breakdown': success_breakdown,
        'class_success_rates': class_success,
        'download_comparison': download_comparison,
        'quality_issues_detailed': quality_detailed,
        'summary_cards': summary_cards,
        'efficiency_analysis': efficiency_chart
    }