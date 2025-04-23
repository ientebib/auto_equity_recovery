"""
Utility functions for the Lead Recovery Streamlit Dashboard.

Includes functions for loading data, defining color maps, calculating KPIs,
and preparing data for download.
"""

import streamlit as st
import pandas as pd
import os
from io import BytesIO
import logging
from pathlib import Path

# --- Constants ---
# Default path relative to the project root where streamlit run is executed.
DEFAULT_CSV_PATH = "output_run/analysis.csv"

# Expected columns and their types
EXPECTED_COLUMNS = {
    "lead_id": "int64",
    "created_at": "datetime64[ns]",
    "name": "object", # String
    "last_name": "object", # String
    "cleaned_phone": "object", # String
    "result": "object", # String
    "stall_reason": "object", # String (enum)
    "key_interaction": "object", # String
    "suggestion": "object", # String
    "summary": "object" # String
}

# Color mapping for stall reasons
STALL_REASON_COLORS = {
    'PARTIAL_PROGRESS': '#FFD60A', # amber
    'WANTS_INFO': '#2ECC71', # green
    'IGNORED': '#808080', # grey
    'NO_OUTBOUND': '#1E90FF', # blue
    'NO_INTEREST': '#E74C3C', # red
    'NOT_ELIGIBLE': '#8E44AD', # purple
    'OTHER': '#95A5A6' # light grey
}

# --- Logging Setup ---
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Data Loading ---
# Remove the cache decorator as we load from an uploaded file object now
# @st.cache_data(ttl=60) # No longer applicable
def load_data(upload_source: "st.runtime.uploaded_file_manager.UploadedFile | str | os.PathLike | None") -> pd.DataFrame | None:
    """Load analysis CSV from either a Streamlit *UploadedFile* **or** a file path.

    The original dashboard expected a file uploaded via *st.file_uploader*.
    To support the new *recipe selector* workflow we also accept a string / Path
    pointing to an *analysis.csv* produced by the pipeline.

    Args:
        upload_source: Either the uploaded file object **or** a local path
            (``str`` / ``Path``). ``None`` returns an empty DataFrame placeholder.

    Returns
    -------
    pd.DataFrame | None
        Loaded DataFrame with standard preprocessing, an **empty** frame if
        nothing provided yet, or **None** if a critical loading error occurs.
    """

    # ------------------------------------------------------------------- #
    # Handle *no* input (placeholder stage)
    # ------------------------------------------------------------------- #
    if upload_source is None:
        logger.info("No file uploaded or selected yet – returning empty DataFrame.")
        return pd.DataFrame(columns=list(EXPECTED_COLUMNS.keys()))

    # ------------------------------------------------------------------- #
    # Branch by input‑type
    # ------------------------------------------------------------------- #
    if hasattr(upload_source, "read") and hasattr(upload_source, "name"):
        # Likely a Streamlit UploadedFile
        uploaded_file = upload_source  # type: ignore[assignment]
        file_name = uploaded_file.name
        file_obj = uploaded_file  # pandas can consume directly
        file_size = getattr(uploaded_file, "size", None)
    else:
        # Assume path‑like
        file_path = Path(upload_source)
        if not file_path.exists():
            logger.warning("File path provided does not exist: %s", file_path)
            return pd.DataFrame(columns=list(EXPECTED_COLUMNS.keys()))
        file_name = file_path.name
        file_obj = str(file_path)  # pandas can take str path
        file_size = file_path.stat().st_size

    logger.info("Attempting to load data from %s", file_name)

    try:
        # Check if file is empty (size == 0) when info available
        if file_size == 0:
            logger.warning("File '%s' is empty. Returning empty DataFrame.", file_name)
            if "streamlit" in globals():
                st.warning(f"The file '{file_name}' appears to be empty.")
            return pd.DataFrame(columns=list(EXPECTED_COLUMNS.keys()))

        df = pd.read_csv(file_obj)  # Pass the file object/path directly to pandas
        logger.info(f"Successfully loaded {len(df)} rows from {file_name}")

        # --- Basic Data Cleaning & Preprocessing ---

        # Check for required columns
        missing_cols = [col for col in EXPECTED_COLUMNS if col not in df.columns]
        if missing_cols:
            logger.error(f"Missing required columns in {file_name}: {missing_cols}")
            st.error(f"Uploaded CSV file '{file_name}' is missing required columns: {', '.join(missing_cols)}", icon="🚨")
            # Return empty df but signal issue upstream
            return pd.DataFrame(columns=list(EXPECTED_COLUMNS.keys()))

        # Convert 'created_at' to datetime
        try:
            df['created_at'] = pd.to_datetime(df['created_at'])
        except Exception as e:
            logger.error(f"Error converting 'created_at' to datetime in {file_name}: {e}")
            st.error(f"Failed to parse the 'created_at' column in '{file_name}'. Check data format.", icon="🚨")
            # Decide if this is critical. Let's return empty for now.
            return pd.DataFrame(columns=list(EXPECTED_COLUMNS.keys()))

        # Add a 'created_date' column for easier date-based filtering
        df['created_date'] = df['created_at'].dt.date

        # Combine name and last_name if they exist
        if 'name' in df.columns and 'last_name' in df.columns:
            df['full_name'] = df['name'].fillna('') + ' ' + df['last_name'].fillna('')
            df['full_name'] = df['full_name'].str.strip()
        elif 'name' in df.columns:
             df['full_name'] = df['name'].fillna('')
        else:
             df['full_name'] = 'N/A' # Placeholder if no name columns


        # Fill NA in key string columns used for display/filtering
        for col in ['result', 'stall_reason', 'key_interaction', 'suggestion', 'summary', 'cleaned_phone']:
            if col in df.columns:
                 df[col] = df[col].fillna('N/A')
            else:
                # If even these are missing, add them with N/A
                df[col] = 'N/A'

        # Optional: Convert other columns to expected types (more robust error handling needed for production)
        for col, dtype in EXPECTED_COLUMNS.items():
            if col in df.columns and col != 'created_at': # Skip already handled datetime
                try:
                    if pd.api.types.is_datetime64_any_dtype(dtype):
                         # Already handled
                         pass
                    elif dtype == 'int64':
                        # Handle potential float representations if coming from CSV
                        df[col] = df[col].fillna(0).astype(float).astype(dtype)
                    else:
                        df[col] = df[col].astype(dtype)
                except Exception as e:
                    logger.warning(f"Could not convert column '{col}' to type '{dtype}': {e}")
                    # Keep original type if conversion fails

        logger.info("Data preprocessing complete.")
        return df

    except pd.errors.EmptyDataError:
        logger.warning(f"Uploaded CSV file '{file_name}' is empty or contains only headers.")
        st.warning(f"The uploaded file '{file_name}' contains no data rows.")
        return pd.DataFrame(columns=list(EXPECTED_COLUMNS.keys()))
    except Exception as e:
        logger.critical(f"An unexpected error occurred during data loading from {file_name}: {e}", exc_info=True)
        st.error(f"A critical error occurred while loading the data from '{file_name}': {e}", icon="🔥")
        return None # Signal critical failure


# --- KPI Calculation ---
def calculate_kpis(df: pd.DataFrame) -> dict:
    """Calculates Key Performance Indicators based on the filtered DataFrame.

    Args:
        df (pd.DataFrame): The filtered DataFrame.

    Returns:
        dict: A dictionary containing KPI values.
    """
    if df is None or df.empty:
        return {
            "Leads loaded": 0,
            "Contacted": "—", # Placeholder
            "Profile completed": "—", # Placeholder
            "Stall Reason Counts": pd.Series(dtype='int')
        }

    kpis = {
        "Leads loaded": len(df),
        "Contacted": "—",  # Placeholder - No data available yet
        "Profile completed": "—",  # Placeholder - No data available yet
    }

    # Calculate stall reason distribution
    if 'stall_reason' in df.columns:
        kpis["Stall Reason Counts"] = df['stall_reason'].value_counts()
    else:
         kpis["Stall Reason Counts"] = pd.Series(dtype='int') # Empty series if column missing

    return kpis


# --- Data Export ---
def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Converts a DataFrame to CSV formatted bytes for download.

    Args:
        df (pd.DataFrame): The DataFrame to convert.

    Returns:
        bytes: CSV data encoded in UTF-8.
    """
    output = BytesIO()
    df.to_csv(output, index=False, encoding='utf-8')
    processed_data = output.getvalue()
    return processed_data

# --- Placeholder Functions for Future Features ---

# TODO(v0.2): Implement API call logic
def record_call_status(lead_id: int, status: str):
    """Placeholder: Posts status update to a hypothetical API endpoint."""
    logger.info(f"[Placeholder] Recording status '{status}' for lead_id: {lead_id}")
    st.toast(f"Status update for {lead_id} not implemented yet.", icon="🚧")
    # Example API call structure (replace with actual implementation):
    # try:
    #     response = requests.post(f"http://your-api/api/record_call", json={'lead_id': lead_id, 'status': status})
    #     response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
    #     st.success(f"Successfully updated status for lead {lead_id}")
    # except requests.exceptions.RequestException as e:
    #     st.error(f"Failed to update status for lead {lead_id}: {e}")
    #     logger.error(f"API call failed for lead {lead_id}: {e}")

# TODO(v0.4): Integrate Twilio click-to-call
def add_twilio_button(phone_number: str):
    """Placeholder: Adds a Twilio click-to-call button."""
    logger.info(f"[Placeholder] Twilio button for {phone_number}")
    # Implementation would involve generating a button that triggers
    # a call via Twilio API, likely involving backend interaction.

# TODO(v0.3): Handle authentication actions
def handle_auth_action():
    """Placeholder: Handles actions related to user authentication."""
    logger.info("[Placeholder] Authentication action")
    # Implementation depends on the chosen auth method (Streamlit experimental, Okta, etc.) 