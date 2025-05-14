# Lead Recovery Dashboard

A Streamlit dashboard for the Lead Recovery Pipeline that allows you to:
- View and run recipes
- Manage Redshift markers
- Monitor pipeline execution
- Explore recipe configurations

## Features

- **Auto-detection**: Automatically detects all recipes in the `recipes/` directory
- **Hot-reload**: Updates UI when new recipe directories appear without restarting
- **User-friendly interface**: Zero CLI knowledge required
- **Secure**: No database credentials visible in the UI
- **Real-time logs**: Streams logs while a recipe runs
- **OS integration**: Open output directories directly in Finder (macOS)

## Installation

1. Make sure you have the lead-recovery package installed:
   ```bash
   pip install -e ..
   ```

2. Install dashboard requirements:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Launch the dashboard with:

```bash
streamlit run app.py
```

The dashboard will be available at http://localhost:8501

## Dashboard Structure

- **Recipe Management** (left sidebar): Select recipes, view status, refresh detection
- **Recipe Explorer** (main area): View recipe configurations through tabs
  - Meta / Config: View meta.yml
  - SQL: View Redshift and BigQuery SQL
  - Prompt: View LLM prompt
  - Python: View global functions and custom analyzers
- **Execution Controls** (right sidebar): Configure and run recipes
  - Skip options (Redshift, BigQuery, Summarize)
  - Cache options
  - Max workers setting
  - Real-time log streaming
  - Output summary

## Requirements

- Python 3.10+
- Streamlit 1.33.0+
- PyYAML 6.0+
- lead-recovery package (installed locally) 