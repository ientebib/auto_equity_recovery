# Lead Recovery Recipe Creation Guide

## Quick Reference

```bash
# Recipe creation steps
1. Create directory: recipes/your_recipe_name/
2. Add SQL files: redshift.sql, bigquery.sql
3. Create prompt: prompt.txt
4. Define metadata: meta.yml
5. Run: python -m lead_recovery.cli.main run --recipe your_recipe_name
```

## Introduction

This guide provides clear, step-by-step instructions for creating and running recipes in the Lead Recovery pipeline. It focuses on avoiding common pitfalls and ensuring consistent behavior.

## What Is A Recipe?

A recipe is a self-contained configuration for analyzing a specific set of customer conversations. It consists of:

- SQL queries to fetch data
- A prompt for AI analysis
- Configuration metadata
- Output specification

## Folder Structure and Organization

### 1. Recipe Location

All recipes MUST be created as subdirectories under the `recipes/` folder in the project root:

```
lead_recovery_project/
└── recipes/
    ├── your_recipe_name/        # Your new recipe goes here
    ├── simulation_to_handoff/   # Existing recipe
    ├── diana_originacion_mayo/  # Existing recipe
    └── ...
```

### 2. Recipe Folder Structure

Each recipe folder MUST contain these specific files. The filenames can be defined in two ways:

#### Option 1: Generic Names (Default)
```
recipes/your_recipe_name/
├── bigquery.sql       # REQUIRED: BigQuery conversation fetching query
├── prompt.txt         # REQUIRED: LLM instructions (for standard recipes)
├── meta.yml           # REQUIRED: Configuration and metadata
├── redshift.sql       # OPTIONAL: Redshift lead fetching query
├── analyzer.py        # OPTIONAL: Custom analysis logic (for custom recipes)
└── __main__.py        # OPTIONAL: Custom processing script (for custom recipes)
```

#### Option 2: Custom File Names (Specified in meta.yml)
```
recipes/your_recipe_name/
├── your_recipe_name_bigquery.sql    # REQUIRED: BigQuery query
├── your_recipe_name_prompt_v12.txt  # REQUIRED: LLM instructions
├── meta.yml                         # REQUIRED: Configuration (never renamed)
├── your_recipe_name_redshift.sql    # OPTIONAL: Redshift query
└── analyzer.py                      # OPTIONAL: Custom logic (never renamed)
```

**Important**: If using custom filenames (Option 2), you MUST specify them in meta.yml:

```yaml
# In meta.yml
redshift_sql: your_recipe_name_redshift.sql
bigquery_sql: your_recipe_name_bigquery.sql
prompt_file: your_recipe_name_prompt_v12.txt
```

**Note**: The simulation_to_handoff recipe (our most robust recipe) uses Option 2 with custom filenames specified in meta.yml.

### 3. Output Structure

When you run a recipe, it generates output in this structure:

```
output_run/your_recipe_name/     # Created automatically when the recipe runs
├── YYYY-MM-DDTHH-MM/           # Timestamped folder for each run
│   ├── analysis.csv            # Main results file
│   └── ignored.csv             # (Optional) Filtered/error records
├── latest.csv                  # Symbolic link to most recent analysis.csv
├── latest_ignored.csv          # Symbolic link to most recent ignored.csv
├── leads.csv                   # Phone numbers being analyzed
└── conversations.csv           # Raw conversation data from BigQuery
```

The pipeline may also create additional files:
- `your_recipe_name_analysis_YYYYMMDD.csv` - Dated copies of analysis results
- `your_recipe_name_analysis_YYYYMMDD.html` - HTML report version
- `your_recipe_name_analysis_YYYYMMDD_report.csv` - Specialized report format
- `cache.csv` - Cache data to avoid reprocessing unchanged conversations

- The pipeline will automatically create the `output_run/your_recipe_name/` directory when needed
- Each run creates a new timestamped subfolder to preserve history
- The `latest.csv` symbolic link always points to the most recent analysis.csv file
- The `latest_ignored.csv` symbolic link points to the most recent ignored.csv file

## 1. Create Recipe Directory

First, create a directory for your recipe:

```bash
mkdir -p recipes/your_recipe_name
```

## 2. Create Required Files

### 2.1. `bigquery.sql` (REQUIRED)

This file defines how to fetch conversation data from BigQuery.

```sql
-- File: recipes/your_recipe_name/bigquery.sql

-- This query MUST return these exact column names:
-- - cleaned_phone_number (or a column will be converted to this)
-- - creation_time
-- - msg_from
-- - message

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
  AND a.creation_time >= TIMESTAMP('2025-04-01 00:00:00')
ORDER BY cleaned_phone_number, a.creation_time ASC;
```

**CRITICAL:** The `@target_phone_numbers_list` parameter is provided by the pipeline. Your query must include it.

**IMPORTANT:** Column names must match exactly as shown above - the code expects these specific names.

### 2.2. `redshift.sql` (OPTIONAL)

This file fetches the list of phone numbers to analyze. If not provided, you must manually supply a `leads.csv` file.

```sql
-- File: recipes/your_recipe_name/redshift.sql

-- This query MUST produce a result with at least one column:
-- - cleaned_phone (or a column that can be converted to this)

SELECT 
    RIGHT(phone_number, 10) as cleaned_phone,
    lead_id,
    -- Other columns you need
FROM your_redshift_table
WHERE your_condition = 'your_value'
LIMIT 1000;
```

**IMPORTANT:** The `cleaned_phone` column is required, either directly or by converting another column.

### 2.3. `prompt.txt` (REQUIRED)

This file contains instructions for the AI model to analyze conversations.

```
File: recipes/your_recipe_name/prompt.txt

You are a conversation analyzer for Kuna Capital. Analyze the conversation below and extract key information.

Current date: {HOY_ES}
Last message timestamp: {LAST_QUERY_TIMESTAMP}
Time since last message: {delta_real_time_formateado}

CONVERSATION:
{conversation_text}

Please provide your analysis in valid YAML format with the following fields:
```yaml
lead_name: Full name of the customer
summary: Brief summary of the conversation
current_engagement_status: One of [ENGAGED, STALLED, DISENGAGED]
primary_stall_reason_code: One of [NO_RESPONSE, TECHNICAL_ISSUE, CHANGED_MIND, FOUND_ALTERNATIVE, OTHER]
next_action_code: One of [FOLLOW_UP, OFFER_HELP, SUGGEST_ALTERNATIVE, CLOSE_LEAD]
suggested_message: A personalized message to re-engage the customer
```

Ensure all fields are present and accurately represent the conversation.
```

**CRITICAL:** The fields in the YAML block must exactly match those in `meta.yml` -> `expected_yaml_keys`.

**IMPORTANT:** Use placeholders like `{HOY_ES}`, `{LAST_QUERY_TIMESTAMP}`, and `{conversation_text}` which will be filled by the pipeline.

### 2.4. `meta.yml` (REQUIRED)

This file contains configuration for the recipe.

```yaml
# File: recipes/your_recipe_name/meta.yml

name: "Your Recipe Name"
description: "Description of what this recipe analyzes"
version: "1.0"

# CRITICAL: These MUST match exactly the fields in your prompt.txt YAML output
expected_yaml_keys:
  - lead_name
  - summary
  - current_engagement_status
  - primary_stall_reason_code
  - next_action_code
  - suggested_message

# Define which columns appear in output files and their order
output_columns:
  - cleaned_phone
  - lead_name
  - summary
  - current_engagement_status
  - primary_stall_reason_code
  - next_action_code
  - suggested_message
  - last_message_sender
  - last_message_ts

# Optional: For enum validation (ensures values match expected options)
validation_enums:
  primary_stall_reason_code:
    - NO_RESPONSE
    - TECHNICAL_ISSUE
    - CHANGED_MIND
    - FOUND_ALTERNATIVE
    - OTHER
  next_action_code:
    - FOLLOW_UP
    - OFFER_HELP
    - SUGGEST_ALTERNATIVE
    - CLOSE_LEAD

# Optional: Google Sheets integration
google_sheets:
  sheet_id: "your-google-sheet-id"
  worksheet_name: "your-target-worksheet-name"
```

**CRITICAL:** The `expected_yaml_keys` list MUST exactly match all the fields your prompt instructs the AI to output.

## 3. Authentication Setup

### 3.1. BigQuery Authentication

The project uses Google Cloud's Application Default Credentials (ADC) mechanism. 

**IMPORTANT:** Use `BigQueryClient` from `lead_recovery.db_clients` instead of creating your own client!

```python
# CORRECT WAY:
from lead_recovery.db_clients import BigQueryClient
client = BigQueryClient()
df = client.query(query, params=query_params)

# WRONG WAY - will cause authentication issues:
from google.cloud import bigquery
client = bigquery.Client()  # DON'T do this!
```

If you encounter authentication errors:

1. Ensure `GOOGLE_APPLICATION_CREDENTIALS` environment variable is set to your service account JSON path.
2. Or use the `GOOGLE_CREDENTIALS_PATH` in your `.env` file.
3. Check the service account has BigQuery permissions.

## 4. Running Your Recipe

### 4.1. Command for Running

Always use this command format for reliability:

```bash
python -m lead_recovery.cli.main run --recipe your_recipe_name
```

### 4.2. Important Options

- `--skip-redshift`: Skip fetching from Redshift (use existing leads.csv)
- `--skip-bigquery`: Skip fetching from BigQuery (use existing conversations)
- `--skip-summarize`: Skip LLM analysis (data fetch only)
- `--no-use-cache`: Force re-analysis with OpenAI (don't use summarization cache)
- `--max-workers 5`: Limit concurrent API calls (lower = slower but more reliable)

## 5. Understanding the Output

All output is stored in `output_run/your_recipe_name/`:

- Timestamped folders (e.g., `2025-05-09T14-30/`):
  - `analysis.csv`: Main results file
  - `ignored.csv`: (Optional) Filtered/error records
- `latest.csv`: Symlink to most recent analysis.csv
- `latest_ignored.csv`: Symlink to most recent ignored.csv
- `leads.csv`: Phone numbers being analyzed
- `conversations.csv`: Raw conversation data from BigQuery

## 6. Debugging Common Issues

### 6.1. BigQuery Authentication Errors

**Error:** `Access Denied: Project m-infra: User does not have bigquery.jobs.create permission`

**Solution:**
1. Always use `lead_recovery.db_clients.BigQueryClient()`
2. Set `GOOGLE_APPLICATION_CREDENTIALS` to your service account JSON file
3. Run with proper authentication: `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json python -m lead_recovery.cli.main run --recipe your_recipe_name`

### 6.2. Missing or Incorrect Columns

**Error:** `KeyError: 'cleaned_phone_number'` or similar

**Solution:**
1. Check your SQL query columns match what the code expects
2. Make sure column names match: `cleaned_phone_number`, `msg_from`, `message`, `creation_time`
3. Use SQL aliases if needed: `SELECT your_column AS cleaned_phone_number, ...`

### 6.3. YAML Parsing Errors

**Error:** Missing keys in results or validation errors

**Solution:**
1. Ensure `expected_yaml_keys` in `meta.yml` matches exactly what your prompt asks the AI to produce
2. Verify your prompt instructions are clear about required YAML format
3. Check that validation_enums values match what your prompt expects

## 7. Example Recipe

For reference, see existing recipes:
- `recipes/simulation_to_handoff/`: Complex recipe with Google Sheets integration
- `recipes/diana_originacion_mayo/`: Simple recipe for template detection 

## 8. Testing Your Recipe

Before running on a large dataset:

1. Test with a small sample of phone numbers (10-20)
2. Check the BigQuery SQL results manually before processing
3. Verify AI prompt outputs expected YAML structure
4. Examine final CSV output to ensure all fields are present

## 9. Using the Recipe Generator Script

The easiest way to create a new recipe is to use the provided `create_recipe.py` script, which will automatically create all required files with the proper structure:

```bash
# Basic recipe (using LLM with prompt.txt)
python create_recipe.py your_recipe_name --description "Your recipe description" --author "Your Name"

# Custom recipe with analyzer.py (Python-based analysis)
python create_recipe.py your_recipe_name --template analyzer --description "Description" --author "Your Name"

# Fully custom recipe with analyzer.py and __main__.py
python create_recipe.py your_recipe_name --template custom --description "Description" --author "Your Name"
```

The script will:
1. Create the recipe directory: `recipes/your_recipe_name/`
2. Generate all required files with correct templates
3. Properly format placeholders and variables
4. Print detailed instructions for running the recipe

### Generator Output

After running the script, you'll see:
- The location of all created files
- Step-by-step instructions for using the recipe
- Where to find the output files

For example:
```
Recipe 'test_recipe' created successfully with 6 files!
To run this recipe: python -m lead_recovery.cli.main run --recipe test_recipe

Complete Recipe Workflow:
1. Recipe files created in:
   recipes/test_recipe/
2. When you run the recipe, it will:
   a. Query Redshift using recipes/test_recipe/redshift.sql to get leads
   b. Save leads to output_run/test_recipe/leads.csv
3. The recipe will then:
   a. Query BigQuery using recipes/test_recipe/bigquery.sql for conversations
   b. Analyze conversations using prompt.txt (LLM)
   c. Generate results in output_run/test_recipe/<timestamp>/test_recipe_results.csv
   d. Create a 'latest.csv' symbolic link to the most recent results

To check the results after running:
1. Look in: output_run/test_recipe/<timestamp>/
2. Or use the convenience link: output_run/test_recipe/latest.csv
```

## Conclusion

Following this guide will help you create reliable recipes that consistently produce the expected results. Always verify your SQL queries and prompt instructions to ensure they match the expected column names and output format. 