"""CLI command for generating reports from analysis results."""
from pathlib import Path
from typing import Optional
from datetime import datetime
import logging
import yaml

import typer
import pandas as pd

from ..reporting import to_html, to_csv
from ..config import settings

logger = logging.getLogger(__name__)

app = typer.Typer()

@app.callback(invoke_without_command=True)
def report(
    output_dir: Path = typer.Option(settings.OUTPUT_DIR, "--output-dir"),
    # Added: Recipe name for output filename
    recipe_name: Optional[str] = typer.Option(None, help="Recipe name for output filename."),
    format: str = typer.Option("html", "--format", "-f", help="Output format: html, csv, or both"),
):
    """Generate HTML/CSV reports from merged analysis results."""
    # Default recipe name if not provided (e.g., when called directly, not via 'run')
    _recipe_name = recipe_name or output_dir.name
    today_str = datetime.now().strftime('%Y%m%d')
    base_filename = f"{_recipe_name}_analysis_{today_str}"
    csv_input_path = output_dir / f"{base_filename}.csv" # Input is the new CSV name
    
    # Check if csv file exists
    if not csv_input_path.is_file():
        # Try older filename pattern without date
        legacy_csv_path = output_dir / "analysis.csv"
        if legacy_csv_path.is_file():
            csv_input_path = legacy_csv_path
            logger.info(f"Using legacy CSV file: {legacy_csv_path}")
        else:
            typer.echo(f"Analysis CSV not found at {csv_input_path} or {legacy_csv_path}. Run summarize first.")
            raise typer.Exit(1)

    # Load the CSV data
    df = pd.read_csv(csv_input_path)
    logger.info(f"Loaded {len(df)} rows from {csv_input_path}")
    
    # Try to load output_columns from meta.yml if recipe_name is provided
    output_columns = None
    if recipe_name:
        meta_path = settings.PROJECT_ROOT / "recipes" / recipe_name / "meta.yml"
        if meta_path.exists():
            try:
                with open(meta_path, 'r') as f:
                    meta_data = yaml.safe_load(f)
                    if meta_data and 'output_columns' in meta_data:
                        output_columns = meta_data['output_columns']
                        logger.info(f"Using {len(output_columns)} output columns from {meta_path}")
            except Exception as e:
                logger.warning(f"Error loading meta.yml for recipe {recipe_name}: {e}")
    
    # Generate outputs based on requested format
    if format.lower() in ["html", "both"]:
        html_output_path = output_dir / f"{base_filename}.html"
        to_html(df, html_output_path, columns=output_columns)
        typer.echo(f"HTML report generated at {html_output_path}")
    
    if format.lower() in ["csv", "both"]:
        # Only regenerate CSV if not the same as input
        new_csv_path = output_dir / f"{base_filename}_report.csv"
        if new_csv_path != csv_input_path:
            to_csv(df, new_csv_path, columns=output_columns)
            typer.echo(f"CSV report generated at {new_csv_path}")
            
    return df  # Return the DataFrame for programmatic access 