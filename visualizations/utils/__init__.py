import plotly.graph_objects as go
import plotly.express as px

from .plot_helpers import (
    theme, apply_global_style, create_figure, create_subplots,
    style_bar_chart, style_pie_chart, style_histogram, style_scatter_plot,
    style_line_chart, add_value_labels, format_large_numbers,
    create_metric_card, save_plot, display_config
)
from .data_loader import (
    load_report_data, extract_quantitative_stats, extract_temporal_stats,
    extract_quality_stats, create_class_distribution_df, create_category_distribution_df,
    create_format_distribution_df, create_color_mode_df, create_quality_issues_df,
    get_file_size_stats, get_dimension_stats, get_duplicate_stats,
    get_temporal_metrics, get_overview_metrics, format_bytes, format_duration
)

# Make plotly objects available to all modules
__all__ = [
    'go', 'px', 'theme', 'apply_global_style', 'create_figure', 'create_subplots',
    'style_bar_chart', 'style_pie_chart', 'style_histogram', 'style_scatter_plot',
    'style_line_chart', 'add_value_labels', 'format_large_numbers',
    'create_metric_card', 'save_plot', 'display_config',
    'load_report_data', 'extract_quantitative_stats', 'extract_temporal_stats',
    'extract_quality_stats', 'create_class_distribution_df', 'create_category_distribution_df',
    'create_format_distribution_df', 'create_color_mode_df', 'create_quality_issues_df',
    'get_file_size_stats', 'get_dimension_stats', 'get_duplicate_stats',
    'get_temporal_metrics', 'get_overview_metrics', 'format_bytes', 'format_duration'
]