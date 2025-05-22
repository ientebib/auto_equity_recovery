# Lead Recovery Pipeline

A Python-based pipeline for analyzing lead information from Redshift and conversation history from BigQuery to identify and recover potential customers who showed initial interest but did not complete the profiling process.

## Project Overview

This pipeline automates the analysis of lead data and customer conversations using:

* **Data retrieval** from Redshift and BigQuery databases.
* **AI-powered conversation summarization** with OpenAI's LLMs.
* **Modular Python processors** for specific analysis tasks.
* **Structured output** in CSV format.
* **Recipe-based configuration** for different lead recovery scenarios.
* **(Optional) Google Sheets integration** for specific recipes.
* **Efficient caching** with SQLite to avoid redundant API calls.
* **Secure database queries** with proper parameterization.

The pipeline follows this workflow:

1. **(Optional) Fetch target leads** from Redshift based on criteria defined in the recipe's `redshift.sql`.
2. **(Optional) Read target leads** from a `leads.csv` file if the Redshift step is skipped.
3. **Fetch conversation history** for these leads from BigQuery using the recipe's `bigquery.sql`.
4. **Execute Python processors** that calculate features and analyze the conversation data.
5. **Analyze conversations** using OpenAI and the recipe's `prompt.txt` to extract structured insights (utilizing caching where possible).
6. **Generate reports** in CSV format (`analysis.csv`, `ignored.csv`) within a timestamped directory in `output_run/<recipe_name>/`.
7. **Update convenience links** (`latest.csv`, `latest_ignored.csv`) in the recipe's output directory.
8. **(Conditional) Upload `latest.csv`** to a configured Google Sheet if the recipe has Google Sheets configuration.

## Quick Start

### Running a Recipe

The standard way to run any recipe is through the CLI:

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name>
```

### Essential CLI Options

* `--recipe <recipe_name>` (required): Specifies which recipe to run
* `--recipes-dir <path>`: Override the default recipes directory location (default: recipes/ in project root)
* `--skip-redshift`: Skip fetching data from Redshift (use existing leads.csv)
* `--skip-bigquery`: Skip fetching conversations from BigQuery (use existing conversations.csv)
* `--skip-summarize`: Skip LLM summarization (Python processors only)
* `--limit <number>`: Process only the first N conversations (for testing)
* `--skip-processor <ProcessorClassName>`: Skip specific processor(s)
* `--run-only-processor <ProcessorClassName>`: Run only specific processor(s)

For a complete guide to execution options, see [documentation/execution_guide.md](documentation/execution_guide.md).

### Google Sheets Integration

The pipeline supports automatic uploading of results to Google Sheets. To use this feature:

1. **Enable required dependencies**:
   The required dependencies (`gspread`, `gspread-dataframe`, and `google-auth`) are included in the project requirements.

2. **Set up Google credentials**:
   - Create a Google Cloud service account with access to Google Sheets API
   - Download the service account JSON key file
   - Set the path to this file in your `.env`:
     ```
     GOOGLE_CREDENTIALS_PATH=/path/to/your/google-credentials.json
     ```
   - Share your target Google Sheet with the service account email (giving it Editor access)

3. **Configure in recipe's meta.yml**:
   ```yaml
   gsheets_config:
     sheet_id: "your-google-sheet-id-here"
     worksheet_name: "YourWorksheetName"  # Default: sheet's first tab
   ```

4. **Run the recipe normally**:
   ```bash
   python -m lead_recovery.cli.main run --recipe <recipe_name>
   ```
   The results will be automatically uploaded to the specified Google Sheet after processing.

The Sheet ID is the long string in your sheet's URL: `https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit`

## Recipe Structure

Recipes are defined in subdirectories under `recipes/` with the following key files:

```
recipes/your_recipe_name/
├── meta.yml          # Core configuration (processors, LLM settings, output)
├── prompt.txt        # LLM instructions 
├── bigquery.sql      # Query to fetch conversation data
└── redshift.sql      # Query to fetch target leads (optional)
```

For details on creating recipes, see [RECIPE_CREATION_GUIDE.md](RECIPE_CREATION_GUIDE.md).

## Processor Architecture

Lead Recovery uses a modular processor architecture to perform various analysis tasks:

* **TemporalProcessor**: Calculates time-based features
* **MessageMetadataProcessor**: Extracts message metadata
* **HandoffProcessor**: Analyzes handoff processes
* **TemplateDetectionProcessor**: Detects template messages
* **ValidationProcessor**: Detects pre-validation questions
* **ConversationStateProcessor**: Determines conversation state
* **HumanTransferProcessor**: Detects human transfer events

Processors are configured in each recipe's `meta.yml` file and can be controlled at runtime using CLI flags.

For detailed processor documentation, see [documentation/python_processors_guide.md](documentation/python_processors_guide.md).

## Output Control

The `output_columns` section in a recipe's `meta.yml` determines which columns appear in the final CSV report, and in what order. This list should include any desired Python-generated columns.

You can override output columns at runtime with CLI flags:
* `--include-columns "col1,col2,col3"`: Include only these columns
* `--exclude-columns "col1,col2,col3"`: Exclude these columns

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
   REDSHIFT_HOST=your-redshift-host.region.redshift.amazonaws.com
   REDSHIFT_PORT=5439
   REDSHIFT_DATABASE=your_database
   REDSHIFT_USER=your_user
   REDSHIFT_PASSWORD=your_password
   ```

## Documentation

For more detailed information, refer to the following documentation:

* [Execution Guide](documentation/execution_guide.md) - Complete guide to running recipes
* [Python Processors Guide](documentation/python_processors_guide.md) - Documentation for all processors
* [Recipe Creation Guide](RECIPE_CREATION_GUIDE.md) - How to create and configure recipes
* [PROMPTING_AND_YAML_GUIDE.md](PROMPTING_AND_YAML_GUIDE.md) - Guide to LLM prompting and configuration
* [Codebase Maintenance](documentation/codebase_maintenance.md) - Guide for maintaining and cleaning up the codebase
* [Dashboard Service Setup](documentation/dashboard_service_setup.md) - Configure the macOS launch agent

## Debugging Insights (Key Learnings)

*   **CLI Flags are Key**: Use `--skip-processor` flags (e.g., `--skip-processor TemporalProcessor`, `--skip-processor MessageMetadataProcessor`) to control which processors run. These are the primary way to control which columns are calculated.
*   **`meta.yml` Roles**: Understand the distinct roles within `meta.yml`:
    *   `expected_yaml_keys`: **Only** for validating the output requested from the LLM in `prompt.txt`. Python-generated columns *never* go here.
    *   `output_columns`: Defines the **final columns** in the output CSV. List all desired columns here (lead info, LLM fields, desired Python-generated columns).
*   **Processors vs. LLM Output**: Processors generate columns independently from the LLM analysis. The columns they generate appear in the final output only if listed in `output_columns`.
*   **Skipped Processors & Output**: If a processor is skipped via a CLI flag, but its columns are still listed in `output_columns`, the columns *will appear* in the CSV (often with N/A or empty values).
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
        │   ├── <recipe_name>_analysis.csv  # Main results
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
│   └── cache/                      # Cache data (optional)
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

*   **Control via CLI**: The primary way to enable/disable processors is through the CLI `--skip-processor` and `--run-only-processor` arguments (e.g., `--skip-processor TemporalProcessor`, `--run-only-processor HandoffProcessor`). These processor-level controls replace the older flag-based approach.
*   **Output Control via `meta.yml`**: The `output_columns` section in a recipe's `meta.yml` determines which columns ultimately appear in the final CSV report, and in what order. This list should include any desired Python-generated columns.
*   **Interaction**: If a processor is skipped using the CLI, any columns it would have generated will still be present in the output CSV if listed in `output_columns`, typically containing default values (like N/A or empty strings). To completely remove a column from the output, remove its name from the `output_columns` list in `meta.yml`.
*   **Management**: The `lead-recovery update-recipe-columns` command helps synchronize the `output_columns` in `meta.yml` with the columns expected from active processors.

### Configuration in meta.yml 

Processors are configured in the `python_processors` section of the `meta.yml` file. Each processor may have its own parameters that control its behavior:

```yaml
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
  - module: "lead_recovery.processors.template.TemplateDetectionProcessor"
    params:
      template_type: "recovery"
      skip_consecutive_count: false
  - module: "lead_recovery.processors.validation.ValidationProcessor"
    params: {}
  - module: "lead_recovery.processors.conversation_state.ConversationStateProcessor"
    params: {}
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
  
  # Python-generated columns (presence determined by this list, values depend on active processors)
  - last_message_sender
  - handoff_finalized
  - HOURS_MINUTES_SINCE_LAST_MESSAGE
```

### Update Recipe Columns CLI Command

A CLI command is available to update a recipe's `meta.yml` file with the correct columns based on the configured processors:

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
  - Check the `

## Recipe Schema Versioning

All recipes must include a `recipe_schema_version: 2` field at the root of their `meta.yml` file. This ensures compatibility with the latest schema and migration tools. If you see a schema version error, run the migration tool or update your recipe's meta.yml accordingly.

## Deprecated Features Removed
- The old `update-recipe-columns` CLI command and skip_processors.txt files are no longer used. Processor control is now handled via the `python_processors` section in meta.yml and CLI flags like `--skip-processor`.

## Processor Registry and Dynamic Output Columns

The system uses a processor registry to dynamically determine which columns are generated by each processor. When creating or updating a recipe, ensure that all desired processor-generated columns are listed in `output_columns` in meta.yml. The registry enables tools and the CLI to suggest or auto-populate these columns.

## Cache Maintenance and Pruning

The SQLite cache can be pruned automatically if it grows too large. Configure the maximum cache size in your settings. To manually clear the cache, delete the `data/cache/summary_cache.sqlite` file. The cache system is robust to journal mode issues and will fall back to DELETE mode if WAL is not supported.

## Recipe Generator CLI

Use the recipe generator CLI to create new recipes from a template:

```bash
python create_recipe.py your_recipe_name
```

This will scaffold a new recipe directory with the correct structure and schema version.

## Troubleshooting

- **Schema Version Errors:** Ensure your meta.yml includes `recipe_schema_version: 2` at the root.
- **Processor Output Columns:** If columns are missing from your output, check that they are listed in `output_columns` and that the relevant processor is active in `python_processors`.
- **Cache Issues:** If you encounter cache errors, try clearing the cache file or adjusting the journal mode in your settings.