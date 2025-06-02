import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.io as pio

class PlotTheme:
    def __init__(self):
        self.colors = {
            'primary': '#2E86AB',
            'secondary': '#A23B72', 
            'accent': '#F18F01',
            'success': '#C73E1D',
            'warning': '#FFB627',
            'info': '#845EC2',
            'light': '#F8F9FA',
            'dark': '#212529',
            'background': '#FFFFFF',
            'text': '#2C3E50'
        }
        
        self.color_palette = [
            '#2E86AB', '#A23B72', '#F18F01', '#C73E1D', 
            '#FFB627', '#845EC2', '#4E9F3D', '#FF8B94',
            '#3CBCCF', '#FFA07A', '#9370DB', '#20B2AA'
        ]
        
        self.layout_config = {
            'font': {
                'family': 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                'size': 14,
                'color': self.colors['text']
            },
            'paper_bgcolor': self.colors['background'],
            'plot_bgcolor': self.colors['background'],
            'title': {
                'font': {'size': 20, 'color': self.colors['text']},
                'x': 0.5,
                'xanchor': 'center'
            },
            'legend': {
                'bgcolor': 'rgba(255, 255, 255, 0.8)',
                'bordercolor': 'rgba(0, 0, 0, 0.1)',
                'borderwidth': 1
            },
            'margin': {'l': 60, 'r': 60, 't': 80, 'b': 60}
        }

theme = PlotTheme()

def apply_global_style():
    pio.templates.default = "plotly_white"
    pio.templates["custom"] = go.layout.Template(
        layout=go.Layout(
            **theme.layout_config,
            colorway=theme.color_palette,
            xaxis=dict(
                gridcolor='rgba(128, 128, 128, 0.2)',
                linecolor='rgba(128, 128, 128, 0.3)',
                tickfont=dict(color=theme.colors['text'])
            ),
            yaxis=dict(
                gridcolor='rgba(128, 128, 128, 0.2)',
                linecolor='rgba(128, 128, 128, 0.3)',
                tickfont=dict(color=theme.colors['text'])
            )
        )
    )
    pio.templates.default = "custom"

def create_figure(title="", width=800, height=500, **kwargs):
    apply_global_style()
    fig = go.Figure()
    
    # Create layout config without title to avoid conflict
    layout_config = theme.layout_config.copy()
    if title:
        layout_config['title']['text'] = title
    
    fig.update_layout(
        width=width,
        height=height,
        **layout_config,
        **kwargs
    )
    return fig

def create_subplots(rows=1, cols=1, subplot_titles=None, **kwargs):
    apply_global_style()
    fig = make_subplots(
        rows=rows, 
        cols=cols, 
        subplot_titles=subplot_titles,
        **kwargs
    )
    fig.update_layout(**theme.layout_config)
    return fig

def style_bar_chart(fig, color_sequence=None):
    if color_sequence is None:
        color_sequence = theme.color_palette
    
    fig.update_traces(
        marker=dict(
            line=dict(width=0.5, color='rgba(255, 255, 255, 0.8)'),
            opacity=0.8
        ),
        hovertemplate='<b>%{x}</b><br>Count: %{y:,.0f}<extra></extra>'
    )
    return fig

def style_pie_chart(fig):
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>Count: %{value:,.0f}<br>Percentage: %{percent}<extra></extra>',
        marker=dict(
            colors=theme.color_palette,
            line=dict(color='#FFFFFF', width=2)
        )
    )
    return fig

def style_histogram(fig):
    fig.update_traces(
        marker=dict(
            color=theme.colors['primary'],
            opacity=0.7,
            line=dict(width=0.5, color='rgba(255, 255, 255, 0.8)')
        ),
        hovertemplate='Range: %{x}<br>Count: %{y:,.0f}<extra></extra>'
    )
    return fig

def style_scatter_plot(fig):
    fig.update_traces(
        marker=dict(
            size=8,
            opacity=0.6,
            line=dict(width=0.5, color='rgba(255, 255, 255, 0.8)')
        ),
        hovertemplate='<b>X:</b> %{x:,.0f}<br><b>Y:</b> %{y:,.0f}<extra></extra>'
    )
    return fig

def style_line_chart(fig):
    fig.update_traces(
        line=dict(width=3),
        mode='lines+markers',
        marker=dict(size=6),
        hovertemplate='<b>%{x}</b><br>Value: %{y:,.2f}<extra></extra>'
    )
    return fig

def add_value_labels(fig, format_str='{:.0f}'):
    fig.update_traces(
        texttemplate=format_str,
        textposition='outside'
    )
    return fig

def format_large_numbers(value):
    if value >= 1e6:
        return f'{value/1e6:.1f}M'
    elif value >= 1e3:
        return f'{value/1e3:.1f}K'
    else:
        return f'{value:.0f}'

def create_metric_card(title, value, format_func=None):
    if format_func:
        display_value = format_func(value)
    else:
        display_value = f'{value:,.0f}' if isinstance(value, (int, float)) else str(value)
    
    fig = go.Figure(go.Indicator(
        mode = "number",
        value = value,
        title = {"text": title, "font": {"size": 16}},
        number = {"font": {"size": 32, "color": theme.colors['primary']}},
        domain = {'x': [0, 1], 'y': [0, 1]}
    ))
    
    fig.update_layout(
        height=200,
        **theme.layout_config
    )
    return fig

def save_plot(fig, filename, format='html', width=None, height=None):
    if format == 'html':
        fig.write_html(f"visualizations/output/{filename}.html")
    elif format == 'png':
        fig.write_image(f"visualizations/output/{filename}.png", width=width, height=height)
    elif format == 'pdf':
        fig.write_image(f"visualizations/output/{filename}.pdf", width=width, height=height)

def display_config():
    return {
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d'],
        'toImageButtonOptions': {
            'format': 'png',
            'filename': 'custom_image',
            'height': 600,
            'width': 1000,
            'scale': 2
        }
    }