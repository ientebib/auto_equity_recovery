#!/usr/bin/env python
"""
Recipe Generator Script

Creates a new recipe with all required files set up correctly.
"""
import argparse
import os
from datetime import datetime
from pathlib import Path


def create_recipe(recipe_name, description, author, template_type="basic"):
    """
    Creates a new recipe with all required files.
    
    Args:
        recipe_name: Name of the recipe (will be folder name)
        description: Short description of the recipe's purpose
        author: Name of the recipe creator
        template_type: Type of template to use (basic, analyzer, etc.)
    """
    # Validate recipe name (no spaces, special chars)
    if not recipe_name.isalnum() and not all(c.isalnum() or c == '_' for c in recipe_name):
        print(f"Error: Recipe name '{recipe_name}' contains invalid characters. Use only letters, numbers, and underscores.")
        return False
    
    # Check if recipe already exists
    recipe_dir = Path("recipes") / recipe_name
    if recipe_dir.exists():
        print(f"Error: Recipe '{recipe_name}' already exists at {recipe_dir}")
        return False
    
    # Create recipe directory
    try:
        recipe_dir.mkdir(parents=True, exist_ok=False)
        print(f"Created recipe directory: {recipe_dir}")
    except Exception as e:
        print(f"Failed to create recipe directory: {e}")
        return False
    
    # Define file templates
    templates = {
        "bigquery.sql": """-- recipes/{recipe_name}/bigquery.sql
-- Fetches conversation history from BigQuery for the specified phone numbers.
-- DO NOT MODIFY these column names: cleaned_phone_number, creation_time, msg_from, message

SELECT
    RIGHT(b.user_platform_contact_id, 10) AS cleaned_phone_number,
    a.creation_time,
    a.msg_from,
    a.operator_alias,
    a.message
FROM `botmaker-bigdata.ext_metric_kavakcapital.message_metrics` AS a
INNER JOIN `botmaker-bigdata.ext_metric_kavakcapital.session_metrics` AS b
        ON a.session_id = b.session_id
WHERE RIGHT(b.user_platform_contact_id, 10) IN UNNEST(@target_phone_numbers_list)
  AND a.creation_time >= TIMESTAMP('2025-01-01 00:00:00')  -- Adjust date as needed
ORDER BY cleaned_phone_number, a.creation_time ASC;""",
        
        "redshift.sql": """-- recipes/{recipe_name}/redshift.sql
-- Fetches leads to analyze from Redshift.
-- MUST include a cleaned_phone column.

SELECT 
    RIGHT(phone_number, 10) as cleaned_phone,
    lead_id,
    name,
    email,
    lead_source,
    created_at
FROM your_leads_table
WHERE your_condition = 'your_criteria'
  AND created_at >= '2025-01-01'  -- Adjust date as needed
LIMIT 1000;  -- Adjust limit as needed""",
        
        "prompt.txt": """You are analyzing conversations between customers and the Kuna Capital support team on WhatsApp. 
Your task is to extract specific information and analyze each conversation.

Current date: {HOY_ES}
Last message timestamp: {LAST_QUERY_TIMESTAMP}
Time since last message: {delta_real_time_formateado}

CONVERSATION:
{conversation_text}

Please analyze the conversation and provide your results in the following YAML format:

```yaml
lead_name: The customer's full name from the conversation
summary: A brief summary of the conversation and current situation
current_stage: The current stage in the customer journey
primary_issue: The main problem or reason the customer is stalled
recommended_action: What should be done next with this lead
suggested_followup_message: A message we could send to re-engage this customer
```

Do not include any explanations or additional text outside the YAML block.""",
        
        "meta.yml": """---
name: "{recipe_name}"
description: "{description}"
version: "1.0"
author: "{author}"
created_date: "{date}"

# These MUST match exactly the fields in your prompt's YAML output
expected_yaml_keys:
  - lead_name
  - summary
  - current_stage
  - primary_issue
  - recommended_action
  - suggested_followup_message

# Define which columns appear in your output files and their order
output_columns:
  - cleaned_phone
  - lead_name
  - summary
  - current_stage
  - primary_issue
  - recommended_action
  - suggested_followup_message
  - last_message_sender
  - last_message_ts
  
# Optional: Validate enum values against expected options
validation_enums:
  current_stage:
    - INITIAL_CONTACT
    - QUALIFICATION
    - APPLICATION
    - APPROVAL
    - ONBOARDING
    - ACTIVE
    - DECLINED
  recommended_action:
    - CALL_CUSTOMER
    - SEND_WHATSAPP
    - ESCALATE
    - WAIT
    - CLOSE_LEAD

# Optional: Google Sheets integration 
# google_sheets:
#   sheet_id: "your-sheet-id-here"
#   worksheet_name: "your-worksheet-name"
""",
        
        "README.md": """# {recipe_name}

{description}

## Purpose

This recipe analyzes conversations to identify:
- [Purpose 1]
- [Purpose 2]
- [Purpose 3]

## Usage

```bash
# Run with the CLI
python -m lead_recovery.cli.main run --recipe {recipe_name}
```

## Output

The recipe produces:
- `cleaned_phone`: Phone number
- `lead_name`: Customer name
- `summary`: Conversation summary
- `current_stage`: Customer journey stage
- `primary_issue`: Main reason for stall
- `recommended_action`: Next steps
- `suggested_followup_message`: Re-engagement message

## Notes

Created by: {author}
Creation date: {date}
""",
        
        "__init__.py": "",  # Empty init file
    }
    
    # Add analyzer.py if needed
    if template_type in ["analyzer", "custom"]:
        templates["analyzer.py"] = '''import json
import re
from datetime import datetime

def analyze_conversation(conversation_messages: list) -> dict:
    """
    Analyzes a conversation based on specific criteria.
    
    Args:
        conversation_messages: A list of dictionaries, where each dictionary represents
                             a message with 'msg_from', 'message', 'creation_time', etc.
                             
    Returns:
        A dictionary containing the analysis results.
    """
    # Your custom analysis logic here
    result = {
        "lead_name": "Unknown",
        "summary": "No summary available",
        "current_stage": "UNKNOWN",
        "primary_issue": "UNKNOWN",
        "recommended_action": "WAIT",
        "suggested_followup_message": "Hello, we noticed you didn't complete your application. Can we help?"
    }
    
    # Example: Extract lead name from conversation
    for msg in conversation_messages:
        if msg.get('msg_from') == 'bot' and 'Hola' in msg.get('message', ''):
            # Example pattern: "Hola *Juan Pérez*!"
            name_match = re.search(r'Hola \\*(.*?)\\*!', msg.get('message', ''))
            if name_match:
                result["lead_name"] = name_match.group(1)
                break
    
    return result

if __name__ == '__main__':
    # Example usage
    sample_conversation = [
        {
            "cleaned_phone_number": "1234567890",
            "creation_time": "2025-05-01 10:00:00.000000 UTC",
            "msg_from": "bot",
            "message": "Hola *Juan Pérez*! 👋 Gracias por confiar en Kuna Capital."
        },
        {
            "cleaned_phone_number": "1234567890",
            "creation_time": "2025-05-01 10:01:00.000000 UTC",
            "msg_from": "user",
            "message": "Hola, quiero más información sobre el préstamo."
        }
    ]
    
    result = analyze_conversation(sample_conversation)
    print(f"Analysis result: {result}")
'''
    
    # Add __main__.py if needed
    if template_type in ["main", "custom"]:
        templates["__main__.py"] = '''#!/usr/bin/env python
"""
{recipe_name} Recipe
-----------------------------
{description}
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

# Add parent directory to path so we can import the lead_recovery package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lead_recovery.db_clients import BigQueryClient
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

# If using custom analyzer
try:
    from recipes.{recipe_name}.analyzer import analyze_conversation
except ImportError:
    analyze_conversation = None
    
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
            raise FileNotFoundError(f"Leads file not found: {{leads_file}}")
            
        df = pd.read_csv(leads_file)
        
        if 'cleaned_phone' not in df.columns:
            raise ValueError(f"CSV file {{leads_file}} missing required 'cleaned_phone' column")
            
        phone_numbers = df['cleaned_phone'].astype(str).tolist()
        logger.info(f"Loaded {{len(phone_numbers)}} phone numbers from {{leads_file}}")
        return phone_numbers
    except Exception as e:
        logger.error(f"Error loading phone numbers: {{e}}")
        raise

def query_bigquery(phone_numbers: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Query BigQuery for conversation messages for the given phone numbers.
    Returns a dictionary mapping phone numbers to their conversation messages.
    """
    if not phone_numbers:
        logger.warning("No phone numbers provided for BigQuery query")
        return {{}}
    
    # Use the BigQueryClient from lead_recovery
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
        logger.info(f"Querying BigQuery for {{len(phone_numbers)}} phone numbers")
        df = client.query(query, params=query_params)
        
        # Group by phone number
        conversations = {{}}
        for _, row in df.iterrows():
            phone = row['cleaned_phone_number']
            if phone not in conversations:
                conversations[phone] = []
                
            conversations[phone].append({{
                'cleaned_phone_number': phone,
                'creation_time': row['creation_time'],
                'msg_from': row['msg_from'],
                'operator_alias': row['operator_alias'],
                'message': row['message']
            }})
        
        logger.info(f"Retrieved conversations for {{len(conversations)}} phone numbers")
        return conversations
    except GoogleAPIError as e:
        logger.error(f"Error querying BigQuery: {{e}}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in query_bigquery: {{e}}")
        raise

def main():
    """Main entry point for the script."""
    try:
        # Define paths
        recipe_dir = Path(__file__).resolve().parent
        project_root = recipe_dir.parent.parent
        leads_file = project_root / "output_run" / "{recipe_name}" / "leads.csv"
        
        # Get current time in Mexico City timezone for output directory naming
        now = datetime.now(pytz.timezone("America/Mexico_City"))
        timestamp = now.strftime("%Y-%m-%dT%H-%M")
        
        output_dir = project_root / "output_run" / "{recipe_name}" / timestamp
        ensure_directory_exists(output_dir)
        
        # Load phone numbers
        phone_numbers = load_phone_numbers(leads_file)
        
        # Query BigQuery for conversations
        conversations = query_bigquery(phone_numbers)
        
        # Analyze conversations and prepare results
        results = []
        for phone, msgs in conversations.items():
            # Sort messages by creation_time to ensure correct analysis
            sorted_msgs = sorted(msgs, key=lambda x: x['creation_time'])
            
            # Use custom analyzer if available, otherwise use default
            if analyze_conversation:
                analysis = analyze_conversation(sorted_msgs)
            else:
                # Default simplified analysis
                analysis = {{
                    "lead_name": "Unknown",
                    "summary": "No summary available (no analyzer)",
                    "current_stage": "UNKNOWN",
                    "primary_issue": "UNKNOWN", 
                    "recommended_action": "WAIT",
                    "suggested_followup_message": "Default message"
                }}
            
            # Add results with phone number
            analysis['cleaned_phone'] = phone
            results.append(analysis)
        
        # Add missing phones (those without conversation data) to results
        conversation_phones = set(conversations.keys())
        for phone in phone_numbers:
            if phone not in conversation_phones:
                results.append({{
                    'cleaned_phone': phone,
                    'lead_name': "Unknown",
                    'summary': "No conversation found",
                    'current_stage': "UNKNOWN",
                    'primary_issue': "NO_DATA",
                    'recommended_action': "WAIT",
                    'suggested_followup_message': "Hello, we'd like to follow up on your application."
                }})
        
        # Write results to CSV
        output_file = output_dir / "{recipe_name}_results.csv"
        
        # Read meta.yml to get output columns if available
        meta_path = recipe_dir / "meta.yml"
        output_columns = None
        if meta_path.exists():
            try:
                import yaml
                with open(meta_path, 'r') as f:
                    meta_data = yaml.safe_load(f)
                    output_columns = meta_data.get('output_columns')
            except Exception as e:
                logger.warning(f"Could not read output_columns from meta.yml: {{e}}")
        
        # Use default columns if not specified in meta.yml
        if not output_columns:
            output_columns = [
                'cleaned_phone',
                'lead_name',
                'summary',
                'current_stage',
                'primary_issue',
                'recommended_action',
                'suggested_followup_message'
            ]
            
        # Write results to CSV
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=output_columns, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results)
        
        logger.info(f"Analysis complete. Results written to {{output_file}}")
        
        # Write a summary to a text file
        summary_file = output_dir / "summary.txt"
        with open(summary_file, 'w') as f:
            total_phones = len(results)
            
            f.write(f"{recipe_name} - Analysis Summary\\n")
            f.write(f"Date: {{now.strftime('%Y-%m-%d %H:%M')}}\\n")
            f.write(f"===========================================\\n\\n")
            f.write(f"Total phone numbers: {{total_phones}}\\n")
            
            # Additional statistics depend on your specific recipe
            # Add more statistics here as needed
            
        logger.info(f"Summary written to {{summary_file}}")
        
    except Exception as e:
        logger.error(f"Error in main: {{e}}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
'''

    # Write files to the recipe directory
    created_files = []
    for filename, template in templates.items():
        # Skip optional files based on template_type
        if filename == "analyzer.py" and template_type not in ["analyzer", "custom"]:
            continue
        if filename == "__main__.py" and template_type not in ["main", "custom"]:
            continue
            
        try:
            file_path = recipe_dir / filename
            with open(file_path, "w") as f:
                # Format template with variables
                content = template.format(
                    recipe_name=recipe_name,
                    description=description,
                    author=author,
                    date=datetime.now().strftime("%Y-%m-%d")
                )
                f.write(content)
            created_files.append(file_path)
            print(f"Created file: {file_path}")
        except Exception as e:
            print(f"Failed to create file {filename}: {e}")
    
    print(f"\nRecipe '{recipe_name}' created successfully with {len(created_files)} files!")
    print(f"To run this recipe: python -m lead_recovery.cli.main run --recipe {recipe_name}")
    
    # Add more comprehensive workflow instructions
    print("\nComplete Recipe Workflow:")
    print("1. Recipe files created in:")
    print(f"   {recipe_dir}/")
    
    # Check if the recipe has redshift.sql (for proper instructions)
    has_redshift = (recipe_dir / "redshift.sql").exists()
    if has_redshift:
        print("2. When you run the recipe, it will:")
        print(f"   a. Query Redshift using recipes/{recipe_name}/redshift.sql to get leads")
        print(f"   b. Save leads to output_run/{recipe_name}/leads.csv")
    else:
        print("2. Since this recipe doesn't include redshift.sql, you'll need to:")
        print(f"   a. Manually create output_run/{recipe_name}/ directory")
        print("   b. Place a leads.csv file with a 'cleaned_phone' column there")
        print("   c. Or run with: --skip-redshift flag")
    
    print("3. The recipe will then:")
    print(f"   a. Query BigQuery using recipes/{recipe_name}/bigquery.sql for conversations")
    print(f"   b. Analyze conversations using {'analyzer.py (custom logic)' if template_type in ['analyzer', 'custom'] else 'prompt.txt (LLM)'}")
    print(f"   c. Generate results in output_run/{recipe_name}/<timestamp>/analysis.csv")
    print("   d. Create a 'latest.csv' symbolic link to the most recent analysis.csv")
    
    print("\nTo check the results after running:")
    print(f"1. Look in: output_run/{recipe_name}/<timestamp>/")
    print(f"2. Or use the convenience link: output_run/{recipe_name}/latest.csv")
    
    print("\nAdvanced Recipe Customization:")
    print("1. You can specify custom filenames in meta.yml:")
    print("   ```yaml")
    print(f"   redshift_sql: {recipe_name}_redshift.sql")
    print(f"   bigquery_sql: {recipe_name}_bigquery.sql")
    print(f"   prompt_file: {recipe_name}_prompt.txt")
    print("   ```")
    print("2. This is the approach used by the simulation_to_handoff recipe.")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Create a new recipe for the Lead Recovery Pipeline")
    parser.add_argument("recipe_name", help="Name of the recipe (use underscores instead of spaces)")
    parser.add_argument("--description", "-d", default="Custom recipe for lead analysis", 
                        help="Short description of the recipe's purpose")
    parser.add_argument("--author", "-a", default=os.environ.get("USER", "Unknown"), 
                        help="Name of the recipe creator")
    parser.add_argument("--template", "-t", choices=["basic", "analyzer", "main", "custom"], default="basic",
                        help="Type of template to use: basic (minimal), analyzer (with custom analyzer.py), "
                             "main (with __main__.py), or custom (with both)")
    
    args = parser.parse_args()
    create_recipe(args.recipe_name, args.description, args.author, args.template)

if __name__ == "__main__":
    main() 