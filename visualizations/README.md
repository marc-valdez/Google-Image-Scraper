# Image Scraper Visualization System

This folder contains a comprehensive visualization system for analyzing image scraping results. The system is modular, with reusable Python functions and lightweight Jupyter notebooks.

## Structure

```
visualizations/
├── __init__.py                      # Package initialization
├── data_loader.py                   # Data loading and processing utilities
├── plotters.py                      # Visualization functions
├── README.md                        # This documentation
├── 01_overview_dashboard.ipynb      # Main dashboard and overview
├── 02_class_performance.ipynb       # Class-level performance analysis
├── 03_image_quality_analysis.ipynb  # Image quality and characteristics
├── 04_duplicate_analysis.ipynb      # Duplicate detection and analysis
└── 05_temporal_analysis.ipynb       # Time-based analysis and patterns
```

## Quick Start

1. Navigate to the visualizations folder
2. Start Jupyter: `jupyter notebook`
3. Run notebooks starting with `01_overview_dashboard.ipynb`

## Notebooks Overview

### 1. Overview Dashboard
- Dataset summary statistics
- Category distribution analysis
- Key performance indicators

### 2. Class Performance
- Success rates by class
- Image count distributions
- Problem identification

### 3. Image Quality Analysis
- File size and format analysis
- Resolution statistics
- Quality recommendations

### 4. Duplicate Analysis
- Inter-class and intra-class duplicates
- Storage impact assessment
- Deduplication recommendations

### 5. Temporal Analysis
- Download rate analysis
- Timing patterns
- Performance optimization

## Key Features

- **No Sample Data**: All analysis uses actual metadata from your scraping operations
- **Modular Design**: Reusable functions in separate Python modules
- **Interactive Visualizations**: Plotly-based charts with hover details
- **Actionable Insights**: Specific recommendations for improvement
- **Comprehensive Coverage**: Analysis of all aspects of the scraping process

## Data Requirements

The notebooks expect metadata files in the format:
- Location: `../output/metadata/[category]/[class]/[class]_metadata.json`
- Format: Unified metadata format with `images`, `search_key`, etc.

## Dependencies

- pandas
- numpy
- plotly
- matplotlib
- seaborn

Install with: `pip install pandas numpy plotly matplotlib seaborn`