#!/usr/bin/env python3
"""
Fetch leads for the formalizacion recipe from Google Sheets.

This script connects to a specific Google Sheet, reads the lead data from the
'Autoequity' worksheet, applies necessary cleaning and filtering (phone
standardization, date filtering), and saves the result in the CSV format
expected by the Lead Recovery framework.
"""
import os
import re
from datetime import datetime, timedelta

import gspread
import pandas as pd
from dateutil.parser import parse
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe


def standardize_phone(phone_str: str) -> str:
    """Extract the last 10 digits from a phone number string."""
    if not isinstance(phone_str, str):
        return ""
    digits = re.sub(r"\D", "", phone_str)
    return digits[-10:] if len(digits) >= 10 else ""


def main():
    """Main function to fetch, process, and save lead data."""
    print("🚀 Fetching leads from Google Sheets...")

    # --- Configuration ---
    sheet_id = "1nAU3lsPo98dTqaGOChhJM4WQKhyeItaqRGb5TvEFaXg"
    input_worksheet_name = "Autoequity"
    days_back = 30
    creds_path = os.path.expanduser("~/Desktop/Kavak Capital Service Account.json")
    output_csv_path = os.path.join(os.path.dirname(__file__), "leads.csv")

    # --- Connect and Fetch ---
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(creds_path, scopes=scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(input_worksheet_name)
        print(f"   -> Successfully opened worksheet: '{input_worksheet_name}'")
        df = get_as_dataframe(worksheet, evaluate_formulas=True, header=1)
        # Drop rows where all data is missing, often an issue with sheet formatting
        df.dropna(how="all", inplace=True)
        # Rename columns to remove weird characters from gspread-dataframe
        df.columns = [col.strip() for col in df.columns]
        print(f"   -> Found {len(df)} total rows in the sheet.")
    except Exception as e:
        print(f"❌ Error connecting to Google Sheets: {e}")
        return

    # --- Data Processing ---
    # Use 'Fecha Instalación GPS' for date filtering and 'Número de teléfono' for phone
    date_col = "Fecha Instalación GPS"
    phone_col = "Número de teléfono"

    if date_col not in df.columns or phone_col not in df.columns:
        print(f"❌ Required columns not found. Needed: '{date_col}', '{phone_col}'")
        return

    # Date filtering
    df["parsed_date"] = df[date_col].apply(
        lambda x: parse(x, dayfirst=False) if isinstance(x, str) and x else pd.NaT
    )
    df.dropna(subset=["parsed_date"], inplace=True)
    cutoff_date = datetime.now() - timedelta(days=days_back)
    df = df[df["parsed_date"] >= cutoff_date]
    print(f"   -> After date filtering (last {days_back} days): {len(df)} rows remain.")

    # Phone standardization
    df["cleaned_phone_number"] = df[phone_col].apply(standardize_phone)
    df = df[df["cleaned_phone_number"] != ""]
    print(f"   -> After phone number cleaning: {len(df)} rows remain.")

    # --- Create Final DataFrame ---
    # Map sheet columns to the format expected by the recipe
    result_df = pd.DataFrame(
        {
            "agente": df["Agente"].values if "Agente" in df.columns else "",
            "asset_id": df["Asset ID"].values if "Asset ID" in df.columns else "",
            "nombre": df["Nombre"].values if "Nombre" in df.columns else "",
            "correo": df["Correo"].values if "Correo" in df.columns else "",
            "cleaned_phone": df["cleaned_phone_number"].values,
            "lead_created_at": df["parsed_date"].dt.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

    # --- Save to CSV ---
    result_df.to_csv(output_csv_path, index=False)
    print(f"\n✅ Successfully saved {len(result_df)} leads to {output_csv_path}")
    if not result_df.empty:
        print(
            f"   -> Sample phone numbers: {result_df['cleaned_phone'].head().tolist()}"
        )


if __name__ == "__main__":
    main()
