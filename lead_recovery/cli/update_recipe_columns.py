"""CLI command for updating meta.yml files with Python flag columns."""
import logging
from pathlib import Path
from typing import List, Optional

import typer
import yaml

from ..python_flags_manager import get_python_flag_columns, get_python_flags_from_meta, update_meta_yml_for_python_flags
from ..config import settings

logger = logging.getLogger(__name__)

app = typer.Typer()

@app.callback(invoke_without_command=True)
def update_recipe_columns(
    recipe_name: str = typer.Argument(..., help="Recipe name to update"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without writing them"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Update a recipe's meta.yml file with the correct Python flag columns based on enabled/disabled flags."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    recipe_dir = settings.PROJECT_ROOT / "recipes" / recipe_name
    if not recipe_dir.exists():
        typer.echo(f"Error: Recipe directory '{recipe_dir}' does not exist")
        raise typer.Exit(1)
    
    meta_path = recipe_dir / "meta.yml"
    if not meta_path.exists():
        typer.echo(f"Error: meta.yml file not found at '{meta_path}'")
        raise typer.Exit(1)
    
    # Get Python flags from meta.yml
    skip_flags = get_python_flags_from_meta(recipe_dir)
    
    # Get columns based on enabled/disabled functions
    python_columns = get_python_flag_columns(
        skip_temporal_flags=skip_flags.get("skip_temporal_flags", False),
        skip_metadata_extraction=skip_flags.get("skip_metadata_extraction", False),
        skip_handoff_detection=skip_flags.get("skip_handoff_detection", False),
        skip_human_transfer=skip_flags.get("skip_human_transfer", False),
        skip_recovery_template_detection=skip_flags.get("skip_recovery_template_detection", False),
        skip_consecutive_templates_count=skip_flags.get("skip_consecutive_templates_count", False),
        skip_handoff_invitation=skip_flags.get("skip_handoff_invitation", False),
        skip_handoff_started=skip_flags.get("skip_handoff_started", False),
        skip_handoff_finalized=skip_flags.get("skip_handoff_finalized", False),
        skip_detailed_temporal=skip_flags.get("skip_detailed_temporal", False),
        skip_hours_minutes=skip_flags.get("skip_hours_minutes", False),
        skip_reactivation_flags=skip_flags.get("skip_reactivation_flags", False),
        skip_timestamps=skip_flags.get("skip_timestamps", False),
        skip_user_message_flag=skip_flags.get("skip_user_message_flag", False)
    )
    
    # Print the Python flag columns
    typer.echo(f"Python flag columns for recipe '{recipe_name}':")
    for col in python_columns:
        typer.echo(f"  - {col}")
    
    # Update meta.yml file
    if not dry_run:
        success = update_meta_yml_for_python_flags(recipe_dir, python_columns)
        if success:
            typer.echo(f"Successfully updated meta.yml for recipe '{recipe_name}'")
        else:
            typer.echo(f"Error updating meta.yml for recipe '{recipe_name}'")
            raise typer.Exit(1)
    else:
        typer.echo("Dry run - no changes made")
        
    return python_columns

@app.command()
def update_all(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without writing them"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Update all recipes' meta.yml files with Python flag columns."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    recipes_dir = settings.PROJECT_ROOT / "recipes"
    if not recipes_dir.exists():
        typer.echo(f"Error: Recipes directory '{recipes_dir}' does not exist")
        raise typer.Exit(1)
    
    # Find all recipe directories with meta.yml files
    recipe_dirs = []
    for path in recipes_dir.iterdir():
        if path.is_dir() and (path / "meta.yml").exists():
            recipe_dirs.append(path)
    
    typer.echo(f"Found {len(recipe_dirs)} recipes with meta.yml files")
    
    # Update each recipe
    for recipe_dir in recipe_dirs:
        recipe_name = recipe_dir.name
        typer.echo(f"\nUpdating recipe: {recipe_name}")
        
        # Get Python flags from meta.yml
        skip_flags = get_python_flags_from_meta(recipe_dir)
        
        # Get columns based on enabled/disabled functions
        python_columns = get_python_flag_columns(
            skip_temporal_flags=skip_flags.get("skip_temporal_flags", False),
            skip_metadata_extraction=skip_flags.get("skip_metadata_extraction", False),
            skip_handoff_detection=skip_flags.get("skip_handoff_detection", False),
            skip_human_transfer=skip_flags.get("skip_human_transfer", False),
            skip_recovery_template_detection=skip_flags.get("skip_recovery_template_detection", False),
            skip_consecutive_templates_count=skip_flags.get("skip_consecutive_templates_count", False),
            skip_handoff_invitation=skip_flags.get("skip_handoff_invitation", False),
            skip_handoff_started=skip_flags.get("skip_handoff_started", False),
            skip_handoff_finalized=skip_flags.get("skip_handoff_finalized", False),
            skip_detailed_temporal=skip_flags.get("skip_detailed_temporal", False),
            skip_hours_minutes=skip_flags.get("skip_hours_minutes", False),
            skip_reactivation_flags=skip_flags.get("skip_reactivation_flags", False),
            skip_timestamps=skip_flags.get("skip_timestamps", False),
            skip_user_message_flag=skip_flags.get("skip_user_message_flag", False)
        )
        
        if verbose:
            for col in python_columns:
                typer.echo(f"  - {col}")
        else:
            typer.echo(f"  {len(python_columns)} Python flag columns")
        
        # Update meta.yml file
        if not dry_run:
            success = update_meta_yml_for_python_flags(recipe_dir, python_columns)
            if success:
                typer.echo(f"  Successfully updated meta.yml")
            else:
                typer.echo(f"  Error updating meta.yml")
        
    if dry_run:
        typer.echo("\nDry run - no changes made")
    else:
        typer.echo("\nAll recipes updated successfully") 