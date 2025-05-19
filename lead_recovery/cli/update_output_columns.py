"""
Update Output Columns CLI for Lead Recovery Recipes

Usage:
  python -m lead_recovery.cli.main update-output-columns <recipe_name>
  python -m lead_recovery.cli.main update-output-columns <recipe_name> --dry-run

Features:
- Updates output_columns in meta.yml based on current processors, LLM keys, and lead_columns
- Supports dynamic lead columns (from lead_columns section or default whitelist)
- Preserves order if possible
- Supports --dry-run and --backup
"""
import typer
import yaml
from pathlib import Path
import shutil
from lead_recovery.processors._registry import get_columns_for_processor

app = typer.Typer()

RECIPES_DIR = Path(__file__).resolve().parent.parent.parent / "recipes"
DEFAULT_LEAD_COLUMNS = [
    "cleaned_phone", "lead_id", "user_id", "lead_created_at", "name", "last_name", "Email", "Asset ID", "Last Bureua Score", "Max Loan", "Nombre", "Cohort", "Control Group", "Initial Step", "Initial Step Date", "Last Step", "Last Step Date", "Bill Date", "handoff_reached", "cache_status"
]

def update_output_columns(meta_path: Path, dry_run: bool = False, backup: bool = True) -> bool:
    with open(meta_path, "r") as f:
        meta = yaml.safe_load(f)
    changed = False
    # Get lead columns
    lead_columns = meta.get("lead_columns", DEFAULT_LEAD_COLUMNS)
    # Get processor columns
    processor_columns = set()
    if "python_processors" in meta:
        for proc in meta["python_processors"]:
            if isinstance(proc, dict) and "module" in proc:
                class_name = proc["module"].split(".")[-1]
                processor_columns.update(get_columns_for_processor(class_name))
    # Get LLM keys
    llm_keys = set()
    if "llm_config" in meta and meta["llm_config"] and "expected_llm_keys" in meta["llm_config"]:
        llm_keys = set(meta["llm_config"]["expected_llm_keys"].keys())
    # Build new output_columns
    new_output_columns = list(lead_columns) + list(llm_keys) + list(processor_columns)
    # Remove duplicates, preserve order
    seen = set()
    new_output_columns = [x for x in new_output_columns if not (x in seen or seen.add(x))]
    if meta.get("output_columns", []) != new_output_columns:
        meta["output_columns"] = new_output_columns
        changed = True
    if changed:
        if dry_run:
            typer.echo(f"[DRY RUN] Would update {meta_path} output_columns:")
            typer.echo(yaml.dump({"output_columns": new_output_columns}, sort_keys=False))
        else:
            if backup:
                shutil.copy2(meta_path, meta_path.with_suffix(".yml.bak"))
            with open(meta_path, "w") as f:
                yaml.dump(meta, f, sort_keys=False)
            typer.echo(f"Updated output_columns in {meta_path}")
    else:
        typer.echo(f"No changes needed for {meta_path}")
    return changed

@app.command()
def update(
    recipe_name: str = typer.Argument(..., help="Recipe name to update"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing files"),
    no_backup: bool = typer.Option(False, "--no-backup", help="Do not create .bak backup files")
):
    """Update output_columns in a recipe's meta.yml based on processors, LLM keys, and lead_columns."""
    recipe_dir = RECIPES_DIR / recipe_name
    meta_path = recipe_dir / "meta.yml"
    if not meta_path.exists():
        typer.echo(f"No meta.yml found for {recipe_name}.")
        raise typer.Exit(1)
    update_output_columns(meta_path, dry_run=dry_run, backup=not no_backup)

if __name__ == "__main__":
    app() 