# Creating a New Recipe in the Lead Recovery Project

This guide explains how to create a new recipe from scratch in the Lead Recovery project. It's designed to make it easy for LLM agents to assist in recipe creation.

## Recipe Directory Structure

A recipe is a directory with a specific set of files:

```
recipes/
└── your_recipe_name/
    ├── meta.yml           # Recipe configuration (required)
    ├── prompt.txt         # LLM prompt template (required for LLM recipes)
    ├── redshift.sql       # SQL query for Redshift (if using Redshift)
    └── bigquery.sql       # SQL query for BigQuery (if using BigQuery)
```

## Step 1: Create the Recipe Directory

First, create a directory for your recipe under the `recipes` folder:

```bash
mkdir -p recipes/your_recipe_name
```

Use a descriptive name that reflects the purpose of the recipe (e.g., `simulation_to_handoff`, `profiling_incomplete`).

## Step 2: Create the meta.yml File

The `meta.yml` file is the core configuration file for your recipe. It follows a Pydantic-validated schema.

Here's a template to start with:

```yaml
recipe_name: your_recipe_name
description: "Brief description of what this recipe does"
version: "1.0"
recipe_schema_version: 2

data_input:
  lead_source_type: redshift  # Options: redshift, bigquery, csv
  redshift_config:
    sql_file: "redshift.sql"
  # Or for BigQuery:
  # lead_source_type: bigquery
  # bigquery_config:
  #   sql_file: "bigquery.sql"
  # Or for CSV:
  # lead_source_type: csv
  # csv_config:
  #   csv_file: "input.csv"

# Only include if using LLM
llm_config:
  prompt_file: "prompt.txt"
  expected_llm_keys:
    summary:
      description: "Brief summary of the conversation"
      type: str
    next_action:
      description: "Recommended next action"
      type: str
      enum_values: ["FOLLOW_UP", "WAIT", "CLOSE"]

# Include processors you want to use
python_processors:
  - module: "lead_recovery.processors.temporal.TemporalProcessor"
    params:
      timezone: "America/Mexico_City"
  - module: "lead_recovery.processors.metadata.MessageMetadataProcessor"
    params:
      max_message_length: 150
  - module: "lead_recovery.processors.handoff.HandoffProcessor"
    params: {}

# Define output columns (must include all processor and LLM outputs you want)
output_columns:
  - lead_id
  - conversation_id
  - summary
  - next_action
  - HOURS_MINUTES_SINCE_LAST_USER_MESSAGE
  - last_message_sender
  - handoff_finalized
```

## Step 3: Create the SQL Files

Create SQL query files appropriate for your data source:

### For Redshift (redshift.sql)

```sql
-- Example Redshift query
SELECT
    lead_id,
    conversation_id,
    customer_phone,
    -- Add other fields you need
FROM
    your_schema.your_table
WHERE
    -- Add your filter conditions
    created_at >= CURRENT_DATE - 30
LIMIT 1000; -- Consider a limit for testing
```

### For BigQuery (bigquery.sql)

```sql
-- Example BigQuery query
SELECT
    lead_id,
    conversation_id,
    customer_phone,
    -- Add other fields you need
FROM
    `project.dataset.table`
WHERE
    -- Add your filter conditions
    created_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
LIMIT 1000; -- Consider a limit for testing
```

## Step 4: Create the LLM Prompt (prompt.txt)

If your recipe uses LLM, create a prompt template:

```
You are an expert at analyzing conversations with leads. Your task is to analyze the following conversation between a lead and a chatbot.

CONVERSATION:
{conversation}

Additional context:
- Hours since last user message: {HOURS_MINUTES_SINCE_LAST_USER_MESSAGE}
- Handoff was finalized: {handoff_finalized}
- Last message sender: {last_message_sender}

Provide your analysis in the following YAML format:

```yaml
summary: Brief summary of what the conversation is about
next_action: FOLLOW_UP | WAIT | CLOSE
```
```

## Step 5: Test Your Recipe

Once your files are created, test your recipe with:

```bash
python -m lead_recovery.cli.main run --recipe your_recipe_name --limit 10
```

Add `--skip-redshift --skip-bigquery` if you want to test without accessing databases initially.

## Important Considerations

### 1. Choosing Processors

Select processors based on the analysis you need:
- `TemporalProcessor`: For time-based analysis
- `MessageMetadataProcessor`: For basic message information
- `HandoffProcessor`: For detecting handoff patterns
- `TemplateDetectionProcessor`: For detecting template messages
- `ValidationProcessor`: For detecting pre-validation messages
- `ConversationStateProcessor`: For determining conversation state
- `HumanTransferProcessor`: For detecting transfers to human agents

### 2. LLM Key Configuration

For each LLM output field:
- Provide a clear description
- Set the appropriate type (str, int, float, bool)
- Use enum_values for fields with a fixed set of possible values
- Mark fields as optional with `is_optional: true` if needed

### 3. Output Columns

Ensure your `output_columns` list includes:
- Essential identifier fields (lead_id, conversation_id)
- All non-optional LLM output fields
- All processor-generated fields you want to include in the final output

## Cookbook of Common Patterns

### Analyzing Customer Intent

```yaml
llm_config:
  expected_llm_keys:
    customer_intent:
      description: "The main intent of the customer"
      type: str
      enum_values: ["INFORMATION", "PURCHASE", "COMPLAINT", "SUPPORT"]
    intent_confidence:
      description: "Confidence level in the intent classification"
      type: float
```

### Setting Up a Recovery Analysis Recipe

```yaml
python_processors:
  - module: "lead_recovery.processors.temporal.TemporalProcessor"
    params:
      timezone: "America/Mexico_City"
  - module: "lead_recovery.processors.template.TemplateDetectionProcessor"
    params:
      template_type: "recovery"
```

### Adding Custom Analyzer Module

```yaml
custom_analyzer_module: "recipes.your_recipe_name.analyzer.YourCustomAnalyzer"
custom_analyzer_params:
  threshold: 0.75
  mode: "detailed"
```

## Schema Versioning

All new recipes must include a `recipe_schema_version: 2` field at the root of meta.yml. This is required for validation and migration tooling.

## Using the Processor Registry

When defining `output_columns`, use the processor registry to ensure all columns generated by your active processors are included. See the Python Processors Guide for details on using the registry.

### Troubleshooting
- **Schema Version Errors:** Ensure your meta.yml includes `recipe_schema_version: 2` at the root.
- **Missing Columns:** Use the processor registry to check which columns are generated by each processor and include them in `output_columns`. 