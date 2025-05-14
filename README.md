# Lead Recovery Pipeline

A Python-based pipeline for analyzing lead information from Redshift and conversation history from BigQuery to identify and recover potential customers who showed initial interest but did not complete the profiling process.

## Project Overview

This pipeline automates the analysis of lead data and customer conversations using:

* **Data retrieval** from Redshift and BigQuery databases.
* **AI-powered conversation summarization** with OpenAI's LLMs.
* **Structured output** in CSV format.
* **Recipe-based configuration** for different lead recovery scenarios.
* **(Optional) Google Sheets integration** for specific recipes.
* **Efficient caching** with SQLite to avoid redundant API calls.
* **Secure database queries** with proper parameterization.

The pipeline follows this workflow:

1. **(Optional) Fetch target leads** from Redshift based on criteria defined in the recipe's `redshift.sql`.
2. **(Optional) Read target leads** from a `leads.csv` file if the Redshift step is skipped.
3. **Fetch conversation history** for these leads from BigQuery using the recipe's `bigquery.sql`.
4. **Analyze conversations** using OpenAI and the recipe's `prompt.txt` to extract structured insights (utilizing caching where possible).
5. **Generate reports** in CSV format (`analysis.csv`, `ignored.csv`) within a timestamped directory in `output_run/<recipe_name>/`.
6. **Update convenience links** (`latest.csv`, `latest_ignored.csv`) in the recipe's output directory.
7. **(Conditional) Upload `latest.csv`** to a configured Google Sheet if the recipe has Google Sheets configuration.

## Debugging Insights (Key Learnings)

*   **CLI Flags are Key**: Use `--skip-...` flags (e.g., `--skip-redshift`, `--skip-metadata-extraction`, `--skip-temporal-flags`) to control which parts of the pipeline run and which Python flags are calculated. These are the primary way to toggle Python flag calculations.
*   **`meta.yml` Roles**: Understand the distinct roles within `meta.yml`:
    *   `expected_yaml_keys`: **Only** for validating the output requested from the LLM in `prompt.txt`. Python flags *never* go here.
    *   `output_columns`: Defines the **final columns** in the output CSV. List all desired columns here (lead info, LLM fields, desired Python flags).
*   **Python Flags vs. LLM Output**: Python flags (metadata, temporal, detection) are calculated separately from the LLM analysis. Their appearance in the final output depends on whether they are listed in `output_columns`.
*   **Skipped Python Flags & Output**: If a Python flag calculation is skipped via a CLI flag, but its column is still listed in `output_columns`, the column *will appear* in the CSV (often with N/A or empty values).
*   **Guides**: Refer to `PROMPTING_AND_YAML_GUIDE.md` and `RECIPE_CREATION_GUIDE.md` for detailed configuration and creation instructions.

## Recipe Creation and Standardization

**IMPORTANT: FOLLOW THESE GUIDELINES WHEN CREATING NEW RECIPES**

### Recipe Types and Structure

We now support two standardized recipe types:

1. **Standard Recipes** (LLM-based analysis):
   - Required files: `bigquery.sql`, `prompt.txt`, `meta.yml`
   - Optional files: `redshift.sql`
   - Use the core pipeline's built-in LLM processing

2. **Custom Recipes** (Python-based analysis):
   - Required files: `bigquery.sql`, `meta.yml`, `analyzer.py`
   - Optional files: `redshift.sql`, `__main__.py`
   - Use custom Python code for specialized analysis

### Folder Structure Quick Reference

```
lead_recovery_project/            # Project root
├── recipes/                      # All recipes go here
│   └── your_recipe_name/         # Create your recipe here
│       ├── bigquery.sql          # Default filename for BigQuery query
│       ├── prompt.txt            # Default filename for LLM instructions
│       ├── meta.yml              # REQUIRED: Configuration (specify custom filenames here)
│       ├── redshift.sql          # Default filename for Redshift query
│       └── analyzer.py           # Optional: For custom Python analysis
└── output_run/                   # Output goes here (created automatically)
    └── your_recipe_name/         # Created when recipe runs
        ├── YYYY-MM-DDTHH-MM/     # Timestamped results
        │   ├── analysis.csv      # Main results file
        │   └── ignored.csv       # (Optional) Filtered/error records
        ├── latest.csv            # Link to latest analysis.csv
        ├── latest_ignored.csv    # Link to latest ignored.csv
        ├── leads.csv             # Lead data
        └── conversations.csv     # Conversation data
```

**Note**: Custom filename pattern used in simulation_to_handoff (our most robust recipe):
```yaml
# In meta.yml
redshift_sql: simulation_to_handoff_redshift.sql
bigquery_sql: simulation_to_handoff_bigquery.sql
prompt_file: simulation_to_handoff_prompt_v12.txt
```

### Mandatory Output Structure

All recipes MUST generate outputs in this standardized structure:

```
output_run/<recipe_name>/
├── <timestamp>/                # e.g., 2025-05-09T14-30/
│   ├── <recipe_name>_results.csv  # Main results
│   └── summary.txt              # Summary statistics
├── latest.csv                  # Symbolic link to most recent results
├── leads.csv                   # Phone numbers being analyzed
└── cache/                      # Cache data (optional)
```

### Recipe Creation Tools

Use these tools to ensure consistency when creating new recipes:

1. **Recipe Creation Guide**: Detailed instructions in `RECIPE_CREATION_GUIDE.md`
2. **Recipe Templates**: Copy-pastable templates in `RECIPE_TEMPLATES.md`
3. **Recipe Generator**: Automatic recipe creator: `python create_recipe.py your_recipe_name`

**LLM INSTRUCTIONS:** When modifying or creating recipes, reference these files to ensure standardization. ALWAYS use the BigQueryClient from lead_recovery.db_clients when accessing BigQuery to avoid authentication issues.

## Recent Enhancements (May 2025)

* **Python-based message metadata extraction**: Message metadata fields (`last_message_sender`, `last_user_message_text`, `last_kuna_message_text`, `last_message_ts`) are now extracted directly in Python rather than by the LLM, improving accuracy and reducing token usage.
* **Customizable output columns**: You can now precisely control which columns appear in your output CSV and HTML files by defining an `output_columns` list in your recipe's `meta.yml`. This allows you to:
  * Remove technical fields like `conversation_digest` from the output
  * Control the exact order of columns in your output files
  * Ensure consistent output structure across different runs
* **Recipe-specific conversation filtering**: Added recipe-specific content filtering to process only relevant conversations:
  * The `top_up_may` recipe now only processes conversations containing specific top-up template messages (e.g., pre-approved credit offers), skipping all others to improve analysis focus
  * Other recipes can implement similar filtering by adding custom detection logic in `analysis.py`
* **Enhanced reporting**: Report generation now respects the `output_columns` configuration from `meta.yml`
* **Improved error handling**: Better handling of cached results when conversation formats vary or unexpected issues arise

## Python Flag Modularity

The Lead Recovery system allows control over which Python-calculated flags are generated.

*   **Control via CLI**: The primary way to enable/disable Python flag calculations is through the CLI `--skip-...` arguments (e.g., `--skip-temporal-flags`, `--skip-metadata-extraction`). These flags are passed down through the pipeline.
*   **Output Control via `meta.yml`**: The `output_columns` section in a recipe's `meta.yml` determines which columns ultimately appear in the final CSV report, and in what order. This list should include any desired Python-generated columns.
*   **Interaction**: If a Python flag's calculation is skipped using a CLI flag, but its column name remains listed in `output_columns`, the column will still be present in the output CSV, typically containing default values (like N/A or empty strings). To completely remove a Python flag's column from the output, remove its name from the `output_columns` list in `meta.yml`.
*   **Management**: The `lead-recovery update-recipe-columns` command can help synchronize the `output_columns` in `meta.yml` with the flags expected to be active (though CLI overrides at runtime still take precedence for *calculation*).

### Configuration in meta.yml (Reference for `update-recipe-columns`)

While CLI flags control the *runtime calculation*, the `python_flags` section in `meta.yml` might be used by tools like `update-recipe-columns` to manage the default state of `output_columns`. It serves as a reference for the intended default configuration.

```yaml
# Python Flags Configuration (Used as reference, CLI flags override runtime calculation)
python_flags:
  # Temporal flags
  skip_temporal_flags: false
  skip_detailed_temporal: false
  skip_hours_minutes: false
  skip_reactivation_flags: false
  skip_timestamps: false
  skip_user_message_flag: false
  
  # Message metadata
  skip_metadata_extraction: false
  
  # Handoff detection
  skip_handoff_detection: false
  skip_handoff_invitation: false
  skip_handoff_started: false
  skip_handoff_finalized: false
  
  # Other detections
  skip_human_transfer: false
  skip_recovery_template_detection: false
  skip_topup_template_detection: true  # Skip this specific function
  skip_consecutive_templates_count: false
```

### Output Columns in meta.yml

The `output_columns` section in `meta.yml` defines the final structure of the output CSV. List all desired columns here, including Python-generated ones.

```yaml
output_columns:
  # Core lead info
  - cleaned_phone
  - name
  
  # LLM-generated columns
  - summary
  - primary_stall_reason_code
  
  # Python-generated columns (presence determined by this list, values depend on CLI skip flags)
  - last_message_sender
  - handoff_finalized
  - HOURS_MINUTES_SINCE_LAST_MESSAGE
```

### Update Recipe Columns CLI Command

A new CLI command has been added to update a recipe's `meta.yml` file with the correct Python flag columns based on enabled/disabled flags:

```bash
lead-recovery update-recipe-columns <recipe_name>
```

Options:
- `--dry-run`: Show changes without writing them
- `--verbose`: Show detailed output

To update all recipes at once:

```bash
lead-recovery update-recipe-columns update-all
```

## Installation

### Prerequisites

* Python 3.10 or higher
* Access credentials for:
  * Redshift database (if not skipping Redshift steps)
  * Google Cloud (BigQuery and potentially Google Sheets)
  * OpenAI API
* `gcloud` CLI installed and configured (for ADC authentication method)

### Setup

1. **Clone the repository:**
   ```bash
   git clone [repository-url]
   cd lead_recovery_project
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv fresh_env
   source fresh_env/bin/activate  # On Windows: fresh_env\Scripts\activate
   ```

3. **Install dependencies (choose one method):**
   
   Using pip:
   ```bash
   pip install -r requirements.txt
   pip install -e .  # Install package in development mode
   ```
   
   Using Poetry (recommended):
   ```bash
   pip install poetry
   poetry install
   ```

4. **Configure authentication:**

   Create a `.env` file in the project root with the following variables (see `.env-sample` for an example):
   ```
   # OpenAI API key for summarization
   OPENAI_API_KEY=your-openai-api-key

   # Google service account credentials path
   GOOGLE_CREDENTIALS_PATH=/path/to/your/google-credentials.json
   # Or set the standard GOOGLE_APPLICATION_CREDENTIALS env var

   # Redshift credentials
   REDSHIFT_HOST=your-redshift-host
   REDSHIFT_DATABASE=your-redshift-database
   REDSHIFT_USER=your-redshift-username
   REDSHIFT_PASSWORD=your-redshift-password
   ```

## Usage

### Run the Pipeline with the CLI

The project has a modular CLI structure with the following commands:

```bash
# Full pipeline for a specific recipe
lead-recovery run --recipe <recipe_name>

# Individual steps
lead-recovery fetch-leads --output-dir <dir>
lead-recovery fetch-convos --output-dir <dir>
lead-recovery summarize --output-dir <dir>
lead-recovery report --output-dir <dir> --format html
```

Common options for the `run` command:
* `--skip-redshift`: Skip fetching leads from Redshift
* `--skip-bigquery`: Skip fetching conversations from BigQuery
* `--skip-summarize`: Skip the OpenAI summarization step
* `--output-dir PATH`: Set a custom output directory (defaults to project's `output_run/`)
* `--max-workers INT`: Set the maximum number of concurrent workers for OpenAI calls
* `--no-use-cached-redshift`: Force fetch from Redshift even if cached data exists
* `--no-cache`: Disable summarization cache for forced refresh
* `--ignore-redshift-marker`: Ignore existing Redshift marker and run query (even if already run today)

### Common Command Examples

**Most reliable way to run the recipe:**
```bash
python -m lead_recovery.cli.main run --recipe simulation_to_handoff
```

**Run with limited API calls (testing with fewer workers):**
```bash
python -m lead_recovery.cli.main run --recipe simulation_to_handoff --max-workers 2
```

**Run using cached conversations (skip BigQuery):**
```bash
python -m lead_recovery.cli.main run --recipe simulation_to_handoff --skip-bigquery
```

**Run using cached leads data (skip Redshift):**
```bash
python -m lead_recovery.cli.main run --recipe simulation_to_handoff --skip-redshift
```

**Run fresh analysis ignoring all caches:**
```bash
python -m lead_recovery.cli.main run --recipe simulation_to_handoff --no-cache --no-use-cached-redshift
```

**Run only data retrieval steps (skip LLM analysis):**
```bash
python -m lead_recovery.cli.main run --recipe simulation_to_handoff --skip-summarize
```

**Force reanalyze with OpenAI (only for conversations that changed):**
```bash
python -m lead_recovery.cli.main run --recipe simulation_to_handoff --skip-redshift --skip-bigquery --no-cache
```

**Force new Redshift query (even if already run today):**
```bash
python -m lead_recovery.cli.main run --recipe simulation_to_handoff --ignore-redshift-marker
```

**Skip specific Python flag calculations (e.g., topup template detection):**
```bash
python -m lead_recovery.cli.main run --recipe simulation_to_handoff --skip-topup-template-detection
```

### Run with Automation Script

You can also use the automation script:

```bash
python automate_pipeline.py <recipe_name>
```

This script:
1. Sets up the environment and credentials automatically
2. Runs the specified recipe
3. Creates a marker file to avoid re-querying Redshift on the same day
4. Logs all activity to `cron_lead_recovery.log`

## Recipes and Output Locations

Recipes are configuration directories under `recipes/` that define:

* `redshift.sql`: Query to fetch target leads from Redshift.
* `bigquery.sql`: Query to fetch conversations from BigQuery.
* `prompt.txt`: Instructions for the OpenAI model to analyze conversations.
* `meta.yml`: Configuration including expected keys to extract and optional Google Sheets settings.

### Customizing Output Columns

You can customize which columns appear in your final output files by defining the `output_columns` list in your recipe's `meta.yml` file. The system will output only the columns you specify, in the exact order you define:

```yaml
# meta.yml output columns example
output_columns:
  # Core lead info 
  - lead_id
  - user_id
  - name
  - phone
  
  # Analysis data
  - summary
  - primary_stall_reason_code
  - next_action_code
  - suggested_message
  
  # Python-detected metadata
  - last_message_sender
  - last_user_message_text
  - last_message_ts
```

Benefits of customizing output columns:
* Remove technical fields like `conversation_digest` from user-facing reports
* Ensure the most important fields appear first in spreadsheets
* Create cleaner, more focused reports for different stakeholders

### Output Locations

When you run a recipe, the output is stored in:
```
output_run/<recipe_name>/
```

Inside each recipe's output directory, you'll find:
* `latest.csv` - Always points to the most recent analysis results
* `latest_ignored.csv` - Contains any leads that were filtered out
* Time-stamped folders (e.g., `2025-05-06T14-30/`) - Contains that specific run's data
* `cache.csv` - Stores cached results to avoid re-analyzing unchanged conversations

### Google Sheets Integration

**IMPORTANT:** Currently, only the `simulation_to_handoff` recipe automatically uploads to Google Sheets by default.

The `latest.csv` file from this recipe is automatically uploaded to:
* Sheet ID: `1466ljSang2OBqqgn6XWGVXUS2JQ7VPcbEJ6eYYG-WO8`
* Worksheet: `perfAp-handoff`

For other recipes, you can enable Google Sheets uploads by adding a `meta.yml` file to the recipe directory:

```yaml
google_sheets:
  sheet_id: "your-sheet-id-here"
  worksheet_name: "your-worksheet-name"
expected_yaml_keys:
  - key1
  - key2
  # ... other expected keys
```

Without this configuration, recipes will save data locally only, with no Google Sheets upload.

## Codebase Structure

The project has been refactored for better maintainability and optimization:

* **CLI (`lead_recovery/cli/`)**: Modular command-line interface
  * `main.py`: CLI entry point
  * `fetch_leads.py`: Command for fetching leads from Redshift
  * `fetch_convos.py`: Command for fetching conversations from BigQuery
  * `summarize.py`: Command for summarizing conversations with OpenAI
  * `report.py`: Command for generating reports
  * `run.py`: Command for running the full pipeline
* **Config (`config.py`)**: Centralized settings from environment variables with injectable settings for testing
* **Database Access (`db_clients.py`)**: Redshift and BigQuery clients with optimized memory usage and proper query parameterization
* **File System Utilities (`fs.py`)**: File operations including symbolic links
* **Google Sheets Integration (`gsheets.py`)**: Uploads CSV data to configured Google Sheets
* **Cache Management (`cache.py`)**: Efficient caching with SQLite to avoid redundant API calls
* **Analysis (`analysis.py`)**: Core conversation analysis and summarization
* **Summarizer (`summarizer.py`)**: OpenAI integration with accurate token handling via tiktoken
* **Reporting (`reporting.py`)**: Functions for generating CSV and HTML reports with column filtering
* **CI/CD**: GitHub Actions workflow for automated testing

## Key Improvements

* **Security**: Fixed SQL injection vulnerabilities with proper query parameterization
* **Performance**: Added SQLite-based `SummaryCache` to prevent redundant OpenAI API calls
* **Accuracy**: Replaced character-based token counting with tiktoken for accurate measurement
* **Architecture**: Restructured CLI from monolithic file into modular commands
* **Efficiency**: Moved message metadata extraction from LLM to Python for better accuracy and lower token usage
* **Customization**: Added output column filtering to control which columns appear in final CSV and HTML files
* **Redshift Marker System**: Added a per-recipe marker system to prevent redundant Redshift queries:
  * Creates a `redshift_queried_<recipe_name>_<date>.marker` file after successful queries
  * Automatically detects and skips Redshift for recipes without a `redshift.sql` file
  * Provides `--ignore-redshift-marker` flag to force a fresh query when needed
  * Includes a utility script `test_marker_system.py` for managing markers
  * See `REDSHIFT_MARKER_SYSTEM.md` for detailed documentation
* **Selective Python Processing**: For performance-sensitive recipes, detailed Python-based temporal flag calculations (e.g., `HOURS_MINUTES_SINCE_LAST_MESSAGE`) can now be skipped. This is controlled by adding a `behavior_flags` section to the recipe's `meta.yml`:
  ```yaml
  # In your recipe's meta.yml
  behavior_flags:
    skip_detailed_temporal_processing: true
  ```
  When `skip_detailed_temporal_processing` is `true`, only essential timestamps (`LAST_MESSAGE_TIMESTAMP_TZ`, `LAST_USER_MESSAGE_TIMESTAMP_TZ`) and the `NO_USER_MESSAGES_EXIST` flag are computed by the core Python analysis, potentially speeding up recipes that do not require fine-grained temporal analysis for their LLM prompts or direct output. Other Python-derived fields like `last_message_sender`, `last_user_message_text`, `last_kuna_message_text`, and `handoff_finalized` are still calculated.
* **CI/CD**: Added GitHub Actions workflow for continuous integration
* **Testability**: Made settings injectable via get_settings() for better testability
* **Logging**: Added proper error logging with exc_info=True for complete tracebacks
* **Organization**: Moved scripts into proper package structure

## Cron Job Setup

The project is designed to be run on a schedule using cron. The `automate_pipeline.py` script handles all the necessary environment setup and runs the specified recipe.

Example cron entry (runs `simulation_to_handoff` recipe every hour from 10am to 6pm on weekdays):

```
0 10-18 * * 1-5 cd /path/to/lead_recovery_project && python automate_pipeline.py simulation_to_handoff >> cron_lead_recovery.log 2>&1
```

The script includes (commented out) code to enforce business hours in Mexico City time zone.

## Troubleshooting

* **Authentication Errors:** Check your `.env` file for proper credentials (like `GOOGLE_CREDENTIALS_PATH`, `OPENAI_API_KEY`) or ensure the standard `GOOGLE_APPLICATION_CREDENTIALS` environment variable is correctly set and points to a valid service account JSON key file. The service account needs appropriate permissions for BigQuery and, if used, Google Sheets.
   
* **Google Sheets Errors:** If upload to Google Sheets fails:
  - Ensure the service account has Editor access to the sheet
  - Verify the sheet ID and worksheet name in `meta.yml` or for `simulation_to_handoff` 

* **OpenAI API Key Issues:** The OpenAI API key is now optional for starting up, but still required for the summarization step.

* **BigQuery Memory Errors:** If you encounter memory issues with large result sets, the system now streams results in chunks.

* **Column Filtering Issues:** If your output is missing expected columns or has technical columns you don't want:
  - Check the `output_columns` list in your recipe's `meta.yml` file
  - Make sure the column names match exactly what's in your data
  - Remember that column ordering in the output follows the exact order in `output_columns`

* **Logs:** Check `cron_lead_recovery.log` for detailed execution information.

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=lead_recovery

# Run specific test file
pytest tests/test_cli.py
```

### Configuring and Running Recipes

This guide explains how to set up and run new or existing recipes for the lead recovery pipeline.

**1. Understanding Recipes**

A recipe is a self-contained set of configurations that defines a specific lead recovery task. Each recipe is a directory located under `recipes/`. It tells the pipeline:
*   Which leads to target.
*   How to fetch their conversation history.
*   How to interpret and summarize these conversations using AI.
*   What specific information to extract.
*   Which columns to include in the final output files.

**2. Recipe Directory Structure**

To create a new recipe, create a new directory inside the `recipes/` folder (e.g., `recipes/my_new_campaign`). Each recipe directory should contain the following files:

*   **`redshift.sql`** (Optional)
    *   **Purpose**: Defines the SQL query to fetch the initial list of target leads from your Redshift database.
    *   **Output**: This query should produce a CSV file named `leads.csv` in the `output_run/<recipe_name>/` directory.
    *   **Key Columns**: Minimally, it should output a column containing phone numbers. The pipeline internally expects this column to be named or aliased as `cleaned_phone` after normalization (typically 10-digit numbers).
    *   **Skipping**: If you skip the Redshift step (e.g., using `--skip-redshift` or if this file is absent), you must manually provide a `leads.csv` file in `output_run/<recipe_name>/` with at least a `cleaned_phone` column.

*   **`bigquery.sql`**
    *   **Purpose**: Defines the SQL query to fetch conversation history for the leads identified by `redshift.sql` (or your provided `leads.csv`).
    *   **Input**: The query uses a list of phone numbers (`@target_phone_numbers_list`) passed by the pipeline.
    *   **CRUCIAL - Column Naming**: The column names you define in this SQL query *must* align with what the Python processing scripts in `lead_recovery/analysis.py` and `lead_recovery/summarizer.py` expect. Mismatches will lead to `KeyError` exceptions.
        *   **Phone Number**: Ensure one column contains the phone number, typically aliased as `cleaned_phone_number` or `cleaned_phone`. The pipeline will attempt to normalize this.
        *   **Message Content**: The actual text of the message is expected in a column named `message`. If your database uses a different name, alias it (e.g., `SELECT your_msg_column AS message, ...`).
        *   **Sender**: A column indicating the sender (e.g., `user` or `kuna`) is usually named `msg_from`.
        *   **Timestamp**: A message creation timestamp column, e.g., `creation_time`.
    *   **Output**: This query populates `output_run/<recipe_name>/conversations.csv`.

*   **`prompt.txt`**
    *   **Purpose**: Contains the instructions and template for the AI model (OpenAI LLM) to analyze and summarize each conversation.
    *   **Dynamic Variables**: You can use placeholders like `{HOY_ES}`, `{LAST_QUERY_TIMESTAMP}`, and `{conversation_text}` which will be injected by the pipeline.
    *   **Output Format**: This prompt *must* instruct the AI to return its analysis in a **valid YAML format**. The keys used in this YAML output are critical.

*   **`meta.yml`** (Highly Recommended)
    *   **Purpose**: Provides metadata and configuration for the recipe.
    *   **`expected_yaml_keys`**: This is a **critical** list. It must exactly match all the top-level keys that your `prompt.txt` instructs the AI to output in its YAML response. If these don't match, parsing will fail, or data will be incomplete.
        ```yaml
        expected_yaml_keys:
          - lead_name
          - summary
          - current_engagement_status
          # ... and all other keys from your prompt's YAML output
        ```
    *   **`output_columns`**: (New) Defines which columns to include in the final output and their order:
        ```yaml
        output_columns:
          - lead_id
          - summary
          - next_action_code
          # ... all columns you want in the output, in desired order
        ```
    *   **`google_sheets`** (Optional): If you want to upload the final `analysis.csv` to Google Sheets, configure it here:
        ```yaml
        google_sheets:
          sheet_id: "your-google-sheet-id"
          worksheet_name: "your-target-worksheet-name"
        ```
    *   **Other fields**: `name`, `description` for recipe identification.

## Recipe Organization and Uniformity Guidelines

### Maintaining Recipe Consistency

To ensure consistency across all recipes and simplify maintenance:

1. **Choose the Appropriate Recipe Type**:
   - **Standard Recipes**: Use for most cases where LLM-based analysis is sufficient. Requires only SQL files, prompt.txt, and meta.yml.
   - **Custom Recipes**: Use only when standard analysis can't handle your requirements. This adds analyzer.py for custom Python analysis.

2. **Why Some Recipes Have Python Scripts**:
   - **analyzer.py**: Used for custom recipes that require specific pattern detection or complex logic beyond what an LLM can do
   - **__main__.py**: Used for recipes with completely custom workflows that deviate from the standard pipeline

3. **Standardization Instructions for LLMs**:
   - When modifying existing recipes: Maintain the current pattern (standard vs. custom)
   - When creating new recipes: Default to standard recipes unless specific requirements necessitate custom code
   - Always follow the structure in RECIPE_CREATION_GUIDE.md and RECIPE_TEMPLATES.md

4. **Outputs Must Be Consistent**:
   - All recipes MUST create results with a common filename pattern: `<recipe_name>_results.csv`
   - All recipes MUST include a summary.txt with standard statistics
   - All recipes MUST update a "latest.csv" symbolic link to the most recent results

5. **Recipe Utilities**:
   - For quick recipe creation: `python create_recipe.py your_recipe_name --template basic`
   - For custom analyzers: `python create_recipe.py your_recipe_name --template analyzer`
   - For fully custom recipes: `python create_recipe.py your_recipe_name --template custom`

### Example Recipe Types

**Standard Recipe (diana_originacion_mayo)**:
- Uses built-in LLM analysis with prompt.txt
- Standard meta.yml configuration
- Simple pattern detection

**Custom Recipe (sample_recipe)**:
- Uses custom analyzer.py with Python logic
- More complex pattern detection
- Still follows standard output format

## Documentation

* [Main README](README.md) - This file, with overview of the entire project
* [Recipe Creation Guide](RECIPE_CREATION_GUIDE.md) - Detailed guide for creating new recipes
* [Recipe Templates](RECIPE_TEMPLATES.md) - Copy-pastable templates for recipe files
* [Prompting & YAML Guide](PROMPTING_AND_YAML_GUIDE.md) - Guide for working with prompts and YAML

## License

[Specify your license information]

## Contact

Kavak
