"""gsheets.py
Google Sheets integration for the lead recovery pipeline.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials

from .config import settings
from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)

def upload_to_google_sheets(csv_path: Path, sheet_id: str, worksheet_name: str, credentials_path: str = None):
    """Uploads the content of a CSV or JSON file to a specified Google Sheet worksheet.
    
    Args:
        csv_path: Path to the CSV or JSON file to upload
        sheet_id: Google Sheet ID
        worksheet_name: Name of the worksheet to upload to
        credentials_path: Path to the Google service account credentials JSON file.
                         If None, will try to use settings.GOOGLE_CREDENTIALS_PATH
    """
    file_path = Path(csv_path)
    logger.info(f"Attempting to upload {file_path.name} to Google Sheet ID {sheet_id}, worksheet '{worksheet_name}'")
    
    # Use credentials_path if provided, otherwise use settings
    if credentials_path is None:
        credentials_path = settings.GOOGLE_CREDENTIALS_PATH
        if credentials_path is None:
            raise ConfigurationError("No Google credentials path provided. Set GOOGLE_CREDENTIALS_PATH in .env or pass credentials_path.")
    
    upload_start_time = datetime.now(timezone.utc).astimezone()  # Get current time
    upload_timestamp_str = upload_start_time.strftime('%Y-%m-%d %H:%M:%S %Z')
    
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        logger.info(f"Loading credentials from: {credentials_path}")
        creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        gc = gspread.authorize(creds)

        spreadsheet = gc.open_by_key(sheet_id)

        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
            logger.info(f"Found existing worksheet '{worksheet_name}'")
        except gspread.WorksheetNotFound:
            logger.warning(f"Worksheet '{worksheet_name}' not found. Creating it.")
            # Consider adding rows/cols based on expected data size if needed
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="100", cols="20") 

        # Determine file type from extension and load appropriately
        file_extension = file_path.suffix.lower()
        
        if file_extension == '.json':
            import json
            logger.info(f"Loading JSON data from {file_path}")
            with open(file_path, 'r', encoding='utf-8') as json_file:
                data = json.load(json_file)
                # Convert JSON to DataFrame (assuming JSON is in records format)
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                else:
                    # If it's a single object, wrap it in a list
                    df = pd.DataFrame([data])
        else:
            # Default is CSV
            logger.info(f"Loading CSV data from {file_path}")
            df = pd.read_csv(file_path)
            
        # Replace NaN/NaT with empty strings for Sheets compatibility
        df = df.fillna('').astype(str)

        # Clear the worksheet and upload new data
        worksheet.clear()
        # Write timestamp to A1
        worksheet.update('A1', f"Last updated at: {upload_timestamp_str}")
        # Write DataFrame starting from A2
        set_with_dataframe(worksheet, df, row=2, col=1, include_index=False, include_column_header=True, resize=True)
        logger.info(f"Successfully uploaded data to worksheet '{worksheet_name}'")
        
        return True

    except FileNotFoundError:
        logger.error(f"File not found at: {file_path}")
        raise
    except gspread.exceptions.APIError as e:
        logger.error(f"Google Sheets API Error: {e}")
        if "PERMISSION_DENIED" in str(e):
             logger.error("Ensure the service account email has edit access to the Google Sheet.")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during Google Sheets upload: {e}", exc_info=True)
        # Re-raise with original exception context preserved
        raise Exception(f"Google Sheets upload failed: {e}") from e 