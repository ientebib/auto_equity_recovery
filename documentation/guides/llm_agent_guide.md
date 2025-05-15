# Guide for LLM Agents Working with Lead Recovery

This guide is specifically designed for LLM agents (like Claude) using Cursor to help users with the Lead Recovery codebase. It provides quick reference information to help you respond accurately to user queries about running, modifying, or creating recipes.

## Project Overview

The Lead Recovery Project analyzes conversations with leads to determine their status and recommend follow-up actions. The system uses:

1. **Recipes**: Configuration directories that define analysis pipelines
2. **Processors**: Python modules that extract features from conversations
3. **LLM Analysis**: OpenAI-powered summarization and classification
4. **Data Sources**: Redshift/BigQuery/CSV for lead and conversation data

## Quick Reference for Common Tasks

### Running a Recipe

When a user asks you to run a recipe:

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name>
```

Common options to suggest:
- `--limit 10` (for testing with limited data)
- `--skip-redshift --skip-bigquery` (to use cached data)
- `--skip-summarize` (to skip LLM calls)
- `--no-cache` (for fresh LLM analysis)

### Creating a New Recipe

When a user asks to create a new recipe:

1. Create the recipe directory:
   ```bash
   mkdir -p recipes/new_recipe_name
   ```

2. Create the required files:
   - `meta.yml` (configuration)
   - `prompt.txt` (LLM prompt)
   - `redshift.sql` and/or `bigquery.sql` (data queries)

3. Suggest testing with:
   ```bash
   python -m lead_recovery.cli.main run --recipe new_recipe_name --limit 5
   ```

### Modifying a Recipe's Configuration

When a user wants to modify a recipe's configuration, edit the `meta.yml` file in the recipe directory. Always ensure:

1. The `recipe_name` matches the directory name
2. All required fields are present
3. The `output_columns` list includes all fields needed in the output
4. The prompt and expected LLM output keys match

## Core Documentation Paths

When you need to look up information to help users:

- **Running Recipes**: `documentation/guides/running_recipes/`
- **Creating Recipes**: `documentation/guides/creating_recipes/`
- **Configuration Details**: `documentation/guides/configuration/`
- **Processor Reference**: `documentation/python_processors_guide.md`
- **Schema Reference**: `documentation/meta_yml_schema_guide.md`

## How to Answer Common User Questions

### "How do I run a recipe?"

```
You can run a recipe with this command:

python -m lead_recovery.cli.main run --recipe recipe_name

For testing, add --limit 10 to process only 10 conversations.
```

### "How do I create a new recipe?"

```
To create a new recipe:

1. Create the directory: mkdir -p recipes/your_recipe_name
2. Create meta.yml with the required configuration
3. Create prompt.txt for the LLM
4. Create SQL files for data fetching
5. Test with: python -m lead_recovery.cli.main run --recipe your_recipe_name --limit 5
```

### "What processors are available?"

```
Available processors include:

- TemporalProcessor: Time-based analysis
- MessageMetadataProcessor: Message content extraction
- HandoffProcessor: Handoff detection
- TemplateDetectionProcessor: Template message detection
- ValidationProcessor: Pre-validation detection
- ConversationStateProcessor: Conversation state analysis
- HumanTransferProcessor: Human transfer detection

You can configure these in the meta.yml file's python_processors section.
```

### "How do I modify a prompt?"

```
To modify a prompt:

1. Edit the prompt.txt file in the recipe directory
2. Ensure the YAML structure in the prompt matches the expected_llm_keys in meta.yml
3. Include context variables from processors with {variable_name} syntax
4. Test your changes with: python -m lead_recovery.cli.main run --recipe recipe_name --limit 5 --no-cache
```

## File Locations for Quick Reference

- **Recipe Configurations**: `recipes/<recipe_name>/meta.yml`
- **Recipe Prompts**: `recipes/<recipe_name>/prompt.txt`
- **SQL Queries**: `recipes/<recipe_name>/redshift.sql` or `recipes/<recipe_name>/bigquery.sql`
- **Output Files**: `output_run/<recipe_name>/latest.csv` (symlink to the most recent analysis file, e.g., `output_run/<recipe_name>/<timestamp>/analysis.csv`). A dated CSV like `output_run/<recipe_name>/<recipe_name>_analysis_<date>.csv` is also generated.
- **Processors**: `lead_recovery/processors/`
- **Schema Definition**: `lead_recovery/recipe_schema.py`
- **Main CLI**: `lead_recovery/cli/main.py`

## Troubleshooting Common Issues

When a user encounters errors, check:

1. **Recipe Loading Errors**: Validate the meta.yml against the schema
2. **Missing Files**: Ensure all required files exist in the recipe directory
3. **Processor Errors**: Check processor parameters and dependencies
4. **LLM Format Errors**: Verify prompt.txt and meta.yml LLM key definitions match
5. **Output Column Errors**: Ensure all expected columns are in the output_columns list

## Using Parameters in Commands

When suggesting commands with parameters, replace placeholders:

```
# DO NOT suggest:
python -m lead_recovery.cli.main run --recipe <recipe_name>

# INSTEAD suggest:
python -m lead_recovery.cli.main run --recipe simulation_to_handoff
```

If you don't know the exact value, ask the user:

```
Which recipe would you like to run? Once you tell me the recipe name, I can provide the exact command.
``` 