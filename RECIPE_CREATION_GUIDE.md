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
- Processor specifications
- Output specification

## Folder Structure and Organization

### 1. Recipe Location

All recipes MUST be created as subdirectories under the `recipes/` folder in the project root:

```
lead_recovery_project/
└── recipes/
    ├── your_recipe_name/        # Your new recipe goes here
    ├── simulation_to_handoff/   # Existing recipe
    ├── marzo_cohorts_live/      # Existing recipe
    └── ...
```

### 2. Recipe Folder Structure

Each recipe folder MUST contain these specific files. The filenames can be defined in two ways:

#### Option 1: Generic Names (Default)
```
recipes/your_recipe_name/
├── bigquery.sql       # REQUIRED: BigQuery conversation fetching query
├── prompt.txt         # REQUIRED: LLM instructions
├── meta.yml           # REQUIRED: Configuration and metadata
└── redshift.sql       # OPTIONAL: Redshift lead fetching query
```

#### Option 2: Custom File Names (Specified in meta.yml)
```
recipes/your_recipe_name/
├── your_recipe_name_bigquery.sql    # REQUIRED: BigQuery query
├── your_recipe_name_prompt_v12.txt  # REQUIRED: LLM instructions
├── meta.yml                         # REQUIRED: Configuration (never renamed)
└── your_recipe_name_redshift.sql    # OPTIONAL: Redshift query
```

**Important**: If using custom filenames (Option 2), you MUST specify them in meta.yml:

```yaml
# In meta.yml
recipe_name: "your_recipe_name"
version: "2.0"
description: "Description of what this recipe analyzes"

data_input:
  lead_source_type: redshift  # Options: redshift, bigquery, csv
  redshift_config:
    sql_file: "your_recipe_name_redshift.sql"
  bigquery_config:
    sql_file: "your_recipe_name_bigquery.sql"
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

**CRITICAL:** The fields in the YAML block must exactly match those in `meta.yml` -> `llm_config.expected_llm_keys`.

**IMPORTANT:** Use placeholders like `{HOY_ES}`, `{LAST_QUERY_TIMESTAMP}`, and `{conversation_text}` which will be filled by the pipeline.

### 2.4. `meta.yml` (REQUIRED)

This file contains configuration for the recipe using the standardized Pydantic schema.

```yaml
# File: recipes/your_recipe_name/meta.yml

recipe_name: "your_recipe_name"
version: "2.0"
description: "Description of what this recipe analyzes"

# Data input configuration
data_input:
  lead_source_type: redshift  # Options: redshift, bigquery, csv
  redshift_config:
    sql_file: "redshift.sql"  # Required if lead_source_type is redshift
  # OR
  bigquery_config:
    sql_file: "bigquery.sql"  # Required if lead_source_type is bigquery
  # OR
  csv_config:
    csv_file: "leads.csv"     # Required if lead_source_type is csv

# LLM Configuration
llm_config:
  prompt_file: "prompt.txt"
  # CRITICAL: These MUST match exactly the fields in your prompt.txt YAML output
  expected_llm_keys:
    lead_name:
      description: "Full name of the customer"
      type: str
    summary:
      description: "Brief summary of the conversation"
      type: str
    current_engagement_status:
      description: "Current engagement status of the lead"
      type: str
      enum_values: [ENGAGED, STALLED, DISENGAGED]
    primary_stall_reason_code:
      description: "Primary reason the lead stalled"
      type: str
      enum_values: [NO_RESPONSE, TECHNICAL_ISSUE, CHANGED_MIND, FOUND_ALTERNATIVE, OTHER]
    next_action_code:
      description: "Next action to take for this lead"
      type: str
      enum_values: [FOLLOW_UP, OFFER_HELP, SUGGEST_ALTERNATIVE, CLOSE_LEAD]
    suggested_message:
      description: "Personalized re-engagement message"
      type: str
  # Optional: Python processor outputs to include in LLM prompt
  context_keys_from_python: []

# Python Processors Configuration
python_processors:
  - module: "lead_recovery.processors.temporal.TemporalProcessor"
    params:
      timezone: "America/Mexico_City"
  - module: "lead_recovery.processors.metadata.MessageMetadataProcessor"
    params:
      max_message_length: 150
  - module: "lead_recovery.processors.handoff.HandoffProcessor"
    params: {}

# Output Columns (defines what appears in the final CSV)
output_columns:
  - cleaned_phone
  - lead_name
  - summary
  - current_engagement_status
  - primary_stall_reason_code
  - next_action_code
  - suggested_message
  - HOURS_MINUTES_SINCE_LAST_MESSAGE
  - handoff_invitation_detected
  - handoff_response
```

## 3. Running Your Recipe

Use the standard CLI command to run your recipe:

```bash
python -m lead_recovery.cli.main run --recipe your_recipe_name
```

### Common CLI Options

- **Skip data fetching**: `--skip-redshift --skip-bigquery` (uses existing data files)
- **Skip LLM summarization**: `--skip-summarize` (runs only Python processors)
- **Limit processing**: `--limit 10` (processes only the first 10 conversations)
- **Control processors**: `--skip-processor TemporalProcessor` or `--run-only-processor HandoffProcessor`

For a complete list of CLI options, use:

```bash
python -m lead_recovery.cli.main run --help
```

For more detailed information about running recipes, see the comprehensive [Execution Guide](documentation/execution_guide.md).

## 4. Debugging and Troubleshooting

### Checking Recipe Validity

You can test that your recipe loads correctly without running it:

```bash
python test_all_recipes.py
```

### Common Issues

1. **Meta.yml Validation Fails**:
   - Check for required fields and correct data types
   - Ensure all enum_values are properly defined
   - Verify that the python_processors module paths are correct

2. **Missing Data or Empty Results**:
   - Verify that your SQL queries return the expected data
   - Check if caching is causing stale results (`--no-cache` flag)

3. **Processor Errors**:
   - Test individual processors using `--run-only-processor`
   - Check that processor parameters in meta.yml are valid

### Best Practices

1. **Start Small**: Begin with a small limit (`--limit 5`) to test your recipe
2. **Test Incrementally**: Add one processor at a time and test functionality
3. **Validate LLM Output**: Ensure the LLM output matches your expected_llm_keys
4. **Examine Raw Data**: Check leads.csv and conversations.csv to verify input data
5. **Review Console Output**: The CLI provides detailed logging about each step

## 5. Advanced Features

### Context Keys From Python Processors

You can pass processor results to the LLM prompt using `context_keys_from_python`:

```yaml
llm_config:
  prompt_file: "prompt.txt"
  expected_llm_keys:
    # ...
  context_keys_from_python: ["handoff_invitation_detected", "handoff_response"]
```

Then in your prompt.txt, use them as variables:

```
Handoff invitation: {handoff_invitation_detected}
Response to handoff: {handoff_response}
```

### Custom Output Columns

The `output_columns` field in meta.yml controls exactly which columns appear in the final CSV output, and in what order. It should include:

- Columns from lead data (e.g., `cleaned_phone`, `Asset ID`)
- LLM-generated columns (e.g., `summary`, `next_action_code`)
- Python processor-generated columns (e.g., `handoff_invitation_detected`)

### Selective Column Processing

You can override the output_columns setting at runtime with the CLI:

```bash
python -m lead_recovery.cli.main run --recipe your_recipe_name --include-columns "cleaned_phone,summary,next_action_code"
``` 