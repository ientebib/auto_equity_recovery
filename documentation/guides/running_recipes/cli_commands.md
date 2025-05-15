# Running Lead Recovery Recipes: CLI Guide

This guide explains how to run Lead Recovery recipes using the command-line interface (CLI). It's designed to be easy to follow for both humans and LLM agents.

## Basic Recipe Execution

To run any recipe, use this basic command format:

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name>
```

Replace `<recipe_name>` with the name of the recipe you want to run (the folder name under `recipes/`).

## Common Command Patterns

### Standard Production Run

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name> --no-cache
```

### Testing with Limited Data

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name> --limit 10
```

### Skip Data Fetching (Using Existing Data)

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name> --skip-redshift --skip-bigquery
```

### Skip LLM Summarization (Processor-Only Mode)

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name> --skip-summarize
```

## Key CLI Options

| Option | Description | Usage Example |
|--------|-------------|---------------|
| `--recipe` | Specify the recipe to run | `--recipe simulation_to_handoff` |
| `--limit` | Limit number of conversations to process | `--limit 10` |
| `--skip-redshift` | Skip fetching data from Redshift | `--skip-redshift` |
| `--skip-bigquery` | Skip fetching conversations from BigQuery | `--skip-bigquery` |
| `--skip-summarize` | Skip LLM summarization | `--skip-summarize` |
| `--no-cache` | Don't use cached LLM responses | `--no-cache` |
| `--output-dir` | Override output directory | `--output-dir /custom/path` |
| `--skip-processor` | Skip specific processors | `--skip-processor TemporalProcessor` |
| `--run-only-processor` | Run only specific processors | `--run-only-processor HandoffProcessor` |

## Processor Control

### Running Specific Processors

To run only certain processors:

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name> --run-only-processor MessageMetadataProcessor
```

To skip specific processors:

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name> --skip-processor TemporalProcessor
```

Multiple processors can be specified by repeating the flag:

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name> --run-only-processor MessageMetadataProcessor --run-only-processor HandoffProcessor
```

## Output Control

Control columns in the output:

```bash
# Include only specific columns
python -m lead_recovery.cli.main run --recipe <recipe_name> --include-columns "lead_id,summary,next_action_code"

# Exclude specific columns
python -m lead_recovery.cli.main run --recipe <recipe_name> --exclude-columns "detailed_analysis,raw_conversation"
```

## Caching Options

By default, the pipeline caches LLM responses and Redshift data:

```bash
# Disable LLM cache
python -m lead_recovery.cli.main run --recipe <recipe_name> --no-cache

# Disable Redshift cache
python -m lead_recovery.cli.main run --recipe <recipe_name> --no-use-cached-redshift

# Force new Redshift query even if run today
python -m lead_recovery.cli.main run --recipe <recipe_name> --ignore-redshift-marker
```

## Examples for Common Tasks

### Debugging a Specific Processor

```bash
python -m lead_recovery.cli.main run --recipe simulation_to_handoff --run-only-processor HandoffProcessor --skip-redshift --skip-bigquery --skip-summarize
```

### Full Pipeline Run With Fresh Data

```bash
python -m lead_recovery.cli.main run --recipe simulation_to_handoff --no-cache --ignore-redshift-marker
```

### Quick Test Run

```bash
python -m lead_recovery.cli.main run --recipe simulation_to_handoff --limit 5 --skip-redshift --skip-bigquery
```

## Handling Command Outputs

Look for output files in:
```
output_run/<recipe_name>/
```

Unless overridden with `--output-dir`. 