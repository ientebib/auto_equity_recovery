# Lead Recovery Pipeline

A Python-based pipeline for analyzing lead information from Redshift and conversation history from BigQuery to identify and recover potential customers who showed initial interest but did not complete the profiling process.

## Project Overview

This pipeline automates the analysis of lead data and customer conversations using:
- **Data retrieval** from Redshift and BigQuery databases
- **AI-powered conversation summarization** with OpenAI's LLMs
- **Structured output** in CSV and HTML formats
- **Recipe-based configuration** for different lead recovery scenarios

The pipeline follows this workflow:
1. Fetch target leads from Redshift based on configurable criteria
2. Retrieve conversation history for these leads from BigQuery
3. Analyze conversations using OpenAI to extract:
   - Summarized conversations
   - Stall reasons (why the lead didn't proceed)
   - Key interactions
   - Suggested follow-up actions
4. Generate reports in CSV and HTML formats

## Installation

### Prerequisites
- Python 3.10 or higher
- Access credentials for:
  - Redshift database
  - BigQuery database
  - OpenAI API

### Setup

1. Clone the repository:
```bash
git clone [repository-url]
cd lead_recovery_project
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the package:
   - For running the pipeline:
   ```bash
   pip install .
   ```
   - For development (including linters, formatters, testing tools):
   ```bash
   pip install .[dev]
   ```

4. Create a `.env` file in the project root with your credentials:
```
# Redshift Credentials
REDSHIFT_HOST=your-redshift-host
REDSHIFT_DATABASE=your-redshift-database
REDSHIFT_USER=your-redshift-username
REDSHIFT_PASSWORD=your-redshift-password
REDSHIFT_PORT=5439

# BigQuery Credentials
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/gcp-service-account-key.json

# OpenAI API Key
OPENAI_API_KEY=sk-your-openai-api-key
```

## Usage

### Command-Line Interface

The package installs a `lead-recovery` command-line tool with the following subcommands:

#### Individual Steps
```bash
# Fetch leads from Redshift
lead-recovery fetch-leads [--since YYYY-MM-DD] [--output-dir PATH]

# Fetch conversations from BigQuery
lead-recovery fetch-convos [--batch-size N] [--output-dir PATH]

# Summarize conversations using OpenAI
lead-recovery summarize [--max-workers N] [--prompt-template PATH] [--output-dir PATH]

# Generate HTML report from analysis.csv
lead-recovery report [--output-dir PATH]
```

#### Recipe-Based Execution
```bash
# Run the complete pipeline using a specific recipe
lead-recovery run --recipe RECIPE_NAME [--since YYYY-MM-DD] [--output-dir PATH]

# Run with optional skip flags
lead-recovery run --recipe RECIPE_NAME --skip-redshift --skip-bigquery --skip-summarize
```

### Output Files

The pipeline generates these files in the output directory:
- `leads.csv`: Raw lead data from Redshift
- `conversations.csv`: Conversation history from BigQuery
- `analysis.csv`: The final merged data with AI-generated summaries
- `analysis.html`: An HTML formatted report for easier viewing

## Recipe System

The project uses a recipe-based approach to configure different lead recovery scenarios:

### Recipe Structure
Each recipe is a directory under `recipes/` containing:
- `redshift.sql`: Query to select leads from Redshift
- `bigquery.sql`: Query to fetch conversations from BigQuery
- `prompt.txt`: OpenAI prompt template for summarization
- `meta.yml`: Configuration metadata for the recipe

### Available Recipes
- `profiling_incomplete`: Targets leads who initiated but didn't complete profiling
- `handoffapp_to_bill`: Targets leads in the handoff application process

### Creating New Recipes
1. Create a new directory under `recipes/`
2. Add the required files (redshift.sql, bigquery.sql, prompt.txt, meta.yml)
3. Configure the meta.yml with appropriate settings

## Core Components

### Database Clients
- `RedshiftClient`: Handles connections and queries to Redshift
- `BigQueryClient`: Manages BigQuery operations with pagination support

### Conversation Summarizer
Uses OpenAI's API to analyze conversations and extract structured information:
- Result summary
- Stall reason (categorized)
- Key interactions
- Suggested follow-up actions

### Recipe Loader
Handles discovery and loading of recipe configurations from the `recipes/` directory.

### Reporting
Generates CSV and HTML reports from the analysis data.

## Configuration

Configuration is managed via environment variables or `.env` file, loaded by Pydantic:

### Required Settings
- Redshift credentials
- BigQuery credentials (service account path)
- OpenAI API key

### Optional Settings
- `TIME_WINDOW_DAYS`: Lookback period for leads (default: 90)
- `BQ_BATCH_SIZE`: Number of phone numbers per BigQuery request (default: 500)
- `BQ_MAX_CONCURRENT_QUERIES`: Maximum parallel BigQuery queries (default: 10)
- `OUTPUT_DIR`: Directory for output files (default: `output_run`)

## Performance Optimizations

The pipeline incorporates several performance optimizations:
- Concurrent API calls to OpenAI using ThreadPoolExecutor
- Batch processing for BigQuery queries
- Progress bars for long-running operations
- Temporary file handling for large BigQuery results
- Automatic retries with exponential backoff for API calls

## Error Handling

The system implements robust error handling for:
- Database connections and queries
- API calls with automatic retries
- File operations
- Data validation and parsing

## Development

### Code Structure
```
lead_recovery_project/
├── lead_recovery/          # Main package
│   ├── __init__.py
│   ├── cli.py              # Command-line interface
│   ├── config.py           # Configuration settings
│   ├── db_clients.py       # Database connection handlers
│   ├── recipe_loader.py    # Recipe discovery and loading
│   ├── reporting.py        # Report generation
│   ├── summarizer.py       # OpenAI summarization logic
│   └── utils.py            # Utility functions
├── recipes/                # Recipe directories
│   ├── profiling_incomplete/
│   │   ├── redshift.sql
│   │   ├── bigquery.sql
│   │   ├── prompt.txt
│   │   └── meta.yml
│   └── handoffapp_to_bill/
│       └── ...
├── tests/                  # Test directory
├── .env                    # Environment variables
├── pyproject.toml          # Project configuration
└── requirements.txt        # Dependencies
```

### Testing
- Uses pytest for unit testing
- Test utilities in the `tests/` directory

### Code Quality
- Linting and formatting with ruff, black, and isort
- Pre-commit hooks for code quality enforcement

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Verify credentials in `.env`
   - Check network connectivity
   - Ensure service account has appropriate permissions

2. **Missing Data**
   - Verify SQL queries correctly identify target leads
   - Check phone number formats match between Redshift and BigQuery
   - Ensure the TIME_WINDOW_DAYS setting is appropriate

3. **OpenAI API Issues**
   - Validate API key
   - Check for rate limiting
   - Review prompt template for errors

4. **Performance Issues**
   - Adjust BQ_BATCH_SIZE for memory constraints
   - Modify max_workers for summarization
   - Check for inefficient SQL queries

## Web Dashboard (Experimental)

A simple web interface built with Streamlit is available for easier execution:

1. Ensure Streamlit and other dependencies are installed:
   ```bash
   # Install the main package and its dependencies
   pip install .
   # If you haven't already, install streamlit
   # pip install streamlit
   ```
   *(Note: `streamlit` is now included in the project dependencies, so `pip install .` should install it automatically.)*

2. Run the dashboard from the project root directory:
   ```bash
   streamlit run dashboard.py
   ```

This allows selecting recipes, optionally setting a 'since' date, running the pipeline, and viewing/downloading the results directly in the browser.

## License

[Specify your license information]

## Contact

Kavak 