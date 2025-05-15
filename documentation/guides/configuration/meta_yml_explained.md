# Understanding meta.yml Configuration

This guide provides a practical explanation of the `meta.yml` file structure used in Lead Recovery recipes. It explains each section with examples and best practices in a format optimized for LLM agents to understand.

## meta.yml Overview

The `meta.yml` file defines how a recipe works, including:
- Data sources
- Python processors to run
- LLM configuration
- Output columns

Every recipe's `meta.yml` file follows a Pydantic-validated schema defined in `lead_recovery/recipe_schema.py`.

## Basic Structure

At the root level, a `meta.yml` file has these components:

```yaml
recipe_name: "your_recipe_name"  # Required, must match directory name
description: "What this recipe does"  # Optional
version: "1.0"  # Optional

data_input:  # Required
  # Data source configuration

llm_config:  # Optional
  # LLM configuration

python_processors:  # Optional
  # List of processors to run

output_columns:  # Required
  # List of columns to include in output
```

## Data Input Section

The `data_input` section defines how the recipe sources its data:

```yaml
data_input:
  lead_source_type: redshift  # Required: redshift, bigquery, or csv
  
  # If using Redshift
  redshift_config:
    sql_file: "redshift.sql"
    
  # If using BigQuery
  # bigquery_config:
  #   sql_file: "bigquery.sql"
    
  # If using CSV
  # csv_config:
  #   csv_file: "input.csv"
  
  # Optional: separate SQL for conversations
  # conversation_sql_file_redshift: "conversations_redshift.sql"
  # conversation_sql_file_bigquery: "conversations_bigquery.sql"
```

Only include the config section for your chosen `lead_source_type`:
- If `lead_source_type: redshift`, include `redshift_config`
- If `lead_source_type: bigquery`, include `bigquery_config`
- If `lead_source_type: csv`, include `csv_config`

## LLM Configuration Section

The `llm_config` section defines how the LLM component works:

```yaml
llm_config:
  prompt_file: "prompt.txt"  # Optional, defaults to "prompt.txt"
  
  # Define the expected YAML output from the LLM
  expected_llm_keys:
    summary:
      description: "Summary of the conversation"
      type: str
      
    next_action:
      description: "Recommended next action"
      type: str
      enum_values: ["FOLLOW_UP", "WAIT", "CLOSE"]
      
    priority_score:
      description: "Priority score from 1-10"
      type: int
      is_optional: true  # This field is optional
      
  # List of processor-generated fields to make available in the prompt
  context_keys_from_python:
    - "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE"
    - "handoff_finalized"
    - "last_message_sender"
```

### expected_llm_keys Options

Each key in `expected_llm_keys` can have these properties:

- `description`: Human-readable explanation
- `type`: Data type (`str`, `int`, `float`, `bool`, `list`, `dict`)
- `enum_values`: List of allowed values (optional)
- `is_optional`: Whether the field is required (defaults to `false`)

## Python Processors Section

The `python_processors` section defines which analysis modules to run:

```yaml
python_processors:
  - module: "lead_recovery.processors.temporal.TemporalProcessor"
    params:
      timezone: "America/Mexico_City"
      
  - module: "lead_recovery.processors.metadata.MessageMetadataProcessor"
    params:
      max_message_length: 150
      
  - module: "lead_recovery.processors.handoff.HandoffProcessor"
    params: {}
```

Each processor entry needs:
- `module`: Full Python import path to the processor class
- `params`: Dictionary of parameters (can be empty `{}`)

The order of processors matters - they run sequentially, and later processors can access results from earlier ones.

## Output Columns Section

The `output_columns` section defines which columns appear in the final output CSV:

```yaml
output_columns:
  - lead_id
  - conversation_id
  - summary                            # From LLM
  - next_action                        # From LLM
  - HOURS_MINUTES_SINCE_LAST_MESSAGE   # From TemporalProcessor
  - last_message_sender                # From MessageMetadataProcessor
  - handoff_finalized                  # From HandoffProcessor
```

This list must include:
1. Essential lead identifier fields (e.g., `lead_id`)
2. All non-optional fields from `llm_config.expected_llm_keys` you want in the output
3. All processor-generated fields you want in the output

The order of columns in this list determines their order in the output CSV.

## Complete Example

Here's a complete example of a `meta.yml` file:

```yaml
recipe_name: handoff_analysis
description: "Analyzes conversations for handoff quality and outcomes"
version: "1.0"

data_input:
  lead_source_type: redshift
  redshift_config:
    sql_file: "redshift.sql"
  conversation_sql_file_bigquery: "conversations.sql"

llm_config:
  prompt_file: "prompt.txt"
  expected_llm_keys:
    handoff_quality:
      description: "Quality assessment of the handoff process"
      type: str
      enum_values: ["EXCELLENT", "GOOD", "NEEDS_IMPROVEMENT", "POOR"]
    issues:
      description: "Issues identified in the handoff process"
      type: str
    improvement_suggestions:
      description: "Suggestions for improving the handoff"
      type: str
      is_optional: true
  context_keys_from_python:
    - "handoff_invitation_detected"
    - "handoff_finalized"
    - "last_message_sender"

python_processors:
  - module: "lead_recovery.processors.temporal.TemporalProcessor"
    params:
      timezone: "America/Mexico_City"
  - module: "lead_recovery.processors.metadata.MessageMetadataProcessor"
    params:
      max_message_length: 150
  - module: "lead_recovery.processors.handoff.HandoffProcessor"
    params: {}

output_columns:
  - lead_id
  - conversation_id
  - handoff_invitation_detected
  - handoff_finalized
  - handoff_quality
  - issues
  - improvement_suggestions
```

## Custom Analyzer Option

For complex analysis that doesn't fit the processor model, you can use a custom analyzer:

```yaml
custom_analyzer_module: "recipes.my_recipe.analyzer.MyCustomAnalyzer"
custom_analyzer_params:
  threshold: 0.75
  mode: "detailed"
```

This should be used sparingly, as processors are preferred for most scenarios.

## Common Pitfalls to Avoid

1. **Schema Mismatch**: Always ensure `recipe_name` matches the directory name
2. **Missing Required Fields**: `recipe_name`, `data_input`, and `output_columns` are required
3. **Type Errors**: Ensure list fields are formatted as lists with hyphens, not as objects
4. **Missing Output Columns**: Include all fields you want in the final output in `output_columns`
5. **Parameter Typos**: Double-check processor parameter names against documentation
6. **Missing Expected LLM Keys**: Ensure all non-optional LLM output fields are in `output_columns`

## Validation

Recipes are validated when loaded. If you see a validation error, check:
1. The structure matches the schema
2. Required fields are present
3. Types are correct
4. Values are within allowed ranges 