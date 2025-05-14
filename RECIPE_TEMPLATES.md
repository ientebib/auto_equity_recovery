# Recipe Templates

This document contains copy-pastable templates for creating new recipes in the Lead Recovery Pipeline.

## Directory Structure

```
recipes/your_recipe_name/
├── bigquery.sql       # REQUIRED: Query to fetch conversations
├── redshift.sql       # OPTIONAL: Query to fetch leads
├── prompt.txt         # REQUIRED: Instructions for the AI
├── meta.yml           # REQUIRED: Configuration
└── README.md          # OPTIONAL: Documentation
```

## Template: bigquery.sql

```sql
-- recipes/your_recipe_name/bigquery.sql
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
ORDER BY cleaned_phone_number, a.creation_time ASC;
```

## Template: redshift.sql

```sql
-- recipes/your_recipe_name/redshift.sql
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
LIMIT 1000;  -- Adjust limit as needed
```

## Template: prompt.txt

```
You are analyzing conversations between customers and the Kuna Capital support team on WhatsApp. 
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

Do not include any explanations or additional text outside the YAML block.
```

## Template: meta.yml

```yaml
---
name: "Your Recipe Name"
description: "Description of what this recipe analyzes"
version: "1.0"
author: "Your Name"

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
```

## Template: analyzer.py (Optional)

If you need a custom analyzer without using the LLM:

```python
# recipes/your_recipe_name/analyzer.py
# Custom analyzer for processing conversations without using an LLM

def analyze_conversations(conversation_messages: list) -> dict:
    """
    Analyzes a conversation based on specific criteria.
    
    Args:
        conversation_messages: A list of dictionaries, where each dictionary represents
                               a message with 'msg_from', 'message', etc.
                               
    Returns:
        A dictionary containing the analysis results.
    """
    # Your custom analysis logic here
    result = {
        "custom_field_1": "value1",
        "custom_field_2": "value2",
        # Add more fields as needed
    }
    
    return result
```

## Template: __main__.py (Optional)

If you need a custom main script for your recipe:

```python
#!/usr/bin/env python
"""
Custom Recipe Main Script
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path so we can import the lead_recovery package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lead_recovery.db_clients import BigQueryClient
# Import other required modules

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the custom recipe."""
    try:
        # Your custom logic here
        pass
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Running Your Recipe

Once you've created all required files:

```bash
# Run with the CLI
python -m lead_recovery.cli.main run --recipe your_recipe_name

# If you have a custom __main__.py
python -m recipes.your_recipe_name
``` 