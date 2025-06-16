#!/usr/bin/env python3
"""
Standard Runner for the Formalizacion Recipe

This script provides a reliable, standardized way to execute the formalizacion
recipe. It handles the full pipeline:
1. Fetching leads from the designated Google Sheet.
2. Fetching conversations from BigQuery using the standard CLI script.
3. Running the core Lead Recovery analysis directly, bypassing the faulty CLI runner.
4. Uploading the clean results back to a Google Sheet.

This is the official, stable way to run this recipe.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import yaml

# Add project root to path to allow direct imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from lead_recovery.analysis import run_summarization_step


def _get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def _run_command(command: list[str], cwd: str, env: dict | None = None) -> bool:
    """Run a command and return True on success, False on failure."""
    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        print(f"   -> Command successful: {' '.join(command)}")
        if process.stdout:
            print(f"   STDOUT: {process.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running command: {' '.join(command)}")
        print(f"   Return Code: {e.returncode}")
        if e.stdout:
            print(f"   STDOUT: {e.stdout.strip()}")
        if e.stderr:
            print(f"   STDERR: {e.stderr.strip()}")
        return False


async def main():
    """Main execution function for the formalizacion recipe."""
    print("🚀 ** Starting Formalizacion Recipe Pipeline **")
    print("=" * 50)

    # --- Configuration ---
    root = _get_project_root()
    recipe_name = "formalizacion"
    recipe_dir = root / "recipes" / recipe_name
    output_dir = root / "output_run" / recipe_name

    # Load recipe config
    with open(recipe_dir / "meta.yml", "r") as f:
        meta_config = yaml.safe_load(f)

    # --- Step 1: Fetch Leads ---
    print("📊 Step 1: Fetching leads from Google Sheets...")
    if not _run_command(["python3", "fetch_leads_from_sheets.py"], cwd=str(recipe_dir)):
        sys.exit("Pipeline failed at lead fetching step.")

    # --- Step 2: Fetch Conversations ---
    print("\n🗣️ Step 2: Fetching conversations from BigQuery...")
    # The fetch_convos script reads the leads.csv from the output dir
    # so we need to copy it there first.
    os.makedirs(output_dir, exist_ok=True)
    subprocess.run(["cp", str(recipe_dir / "leads.csv"), str(output_dir / "leads.csv")])
    
    # We must run this from the project root with PYTHONPATH set
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    fetch_convos_command = [
        "python3",
        "-m",
        "lead_recovery.cli.fetch_convos",
        "--output-dir",
        str(output_dir),
        "--sql-file",
        str(recipe_dir / "formalizacion_bigquery.sql"),
    ]
    if not _run_command(fetch_convos_command, cwd=str(root), env=env):
        sys.exit("Pipeline failed at conversation fetching step.")

    # --- Step 3: Run Summarization Directly ---
    print("\n🤖 Step 3: Running summarization analysis...")
    try:
        await run_summarization_step(
            output_dir=output_dir,
            prompt_template_path=recipe_dir / "prompt.txt",
            recipe_name=recipe_name,
            gsheet_config=meta_config.get("custom_analyzer_params", {}).get("google_sheets"),
            meta_config=meta_config,
            use_cache=False,  # Force re-computation
        )
        print("   -> Summarization analysis completed.")
    except Exception as e:
        print(f"❌ Summarization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # --- Step 4: Final Upload Verification ---
    print("\n📤 Step 4: Verifying Google Sheets Upload...")
    worksheet_name = meta_config.get("custom_analyzer_params", {}).get("google_sheets", {}).get("worksheet_name", "Bot Live")
    print(f"   -> Pipeline attempts to upload to Google Sheet '{worksheet_name}'.")
    print("   -> Please verify the contents in Google Sheets.")

    print("\n🎉 ** SUCCESS! Formalizacion recipe completed! **")
    print(f"📁 Final results are in: {output_dir}/latest.csv")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main()) 