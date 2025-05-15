"""CLI command for generating reports from analysis results."""
from pathlib import Path
from typing import Optional, List, Union
from datetime import datetime
import logging
import yaml

import typer
import pandas as pd

from ..reporting import export_data
from ..config import settings

logger = logging.getLogger(__name__)

app = typer.Typer()

@app.callback(invoke_without_command=True)
def report(
    output_dir: Path = typer.Option(settings.OUTPUT_DIR, "--output-dir"),
    # Added: Recipe name for output filename
    recipe_name: Optional[str] = typer.Option(None, help="Recipe name for output filename."),
    format: str = typer.Option("csv", "--format", "-f", help="Output format: csv, json, or all"),
):
    """Generate reports from merged analysis results."""
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
    try:
        df = pd.read_csv(csv_input_path)
        logger.info(f"Loaded {len(df)} rows from {csv_input_path}")
    except Exception as e:
        typer.echo(f"Error loading CSV file {csv_input_path}: {e}")
        raise typer.Exit(1)
    
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
    
    # Determine which formats to export based on the format parameter
    export_formats = []
    format_value = str(format).lower()
    if hasattr(format, 'name') and hasattr(format, 'default'):
        # This is likely a typer.Option object, use its default value
        format_value = format.default or "csv"
        format_value = format_value.lower()
    
    if format_value == "all":
        export_formats = ["csv", "json"]
    elif format_value in ["csv", "json"]:
        export_formats = [format_value]
    else:
        logger.warning(f"Unsupported format: {format_value}. Using csv as default.")
        export_formats = ["csv"]
    
    # Use the unified export function
    try:
        # Ensure we don't overwrite the input file if it's part of the export formats
        output_base_name = f"{base_filename}_report" if "csv" in export_formats else base_filename
        
        result_paths = export_data(
            df=df,
            output_dir=output_dir,
            base_name=output_base_name,
            formats=export_formats,
            columns=output_columns
        )
        
        # Report to user
        for fmt, path in result_paths.items():
            typer.echo(f"{fmt.upper()} report generated at {path}")
        
        return df  # Return the DataFrame for programmatic access
    except Exception as e:
        logger.error(f"Error generating reports: {e}")
        typer.echo(f"Error generating reports: {e}")
        raise typer.Exit(1) 