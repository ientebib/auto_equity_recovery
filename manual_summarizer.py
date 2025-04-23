"""
manual_summarizer.py

Standalone script to simulate the BigQuery summarization step using a manually
exported conversation CSV file.

This script takes a recipe name and a path to a conversation CSV as input.
It reads the corresponding leads CSV for the recipe, generates summaries for
conversations found in the manual CSV using the recipe's prompt, and merges
the results, saving them to `output_run/{recipe_name}/bigquery_simulation.csv`.

It relies on the `lead_recovery` package being installed.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List
import os
import sys

import pandas as pd
from tqdm import tqdm
import numpy as np

# Attempt to import from the installed package
try:
    from lead_recovery.recipe_loader import load_recipe, Recipe
    from lead_recovery.summarizer import ConversationSummarizer
    from lead_recovery.reporting import to_csv
    # We don't need settings directly, ConversationSummarizer loads it.
except ImportError as e:
    print(f"Error: Failed to import lead_recovery package components: {e}")
    print("Please ensure the lead_recovery package is installed ('pip install .')")
    exit(1)

# --- Logging Setup ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)-8s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Constants ---
DEFAULT_OUTPUT_BASE = Path("output_run")
LEADS_FILENAME = "leads.csv"
OUTPUT_FILENAME = "final_simulation.csv"
PHONE_COL_LEADS = "cleaned_phone" # Expected phone column in leads.csv
PHONE_COL_CONVOS = "cleaned_phone_number" # Expected phone column in manual convo export
REQUIRED_CONVO_COLS = [PHONE_COL_CONVOS, "msg_from", "message"] # Min cols for summarizer

def load_recipe(name: str) -> Recipe:
    """Load the recipe with the given name."""
    # Import dynamically to avoid circular imports
    from lead_recovery.recipe_loader import load_recipe
    return load_recipe(name)

def read_leads_csv(path: str) -> pd.DataFrame:
    """Read the leads CSV file."""
    logger.info(f"Reading leads from {path}")
    if not os.path.exists(path):
        logger.error(f"Leads CSV not found at {path}")
        raise FileNotFoundError(f"Leads CSV not found at {path}")
    
    return pd.read_csv(path)

def read_manual_conversation_csv(path: str) -> pd.DataFrame:
    """Read the manual conversation CSV file."""
    logger.info(f"Reading manual conversation CSV from {path}")
    if not os.path.exists(path):
        logger.error(f"Manual conversation CSV not found at {path}")
        raise FileNotFoundError(f"Manual conversation CSV not found at {path}")
    
    return pd.read_csv(path)

def group_conversations_by_phone(conversations_df: pd.DataFrame) -> Dict[str, List[Dict]]:
    """Group conversations by phone number."""
    # Check phone number format first
    sample_phones = conversations_df['cleaned_phone_number'].head(5).tolist()
    print(f"SAMPLE CONVERSATION PHONES (first 5): {sample_phones}")
    print(f"CONVERSATION PHONE DATA TYPE: {type(conversations_df['cleaned_phone_number'].iloc[0])}")
    
    grouped = {}
    for _, row in conversations_df.iterrows():
        phone = str(row['cleaned_phone_number']).strip()
        # Normalize by taking the last 10 digits if longer
        if len(phone) > 10:
            phone = phone[-10:]
        
        if phone not in grouped:
            grouped[phone] = []
        
        # Convert creation_time to string to prevent serialization issues
        creation_time = str(row['creation_time'])
        
        # Check for Spanish characters in message
        message = row['message']
        has_spanish_chars = any(c in message for c in "áéíóúüñÁÉÍÓÚÜÑ¿¡")
        if has_spanish_chars:
            print(f"FOUND SPANISH CHARS in message for phone {phone}: {message[:50]}...")
        
        grouped[phone].append({
            'creation_time': creation_time,
            'msg_from': row['msg_from'],
            'operator_alias': row.get('operator_alias', ''),
            'message': message
        })
    
    # Sort conversations by creation_time for each phone number
    for phone in grouped:
        grouped[phone] = sorted(grouped[phone], key=lambda x: x['creation_time'])
    
    logger.info(f"Grouped conversations for {len(grouped)} unique phone numbers")
    return grouped

def normalize_phone_number(phone):
    """Normalize phone numbers to ensure matching."""
    if phone is None:
        return None
    
    # Convert to string and handle various formats
    phone_str = str(phone).strip()
    
    # Remove non-digit characters
    digits_only = ''.join(c for c in phone_str if c.isdigit())
    
    # If it's a float with decimal part, remove the decimal part
    if '.' in phone_str:
        digits_only = ''.join(c for c in phone_str.split('.')[0] if c.isdigit())
    
    # Take last 10 digits if longer
    if len(digits_only) > 10:
        digits_only = digits_only[-10:]
    
    return digits_only

def generate_summaries(
    grouped_conversations: Dict[str, List[Dict]],
    leads_df: pd.DataFrame,
    recipe: Recipe,
    output_path: str,
) -> None:
    """Generate summaries for all leads."""
    # Initialize the summarizer
    summarizer = ConversationSummarizer()
    
    # Check phone number format in leads_df
    print(f"LEADS DF COLUMNS: {leads_df.columns.tolist()}")
    
    # Create a normalized_phone column for matching
    leads_df['normalized_phone'] = leads_df['cleaned_phone'].apply(normalize_phone_number)
    
    sample_leads_phones = leads_df['normalized_phone'].head(5).tolist()
    print(f"SAMPLE LEADS PHONES (first 5): {sample_leads_phones}")
    print(f"LEADS PHONE DATA TYPE: {type(leads_df['cleaned_phone'].iloc[0])}")
    
    # Debug output to show matching
    conversation_phones = set(grouped_conversations.keys())
    normalized_conversation_phones = {normalize_phone_number(p) for p in conversation_phones}
    leads_phones = set(leads_df['normalized_phone'].astype(str).tolist())
    
    print(f"TOTAL UNIQUE CONVERSATION PHONES: {len(conversation_phones)}")
    print(f"TOTAL UNIQUE LEADS PHONES: {len(leads_phones)}")
    print(f"MATCHING PHONES COUNT: {len(leads_phones.intersection(normalized_conversation_phones))}")
    
    # Count actual summaries generated
    summaries_generated = 0
    skipped_summaries = 0
    
    # Create a new DataFrame for the results
    results_df = leads_df.copy()
    
    # Add result columns
    results_df['result'] = None
    results_df['stall_reason'] = None
    results_df['key_interaction'] = None
    results_df['suggestion'] = None
    results_df['summary'] = None
    
    # Loop through each lead
    for i, row in results_df.iterrows():
        if i % 100 == 0:
            logger.info(f"Processing lead {i} of {len(results_df)}")
        
        lead_id = row['lead_id']
        phone = normalize_phone_number(row['cleaned_phone'])
        
        # Try to find conversations for this lead's phone number
        if phone in normalized_conversation_phones:
            # Find the original phone format in the grouped_conversations
            matching_phone = next((p for p in grouped_conversations.keys() 
                                  if normalize_phone_number(p) == phone), None)
            
            if matching_phone:
                conversations = grouped_conversations[matching_phone]
                
                try:
                    print(f"GENERATING SUMMARY for lead_id={lead_id}, phone={phone} with {len(conversations)} messages")
                    
                    # Check for Spanish content in first few messages
                    for i, conv in enumerate(conversations[:3]):
                        if i >= len(conversations):
                            break
                        message = conv['message']
                        if any(c in message for c in "áéíóúüñÁÉÍÓÚÜÑ¿¡"):
                            print(f"SPANISH CONTENT in conversation for lead {lead_id}: {message[:50]}...")
                    
                    # Generate summary – ConversationSummarizer.summarize now
                    # expects only the conversation DataFrame.
                    conv_df = pd.DataFrame(conversations)
                    result = summarizer.summarize(conv_df)
                    
                    # Update the results DataFrame
                    results_df.loc[results_df['lead_id'] == lead_id, 'result'] = result.get('result', 'Unknown')
                    results_df.loc[results_df['lead_id'] == lead_id, 'stall_reason'] = result.get('stall_reason', 'N/A')
                    results_df.loc[results_df['lead_id'] == lead_id, 'key_interaction'] = result.get('key_interaction', 'N/A')
                    results_df.loc[results_df['lead_id'] == lead_id, 'suggestion'] = result.get('suggestion', 'N/A')
                    results_df.loc[results_df['lead_id'] == lead_id, 'summary'] = result.get('summary', 'Error generating summary')
                    
                    # Check for Spanish in the summary
                    summary = result.get('summary', '')
                    if any(c in summary for c in "áéíóúüñÁÉÍÓÚÜÑ¿¡"):
                        print(f"SPANISH CHARS IN SUMMARY for lead {lead_id}: {summary[:50]}...")
                    
                    summaries_generated += 1
                
                except Exception as e:
                    logger.error(f"Error generating summary for lead {lead_id}: {e}")
                    results_df.loc[results_df['lead_id'] == lead_id, 'result'] = 'Error'
                    results_df.loc[results_df['lead_id'] == lead_id, 'summary'] = f"Error generating summary: {str(e)}"
            else:
                print(f"SKIPPING lead_id={lead_id}, phone={phone} - No conversations found despite normalization")
                results_df.loc[results_df['lead_id'] == lead_id, 'result'] = 'No Conversation Data'
                results_df.loc[results_df['lead_id'] == lead_id, 'stall_reason'] = 'NO_OUTBOUND'
                results_df.loc[results_df['lead_id'] == lead_id, 'key_interaction'] = 'N/A'
                results_df.loc[results_df['lead_id'] == lead_id, 'suggestion'] = 'N/A'
                results_df.loc[results_df['lead_id'] == lead_id, 'summary'] = 'No conversation history found in the provided manual CSV.'
                skipped_summaries += 1
        else:
            print(f"SKIPPING lead_id={lead_id}, phone={phone} - No matching phone in conversations")
            results_df.loc[results_df['lead_id'] == lead_id, 'result'] = 'No Conversation Data'
            results_df.loc[results_df['lead_id'] == lead_id, 'stall_reason'] = 'NO_OUTBOUND'
            results_df.loc[results_df['lead_id'] == lead_id, 'key_interaction'] = 'N/A'
            results_df.loc[results_df['lead_id'] == lead_id, 'suggestion'] = 'N/A'
            results_df.loc[results_df['lead_id'] == lead_id, 'summary'] = 'No conversation history found in the provided manual CSV.'
            skipped_summaries += 1
    
    print(f"FINAL SUMMARY: Generated {summaries_generated} summaries, skipped {skipped_summaries} leads")
    
    # Save the results to the output path
    logger.info(f"Saving {len(results_df)} summaries to {output_path}")
    to_csv(results_df, output_path)

def main():
    parser = argparse.ArgumentParser(
        description="Manual Summarizer: Simulate BQ step using local conversation CSV.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "recipe_name",
        help="Name of the recipe folder under 'recipes/' (e.g., 'profiling_incomplete')"
    )
    parser.add_argument(
        "conversation_csv_path",
        type=Path,
        help="Path to the manually exported BigQuery conversation CSV file."
    )
    parser.add_argument(
        "--output-base",
        type=Path,
        default=DEFAULT_OUTPUT_BASE,
        help="Base directory for output ('<output-base>/<recipe_name>/')"
    )
    args = parser.parse_args()

    recipe_name: str = args.recipe_name
    conversation_csv_path: Path = args.conversation_csv_path
    output_base_dir: Path = args.output_base

    # --- Path Definitions ---
    recipe_output_dir = (output_base_dir / recipe_name).resolve()
    leads_csv_path = recipe_output_dir / LEADS_FILENAME
    final_output_path = recipe_output_dir / OUTPUT_FILENAME

    logger.info(f"Starting manual simulation for recipe: '{recipe_name}'")
    logger.info(f"Using manual conversation CSV: {conversation_csv_path}")
    logger.info(f"Expecting leads CSV at: {leads_csv_path}")
    logger.info(f"Output will be saved to: {final_output_path}")

    # --- Load Recipe ---
    try:
        recipe: Recipe = load_recipe(recipe_name)
        logger.info(f"Successfully loaded recipe '{recipe_name}'. Using prompt: {recipe.prompt_path}")
    except FileNotFoundError as e:
        logger.error(f"Error loading recipe: {e}")
        return # Exit if recipe not found

    # --- Read Input Files ---
    try:
        leads_df = pd.read_csv(leads_csv_path)
        logger.info(f"Read {len(leads_df)} rows from {leads_csv_path}")
        if PHONE_COL_LEADS not in leads_df.columns:
             logger.error(f"Missing required column '{PHONE_COL_LEADS}' in {leads_csv_path}")
             return
    except FileNotFoundError:
        logger.error(f"Leads file not found: {leads_csv_path}")
        logger.error("Ensure the Redshift part of the pipeline has been run for this recipe.")
        return
    except Exception as e:
        logger.error(f"Error reading leads CSV {leads_csv_path}: {e}")
        return

    try:
        convos_df = pd.read_csv(conversation_csv_path)
        logger.info(f"Read {len(convos_df)} rows from {conversation_csv_path}")
        missing_cols = [col for col in REQUIRED_CONVO_COLS if col not in convos_df.columns]
        if missing_cols:
            logger.error(f"Missing required columns in conversation CSV {conversation_csv_path}: {missing_cols}")
            logger.error("Ensure the CSV contains at least: 'cleaned_phone_number', 'msg_from', 'message'")
            return
        # Convert phone number to string just in case it was read as numeric
        convos_df[PHONE_COL_CONVOS] = convos_df[PHONE_COL_CONVOS].astype(str)

    except FileNotFoundError:
        logger.error(f"Manual conversation file not found: {conversation_csv_path}")
        return
    except Exception as e:
        logger.error(f"Error reading conversation CSV {conversation_csv_path}: {e}")
        return

    # --- Clean and normalize phone numbers in leads DataFrame ---
    # Convert float phone numbers to integers by removing decimal part
    if leads_df[PHONE_COL_LEADS].dtype == 'float64':
        # Convert float phones to integers (10 digits) by removing decimal point
        leads_df['normalized_phone'] = leads_df[PHONE_COL_LEADS].fillna(0).astype(np.int64).astype(str)
        print(f"Converted phone numbers from float to integer format (removed decimal points)")
        # Use the normalized column for matching
        phone_col_for_matching = 'normalized_phone'
    else:
        # If already string or other format, just convert to string
        leads_df['normalized_phone'] = leads_df[PHONE_COL_LEADS].astype(str)
        phone_col_for_matching = 'normalized_phone'

    # --- Prepare Conversation Data ---
    if convos_df.empty:
        logger.warning("Manual conversation file is empty. Summaries will indicate no conversation.")
        phone_groups = {}
    else:
        # Group conversations by phone number
        phone_groups = {
            str(phone): group.sort_values(by="creation_time") if "creation_time" in group.columns else group
            for phone, group in convos_df.groupby(PHONE_COL_CONVOS)
        }
        logger.info(f"Grouped conversations for {len(phone_groups)} unique phone numbers.")
        
        # ADDED: Check for phone number format consistency and matching
        print("\n==== DIRECT DEBUG: PHONE NUMBER FORMAT CHECK ====")
        print(f"First 5 phone numbers from leads.csv ({PHONE_COL_LEADS}):")
        sample_lead_phones = leads_df[PHONE_COL_LEADS].dropna().astype(str).head(5).tolist()
        print(sample_lead_phones)
        
        print(f"\nFirst 5 phone numbers from manual CSV ({PHONE_COL_CONVOS}):")
        sample_convo_phones = list(phone_groups.keys())[:5] if len(phone_groups) >= 5 else list(phone_groups.keys())
        print(sample_convo_phones)
        
        # Check for any matches
        matches = [phone for phone in sample_lead_phones if phone in phone_groups]
        print(f"\nMatches found between samples: {matches}")
        print(f"Total matches in entire dataset: {sum(1 for phone in leads_df[PHONE_COL_LEADS].dropna().astype(str) if phone in phone_groups)}")
        
        if not matches:
            print("\n!!! WARNING: No sample phones match between datasets !!!")
            print("Phone number formatting might be different. Consider normalization.")
            
            # Attempt simple normalization: take last 10 digits
            print("\nAttempting simple normalization (last 10 digits)...")
            
            # Convert convo phones to last 10 digits
            normalized_phone_groups = {}
            for phone, group in phone_groups.items():
                # Take last 10 digits if length > 10
                norm_phone = phone[-10:] if len(phone) >= 10 else phone
                normalized_phone_groups[norm_phone] = group
                
            print(f"Normalized convo phones (first 5): {list(normalized_phone_groups.keys())[:5]}")
            
            # Check matches with normalized phones
            normalized_matches = [phone[-10:] if len(phone) >= 10 else phone for phone in sample_lead_phones if phone[-10:] in normalized_phone_groups]
            print(f"Normalized matches found: {normalized_matches}")
            total_norm_matches = sum(1 for phone in leads_df[PHONE_COL_LEADS].dropna().astype(str) if (phone[-10:] if len(phone) >= 10 else phone) in normalized_phone_groups)
            print(f"Total normalized matches: {total_norm_matches}")
            
            if total_norm_matches > 0:
                print("\n!!! Using normalized phone matching !!!")
                # Replace phone_groups with normalized version
                phone_groups = normalized_phone_groups
        
        print("==== END DEBUG ====\n")


    # --- Initialize Summarizer ---
    try:
        summarizer = ConversationSummarizer(
            prompt_template_path=recipe.prompt_path,
            expected_yaml_keys=recipe.expected_yaml_keys
        )
    except FileNotFoundError as e:
        logger.error(f"Failed to initialize summarizer. Prompt file error: {e}")
        return
    except Exception as e: # Catch potential OpenAI key issues etc.
        logger.error(f"Failed to initialize summarizer: {e}")
        return

    # --- Generate Summaries ---
    summary_results: List[Dict[str, Any]] = []
    phones_to_process = leads_df[phone_col_for_matching].dropna().unique()
    logger.info(f"Generating summaries for {len(phones_to_process)} unique leads...")
    
    # ADDED: Track number of actual summarization calls
    actual_summaries = 0
    skipped_summaries = 0

    # --- Add Debugging ---
    if phones_to_process.size > 0 and phone_groups:
        sample_lead_phone = phones_to_process[0]
        sample_group_keys = list(phone_groups.keys())[:5]
        logger.debug(f"Sample lead phone from leads.csv: {sample_lead_phone} (Type: {type(sample_lead_phone)})")
        logger.debug(f"Sample phone group keys from manual CSV: {sample_group_keys}")
        logger.debug(f"Checking if sample lead phone exists in group keys: {sample_lead_phone in phone_groups}")
    # --- End Debugging ---

    # Add a direct print statement to show what's happening
    print("\n==== DIRECT DEBUG: SUMMARIZATION PROCESS ====")
    print(f"About to process {len(phones_to_process)} phones, with {len(phone_groups)} conversation groups available.")
    
    for phone in tqdm(phones_to_process, desc="Summarizing", unit="lead"):
        # Use normalized matching if needed 
        norm_phone = phone[-10:] if len(phone) >= 10 else phone  # Normalize lead phone the same way

        if phone in phone_groups:
            group_df = phone_groups[phone]
            actual_summaries += 1
            if actual_summaries <= 5:  # Only print first 5 for brevity
                print(f"SUMMARIZING #{actual_summaries}: Found match for {phone}")
            
            try:
                # Add direct print before OpenAI call
                if actual_summaries <= 2:  # Only print first 2 for brevity
                    print(f"About to call OpenAI API for phone {phone}")
                
                summary_dict = summarizer.summarize(group_df) # Returns a dict
                
                # Add direct print after OpenAI call
                if actual_summaries <= 2:
                    print(f"OpenAI API call completed for {phone}. Result: {summary_dict.get('result', 'Unknown')}")
                
                # Add the phone number used for joining
                summary_dict[PHONE_COL_CONVOS] = phone
                # --- Add Debugging ---
                logger.debug(f"Summary generated for {phone}: {summary_dict}")
                # --- End Debugging ---
                summary_results.append(summary_dict)
            except Exception as e:
                logger.error(f"Failed to summarize conversation for phone {phone}: {e}")
                print(f"ERROR summarizing {phone}: {e}")
                # Add default error entry
                error_entry = {
                    PHONE_COL_CONVOS: phone,
                    "result": "Summarization Error",
                    "stall_reason": "OTHER",
                    "key_interaction": "N/A",
                    "suggestion": "Review conversation manually or check logs",
                    "summary": f"Error during processing: {e}"
                }
                summary_results.append(error_entry)
        
        elif norm_phone in phone_groups:  # Try normalized matching
            group_df = phone_groups[norm_phone]
            actual_summaries += 1
            if actual_summaries <= 5:
                print(f"SUMMARIZING #{actual_summaries}: Found NORMALIZED match for {phone} -> {norm_phone}")
            
            try:
                if actual_summaries <= 2:
                    print(f"About to call OpenAI API for normalized phone {norm_phone}")
                
                summary_dict = summarizer.summarize(group_df)
                
                if actual_summaries <= 2:
                    print(f"OpenAI API call completed for {norm_phone}. Result: {summary_dict.get('result', 'Unknown')}")
                
                summary_dict[PHONE_COL_CONVOS] = phone  # Use original phone for joining
                summary_results.append(summary_dict)
            except Exception as e:
                logger.error(f"Failed to summarize conversation for normalized phone {norm_phone}: {e}")
                print(f"ERROR summarizing normalized {norm_phone}: {e}")
                error_entry = {
                    PHONE_COL_CONVOS: phone,
                    "result": "Summarization Error",
                    "stall_reason": "OTHER",
                    "key_interaction": "N/A",
                    "suggestion": "Review conversation manually or check logs",
                    "summary": f"Error during processing: {e}"
                }
                summary_results.append(error_entry)
        
        else:
            # Lead exists in leads.csv but not in the manual convo file
            skipped_summaries += 1
            if skipped_summaries <= 5:  # Only print first 5 for brevity
                print(f"SKIPPED #{skipped_summaries}: No conversation found for {phone}")
            
            logger.debug(f"No conversation found in manual CSV for phone {phone}")
            no_convo_entry = {
                PHONE_COL_CONVOS: phone,
                "result": "No Conversation Data",
                "stall_reason": "NO_OUTBOUND", # Assuming no convo means no outbound attempt captured
                "key_interaction": "N/A",
                "suggestion": "N/A",
                "summary": "No conversation history found in the provided manual CSV."
            }
            summary_results.append(no_convo_entry)
    
    print(f"\nSummary of processing:")
    print(f"- Total leads: {len(phones_to_process)}")
    print(f"- Leads with conversations that were summarized: {actual_summaries}")
    print(f"- Leads without conversations (skipped): {skipped_summaries}")
    print("==== END DEBUG ====\n")

    # --- Merge and Save Results ---
    if not summary_results:
        logger.warning("No summaries were generated. Saving leads data without summaries.")
        summaries_df = pd.DataFrame(columns=[PHONE_COL_CONVOS, 'result', 'stall_reason', 'key_interaction', 'suggestion', 'summary'])
    else:
         summaries_df = pd.DataFrame(summary_results)
         logger.info(f"Generated {len(summaries_df)} summaries.")
         # --- Add Debugging ---
         logger.debug("Head of summaries_df BEFORE merge:")
         logger.debug(summaries_df.head().to_string())
         # Check data types before merge
         logger.debug(f"Data type of leads_df['{PHONE_COL_LEADS}'] before merge: {leads_df[PHONE_COL_LEADS].dtype}")
         if PHONE_COL_CONVOS in summaries_df.columns:
             logger.debug(f"Data type of summaries_df['{PHONE_COL_CONVOS}'] before merge: {summaries_df[PHONE_COL_CONVOS].dtype}")
         else:
             logger.debug(f"Column '{PHONE_COL_CONVOS}' not found in summaries_df before merge.")
         # --- End Debugging ---

    # Merge leads with summaries using the appropriate phone column
    # Determine the correct column name from leads_df to join on
    join_col_leads = PHONE_COL_LEADS # Default
    if 'normalized_phone' in leads_df.columns and phone_col_for_matching == 'normalized_phone':
        join_col_leads = 'normalized_phone'
        
    # Ensure join columns are strings
    leads_df[join_col_leads] = leads_df[join_col_leads].astype(str)
    if PHONE_COL_CONVOS in summaries_df.columns:
        summaries_df[PHONE_COL_CONVOS] = summaries_df[PHONE_COL_CONVOS].astype(str)

    merged_df = leads_df.merge(
        summaries_df,
        left_on=join_col_leads, # Use the determined join column
        right_on=PHONE_COL_CONVOS,
        how="left",
    )

    # --- Clean up columns after merge ---
    # Remove redundant phone column from summaries if it's different from the leads join column
    if PHONE_COL_CONVOS in merged_df.columns and PHONE_COL_CONVOS != join_col_leads:
        merged_df.drop(columns=[PHONE_COL_CONVOS], inplace=True)

    # Determine the correct summary columns based on the recipe's expected keys
    # Use recipe.expected_yaml_keys if available, otherwise fall back to a default set
    summary_cols_to_fill = recipe.expected_yaml_keys or [
        'result', 'stall_reason', 'key_interaction', 'suggestion', 'summary'
    ]
    
    # Default values for filling NaNs - adjust if needed based on typical key names
    fillna_values = {
        # Attempt generic defaults, but specific recipes might need adjustment
        key: 'N/A' for key in summary_cols_to_fill 
    }
    # Override defaults for common keys if they exist in the list
    if 'result' in fillna_values: fillna_values['result'] = 'Merge Error or No Summary'
    if 'stall_reason' in fillna_values: fillna_values['stall_reason'] = 'OTHER'
    if 'reason_for_drop' in fillna_values: fillna_values['reason_for_drop'] = 'OTHER'
    if 'summary' in fillna_values: fillna_values['summary'] = 'N/A - Check logs or original data'

    # Only fillna for columns that actually exist in merged_df and are in our target list
    cols_to_fill = {k: v for k, v in fillna_values.items() if k in merged_df.columns and k in summary_cols_to_fill}
    merged_df.fillna(value=cols_to_fill, inplace=True)

    # Save the final simulation file
    try:
        to_csv(merged_df, final_output_path)
        logger.info(f"Successfully saved simulation results to: {final_output_path}")
    except Exception as e:
        logger.error(f"Failed to save output CSV to {final_output_path}: {e}")


if __name__ == "__main__":
    main() 