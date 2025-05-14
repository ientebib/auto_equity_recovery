# Lead Recovery Pipeline: Prompting & YAML Configuration Guide

## Overview

This guide explains how to work with prompts and YAML configurations in the Lead Recovery Pipeline. The system uses a combination of:

1. **Prompt templates**: Instructions for the LLM to analyze conversations
2. **meta.yml files**: Configuration for each recipe, defining expected outputs and validation rules
3. **Python processing**: Handling data extraction, preparation, and post-processing

## Understanding the Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│  Data Sources   │ => │  Lead Recovery  │ => │  Output Files   │
│ (Redshift, BQ)  │    │     Engine      │    │  (CSV, HTML)    │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
             ┌────────────────┼────────────────┐
             │                │                │
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │                 │ │                 │ │                 │
    │  Prompts (.txt) │ │   meta.yml      │ │  Python Code    │
    │                 │ │                 │ │                 │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Part 1: Prompt Templates

Prompt templates (stored as `.txt` files in each recipe folder) provide instructions to the LLM for analyzing conversation data.

### Best Practices for Prompts

1. **Structure clearly**: Use sections, headers, and formatting to make instructions clear
2. **Define expected output format**: Specify the exact YAML structure expected
3. **Provide examples**: Include example analyses for common scenarios
4. **Keep context concise**: Remove unnecessary text to save tokens
5. **Focus on analysis tasks**: Don't ask the LLM to extract basic metadata (use Python instead)

### Important Note: Message Metadata Extraction

As of May 2025, **message metadata is extracted by Python code**, not the LLM. This includes:
- `last_message_sender`
- `last_user_message_text`
- `last_kuna_message_text`
- `last_message_ts`

DO NOT ask the LLM to extract these fields in your prompts. This saves tokens and improves accuracy.

### Recipe-Specific Conversation Filtering

The system now supports recipe-specific conversation filtering in Python, allowing you to process only the most relevant conversations for each recipe:

#### Top-Up May Campaign Filtering

The `top_up_may` recipe includes specialized filtering to only process conversations containing specific top-up template messages. Conversations without these templates are automatically skipped with the status `SKIPPED_NO_TOPUP_TEMPLATE`. The system looks for patterns such as:

- Messages containing "pre aprobado" credit offers
- Messages thanking for good payment behavior or client history
- Messages with specific formatting patterns (e.g., "Hola [NAME]! 👋")

This filtering happens before the LLM processing step, saving API calls and focusing analysis only on relevant conversations.

#### Adding Custom Filtering to Your Recipe

To implement similar filtering for your recipe:

1. Add custom detection logic in `lead_recovery/analysis.py` within the `summarize_group_df` function
2. Follow the pattern used for other recipes: 
   ```python
   if current_recipe_name == "your_recipe_name":
       # Your custom filtering logic here
       # If conversation should be skipped:
       if not meets_your_criteria:
           return {
               CLEANED_PHONE_COLUMN_NAME: phone,
               "cache_status": "SKIPPED_YOUR_REASON",
               # Add other necessary fields
           }
   ```
3. Update your meta.yml to ensure output_columns includes "cache_status" to see which conversations were skipped

This approach allows each recipe to implement specialized filtering rules while maintaining a common processing framework.

### Example Prompt Snippet

```
# =====================================================================================
# ROLE: Analista de Conversaciones
# =====================================================================================

Analiza la siguiente conversación entre un cliente (user) y Kuna (bot). 
Tu tarea es generar un resumen estructurado en formato YAML.

## INSTRUCCIONES ESPECÍFICAS

1. Identifica el estado actual de la conversación
2. Determina las razones principales de estancamiento
3. Recomienda acciones basadas en el contexto

## FORMATO DE SALIDA

Debes generar un resultado en formato YAML con estos campos:
- summary: Breve resumen de la situación actual (1-2 oraciones)
- timing_reasoning: Análisis de cuándo y por qué se detuvo la conversación
- inferred_stall_stage: Etapa específica donde se detuvo el proceso
...
```

## Part 2: YAML Configuration (meta.yml)

Each recipe has a `meta.yml` file that configures how the recipe should behave, including:
- Recipe identification
- Data sources
- Expected LLM output fields
- Output column configuration
- Validation rules

### Key Sections in meta.yml

#### Basic Configuration

```yaml
name: "simulation_to_handoff_v17"
dashboard_title: "Recuperación Simulación-Hand-Off v17 (Time Aware)"
prompt_file: simulation_to_handoff_prompt_v12.txt
summary_format: YAML
```

#### Expected YAML Keys

This section defines the fields the system expects in the LLM's YAML output:

```yaml
expected_yaml_keys:
  - summary
  - timing_reasoning
  - inferred_stall_stage
  - primary_stall_reason_code
  - prior_reactivation_attempt_count
  - reactivation_status_assessment
  # Example: Python-generated fields should NOT be listed here.
  # If they were previously, they should be commented out or removed.
  # - last_message_sender  # Incorrect: This is Python-generated
  # - last_user_message_text # Incorrect: This is Python-generated
  # - last_kuna_message_text # Incorrect: This is Python-generated
  # - last_message_ts      # Incorrect: This is Python-generated
  - transfer_context_analysis
  - next_action_code
  - next_action_context
  - suggested_message_es
```

**Important:**
*   This list is **exclusively** for keys the LLM is instructed to return in its YAML output.
*   Python-generated flags (e.g., `last_message_sender`, `human_transfer_detected_by_python`, temporal flags like `HOURS_MINUTES_SINCE_LAST_MESSAGE`) **must NOT** be listed in `expected_yaml_keys`. Including them will cause validation errors, as the LLM does not produce these.
*   Only include fields that the LLM directly produces.

#### Output Columns

This section defines which columns appear in the final CSV output, and in what order:

```yaml
output_columns:
  # Core lead info (example)
  - lead_id
  - user_id
  - lead_created_at
  - name
  - last_name
  - cleaned_phone
  
  # LLM Analysis Output (must match keys from 'expected_yaml_keys')
  - summary
  - timing_reasoning
  # ... more LLM-generated columns ...
  - next_action_code 
  
  # Python-generated fields (examples)
  - last_message_sender         # Example Python-generated field
  - last_user_message_text    # Example Python-generated field
  - last_kuna_message_text    # Example Python-generated field
  - last_message_ts           # Example Python-generated field
  - human_transfer_detected_by_python # Example Python-generated flag
  - HOURS_MINUTES_SINCE_LAST_MESSAGE # Example Python-generated temporal flag
  - cache_status                # For monitoring cache usage
```

**Note:**
*   Include ALL columns here that should appear in the output CSV. This includes core lead information, LLM-generated fields (from `expected_yaml_keys`), and any Python-generated flags you wish to have in the final report.
*   The order of columns in this list determines their order in the output CSV.
*   **Handling of Skipped Python Flags**: If a Python flag's calculation is skipped (e.g., via a `--skip-metadata-extraction` CLI option), but its corresponding column name *is still listed* in `output_columns`, the column will appear in the CSV, typically with an empty string, "N/A", or a default value.
*   If you want a Python flag (whether its calculation was skipped or not) to be **completely absent** from the final CSV output, you must remove its column name from this `output_columns` list.

#### Validation Enums (Optional)

For fields with a fixed set of possible values:

```yaml
validation_enums:
  primary_stall_reason_code:
    - "PRENDA_ENCONTRADA"
    - "VEHICULO_ANTIGUO_KM"
    # ... more values ...
```

## Part 3: Recipe Development Workflow

### Creating a New Recipe

1. **Create directories**:
   ```
   mkdir -p recipes/my_new_recipe
   ```

2. **Create base files**:
   - `meta.yml`: Configuration file
   - `prompt.txt`: LLM instructions
   - `redshift.sql` or `bigquery.sql`: Data source query

3. **Configure meta.yml**:
   - Set recipe name and description
   - Define expected output fields
   - Configure output columns

4. **Develop the prompt**:
   - Clearly define the analysis task
   - Specify the exact YAML structure
   - ONLY ask for fields the LLM should analyze (not basic metadata)

5. **Test & Refine**:
   ```
   python -m lead_recovery.cli.main run --recipe my_new_recipe --limit 10
   ```

### Modifying an Existing Recipe

1. **Update the prompt**:
   - Improve clarity of instructions
   - Refine examples and expected output format
   - Remember NOT to ask for fields handled by Python

2. **Update meta.yml**:
   - Ensure `expected_yaml_keys` matches fields in the prompt
   - Comment out any fields handled by Python
   - Include all desired fields in `output_columns`

3. **Test iteratively**:
   ```
   # Run with limited data for faster testing
   python -m lead_recovery.cli.main run --recipe my_recipe --skip-redshift --max-workers 2
   
   # Run with full pipeline
   python -m lead_recovery.cli.main run --recipe my_recipe
   ```

## Part 4: Command-Line Options

### Using the Cache

The system caches conversation analysis results to avoid reprocessing unchanged conversations:

```bash
# Default (uses cache)
python -m lead_recovery.cli.main run --recipe my_recipe

# Force fresh analysis (ignore cache)
python -m lead_recovery.cli.main run --recipe my_recipe --no-use-cache

# Skip fetching new data, use cached data files
python -m lead_recovery.cli.main run --recipe my_recipe --skip-redshift --skip-bigquery
```

### Parallel Processing

Adjust worker count for faster processing:

```bash
# Use 4 parallel workers (default is 8)
python -m lead_recovery.cli.main run --recipe my_recipe --max-workers 4
```

### Debugging

For debugging issues:

```bash
# Run on a small subset of data 
python -m lead_recovery.cli.main run --recipe my_recipe --limit 10

# Run with specific leads
python -m lead_recovery.cli.main run --recipe my_recipe --phones 5551234567,5559876543
```

## Troubleshooting

### Missing Fields in Output

If fields are missing in the output:
1. Check if they're in `output_columns` in meta.yml
2. For LLM-generated fields, verify they're in `expected_yaml_keys`
3. For Python-generated fields, ensure the Python code is extracting them

### YAML Validation Warnings

If you see warnings like "YAML Validation issues detected":
1. Ensure `expected_yaml_keys` only contains fields the LLM is asked to generate
2. Fields handled by Python should be commented out in `expected_yaml_keys`
3. Check the prompt to ensure it's not asking the LLM for those fields

### Performance Issues

If the pipeline is slow:
1. Use the cache where possible (`--use-cache`)
2. Increase parallelism (`--max-workers`)
3. Simplify prompts to reduce token usage
4. Offload more work to Python (e.g., metadata extraction)

## Conclusion

By properly configuring prompts and YAML files, you can effectively customize the Lead Recovery Pipeline for different use cases. Remember these key principles:

1. Prompts focus on analysis tasks, not basic data extraction
2. Python handles message metadata extraction and other routine tasks
3. meta.yml connects everything together and defines the output format

For questions or assistance, refer to the README.md or contact the team. 