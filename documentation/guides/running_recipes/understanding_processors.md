# Understanding Processors in Lead Recovery

This guide explains the available processors in the Lead Recovery system, what they do, and how to control them when running recipes.

## What are Processors?

Processors are modular Python components that analyze conversation data and generate features. Each processor focuses on a specific aspect of conversation analysis, such as timing, message metadata, or detecting specific patterns.

## Available Processors

### TemporalProcessor

**Function:** Analyzes time-related aspects of conversations.

**Generates:**
- `HOURS_MINUTES_SINCE_LAST_USER_MESSAGE`: Time since last user message
- `HOURS_MINUTES_SINCE_LAST_MESSAGE`: Time since last message
- `IS_WITHIN_REACTIVATION_WINDOW`: Whether within reactivation timeframe
- `IS_RECOVERY_PHASE_ELIGIBLE`: Whether eligible for recovery
- `LAST_USER_MESSAGE_TIMESTAMP_TZ`: Timestamp of last user message
- `LAST_MESSAGE_TIMESTAMP_TZ`: Timestamp of last message
- `NO_USER_MESSAGES_EXIST`: Whether user has sent any messages

### MessageMetadataProcessor

**Function:** Extracts basic information about the messages.

**Generates:**
- `last_message_sender`: Who sent the last message
- `last_user_message_text`: Content of the last user message
- `last_kuna_message_text`: Content of the last Kuna message
- `last_message_ts`: Timestamp of the last message

### HandoffProcessor

**Function:** Detects handoff patterns in conversations.

**Generates:**
- `handoff_invitation_detected`: Whether handoff was offered
- `handoff_response`: How the handoff invitation was handled
- `handoff_finalized`: Whether handoff completed successfully

### TemplateDetectionProcessor

**Function:** Identifies use of template messages.

**Generates:**
- `recovery_template_detected`: Whether recovery templates were used
- `topup_template_detected`: Whether top-up templates were used
- `consecutive_recovery_templates_count`: Count of sequential recovery templates

### ValidationProcessor

**Function:** Detects pre-validation questions and messages.

**Generates:**
- `pre_validacion_detected`: Whether pre-validation occurred

### ConversationStateProcessor

**Function:** Determines the overall state of a conversation.

**Generates:**
- `conversation_state`: Current state (PRE_VALIDACION, POST_VALIDACION, HANDOFF)

### HumanTransferProcessor

**Function:** Detects transfers to human agents.

**Generates:**
- `human_transfer`: Whether human transfer occurred

## Using Processors in Commands

### Run All Processors (Default)

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name>
```

### Skip Specific Processors

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name> --skip-processor TemporalProcessor
```

You can skip multiple processors:

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name> --skip-processor TemporalProcessor --skip-processor HandoffProcessor
```

### Run Only Specific Processors

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name> --run-only-processor MessageMetadataProcessor
```

For multiple processors:

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name> --run-only-processor MessageMetadataProcessor --run-only-processor HandoffProcessor
```

## Processor Dependencies

Some processors depend on results from others:

- `ConversationStateProcessor` depends on `ValidationProcessor` and `HandoffProcessor`
- Most processors should run after `TemporalProcessor` and `MessageMetadataProcessor`

When using `--run-only-processor`, be aware that skipping a dependency may cause errors or invalid results.

## Viewing Processor Results

All processor-generated fields appear in the output CSV if they're included in the recipe's `output_columns` list. Use these options to control output:

```bash
# Include only specific columns
python -m lead_recovery.cli.main run --recipe <recipe_name> --include-columns "lead_id,handoff_finalized,conversation_state"

# Exclude specific columns
python -m lead_recovery.cli.main run --recipe <recipe_name> --exclude-columns "HOURS_MINUTES_SINCE_LAST_MESSAGE"
```

## Debugging Processors

If a processor is producing unexpected results, you can isolate it:

```bash
python -m lead_recovery.cli.main run --recipe <recipe_name> --run-only-processor TemporalProcessor --limit 5
```

This runs only the TemporalProcessor on 5 conversations, making it easier to check the results. 