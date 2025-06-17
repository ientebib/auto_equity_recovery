#!/usr/bin/env python3
"""
Clean Formalizacion Recipe Runner

This script provides the CLEAN solution for the formalizacion recipe.
It eliminates 13+ unwanted columns and keeps only the 12 essential columns:

Real Data (6 columns):
- agente, asset_id, nombre, correo, cleaned_phone, lead_created_at

Analysis Results (6 columns):
- resumen_general, documentos_enviados_analisis, enviado_a_validacion
- calidad_atencion_agente, objecion_principal_cliente, gps_instalacion_agendada

This solves the problem mentioned in the execution guide where the framework
adds 15+ unwanted columns that can't be removed via configuration.
"""

import asyncio
import importlib
import os
import sys
from pathlib import Path

import pandas as pd

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

run_standard_recipe = importlib.import_module("recipes.formalizacion.run_recipe").main


def generate_smart_summary(row):
    """Generate crisp, actionable summaries based on analysis results."""
    # Check if we have conversation data
    if (
        pd.isna(row.get("documentos_enviados_analisis"))
        or row.get("documentos_enviados_analisis") == ""
    ):
        return "Sin conversación registrada"

    # Extract analysis fields
    validation = str(row.get("enviado_a_validacion", "No claro")).lower()
    documents = str(row.get("documentos_enviados_analisis", "")).lower()
    quality = str(row.get("calidad_atencion_agente", "")).lower()
    gps = str(row.get("gps_instalacion_agendada", "")).lower()

    # Smart summary logic
    if "gps completado" in gps or "completado" in gps:
        return "Proceso fluido: documentos validados y GPS completado"
    elif "sí" in validation:
        if "agendado" in gps:
            return "Documentos en validación, GPS agendado"
        elif "pendiente" in gps:
            return "Documentos en validación, GPS pendiente"
        else:
            return "Documentos en validación"
    elif "faltan" in documents:
        if "mala" in quality or "regular" in quality:
            return "Cliente atascado: documentos sin validar, atención deficiente"
        else:
            return "Cliente necesita enviar documentos faltantes"
    elif "documentos completos" in documents:
        if "agendado" in gps:
            return "Documentos completos, GPS agendado"
        else:
            return "Documentos completos, GPS pendiente"
    else:
        return "Proceso en curso"


def clean_output_data(df):
    """Clean and filter the output to only essential 12 columns."""
    print("🧹 Cleaning output data...")

    # Define the 12 essential columns
    essential_columns = [
        # Real data (6 columns)
        "agente",
        "asset_id",
        "nombre",
        "correo",
        "cleaned_phone",
        "lead_created_at",
        # Analysis results (6 columns)
        "resumen_general",
        "documentos_enviados_analisis",
        "enviado_a_validacion",
        "calidad_atencion_agente",
        "objecion_principal_cliente",
        "gps_instalacion_agendada",
    ]

    # Check if resumen_general exists, if not add it
    if "resumen_general" not in df.columns:
        print("   -> Generating smart summaries...")
        df["resumen_general"] = df.apply(generate_smart_summary, axis=1)

    # Filter to only essential columns
    missing_columns = [col for col in essential_columns if col not in df.columns]

    if missing_columns:
        print(f"   -> Warning: Missing columns: {missing_columns}")
        # Add missing columns with empty values
        for col in missing_columns:
            df[col] = ""

    # Select only the essential columns
    clean_df = df[essential_columns].copy()

    # Clean NaN values
    clean_df = clean_df.fillna("")
    clean_df = clean_df.astype(str)
    clean_df = clean_df.replace(["nan", "None", "NaN"], "")

    print(f"   -> Reduced from {len(df.columns)} to {len(essential_columns)} columns")
    print(
        f"   -> Eliminated {len(df.columns) - len(essential_columns)} unwanted columns"
    )

    return clean_df


def upload_to_sheets(
    df,
    sheet_id="1nAU3lsPo98dTqaGOChhJM4WQKhyeItaqRGb5TvEFaXg",
    worksheet_name="Bot Live",
):
    """Upload clean data to Google Sheets."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        from gspread_dataframe import set_with_dataframe

        print(f"📤 Uploading to Google Sheets '{worksheet_name}'...")

        # Credentials
        creds_path = os.path.expanduser("~/Desktop/Kavak Capital Service Account.json")
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(creds_path, scopes=scope)
        client = gspread.authorize(creds)

        # Open worksheet
        spreadsheet = client.open_by_key(sheet_id)
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except Exception:
            worksheet = spreadsheet.add_worksheet(
                title=worksheet_name, rows=1000, cols=20
            )

        # Upload data
        worksheet.clear()
        set_with_dataframe(worksheet, df, include_index=False)

        print(f"   -> Successfully uploaded {len(df)} rows to '{worksheet_name}'")
        return True

    except Exception as e:
        print(f"❌ Google Sheets upload failed: {e}")
        return False


async def main():
    """Main execution function for the clean formalizacion recipe."""
    print("🎯 ** Starting CLEAN Formalizacion Recipe **")
    print("=" * 50)
    print("✅ This solution eliminates 13+ unwanted columns")
    print("✅ Keeps only 12 essential columns")
    print("✅ Generates smart analysis summaries")
    print("✅ Auto-uploads to Google Sheets")
    print("=" * 50)

    # Step 1: Run the standard recipe to get raw output
    print("🔄 Step 1: Running standard recipe to generate raw data...")
    await run_standard_recipe()

    # Step 2: Load and clean the output
    print("\n🧹 Step 2: Loading and cleaning output data...")
    output_dir = Path(project_root) / "output_run" / "formalizacion"
    latest_file = output_dir / "latest.csv"

    if not latest_file.exists():
        print(f"❌ Output file not found: {latest_file}")
        return

    # Load the messy output
    df = pd.read_csv(latest_file)
    print(f"   -> Loaded {len(df)} rows with {len(df.columns)} columns")
    print(f"   -> Original columns: {len(df.columns)} (MESSY)")

    # Clean the data
    clean_df = clean_output_data(df)
    print(f"   -> Clean columns: {len(clean_df.columns)} (CLEAN!)")

    # Step 3: Save clean output
    print("\n💾 Step 3: Saving clean output...")
    clean_filename = output_dir / "latest_clean.csv"
    timestamped_filename = (
        output_dir
        / f"clean_formalizacion_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    clean_df.to_csv(clean_filename, index=False)
    clean_df.to_csv(timestamped_filename, index=False)

    print(f"   -> Saved clean output: {clean_filename}")
    print(f"   -> Saved timestamped backup: {timestamped_filename}")

    # Step 4: Upload to Google Sheets
    print("\n📤 Step 4: Uploading to Google Sheets...")
    upload_success = upload_to_sheets(clean_df)

    # Step 5: Summary
    print("\n🎉 ** CLEAN FORMALIZACION RECIPE COMPLETED! **")
    print("=" * 50)
    print(f"✅ Processed: {len(clean_df)} leads")
    print(f"✅ Clean columns: {len(clean_df.columns)} (instead of {len(df.columns)})")
    print(f"✅ Eliminated: {len(df.columns) - len(clean_df.columns)} unwanted columns")
    print(f"✅ Local file: {clean_filename}")
    print(f"✅ Google Sheets: {'✓ Uploaded' if upload_success else '✗ Failed'}")
    print("=" * 50)
    print("📊 Use the clean output for analysis and reporting!")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
