"""
Streamlit Dashboard for Lead Recovery Analysis v0.1

This application displays data from `analysis.csv`, allowing users to filter,
view KPIs, explore leads in an interactive table, and export filtered data.
"""

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, date, timedelta
import os
from pathlib import Path

# Import utility functions from utils.py
try:
    import utils
except ImportError:
    st.error("Failed to import 'utils.py'. Ensure it's in the same directory.")
    st.stop() # Stop execution if utils cannot be imported

# Import recipe discovery helper from backend package (lazy import to avoid hard dep when dashboard alone)
try:
    from lead_recovery.recipe_loader import list_recipes
except Exception:
    # If the backend package isn't on PYTHONPATH (e.g. standalone dashboard deploy)
    def list_recipes():
        return []

# --- Page Configuration ---
st.set_page_config(
    page_title="Lead Recovery Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Constants ---
# REMOVED: ANALYSIS_CSV_PATH = utils.DEFAULT_CSV_PATH

# --- Sidebar : Recipe selection OR manual upload ------------------------ #

st.sidebar.title("Lead Recovery Upload & Filters")

# Allow users to pick from discovered recipe runs (analysis files present)
available_recipes = list_recipes()

selected_recipe: str | None = None
analysis_file: str | None = None

if available_recipes:
    st.sidebar.subheader("Select Recipe Run")
    selected_recipe = st.sidebar.selectbox(
        "Recipe",
        options=["—"] + available_recipes,
        help="Choose a recipe folder inside 'output_run/<recipe>' to load its analysis.csv",
    )
    if selected_recipe != "—":
        candidate_path = Path("output_run") / selected_recipe / "analysis.csv"
        if candidate_path.exists():
            analysis_file = str(candidate_path)
            st.sidebar.caption(f"Loading analysis from: {candidate_path}")
        else:
            st.sidebar.warning(f"analysis.csv not found for recipe '{selected_recipe}'.")

# Fallback: manual file upload
st.sidebar.subheader("Or Upload Analysis File")
uploaded_file = st.sidebar.file_uploader(
    "Choose an analysis.csv file",
    type='csv',
    accept_multiple_files=False
)

# Decide which data source to use
if analysis_file:
    raw_df = utils.load_data(analysis_file)
else:
    raw_df = utils.load_data(uploaded_file)

# Check if data loading failed critically (e.g., unparseable file)
if raw_df is None:
    st.error("Critical error loading or processing the uploaded file. Dashboard cannot proceed.")
    st.stop()

# --- Main Content Area ---
st.title("📊 Lead Recovery Dashboard")

# Only display the rest of the dashboard if a valid file has been uploaded and parsed
if (analysis_file or uploaded_file is not None) and not raw_df.empty:
    source_name = analysis_file or getattr(uploaded_file, "name", "uploaded file")
    st.success(f"Successfully loaded '{source_name}' with {len(raw_df)} rows.")
    st.markdown("Analyze and manage Auto-Equity leads based on AI summaries.")

    # --- Sidebar Filters (Only show if data is loaded) ---
    st.sidebar.header("Filters")

    # Date Range Filter
    # Ensure 'created_date' exists before accessing
    if 'created_date' not in raw_df.columns:
        st.error("The required 'created_at' (or derived 'created_date') column is missing or failed processing.")
        st.stop()

    min_date = raw_df['created_date'].min() # Already checked for empty
    max_date = raw_df['created_date'].max()

    # Default to the full range in the uploaded file
    default_start_date = min_date
    default_end_date = max_date

    selected_date_range = st.sidebar.date_input(
        "Select Date Range (Created At)",
        value=(default_start_date, default_end_date),
        min_value=min_date,
        max_value=max_date,
        key=f"date_range_{uploaded_file.file_id}" # Add key to reset on new upload
    )

    # Handle date range selection
    start_date = selected_date_range[0]
    end_date = selected_date_range[0]
    if len(selected_date_range) == 2:
        end_date = selected_date_range[1]

    if start_date > end_date:
        st.sidebar.error("End date must be after start date.")
        start_date = default_start_date
        end_date = default_end_date

    # Stall Reason Filter
    # Ensure 'stall_reason' exists
    if 'stall_reason' not in raw_df.columns:
        st.error("The required 'stall_reason' column is missing.")
        st.stop()

    all_stall_reasons = sorted(raw_df['stall_reason'].unique().tolist())
    selected_stall_reasons = st.sidebar.multiselect(
        "Stall Reason",
        options=all_stall_reasons,
        default=all_stall_reasons, # Default to all selected
        key=f"stall_select_{uploaded_file.file_id}" # Add key to reset
    )

    # --- Filter Data ---
    # Apply date filter
    date_mask = (raw_df['created_date'] >= start_date) & (raw_df['created_date'] <= end_date)
    filtered_df = raw_df[date_mask]

    # Apply stall reason filter
    if selected_stall_reasons:
        filtered_df = filtered_df[filtered_df['stall_reason'].isin(selected_stall_reasons)]
    else:
        # Show no results if no stall reasons are selected
        filtered_df = filtered_df.head(0)

    # --- KPI Display ---
    st.header("Key Performance Indicators")
    kpis = utils.calculate_kpis(filtered_df)

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Leads Loaded (Filtered)", kpis["Leads loaded"])
    kpi_cols[1].metric("Contacted", kpis["Contacted"])
    kpi_cols[2].metric("Profile Completed", kpis["Profile completed"])

    # Stall Reason Bar Chart
    with kpi_cols[3]:
        st.markdown("**Stall Reason Distribution**")
        if not kpis["Stall Reason Counts"].empty:
            chart_data = kpis["Stall Reason Counts"].reset_index()
            chart_data.columns = ['stall_reason', 'count']

            color_scale = alt.Scale(
                domain=list(utils.STALL_REASON_COLORS.keys()),
                range=list(utils.STALL_REASON_COLORS.values())
            )

            chart = alt.Chart(chart_data).mark_bar().encode(
                x=alt.X('count', title='Number of Leads'),
                y=alt.Y('stall_reason', title='Stall Reason', sort='-x'),
                color=alt.Color('stall_reason', scale=color_scale, legend=None),
                tooltip=['stall_reason', 'count']
            ).properties(
                 height=150
            )
            st.altair_chart(chart, use_container_width=True)
        elif not filtered_df.empty:
            st.caption("No stall reasons found in filtered data.")
        else:
             st.caption("No leads match current filters.")

    # --- Interactive Table ---
    st.header("Lead Details")

    columns_to_display = [
        'lead_id', 'created_at', 'full_name', 'cleaned_phone',
        'result', 'stall_reason'
    ]
    displayable_columns = [col for col in columns_to_display if col in filtered_df.columns]

    if not displayable_columns:
         st.warning("Filtered data is missing key columns needed for the table display.")
    else:
        st.info("Click on a row to see the full summary and suggestions.")

        if 'selected_row_index' not in st.session_state:
            st.session_state.selected_row_index = None

        column_config = {
            "lead_id": st.column_config.NumberColumn("Lead ID", help="Unique identifier for the lead"),
            "created_at": st.column_config.DatetimeColumn("Created At", format="YYYY-MM-DD HH:mm"),
            "full_name": st.column_config.TextColumn("Name"),
            "cleaned_phone": st.column_config.TextColumn("Phone"),
            "result": st.column_config.TextColumn("AI Result Snippet"),
            "stall_reason": st.column_config.TextColumn("Stall Reason")
        }

        df_display = filtered_df[displayable_columns]

        event = st.dataframe(
            df_display,
            key=f"lead_table_{uploaded_file.file_id}", # Use file_id in key to reset on new upload
            on_select="rerun",
            selection_mode="single-row",
            use_container_width=True,
            column_config=column_config,
            hide_index=True,
            height=500
        )

        # --- Row Expansion / Details Display ---
        selected_rows = event.selection.rows
        if selected_rows:
            selected_index = selected_rows[0]
            if selected_index < len(df_display):
                selected_lead_id = df_display.iloc[selected_index]['lead_id']
                lead_details = filtered_df[filtered_df['lead_id'] == selected_lead_id].iloc[0]

                st.session_state.selected_row_index = selected_index

                st.subheader(f"Details for Lead ID: {lead_details['lead_id']}")
                detail_cols = st.columns(2)
                with detail_cols[0]:
                    st.text_input("Name", lead_details.get('full_name', 'N/A'), disabled=True, key=f"name_{selected_lead_id}")
                    st.text_input("Phone", lead_details.get('cleaned_phone', 'N/A'), disabled=True, key=f"phone_{selected_lead_id}")
                    st.text_input("Stall Reason", lead_details.get('stall_reason', 'N/A'), disabled=True, key=f"stall_{selected_lead_id}")

                with detail_cols[1]:
                    created_at_str = lead_details.get('created_at', 'N/A')
                    if pd.notna(created_at_str):
                        created_at_str = created_at_str.strftime('%Y-%m-%d %H:%M:%S')
                    st.text_input("Created At", created_at_str, disabled=True, key=f"created_{selected_lead_id}")
                    # Add more fields if needed

                st.markdown("**AI Summary & Suggestions**")
                st.text_area("Summary", lead_details.get('summary', 'No summary available.'), height=150, disabled=True, key=f"summary_{selected_lead_id}")
                st.text_area("Key Interaction", lead_details.get('key_interaction', 'N/A'), height=100, disabled=True, key=f"interact_{selected_lead_id}")
                st.text_area("Suggestion", lead_details.get('suggestion', 'N/A'), height=100, disabled=True, key=f"suggest_{selected_lead_id}")

                # Placeholder for actions
                st.markdown("**Actions**")
                if st.button("Mark as Contacted (Not Implemented)", key=f"contact_btn_{selected_lead_id}"):
                    utils.record_call_status(lead_details['lead_id'], "Contacted")

            else:
                 st.warning("Could not retrieve details for the selected row. Selection might be out of sync.")
                 st.session_state.selected_row_index = None

        elif st.session_state.get('selected_row_index') is not None:
            st.session_state.selected_row_index = None

    # Add spacer before download button
    st.sidebar.markdown("---")

    # --- Export Button (in Sidebar) ---
    st.sidebar.header("Export")
    if not filtered_df.empty:
        csv_bytes = utils.dataframe_to_csv_bytes(filtered_df)
        # Generate a dynamic filename including the original filename and date range
        export_filename = f"{os.path.splitext(uploaded_file.name)[0]}_filtered_{start_date}_to_{end_date}.csv"

        st.sidebar.download_button(
            label="Download Filtered Data as CSV",
            data=csv_bytes,
            file_name=export_filename,
            mime="text/csv",
            key=f"download_{uploaded_file.file_id}" # Reset button state on new upload
        )
    else:
        st.sidebar.info("No data available to export based on current filters.")

else:
    # Show prompt if no file is uploaded or if the uploaded file is empty/invalid
    if uploaded_file is None:
        st.info("👈 Please upload an analysis.csv file using the sidebar to begin.")
    elif raw_df is not None and raw_df.empty:
        # This case covers empty files or files missing critical columns handled in load_data
        st.warning("The uploaded file is empty or does not contain the expected data structure. Please check the file and try again.")
        # Potentially add more specific feedback based on why raw_df is empty if needed

# --- Footer with TODOs (always visible in sidebar) ---
st.sidebar.markdown("---")
st.sidebar.caption("Development Notes:")
st.sidebar.code("""
# TODO(v0.2): Post status update via API
# TODO(v0.3): Add Authentication
# TODO(v0.4): Integrate Click-to-Call
""", language="python") 