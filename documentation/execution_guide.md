# Lead Recovery Execution Guide

This guide provides comprehensive instructions for executing recipes using the standardized command-line interface (CLI) for the Lead Recovery Pipeline.

## Table of Contents

- [Basic Usage](#basic-usage)
- [CLI Options Reference](#cli-options-reference)
- [Processor Control](#processor-control)
- [Caching Behavior](#caching-behavior)
- [Output Control](#output-control)
- [Common Examples](#common-examples)
- [Troubleshooting](#troubleshooting)

## Basic Usage

The standard way to run any recipe in the Lead Recovery Pipeline is through the main CLI command:

```bash
python3 -m lead_recovery.cli.main run --recipe <recipe_name> [OPTIONS]
```

For example, to run the `simulation_to_handoff` recipe:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff
```

## CLI Options Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--recipe` | TEXT | *Required* | Recipe name (folder name under recipes/) |
| `--recipes-dir` | TEXT | None | Override recipes directory path (default: recipes/ in project root) |
| `--skip-redshift / --no-skip-redshift` | FLAG | `--no-skip-redshift` | Skip fetching leads from Redshift |
| `--skip-bigquery / --no-skip-bigquery` | FLAG | `--no-skip-bigquery` | Skip fetching conversations from BigQuery |
| `--skip-summarize / --no-skip-summarize` | FLAG | `--skip-summarize` | Skip summarizing conversations with LLM |
| `--max-workers` | INTEGER | None | Max concurrent workers for OpenAI calls. Values `None` or `<=0` default to `min(32, max(4, cpu_count))` |
| `--output-dir` | TEXT | None | Override base output directory |
| `--use-cached-redshift / --no-use-cached-redshift` | FLAG | `--use-cached-redshift` | Use cached Redshift data if available |
| `--use-cache / --no-cache` | FLAG | `--use-cache` | Use summarization cache if available |
| `--ignore-redshift-marker` | FLAG | False | Ignore existing Redshift marker and run query even if already run today |
| `--skip-processor` | TEXT | None | List of processor class names to skip |
| `--run-only-processor` | TEXT | None | List of processor class names to run exclusively |
| `--include-columns` | TEXT | None | Comma-separated list of columns to include in the output |
| `--exclude-columns` | TEXT | None | Comma-separated list of columns to exclude from the output |
| `--limit` | INTEGER | None | Limit the number of conversations to process (for testing) |

## Processor Control

The Lead Recovery Pipeline uses a modular processor architecture to analyze conversation data. These processors are defined in the recipe's `meta.yml` file, but can be controlled at runtime using CLI options.

### Skip Specific Processors

To skip one or more processors during execution:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff --skip-processor TemporalProcessor
```

You can skip multiple processors by specifying the option multiple times:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff --skip-processor TemporalProcessor --skip-processor HandoffProcessor
```

### Run Only Specific Processors

To run only certain processors, excluding all others:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff --run-only-processor MessageMetadataProcessor
```

You can specify multiple processors to run by repeating the option:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff --run-only-processor MessageMetadataProcessor --run-only-processor HandoffProcessor
```

### Available Processors

The standard processors available in the system include:

- `TemporalProcessor` - Calculates time-based features
- `MessageMetadataProcessor` - Extracts message metadata
- `HandoffProcessor` - Analyzes handoff processes
- `TemplateDetectionProcessor` - Detects template messages
- `ValidationProcessor` - Detects pre-validation questions
- `ConversationStateProcessor` - Determines conversation state
- `HumanTransferProcessor` - Detects human transfer events

## Caching Behavior

The Lead Recovery Pipeline implements caching to improve performance and reduce API costs.

### Cache Control

- **Summarization Cache**: By default, the pipeline caches LLM responses to avoid re-summarizing unchanged conversations.
  - Enable with `--use-cache` (default)
  - Disable with `--no-cache`

- **Redshift Cache**: By default, the pipeline reuses Redshift data if it was already fetched today.
  - Enable with `--use-cached-redshift` (default)
  - Disable with `--no-use-cached-redshift`
  - Force a new query with `--ignore-redshift-marker`

### Cache Location

Cache files are stored in the recipe's output directory:

```
output_run/<recipe_name>/cache/
```

## Output Control

### Output Directory

By default, all recipe outputs are saved to:

```
output_run/<recipe_name>/
```

You can override this using the `--output-dir` option:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff --output-dir /custom/path
```

### Column Control

Control which columns appear in the output using:

- `--include-columns`: Specify only these columns in output
- `--exclude-columns`: Exclude specific columns from output

Example:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff --include-columns "cleaned_phone,summary,next_action_code"
```

**Note**: These options override the `output_columns` setting in the recipe's `meta.yml` file.

## Common Examples

### Testing with Limited Data

Process only the first 10 conversations:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff --limit 10
```

### Skip Data Fetching (Use Existing Data)

Use existing data files without fetching new data:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff --skip-redshift --skip-bigquery
```

### Using a Custom Recipes Directory

Run a recipe from a non-standard location:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff --recipes-dir /path/to/custom/recipes
```

### Skip LLM Summarization (Processor-Only Mode)

Run only the Python processors without calling the LLM:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff --skip-summarize
```

### Full Production Run

Complete run with all stages:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff --no-cache
```

### Debugging Specific Processors

Run only the handoff analysis:

```bash
python3 -m lead_recovery.cli.main run --recipe simulation_to_handoff --run-only-processor HandoffProcessor --skip-redshift --skip-bigquery --skip-summarize
```

## Troubleshooting

### Common Issues

1. **Recipe Not Found**: Ensure the recipe name matches a directory under the `recipes/` folder or use the `--recipes-dir` option to specify a custom recipes directory location.

2. **Missing Required Files**: Verify the recipe has all required files (meta.yml, prompt.txt, bigquery.sql).

3. **Processor Import Errors**: Check that processor module paths in meta.yml are correct.

4. **Authentication Errors**: Verify that credentials for Google Cloud and OpenAI are correctly set up.

### Debugging Strategies

1. **Limit Processing**: Use `--limit 1` to process just one conversation for faster debugging.

2. **Skip Data Fetching**: Use `--skip-redshift --skip-bigquery` to test with existing data.

3. **Test Specific Processors**: Use `--run-only-processor` to isolate and test specific processors.

4. **Check Console Output**: The CLI provides detailed logging information about each step of the pipeline.

5. **Examine Cache Files**: Look at cache files to see if data is being correctly cached and retrieved.

### Getting Help

For additional help on CLI options:

```bash
python3 -m lead_recovery.cli.main run --help
```

For other commands available in the CLI:

```bash
python3 -m lead_recovery.cli.main --help
``` 