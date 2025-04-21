# Lead Recovery Analysis Script

This script analyzes lead information from Redshift and conversation history from BigQuery to identify leads who showed initial interest but did not complete the profiling stage.

## Overview

The script performs the following actions:
1. Retrieves a batch of target leads from Redshift who haven't completed profiling.
2. Queries BigQuery for conversation history associated with those leads' phone numbers.
3. Merges the data and uses OpenAI to summarize each lead's conversation history.
4. Outputs the combined data (lead details + conversation summaries) to CSV and HTML reports.

## Prerequisites

- Python >=3.10 # Updated version
- Access to Redshift and BigQuery databases
- OpenAI API key
- Google Cloud service account with BigQuery access

## Installation

1. Clone this repository:
```bash
git clone [repository-url]
cd lead_recovery_project
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
   - For running the pipeline:
   ```bash
   pip install .
   ```
   - For development (including linters, formatters, testing tools):
   ```bash
   pip install .[dev]
   ```

4. **Set up environment variables:** Create a `.env` file in the project root by copying `.env.example` (if provided) or manually adding the required variables. See the `Configuration` section below for details. Populate it with your credentials for Redshift, Google Cloud, and OpenAI.

## Usage

The script provides several commands that should generally be run in sequence:

```bash
# Optional: Fetch latest leads from Redshift (creates output_run/leads.csv)
lead-recovery fetch-leads

# Fetch conversations for leads in leads.csv (creates output_run/conversations.csv)
lead-recovery fetch-convos

# Summarize conversations and merge data (creates output_run/analysis.csv and analysis.html)
lead-recovery summarize

# Alternatively, just regenerate the final reports if analysis.csv exists
lead-recovery report
```

Intermediate files are stored in the `output_run` directory (configurable via `OUTPUT_DIR` in `.env` or `config.py`).

## Project Structure

```
lead_recovery_project/
├── lead_recovery/          # Main package source code
│   ├── sql/                # SQL query files
│   │   ├── redshift_query.sql
│   │   └── bigquery_query.sql
│   ├── prompts/            # Prompt templates (e.g., for OpenAI)
│   │   └── openai_prompt.txt
│   ├── cli.py              # Command-line interface (using Typer)
│   ├── config.py           # Configuration settings (using Pydantic)
│   ├── db_clients.py       # Database connection handlers
│   ├── summarizer.py       # OpenAI summarization logic
│   ├── reporting.py        # Report generation (CSV, HTML)
│   └── utils.py            # Utility functions
├── output_run/             # Default directory for output files
│   ├── leads.csv
│   ├── conversations.csv
│   └── analysis.csv
│   └── analysis.html
├── .env                    # Local environment variables (MUST BE CREATED)
├── .gitignore
├── pyproject.toml          # Project metadata and dependencies (PEP 621)
├── README.md               # This file
└── ... (linter/formatter config files, etc.)
```

## Output Files

The script generates the following key files in the `output_run` directory:
- `leads.csv`: Raw lead data fetched from Redshift.
- `conversations.csv`: Conversation history fetched from BigQuery.
- `analysis.csv`: The final merged data including lead details and conversation summaries.
- `analysis.html`: An HTML version of the final analysis report for easier viewing.

The `analysis.csv` includes columns like:
- `lead_id`: Unique identifier for the lead from Redshift
- `user_id`: User identifier from Redshift
- `create_date`: Date the lead was created
- `name`: First name of the lead
- `last_name`: Last name of the lead
- `cleaned_phone_number`: Normalized phone number used for matching
- `summary`: AI-generated summary of the conversation history

(Exact columns depend on the Redshift query defined in `sql/redshift_query.sql`.)

## Error Handling & Retries

The script incorporates:
- Robust error handling for database connections, queries, and file operations.
- Automatic retries with exponential backoff for OpenAI API calls using the `tenacity` library.
- Clear logging of errors and progress.

## Performance

- Concurrent API calls to OpenAI using `concurrent.futures.ThreadPoolExecutor` during the `summarize` step.
- (Future/Planned) Concurrent fetching of conversation data from BigQuery.
- Progress bars (`tqdm`) for long-running operations.

## SQL Queries

The script uses SQL queries stored in the `lead_recovery/sql/` directory:

1. `redshift_query.sql`: Defines which leads to fetch from Redshift based on criteria like creation date, product interest, and profiling status.
2. `bigquery_query.sql`: Fetches conversation history from BigQuery for the phone numbers identified in the Redshift query.

*Important:* Ensure the phone number cleaning/formatting logic (e.g., `RIGHT(phone_number, 10)`) is consistent between both SQL queries and any Python cleaning functions (`utils.clean_phone`) to allow for correct joining of data.

## Configuration

Configuration is managed via `lead_recovery/config.py` using Pydantic, loading values from environment variables or a `.env` file.

**Required `.env` Variables:**
```dotenv
# Redshift Credentials
REDSHIFT_HOST=your-redshift-host
REDSHIFT_DATABASE=your-redshift-database
REDSHIFT_USER=your-redshift-username
REDSHIFT_PASSWORD=your-redshift-password
REDSHIFT_PORT=5439

# BigQuery Credentials (Absolute path to your service account JSON key file)
# Ensure this service account has BigQuery read permissions.
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/gcp-service-account-key.json

# OpenAI API Key
OPENAI_API_KEY=sk-...
```

**Optional Configuration (can be set in `.env` or defaults used from `config.py`):**
- `TIME_WINDOW_DAYS`: How far back to look for leads (default: 90).
- `BQ_BATCH_SIZE`: Number of phone numbers per BigQuery request (default: 500).
- `OUTPUT_DIR`: Directory for output files (default: `output_run`).
- `BQ_MAX_CONCURRENT_QUERIES`: Max parallel BigQuery jobs (relevant for Phase 3 optimization, default TBD).

## Troubleshooting

Common issues:

1. **`FileNotFoundError` for `.env`:** Ensure you have created a `.env` file in the project root and populated it with your credentials.
2. **Database Connection Errors:** Double-check credentials, hostnames, ports in `.env`. Verify network connectivity and firewall rules. Ensure the `GOOGLE_APPLICATION_CREDENTIALS` path is correct and the service account has BigQuery permissions.
3. **Authentication Errors (OpenAI):** Ensure the `OPENAI_API_KEY` is correct and has not expired.
4. **Missing Data / No Summaries:** Check the `TIME_WINDOW_DAYS` setting. Verify the SQL queries correctly identify target leads and conversations. Ensure phone number formats match between Redshift and BigQuery.
5. **Performance Issues:** For large datasets, the `fetch-convos` and `summarize` steps can take time. Monitor logs for progress. Consider adjusting `BQ_BATCH_SIZE` or `max_workers` for the `summarize` command.

## Development

- **Linting/Formatting:** Uses `ruff`, `black`, and `isort`. Run `pre-commit run --all-files` to check and format code.
- **Testing:** Uses `pytest`. (Note: No tests currently included in the repository.)
- **Dependencies:** Managed with `pyproject.toml`. Use `pip-compile` (from `pip-tools`) to generate lock files (`requirements.txt`, `requirements-dev.txt`).

## License

[Specify License - e.g., MIT, Apache 2.0, Proprietary]

## Author

Kavak (Adapted) 