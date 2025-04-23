import streamlit as st
import pandas as pd
from pathlib import Path
import logging
import sys
from datetime import datetime, date
from typing import Optional, Callable

# Add project root to path to allow importing lead_recovery
# Assumes dashboard.py is in the project root alongside the lead_recovery package
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from lead_recovery.recipe_loader import list_recipes, load_recipe, Recipe
    # Import CLI functions which contain the core logic
    from lead_recovery.cli import fetch_leads, fetch_convos, summarize, report
    from lead_recovery.config import settings
    from lead_recovery import __version__ as lr_version
except ImportError as e:
    st.error(
        f"Failed to import the 'lead_recovery' package. "
        f"Ensure it's installed (`pip install .`) and that this script "
        f"is run from the project root. Error: {e}"
    )
    st.stop()

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Lead Recovery Dashboard", layout="wide")


# --- Status Update Helper ---
status_lines = [] # Global list to store status messages for the current run
status_placeholder = st.empty() # Placeholder to display status

def log_status(message, level="info"):
    """Helper to add status messages to the placeholder."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "ℹ️")
    status_lines.append(f"{icon} [{timestamp}] {message}")
    # Use markdown with non-breaking spaces for better spacing
    status_placeholder.markdown("  \n".join(status_lines), unsafe_allow_html=True)

# --- Pipeline Step Runner Helper ---
def run_pipeline_step(step_func: Callable, message: str, *args, **kwargs) -> bool:
    """Runs a pipeline step function, updates status via log_status, and handles errors."""
    log_status(message)
    try:
        spinner_message = message.split(":")[1].strip() if ":" in message else message
        with st.spinner(f"{spinner_message}..."):
            step_func(*args, **kwargs)
        return True
    except Exception as e:
        logger.error(f"Error during {message}: {e}", exc_info=True)
        log_status(f"{message.split(':')[0]}: Failed. Error: {e}", "error")
        return False


# --- UI Elements ---
st.title("Lead Recovery Pipeline Dashboard")
st.caption(f"Using lead-recovery v{lr_version}")

recipes = list_recipes()
if not recipes:
    st.error(
        "No recipes found in the 'recipes/' directory. Please create a recipe first."
    )
    st.stop()

selected_recipe_name = st.selectbox("1. Select Recovery Recipe", recipes, index=0)

# Optional date filter
since_date: Optional[date] = st.date_input(
    "2. Fetch leads created since (Optional)", value=None, help="Leave blank to fetch all leads defined by the recipe's Redshift query."
)

run_button = st.button("🚀 Run Pipeline", type="primary", use_container_width=True)

st.divider()

# --- Placeholder for results ---
results_placeholder = st.empty()


# --- Pipeline Logic ---
if run_button and selected_recipe_name:
    results_placeholder.empty()  # Clear previous results
    status_lines.clear() # Clear status from previous runs
    status_placeholder.empty() # Clear the placeholder visually

    try:
        log_status("Pipeline started...")

        # 1. Load Recipe
        log_status("Loading recipe configuration...")
        recipe: Recipe = load_recipe(selected_recipe_name)
        output_dir = (settings.OUTPUT_DIR / selected_recipe_name).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        log_status(
            f"Loaded recipe: **{recipe.dashboard_title or recipe.name}**. Output Dir: `{output_dir}`"
        )

        # Display recipe details
        with st.expander("Recipe Details"):
            st.write(f"**Redshift SQL:** `{recipe.redshift_sql_path.name}`")
            if recipe.bigquery_sql_path:
                st.write(f"**BigQuery SQL:** `{recipe.bigquery_sql_path.name}`")
            else:
                st.write("**BigQuery SQL:** *(Not used in this recipe)*")
            st.write(f"**Prompt Template:** `{recipe.prompt_path.name}`")
            if recipe.expected_yaml_keys:
                 st.write(f"**Expected Summary Keys:** `{recipe.expected_yaml_keys}`")
            else:
                 st.write("**Expected Summary Keys:** *(Validation skipped)*")

        # Convert st.date_input (date) to datetime expected by fetch_leads
        since_datetime: Optional[datetime] = None
        if since_date:
            since_datetime = datetime(
                since_date.year, since_date.month, since_date.day
            )
            log_status(f"Filtering leads created since: {since_date.strftime('%Y-%m-%d')}")

        # --- Execute Pipeline Steps ---
        all_successful = True
        leads_path = output_dir / "leads.csv"
        convos_path = output_dir / "conversations.csv"
        # Define dynamic filename components
        today_str = datetime.now().strftime('%Y%m%d')
        base_filename = f"{selected_recipe_name}_analysis_{today_str}"
        analysis_path = output_dir / f"{base_filename}.csv" # Use dynamic name
        analysis_html_path = output_dir / f"{base_filename}.html" # Use dynamic name

        # Step 1: Fetch Leads (Redshift)
        original_rs_sql_path = settings.RS_SQL_PATH # Store original
        try:
            settings.RS_SQL_PATH = recipe.redshift_sql_path # Override
            if not run_pipeline_step(
                fetch_leads,
                "STEP 1: Fetching leads from Redshift",
                since=since_datetime,
                output_dir=output_dir,
            ):
                all_successful = False
            elif leads_path.exists():
                log_status(f"STEP 1: Success. Leads saved to `{leads_path.name}`.", "success")
            else:
                log_status("STEP 1: Completed, but leads.csv not found.", "warning")
        finally:
             settings.RS_SQL_PATH = original_rs_sql_path # Restore

        # Step 2: Fetch Conversations (BigQuery) - Only if SQL exists and Step 1 succeeded
        original_bq_sql_path = settings.BQ_SQL_PATH # Store original
        try:
            if all_successful and recipe.bigquery_sql_path and recipe.bigquery_sql_path.exists():
                settings.BQ_SQL_PATH = recipe.bigquery_sql_path # Override
                if not run_pipeline_step(
                    fetch_convos,
                    "STEP 2: Fetching conversations from BigQuery",
                    output_dir=output_dir,
                ):
                    all_successful = False
                elif convos_path.exists():
                    log_status(f"STEP 2: Success. Convos saved to `{convos_path.name}`.", "success")
                else:
                    log_status("STEP 2: Completed, but conversations.csv not found.", "warning")

            elif all_successful:
                log_status("STEP 2: Skipped - No BigQuery SQL file for this recipe.")
                # Ensure empty convos file exists for summarize step
                if not convos_path.exists():
                    pd.DataFrame().to_csv(convos_path, index=False)
                    log_status("Created empty conversations.csv as BQ step was skipped.")
            elif not all_successful:
                log_status("STEP 2: Skipped due to previous errors.", "warning")
        finally:
             settings.BQ_SQL_PATH = original_bq_sql_path # Restore


        # Step 3: Summarize Conversations (OpenAI) - If Step 1&2 succeeded
        if all_successful:
            if not run_pipeline_step(
                summarize,
                "STEP 3: Summarizing conversations using OpenAI",
                output_dir=output_dir,
                prompt_template_path=recipe.prompt_path,
                expected_yaml_keys_internal=recipe.expected_yaml_keys,
                recipe_name=selected_recipe_name # Pass recipe name
            ):
                all_successful = False
            elif analysis_path.exists():
                log_status(f"STEP 3: Success. Analysis saved to `{analysis_path.name}`.", "success")
            else:
                log_status("STEP 3: Completed, but analysis.csv not found.", "error")
                all_successful = False
        else:
            log_status("STEP 3: Skipped due to previous errors.", "warning")

        # Step 4: Generate Report (HTML) - If Step 3 succeeded and analysis exists
        if all_successful and analysis_path.exists():
            if not run_pipeline_step(
                report,
                "STEP 4: Generating HTML report",
                output_dir=output_dir,
                recipe_name=selected_recipe_name # Pass recipe name
            ):
                 # Don't mark pipeline as failed if only HTML generation fails
                 log_status("STEP 4: Failed to generate HTML report.", "warning")
            elif analysis_html_path.exists():
                log_status(f"STEP 4: Success. HTML report saved to `{analysis_html_path.name}`.", "success")
            else:
                st.warning(f"HTML report file (`{analysis_html_path.name}`) not found.") # Use dynamic name in warning


        # --- Display Final Status & Results ---
        st.divider()

        if all_successful and analysis_path.exists():
            log_status("Pipeline completed successfully!", "success")

            with results_placeholder.container():
                st.subheader("Results")
                try:
                    df = pd.read_csv(analysis_path)
                    # Display basic info and preview
                    st.write(f"Generated **{len(df)}** results.")
                    st.dataframe(df.head(10)) # Show preview

                    # Provide download link for CSV
                    with open(analysis_path, "rb") as fp:
                        st.download_button(
                            label="⬇️ Download Full Analysis (CSV)",
                            data=fp,
                            file_name=analysis_path.name, # Use dynamic filename from path object
                            mime="text/csv",
                            use_container_width=True,
                        )

                    # Display HTML report if available
                    if analysis_html_path.exists():
                        with open(analysis_html_path, 'r', encoding='utf-8') as f:
                            html_content = f.read()
                        st.subheader("HTML Report Preview")
                        # Add some basic styling to limit width, similar to GitHub markdown
                        st.components.v1.html(
                            f'<div style="max-width: 100%; overflow-x: auto;">{html_content}</div>',
                            height=600,
                            scrolling=True
                        )
                    else:
                        st.warning(f"HTML report file (`{analysis_html_path.name}`) not found.") # Use dynamic name in warning

                except Exception as e:
                    logger.error(f"Error displaying results: {e}", exc_info=True)
                    st.error(f"Could not display results. Error: {e}")

        else:
            log_status("Pipeline execution finished with errors.", "error")
            results_placeholder.error(
                "❌ Pipeline execution failed. Please check the status messages above for details."
            )

    except Exception as e:
        logger.error(
            f"An unexpected error occurred during pipeline execution: {e}", exc_info=True
        )
        log_status(f"Pipeline failed with an unexpected error: {e}", "error")
        results_placeholder.error(f"An unexpected error stopped the pipeline: {e}") 