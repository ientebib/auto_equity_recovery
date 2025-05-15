#!/usr/bin/env python3
"""Debug tool for testing recipe SQL and summarization.

This is a developer utility for testing recipe configurations without running the full pipeline.
"""
import logging
import sys
from pathlib import Path

import typer

# Add parent directory to path to allow imports from lead_recovery package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lead_recovery.config import get_settings
from lead_recovery.db_clients import BigQueryClient, RedshiftClient
from lead_recovery.utils import load_sql_file

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
)
logger = logging.getLogger("recipe_debugger")

app = typer.Typer(add_completion=False)

@app.command()
def test_redshift(
    recipe: str = typer.Option(..., help="Recipe name to test"),
    limit: int = typer.Option(10, help="Maximum number of rows to return"),
):
    """Test the Redshift SQL for a recipe and show sample results."""
    settings = get_settings()
    rs_client = RedshiftClient()
    
    # Construct paths based on recipe
    recipe_dir = settings.PROJECT_ROOT / "recipes" / recipe
    redshift_sql_path = recipe_dir / "redshift.sql"
    
    if not redshift_sql_path.exists():
        logger.error(f"Redshift SQL file not found for recipe '{recipe}': {redshift_sql_path}")
        raise typer.Exit(1)
    
    sql = load_sql_file(redshift_sql_path)
    
    # Add LIMIT clause if not present
    if "LIMIT" not in sql.upper():
        sql += f"\nLIMIT {limit}"
    
    logger.info(f"Executing Redshift SQL for recipe '{recipe}'")
    try:
        df = rs_client.query(sql)
        print(f"\nResults ({len(df)} rows):")
        print(df.head(limit).to_string())
        print(f"\nColumns: {df.columns.tolist()}")
    except Exception as e:
        logger.error(f"Error executing Redshift SQL: {e}", exc_info=True)
        raise typer.Exit(1)


@app.command()
def test_bigquery(
    recipe: str = typer.Option(..., help="Recipe name to test"),
    limit: int = typer.Option(10, help="Maximum number of rows to return"),
    phone: str = typer.Option(..., help="Test phone number to query"),
):
    """Test the BigQuery SQL for a recipe with a sample phone number."""
    settings = get_settings()
    bq_client = BigQueryClient()
    
    # Construct paths based on recipe
    recipe_dir = settings.PROJECT_ROOT / "recipes" / recipe
    bigquery_sql_path = recipe_dir / "bigquery.sql"
    
    if not bigquery_sql_path.exists():
        logger.error(f"BigQuery SQL file not found for recipe '{recipe}': {bigquery_sql_path}")
        raise typer.Exit(1)
    
    from google.cloud.bigquery import ArrayQueryParameter
    
    sql = load_sql_file(bigquery_sql_path)
    
    # Add LIMIT clause if not present
    if "LIMIT" not in sql.upper():
        sql = sql.replace(";", f" LIMIT {limit};")
    
    logger.info(f"Executing BigQuery SQL for recipe '{recipe}' with phone {phone}")
    try:
        df = bq_client.query(
            sql,
            [ArrayQueryParameter("target_phone_numbers_list", "STRING", [phone])]
        )
        print(f"\nResults ({len(df)} rows):")
        print(df.head(limit).to_string())
        print(f"\nColumns: {df.columns.tolist()}")
    except Exception as e:
        logger.error(f"Error executing BigQuery SQL: {e}", exc_info=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app() 