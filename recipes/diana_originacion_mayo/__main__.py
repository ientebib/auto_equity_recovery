#!/usr/bin/env python
"""
Diana Originacion Mayo Recipe
-----------------------------
Analyzes conversations for template messages and user responses.
"""

import os
import sys
import logging
import csv
import pandas as pd
from datetime import datetime
from pathlib import Path
import pytz
from typing import Dict, List, Any, Optional
import yaml
import json

# Add parent directory to path so we can import the lead_recovery package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lead_recovery.db_clients import BigQueryClient  # Use existing client
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

from recipes.diana_originacion_mayo.analyzer import analyze_diana_conversation

# Import OpenAI summarizer for analyzing stalled handoffs
try:
    from lead_recovery.summarizer import Summarizer
except ImportError:
    Summarizer = None
    logging.warning("Summarizer module not found. LLM analysis will be disabled.")

# Set up more detailed logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

def ensure_directory_exists(path: Path) -> None:
    """Create directory if it doesn't exist."""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

def load_phone_numbers(leads_file: Path) -> List[str]:
    """Load phone numbers from the leads CSV file."""
    try:
        if not leads_file.exists():
            raise FileNotFoundError(f"Leads file not found: {leads_file}")
            
        df = pd.read_csv(leads_file)
        
        if 'cleaned_phone' not in df.columns:
            raise ValueError(f"CSV file {leads_file} missing required 'cleaned_phone' column")
            
        phone_numbers = df['cleaned_phone'].astype(str).tolist()
        logger.info(f"Loaded {len(phone_numbers)} phone numbers from {leads_file}")
        return phone_numbers
    except Exception as e:
        logger.error(f"Error loading phone numbers: {e}")
        raise

def query_bigquery(phone_numbers: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Query BigQuery for conversation messages for the given phone numbers.
    Returns a dictionary mapping phone numbers to their conversation messages.
    """
    if not phone_numbers:
        logger.warning("No phone numbers provided for BigQuery query")
        return {}
    
    # Use the BigQueryClient from lead_recovery instead of creating a new client
    client = BigQueryClient()
    
    # Read query from SQL file
    sql_path = Path(__file__).resolve().parent / 'bigquery.sql'
    with open(sql_path, 'r') as f:
        query = f.read()
    
    # Set up the query parameters
    query_params = [
        bigquery.ArrayQueryParameter("target_phone_numbers_list", "STRING", phone_numbers),
    ]
    
    try:
        # Run the query using the client's query method
        logger.info(f"Querying BigQuery for {len(phone_numbers)} phone numbers")
        df = client.query(query, params=query_params)
        
        # Group by phone number
        conversations = {}
        for _, row in df.iterrows():
            phone = row['cleaned_phone_number']
            if phone not in conversations:
                conversations[phone] = []
                
            conversations[phone].append({
                'cleaned_phone_number': phone,
                'creation_time': row['creation_time'],
                'msg_from': row['msg_from'],
                'operator_alias': row['operator_alias'],
                'message': row['message']
            })
        
        logger.info(f"Retrieved conversations for {len(conversations)} phone numbers")
        return conversations
    except GoogleAPIError as e:
        logger.error(f"Error querying BigQuery: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in query_bigquery: {e}")
        raise

def analyze_conversation_with_llm(messages: List[Dict], prompt_path: Path) -> Dict:
    """
    Use OpenAI to analyze conversations to identify why handoff stalled.
    Only called for conversations that need deeper analysis.
    """
    if Summarizer is None:
        logger.warning("Summarizer module not available. Returning empty analysis.")
        return {
            "handoff_progress": "UNKNOWN", 
            "stall_reason": "UNKNOWN", 
            "suggested_followup": ""
        }
    
    try:
        # Create conversation text for LLM
        conversation_text = "\n".join([
            f"[{msg.get('creation_time')}] {msg.get('msg_from')}: {msg.get('message')}"
            for msg in messages
        ])
        
        # Read prompt template
        with open(prompt_path, 'r') as f:
            prompt_template = f.read()
        
        # Replace placeholder with conversation
        prompt = prompt_template.replace("{conversation_text}", conversation_text)
        
        # Initialize the summarizer with appropriate model
        summarizer = Summarizer(model="gpt-3.5-turbo")
        
        # Get response from LLM
        summary = summarizer.summarize(prompt)
        
        # If we got the special "NO_ANALYSIS_NEEDED" response, return empty results
        if summary.strip() == "NO_ANALYSIS_NEEDED":
            return {
                "handoff_progress": "NO_ANALYSIS_NEEDED", 
                "stall_reason": "NO_ANALYSIS_NEEDED", 
                "suggested_followup": ""
            }
        
        # Try to parse YAML from response
        try:
            # Find YAML section between triple backticks
            import re
            yaml_match = re.search(r'```yaml\n(.*?)\n```', summary, re.DOTALL)
            if yaml_match:
                yaml_content = yaml_match.group(1)
                analysis = yaml.safe_load(yaml_content)
            else:
                # Try to parse the whole response as YAML
                analysis = yaml.safe_load(summary)
                
            return analysis
        except Exception as e:
            logger.error(f"Error parsing YAML from LLM response: {e}")
            return {
                "handoff_progress": "PARSE_ERROR", 
                "stall_reason": "Failed to parse LLM response", 
                "suggested_followup": summary[:100]  # Return part of the raw response for debugging
            }
    except Exception as e:
        logger.error(f"Error in LLM analysis: {e}")
        return {
            "handoff_progress": "ERROR", 
            "stall_reason": f"Error: {str(e)[:100]}", 
            "suggested_followup": ""
        }

# Helper function to handle safe division (avoid division by zero)
def safe_percentage(numerator, denominator, decimal_places=1):
    """Calculate percentage safely, handling division by zero."""
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, decimal_places)

def main():
    """Main entry point for the script."""
    try:
        # Define paths
        recipe_dir = Path(__file__).resolve().parent
        project_root = recipe_dir.parent.parent
        leads_file = project_root / "output_run" / "diana_originacion_mayo" / "leads.csv"
        prompt_path = recipe_dir / "prompt.txt"
        
        # Get current time in Mexico City timezone for output directory naming
        now = datetime.now(pytz.timezone("America/Mexico_City"))
        timestamp = now.strftime("%Y-%m-%dT%H-%M")
        
        output_dir = project_root / "output_run" / "diana_originacion_mayo" / timestamp
        ensure_directory_exists(output_dir)
        
        # Load phone numbers
        phone_numbers = load_phone_numbers(leads_file)
        
        # Query BigQuery for conversations
        conversations = query_bigquery(phone_numbers)
        
        # Save sample bot messages for analysis
        sample_messages_file = output_dir / "sample_bot_messages.txt"
        with open(sample_messages_file, 'w') as f:
            f.write("Sample Bot Messages for Analysis\n")
            f.write("================================\n\n")
            
            # Track unique bot messages
            unique_bot_msgs = set()
            
            for phone, msgs in conversations.items():
                for msg in msgs:
                    if msg.get('msg_from') == 'bot':
                        # Truncate for readability
                        message = msg.get('message', '')[:500]
                        # Check if this is a new message type
                        if message not in unique_bot_msgs and len(unique_bot_msgs) < 50:
                            unique_bot_msgs.add(message)
                            f.write(f"--- Message from phone {phone} ---\n")
                            f.write(f"{message}\n\n")
        
        # Save sample messages for leads that clicked "Me interesa"
        interested_messages_file = output_dir / "interested_leads_messages.txt"
        with open(interested_messages_file, 'w') as f:
            f.write("Messages for Leads that Clicked 'Me interesa'\n")
            f.write("============================================\n\n")
            
            interested_count = 0
            for phone, msgs in conversations.items():
                # First check if this lead clicked "Me interesa"
                for i, msg in enumerate(msgs):
                    if msg.get('msg_from') == 'user':
                        try:
                            raw_message = msg.get('message', '{}')
                            user_data = json.loads(raw_message)
                            if user_data.get('button') == 'Me interesa':
                                # Found an interested lead
                                interested_count += 1
                                if interested_count <= 10:  # Limit to 10 examples
                                    f.write(f"=== Conversation for phone {phone} ===\n")
                                    for conversation_msg in msgs:
                                        f.write(f"[{conversation_msg.get('creation_time')}] {conversation_msg.get('msg_from')}: {conversation_msg.get('message')[:300]}\n")
                                    f.write("\n\n")
                                break
                        except:
                            pass
        
        # Analyze conversations and prepare results
        results = []
        llm_analyzed_count = 0
        
        for phone, msgs in conversations.items():
            # Sort messages by creation_time to ensure correct analysis
            sorted_msgs = sorted(msgs, key=lambda x: x['creation_time'])
            
            # First analyze with our Python analyzer
            python_analysis = analyze_diana_conversation(sorted_msgs)
            
            # Initialize result dictionary with basic info
            result = {
                'cleaned_phone': phone,
                'offer_detected': python_analysis['offer_message_detected'],
                'user_response': python_analysis['user_response_to_offer'] if python_analysis['offer_message_detected'] else 'No offer sent',
                'handoff_reached': python_analysis['handoff_reached'],
                'handoff_response': python_analysis['handoff_response'],
                'handoff_finalized': python_analysis['handoff_finalized'],
                'handoff_stall_reason': python_analysis['handoff_stall_reason']
            }
            
            # Only use LLM for deeper analysis of leads that started but didn't complete handoff
            if (python_analysis['user_response_to_offer'] == 'Me interesa' and 
                python_analysis['handoff_reached'] and 
                python_analysis['handoff_response'] == 'STARTED_HANDOFF' and 
                not python_analysis['handoff_finalized']):
                
                logger.info(f"Using LLM to analyze stalled handoff for phone: {phone}")
                llm_analysis = analyze_conversation_with_llm(sorted_msgs, prompt_path)
                llm_analyzed_count += 1
                
                # Add LLM analysis to result
                if llm_analysis:
                    result.update({
                        'handoff_progress': llm_analysis.get('handoff_progress', 'UNKNOWN'),
                        'stall_reason': llm_analysis.get('stall_reason', 'UNKNOWN'),
                        'suggested_followup': llm_analysis.get('suggested_followup', '')
                    })
            
            results.append(result)
        
        # Add missing phones (those without conversation data) to results
        conversation_phones = set(conversations.keys())
        for phone in phone_numbers:
            if phone not in conversation_phones:
                results.append({
                    'cleaned_phone': phone,
                    'offer_detected': False,
                    'user_response': 'No conversation found',
                    'handoff_reached': False,
                    'handoff_response': 'NOT_APPLICABLE',
                    'handoff_finalized': False,
                    'handoff_stall_reason': ''
                })
        
        # Write results to CSV
        output_file = output_dir / "diana_results.csv"
        
        # Read meta.yml to get output columns
        meta_path = recipe_dir / "meta.yml"
        output_columns = None
        if meta_path.exists():
            try:
                with open(meta_path, 'r') as f:
                    meta_data = yaml.safe_load(f)
                    output_columns = meta_data.get('output_columns')
            except Exception as e:
                logger.warning(f"Could not read output_columns from meta.yml: {e}")
        
        # Default columns if not specified in meta.yml
        if not output_columns:
            output_columns = [
                'cleaned_phone', 
                'offer_detected', 
                'user_response',
                'handoff_reached',
                'handoff_response',
                'handoff_finalized',
                'handoff_stall_reason'
            ]
            
        # Write results to CSV
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=output_columns, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results)
        
        logger.info(f"Analysis complete. Results written to {output_file}")
        
        # Write a summary to a text file
        summary_file = output_dir / "summary.txt"
        with open(summary_file, 'w') as f:
            total_phones = len(results)
            offers_sent = sum(1 for r in results if r['offer_detected'])
            interested = sum(1 for r in results if r['user_response'] == 'Me interesa')
            not_interested = sum(1 for r in results if r['user_response'] == 'de momento no')
            ignored = sum(1 for r in results if r['user_response'] == 'ignored')
            
            # New handoff metrics
            handoff_reached = sum(1 for r in results if r['handoff_reached'])
            handoff_started = sum(1 for r in results if r['handoff_response'] == 'STARTED_HANDOFF')
            handoff_declined = sum(1 for r in results if r['handoff_response'] == 'DECLINED_HANDOFF')
            handoff_ignored = sum(1 for r in results if r['handoff_response'] == 'IGNORED_HANDOFF')
            handoff_completed = sum(1 for r in results if r['handoff_finalized'])
            
            f.write(f"Diana Originacion Mayo - Analysis Summary\n")
            f.write(f"Date: {now.strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"===========================================\n\n")
            f.write(f"Total phone numbers: {total_phones}\n")
            
            # Use safe percentages to avoid division by zero
            offers_pct = safe_percentage(offers_sent, total_phones)
            interested_pct = safe_percentage(interested, offers_sent)
            not_interested_pct = safe_percentage(not_interested, offers_sent)
            ignored_pct = safe_percentage(ignored, offers_sent)
            
            handoff_reached_pct = safe_percentage(handoff_reached, interested)
            handoff_started_pct = safe_percentage(handoff_started, handoff_reached)
            handoff_declined_pct = safe_percentage(handoff_declined, handoff_reached)
            handoff_ignored_pct = safe_percentage(handoff_ignored, handoff_reached)
            handoff_completed_pct = safe_percentage(handoff_completed, handoff_started)
            
            f.write(f"Offers sent: {offers_sent} ({offers_pct:.1f}% of total)\n")
            f.write(f"User responses:\n")
            f.write(f"  - Me interesa: {interested} ({interested_pct:.1f}% of offers)\n")
            f.write(f"  - de momento no: {not_interested} ({not_interested_pct:.1f}% of offers)\n")
            f.write(f"  - Ignored: {ignored} ({ignored_pct:.1f}% of offers)\n\n")
            
            # Add handoff metrics to summary
            f.write(f"Handoff funnel:\n")
            f.write(f"  - Received handoff invitation: {handoff_reached} ({handoff_reached_pct:.1f}% of interested)\n")
            f.write(f"  - Started handoff process: {handoff_started} ({handoff_started_pct:.1f}% of reached)\n")
            f.write(f"  - Declined handoff: {handoff_declined} ({handoff_declined_pct:.1f}% of reached)\n")
            f.write(f"  - Ignored handoff: {handoff_ignored} ({handoff_ignored_pct:.1f}% of reached)\n")
            f.write(f"  - Completed handoff: {handoff_completed} ({handoff_completed_pct:.1f}% of started)\n\n")
            
            f.write(f"LLM Analysis:\n")
            f.write(f"  - Conversations analyzed with LLM: {llm_analyzed_count}\n")
            
        logger.info(f"Summary written to {summary_file}")
        
        # Create symbolic link to latest results
        latest_link = project_root / "output_run" / "diana_originacion_mayo" / "latest.csv"
        try:
            if latest_link.exists() or latest_link.is_symlink():
                latest_link.unlink()
            latest_link.symlink_to(output_file)
            logger.info(f"Created symbolic link: {latest_link} -> {output_file}")
        except Exception as e:
            logger.warning(f"Could not create symbolic link: {e}")
            
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 