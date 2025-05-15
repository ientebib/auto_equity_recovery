# Marzo Cohorts Live Recipe

## Overview
This recipe analyzes the marzo cohorts post-recovery attempt (May 8th onwards) for stall reason, recovery outcome, and next actions, using advanced Python flags.

## Execution Method

The recipe is run through the standard CLI:

```bash
python -m lead_recovery.cli.main run --recipe marzo_cohorts_live
```

This recipe now uses `leads.csv` within its directory as the primary source for leads. The `bigquery.sql` file is used to fetch conversation history for these leads.

This uses the standardized processor-based architecture, running the following processors:
- `TemporalProcessor`
- `MessageMetadataProcessor`
- `HandoffProcessor`
- `HumanTransferProcessor`
- `TemplateDetectionProcessor`
- `ValidationProcessor`
- `ConversationStateProcessor`

Standard CLI options can be used:
```bash
# Skip data fetching steps for testing (BigQuery for conversation history)
python -m lead_recovery.cli.main run --recipe marzo_cohorts_live --skip-bigquery 
# Note: --skip-redshift is not applicable as Redshift is not used by this recipe.

# Run with only specific processors
python -m lead_recovery.cli.main run --recipe marzo_cohorts_live --run-only-processor HandoffProcessor

# Skip specific processors
python -m lead_recovery.cli.main run --recipe marzo_cohorts_live --skip-processor TemporalProcessor
```

## Processor Implementation

The recipe uses the following key processor modules:
- `HandoffProcessor` - Implements handoff detection logic
- `ValidationProcessor` - Implements pre-validation detection logic
- `ConversationStateProcessor` - Implements state tracking logic

## Running Tests
To verify that the recipe can be successfully loaded with the standard system:

```bash
python test_all_recipes.py
``` 