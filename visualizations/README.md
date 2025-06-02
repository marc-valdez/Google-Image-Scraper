# Image Scraper Visualization System

A comprehensive visualization system for analyzing image scraping reports using modern Python plotting libraries.

## Overview

This visualization system provides interactive, publication-quality charts and analysis for image scraping datasets. It's built with **Plotly** for modern, interactive visualizations and follows a modular architecture with clean separation between data processing and presentation.

## Features

### 🎨 **Global Styling System**
- Centralized theme management through `plot_helpers.py`
- Consistent color schemes and typography across all visualizations
- Easy customization of chart appearance globally
- Modern, professional design optimized for both web and print

### 📊 **Comprehensive Analysis Modules**
- **Dataset Overview**: High-level statistics and distributions
- **Image Properties**: Technical analysis of file formats, sizes, and dimensions
- **Quality Analysis**: Success rates, download efficiency, and data quality metrics
- **Temporal Analysis**: Time-based performance and efficiency insights
- **Duplicate Detection**: Hash-based duplicate analysis and cleanup recommendations

### 🔧 **Modular Architecture**
- Clean separation between Jupyter notebooks and Python logic
- Reusable visualization functions in dedicated modules
- Shared utilities for data loading and processing
- Easy to extend and maintain

## Directory Structure

```
visualizations/
├── notebooks/                          # Jupyter notebooks for analysis
│   ├── dataset_overview.ipynb         # Dataset statistics and distributions
│   ├── image_properties.ipynb         # Image technical properties
│   ├── quality_analysis.ipynb         # Data quality and success metrics
│   ├── temporal_analysis.ipynb        # Time-based performance analysis
│   └── duplicate_analysis.ipynb       # Duplicate detection analysis
├── visualizers/                       # Core visualization modules
│   ├── dataset_stats.py              # Dataset overview charts
│   ├── image_analysis.py             # Image properties visualizations
│   ├── quality_metrics.py            # Quality analysis charts
│   ├── temporal_stats.py             # Temporal analysis visualizations
│   └── duplicate_detector.py         # Duplicate analysis charts
├── utils/                             # Shared utilities
│   ├── plot_helpers.py               # Global styling and chart utilities
│   ├── data_loader.py                # Data loading and processing
│   └── __init__.py                   # Package initialization
├── output/                            # Generated charts and reports
└── README.md                         # This documentation
```

## Quick Start

### 1. Installation

Install required dependencies:

```bash
pip install -r requirements.txt
```

### 2. Launch Jupyter

Start Jupyter Lab or Notebook:

```bash
# For JupyterLab (recommended)
jupyter lab

# For classic Jupyter Notebook
jupyter notebook
```

### 3. Run Analysis

Navigate to the `notebooks/` directory and open any notebook:

- **`dataset_overview.ipynb`** - Start here for a general overview
- **`image_properties.ipynb`** - Analyze technical image properties
- **`quality_analysis.ipynb`** - Review data quality and success rates
- **`temporal_analysis.ipynb`** - Examine time-based performance
- **`duplicate_analysis.ipynb`** - Analyze duplicate detection results

## Global Styling Customization

The visualization system uses a centralized styling approach. You can customize the appearance of all charts by modifying `utils/plot_helpers.py`:

### Color Scheme

```python
# Edit in plot_helpers.py
self.colors = {
    'primary': '#2E86AB',      # Main brand color
    'secondary': '#A23B72',    # Secondary brand color
    'accent': '#F18F01',       # Accent color
    # ... customize other colors
}
```

### Typography

```python
# Edit in plot_helpers.py
self.layout_config = {
    'font': {
        'family': 'Your-Font-Name, sans-serif',
        'size': 14,
        'color': self.colors['text']
    },
    # ... other layout settings
}
```

### Chart Themes

The system automatically applies consistent styling to all chart types:
- Bar charts with hover templates and value labels
- Pie charts with consistent color schemes
- Line charts with modern styling
- Gauge charts with branded colors
- Interactive features with professional appearance

## Data Requirements

The system expects a JSON report file with the following structure:

```json
{
  "generated_at": "2025-06-02T18:46:03.540550",
  "quantitative_statistics": {
    "total_image_count": 47075,
    "images_per_class": { ... },
    "images_per_category": { ... },
    "file_size": { ... },
    "dimensions": { ... },
    "color_modes": { ... },
    "formats": { ... },
    "hashes": { ... }
  },
  "temporal_statistics": { ... },
  "quality_checks": { ... }
}
```

## Usage Examples

### Basic Usage

```python
from visualizers.dataset_stats import create_combined_overview
from utils.data_loader import load_report_data

# Load data
data = load_report_data('path/to/report.json')

# Generate visualizations
charts = create_combined_overview(data)

# Display charts
charts['overview'].show()
```

### Custom Styling

```python
from utils.plot_helpers import create_figure, style_bar_chart, theme

# Create a custom chart with global styling
fig = create_figure(title="My Custom Chart")
fig.add_trace(...)
styled_fig = style_bar_chart(fig)
styled_fig.show()
```

### Export Options

```python
from utils.plot_helpers import save_plot

# Save in different formats
save_plot(fig, 'my_chart', 'html')     # Interactive HTML
save_plot(fig, 'my_chart', 'png')     # High-quality PNG
save_plot(fig, 'my_chart', 'pdf')     # Vector PDF
```

## Chart Types Available

### Statistical Charts
- **Bar Charts**: Class distributions, format popularity
- **Pie Charts**: Category breakdowns, color mode distributions
- **Histograms**: File size distributions, dimension analysis
- **Scatter Plots**: Dimension correlations, size vs format

### Performance Charts
- **Gauge Charts**: Success rates, efficiency metrics
- **Timeline Charts**: Scraping progress over time
- **Funnel Charts**: Download process efficiency
- **Metric Cards**: Key performance indicators

### Interactive Features
- **Hover Templates**: Detailed information on hover
- **Zoom and Pan**: Interactive exploration
- **Export Tools**: Built-in export functionality
- **Responsive Design**: Adapts to different screen sizes

## Extending the System

### Adding New Visualizations

1. **Create a new visualizer module** in `visualizers/`
2. **Import utilities** from the `utils` package
3. **Use global styling** functions for consistency
4. **Create corresponding notebook** in `notebooks/`

Example:

```python
# visualizers/my_analysis.py
from utils import create_figure, style_bar_chart

def create_my_chart(data):
    fig = create_figure(title="My Analysis")
    # Add your chart logic here
    return style_bar_chart(fig)
```

### Custom Data Processing

Add new data processing functions to `utils/data_loader.py`:

```python
def process_my_data(data):
    # Your data processing logic
    return processed_data
```

## Performance Considerations

- **Lazy Loading**: Charts are generated only when called
- **Efficient Data Processing**: Pandas-based data manipulation
- **Interactive Rendering**: Plotly's efficient rendering engine
- **Export Optimization**: Multiple format support with quality options

## Troubleshooting

### Common Issues

1. **Module Import Errors**: Ensure you're running notebooks from the correct directory
2. **Missing Dependencies**: Install all requirements from `requirements.txt`
3. **Data Format Issues**: Verify your JSON report matches the expected structure
4. **Styling Issues**: Check `plot_helpers.py` for theme configuration

### Support

For issues and questions:
1. Check the notebook outputs for error messages
2. Verify data file format and location
3. Ensure all dependencies are installed
4. Review the modular structure documentation

## License

This visualization system is part of the Google Image Scraper project and follows the same licensing terms.