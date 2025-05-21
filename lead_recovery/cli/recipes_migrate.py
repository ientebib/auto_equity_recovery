"""
Migration Helper CLI for Lead Recovery Recipes

Usage:
  python -m lead_recovery.cli.main recipes-migrate <recipe_name>
  python -m lead_recovery.cli.main recipes-migrate --all

Features:
- Adds 'recipe_schema_version: 2' if missing
- Updates legacy fields to new schema
- Uses processor registry to suggest output_columns
- Backs up old meta.yml before overwriting (unless --no-backup)
- Supports --dry-run to preview changes
"""
import shutil
from pathlib import Path

import typer
import yaml

from lead_recovery.processors._registry import get_columns_for_processor

app = typer.Typer()

RECIPES_DIR = Path(__file__).resolve().parent.parent.parent / "recipes"


def migrate_meta_yml(meta_path: Path, dry_run: bool = False, backup: bool = True) -> bool:
    with open(meta_path, "r") as f:
        meta = yaml.safe_load(f)
    changed = False
    # Add schema version if missing
    if "recipe_schema_version" not in meta:
        meta["recipe_schema_version"] = 2
        changed = True
    # Update output_columns using processor registry
    if "python_processors" in meta:
        all_columns = set(meta.get("output_columns", []))
        for proc in meta["python_processors"]:
            if isinstance(proc, dict) and "module" in proc:
                class_name = proc["module"].split(".")[-1]
                for col in get_columns_for_processor(class_name):
                    if col not in all_columns:
                        all_columns.add(col)
                        changed = True
        # Keep order: existing output_columns first, then new ones
        meta["output_columns"] = list(meta.get("output_columns", [])) + [c for c in all_columns if c not in meta.get("output_columns", [])]
    # Remove deprecated fields
    for legacy in ["python_flag_columns", "expected_yaml_keys"]:
        if legacy in meta:
            del meta[legacy]
            changed = True
    if changed:
        if dry_run:
            typer.echo(f"[DRY RUN] Would update {meta_path}:")
            typer.echo(yaml.dump(meta, sort_keys=False))
        else:
            if backup:
                shutil.copy2(meta_path, meta_path.with_suffix(".yml.bak"))
            with open(meta_path, "w") as f:
                yaml.dump(meta, f, sort_keys=False)
            typer.echo(f"Updated {meta_path}")
    else:
        typer.echo(f"No changes needed for {meta_path}")
    return changed

@app.command()
def migrate(
    recipe_name: str = typer.Argument(None, help="Recipe name or --all for all recipes"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing files"),
    no_backup: bool = typer.Option(False, "--no-backup", help="Do not create .bak backup files"),
    all_: bool = typer.Option(False, "--all", help="Migrate all recipes")
):
    """Migrate one or all recipes' meta.yml to schema version 2 and update output_columns."""
    recipes = []
    if all_ or recipe_name == "all":
        recipes = [p for p in RECIPES_DIR.iterdir() if (p / "meta.yml").exists()]
    else:
        recipes = [RECIPES_DIR / recipe_name]
    for recipe_dir in recipes:
        meta_path = recipe_dir / "meta.yml"
        if not meta_path.exists():
            typer.echo(f"No meta.yml found for {recipe_dir.name}, skipping.")
            continue
        migrate_meta_yml(meta_path, dry_run=dry_run, backup=not no_backup)

if __name__ == "__main__":
    app() 