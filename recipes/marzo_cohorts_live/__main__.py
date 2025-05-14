#!/usr/bin/env python
"""
Marzo Cohorts Live Recipe
-------------------------
Analyzes conversations for specific Python flags and LLM insights.
This __main__.py directly orchestrates the steps for this recipe,
including custom Python flag extraction and calling the core summarization logic.
"""

import os
import sys
import logging
import csv
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
import pytz
from typing import Dict, List, Any, Optional, Tuple
import yaml
import json
import asyncio

# Add parent directory to path so we can import the lead_recovery package
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir.parent.parent))

from lead_recovery.db_clients import BigQueryClient
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

from recipes.marzo_cohorts_live.analyzer import get_marzo_live_python_flags
from lead_recovery.analysis import run_summarization_step
from lead_recovery.fs import ensure_dir, update_link
from lead_recovery.config import get_settings, settings as global_settings
from lead_recovery.constants import CLEANED_PHONE_COLUMN_NAME, MESSAGE_COLUMN_NAME

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

def query_bigquery_for_recipe(phone_numbers: List[str], recipe_dir: Path) -> Tuple[Dict[str, List[Dict[str, Any]]], pd.DataFrame]:
    if not phone_numbers:
        logger.warning("No phone numbers provided for BigQuery query")
        return {}, pd.DataFrame()
    
    client = BigQueryClient()
    sql_path = recipe_dir / 'bigquery.sql' 
    if not sql_path.exists():
        logger.error(f"BigQuery SQL file not found at {sql_path}")
        raise FileNotFoundError(f"BigQuery SQL file not found at {sql_path}")

    with open(sql_path, 'r') as f:
        query = f.read()
    
    query_params = [bigquery.ArrayQueryParameter("target_phone_numbers_list", "STRING", phone_numbers)]
    
    try:
        logger.info(f"Querying BigQuery for {len(phone_numbers)} phone numbers using {sql_path}")
        df = client.query(query, params=query_params)
        
        conversations_data_for_df = []
        conversations_map = {}

        for _, row in df.iterrows():
            phone = str(row['cleaned_phone_number'])
            row_dict = row.to_dict()
            conversations_data_for_df.append(row_dict)
            if phone not in conversations_map:
                conversations_map[phone] = []
            conversations_map[phone].append(row_dict)
        
        logger.info(f"Retrieved conversations for {len(conversations_map)} phone numbers.")
        return conversations_map, pd.DataFrame(conversations_data_for_df)

    except GoogleAPIError as e:
        logger.error(f"Error querying BigQuery: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in query_bigquery_for_recipe: {e}", exc_info=True)
        raise

async def amain():
    recipe_name = "marzo_cohorts_live"
    recipe_dir = Path(__file__).resolve().parent 
    project_root = recipe_dir.parent.parent
    
    # Define output paths directly
    recipe_base_output_dir = project_root / "output_run" / recipe_name
    ensure_dir(recipe_base_output_dir)
    
    # Timestamp for this specific run's output subfolder
    # Use timezone-aware UTC now, then format (as in core pipeline)
    run_timestamp_utc = datetime.now(timezone.utc)
    # Convert to local time for folder naming if desired, or keep UTC for consistency
    # For now, using a common format that includes date and time for uniqueness.
    # This format is slightly different from the YYYY-MM-DDTHH-MM used elsewhere, 
    # but should be fine. The key is that `run_summarization_step` might create its own.
    # Let's align with how the core pipeline might name its dated files if possible,
    # or be explicit about the path we expect `run_summarization_step` to write to if we need to read from it.
    
    # For `__main__.py` controlled output:
    current_run_timestamp_str = run_timestamp_utc.astimezone(pytz.timezone('America/Mexico_City')).strftime('%Y-%m-%dT%H-%M-%S')
    timestamped_output_dir = ensure_dir(recipe_base_output_dir / current_run_timestamp_str)
    final_results_path = timestamped_output_dir / f"{recipe_name}_analysis.csv" # Changed from analysis.csv to be more specific

    leads_file_path = recipe_base_output_dir / "leads.csv"
    conversations_file_path = recipe_base_output_dir / "conversations.csv"
    meta_file_path = recipe_dir / "meta.yml"
    prompt_file_path = recipe_dir / "prompt.txt"

    try:
        logger.info(f"Starting recipe: {recipe_name}")
        logger.info(f"Output will be in: {timestamped_output_dir}")

        if not leads_file_path.exists():
            logger.critical(f"CRITICAL: leads.csv not found at {leads_file_path}.")
            sys.exit(1)
        
        leads_df = pd.read_csv(leads_file_path, dtype={'cleaned_phone': str})
        logger.info(f"Loaded {len(leads_df)} rows from {leads_file_path}")
        
        phone_numbers_to_query = leads_df[leads_df['cleaned_phone'].notna() & leads_df['cleaned_phone'].str.match(r'^\d+$')]['cleaned_phone'].unique().tolist()
        
        all_conversations_map, convos_for_saving_df = await asyncio.to_thread(query_bigquery_for_recipe, phone_numbers_to_query, recipe_dir) # Pass recipe_dir
        
        if not convos_for_saving_df.empty:
            convos_for_saving_df.to_csv(conversations_file_path, index=False, quoting=csv.QUOTE_MINIMAL)
            logger.info(f"Saved fetched conversations to {conversations_file_path}")
        else:
            pd.DataFrame(columns=[CLEANED_PHONE_COLUMN_NAME, MESSAGE_COLUMN_NAME, 'msg_from', 'creation_time']).to_csv(conversations_file_path, index=False)
            logger.info(f"No conversations returned from BigQuery. Created empty {conversations_file_path}")

        meta_config = {}
        if meta_file_path.exists():
            with open(meta_file_path, 'r') as f:
                meta_config = yaml.safe_load(f) or {}
        
        behavior_flags = meta_config.get('behavior_flags', {})
        skip_detailed_temporal = behavior_flags.get('skip_detailed_temporal_processing', False)

        app_settings = get_settings()
        
        # Define default values since Settings doesn't have these attributes
        default_max_workers = 4
        default_use_cache = True
        
        # run_summarization_step will read leads.csv and conversations.csv from recipe_base_output_dir
        # and write its output (e.g., marzo_cohorts_live_analysis_YYYYMMDD.csv) into recipe_base_output_dir.
        await run_summarization_step(
            output_dir=recipe_base_output_dir, 
            prompt_template_path=prompt_file_path,
            max_workers=default_max_workers, 
            recipe_name=recipe_name,
            use_cache=default_use_cache, 
            meta_config=meta_config,
            skip_detailed_temporal_calc=skip_detailed_temporal
        )
        
        # The analysis file from run_summarization_step will have a date, not a timestamp.
        # Example: output_run/marzo_cohorts_live/marzo_cohorts_live_analysis_20250509.csv
        today_str = datetime.now(pytz.timezone('America/Mexico_City')).strftime('%Y%m%d')
        core_analysis_file = recipe_base_output_dir / f"{recipe_name}_analysis_{today_str}.csv"

        if not core_analysis_file.exists():
            core_analysis_file_generic = recipe_base_output_dir / "analysis.csv" # Generic fallback
            if core_analysis_file_generic.exists():
                core_analysis_file = core_analysis_file_generic
                logger.info(f"Dated core analysis file not found, using generic: {core_analysis_file}")
            else:
                logger.error(f"Core analysis file from run_summarization_step not found at {core_analysis_file} or {core_analysis_file_generic}")
                raise FileNotFoundError(f"Core analysis output missing.")

        logger.info(f"Reading core analysis results from: {core_analysis_file}")
        results_df = pd.read_csv(core_analysis_file, dtype={'cleaned_phone': str})

        custom_flags_data = []
        for index, row in results_df.iterrows():
            phone = str(row[CLEANED_PHONE_COLUMN_NAME])
            conversation_messages = all_conversations_map.get(phone, [])
            marzo_flags = get_marzo_live_python_flags(conversation_messages)
            custom_flags_data.append({
                CLEANED_PHONE_COLUMN_NAME: phone,
                'handoff_reached': marzo_flags['handoff_reached'],
                'handoff_response': marzo_flags['handoff_response']
            })
        
        if custom_flags_data:
            custom_flags_df = pd.DataFrame(custom_flags_data)
            if not custom_flags_df.empty:
                results_df[CLEANED_PHONE_COLUMN_NAME] = results_df[CLEANED_PHONE_COLUMN_NAME].astype(str)
                custom_flags_df[CLEANED_PHONE_COLUMN_NAME] = custom_flags_df[CLEANED_PHONE_COLUMN_NAME].astype(str)
                results_df = pd.merge(results_df, custom_flags_df, on=CLEANED_PHONE_COLUMN_NAME, how='left')
        else:
            results_df['handoff_reached'] = False
            results_df['handoff_response'] = 'NOT_APPLICABLE'

        output_columns = meta_config.get('output_columns', [])
        if output_columns:
            for col in output_columns:
                if col not in results_df.columns:
                    results_df[col] = None 
            final_cols_ordered = [col for col in output_columns if col in results_df.columns]
            results_df = results_df[final_cols_ordered]
        else:
            logger.warning("No output_columns defined in meta.yml, results_df may not have expected structure.")

        results_df.to_csv(final_results_path, index=False, quoting=csv.QUOTE_MINIMAL)
        logger.info(f"Full analysis with custom flags saved to {final_results_path}")

        latest_csv_symlink = recipe_base_output_dir / "latest.csv"
        update_link(final_results_path, latest_csv_symlink) # Use imported update_link
        logger.info(f"Updated symlink: {latest_csv_symlink} -> {final_results_path}")

        logger.info(f"Recipe {recipe_name} finished successfully.")

    except FileNotFoundError as e:
        logger.critical(f"Recipe execution failed: A required file was not found. {e}", exc_info=True)
        sys.exit(1)
    except ValueError as e:
        logger.critical(f"Recipe execution failed: A value error occurred. {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Recipe execution failed with an unexpected error: {e}", exc_info=True)
        sys.exit(1)

def main_sync():
    asyncio.run(amain())

if __name__ == "__main__":
    main_sync() 