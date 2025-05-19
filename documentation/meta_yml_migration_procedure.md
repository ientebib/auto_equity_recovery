# Procedure for Migrating Old meta.yml to New Schema

This document outlines the steps and common patterns for migrating an existing recipe's `meta.yml` file to the new Pydantic-validated schema (defined in `lead_recovery/recipe_schema.py` and guided by `documentation/meta_yml_schema_guide.md`).

**For Each Recipe to be Migrated:**

## Step A: Analyze Old `meta.yml` and Map to New Schema

1.  **Identify Source:** Read the current content of the target recipe's `meta.yml` file.
2.  **Consult Schema Guide:** Refer to `documentation/meta_yml_schema_guide.md` for the target structure of the new `meta.yml`.
3.  **Perform Field Mapping:** Create a "Field Mapping Analysis" (text output) detailing how each relevant field/section from the old `meta.yml` translates to the new schema. Use the following common patterns:

    * **Root Fields:**
        * `name` (old) → `recipe_name` (new). If the old `name` includes versioning (e.g., `my_recipe_v3`), set new `recipe_name` to `my_recipe` and new `version` to `v3` (or `3.0`). Otherwise, if old `recipe_name` exists, use that. `recipe_name` should match the directory.
        * `description` (old) → `description` (new).
        * `version` (old) → `version` (new).
        * **Omitted Root Fields:** Fields like `dashboard_title`, `author`, `summary_format: YAML`, `google_sheets` are not part of the new root `RecipeMeta` schema and should be noted as "omitted" or "to be handled by other mechanisms post-migration if functionality is still required."

    * **Data Input (`data_input`):**
        * Determine `lead_source_type` (`redshift`, `bigquery`, or `csv`).
        * If `redshift_sql: filename.sql` or `redshift_sql_override: filename.sql` exists:
            * `data_input.lead_source_type: redshift`
            * `data_input.redshift_config.sql_file: "filename.sql"`
        * If `bigquery_sql: filename.sql` or `bigquery_sql_override: filename.sql` exists:
            * If Redshift is also primary lead source (see above): `data_input.conversation_sql_file_bigquery: "filename.sql"`
            * If BigQuery is the *only* SQL source: `data_input.lead_source_type: bigquery`, `data_input.bigquery_config.sql_file: "filename.sql"`
        * If `input_csv_file: filename.csv` exists (common in `fede_abril_preperfilamiento`):
            * `data_input.lead_source_type: csv`
            * `data_input.csv_config.csv_file: "filename.csv"`
        * Ensure unused data source configs (e.g., `bigquery_config` if `lead_source_type` is `redshift`) are `null` or omitted in the draft.
        * Map any specific conversation SQL files if present in old format to `conversation_sql_file_redshift` or `conversation_sql_file_bigquery`.

    * **LLM Configuration (`llm_config`):**
        * Map `prompt_file` or `prompt_file_override` to `llm_config.prompt_file`.
        * Convert the old `expected_yaml_keys` (list of strings) into the new `llm_config.expected_llm_keys` (dictionary of objects). For each key from the old list:
            * It becomes a dictionary key in the new structure (e.g., `old_key_name:`).
            * Set `type: str` (or infer `int`, `bool` if obvious from name, e.g., `..._count`, `is_...`).
            * Add a placeholder `description` (e.g., `description: "LLM generated field: old_key_name"`).
            * If the key exists in an old `validation_enums` section, copy the list of enum values to `enum_values: [...]`.
        * Set `llm_config.context_keys_from_python: []` (or omit) unless there's explicit information on this.

    * **Python Processors (`python_processors`):** This requires inferring active processors.
        * **If old `meta.yml` has `python_flag_columns` (like `simulation_to_handoff`):**
            * Use a predefined conceptual mapping (see Appendix A of this guide - we will build this) to determine which processor modules correspond to the columns listed in `python_flag_columns`.
            * Add each inferred processor module to the `python_processors` list with `params: {}`.
        * **If old `meta.yml` has `python_flags: { skip_some_group: false, ... }` (like the original `example_recipe_template`):**
            * Use a predefined conceptual mapping (see Appendix B of this guide - we will build this) of `skip_...` flags to processor module names.
            * If `skip_group_X_flags: false` (or if the key is absent, assuming default is to run), add the corresponding `ProcessorX` to the `python_processors` list.
            * If more granular flags within that group suggest parameters (e.g. `skip_detailed_temporal: false` for a `TemporalProcessor`), add them to the `params` dict for that processor (e.g., `params: { enable_detailed_temporal: true }`).
        * If neither section exists, `python_processors` may be an empty list or omitted.

    * **Output Columns (`output_columns`):**
        * Start with the list from the old `output_columns`.
        * If an `exclude_columns` list exists in the old `meta.yml`, remove these columns from the list you're building.
        * Ensure the list contains:
            * Essential lead identifier fields (e.g., `lead_id`).
            * All non-optional keys from the newly structured `llm_config.expected_llm_keys`.
            * All fields expected to be generated by the active `python_processors` (this might mean keeping most of the original Python-generated columns from the old `output_columns`, assuming they are still relevant).
        * The final order should generally follow the old `output_columns` list.

4.  **Output the "Field Mapping Analysis"** for review.

## Step B: Draft New `meta.yml` Content

1.  Based *only* on the approved "Field Mapping Analysis" from Step A, construct the complete YAML text for the new `meta.yml` file.
2.  Ensure correct YAML syntax, indentation, and adherence to the Pydantic schema structure.
3.  **Output the drafted YAML text** for review.

## Step C: Replace Old `meta.yml` File

1.  Once the drafted YAML from Step B is approved, write this new content to the target recipe's `meta.yml` file, overwriting the old content.

## Step D: Test Loading the Migrated `meta.yml`

1.  Modify the `test_load_migrated_recipe.py` script: change the `recipe_name_to_test` variable to the name of the recipe just migrated.
2.  Run the script: `python test_load_migrated_recipe.py`.
3.  Report the full output. If successful, the recipe migration is complete. If errors occur, revisit Step B to correct the YAML draft based on the error messages.

---
## Appendix A: Mapping from `python_flag_columns` to Processors

This table maps output columns from the old `python_flags.py` module to the new concrete processor modules. Use this mapping when converting recipes with `python_flag_columns`.

| Python Flag Columns | Processor Module | Recommended Parameters |
|---------------------|------------------|------------------------|
| `HOURS_MINUTES_SINCE_LAST_USER_MESSAGE`, `HOURS_MINUTES_SINCE_LAST_MESSAGE`, `LAST_USER_MESSAGE_TIMESTAMP_TZ`, `LAST_MESSAGE_TIMESTAMP_TZ`, `IS_WITHIN_REACTIVATION_WINDOW`, `IS_RECOVERY_PHASE_ELIGIBLE`, `NO_USER_MESSAGES_EXIST` | `lead_recovery.processors.temporal.TemporalProcessor` | `timezone: "America/Mexico_City"` |
| `last_message_sender`, `last_user_message_text`, `last_kuna_message_text`, `last_message_ts` | `lead_recovery.processors.metadata.MessageMetadataProcessor` | `max_message_length: 150` |
| `handoff_finalized`, `handoff_invitation_detected`, `handoff_response` | `lead_recovery.processors.handoff.HandoffProcessor` | `{}` |
| `recovery_template_detected`, `consecutive_recovery_templates_count` | `lead_recovery.processors.template.TemplateDetectionProcessor` | `template_type: "recovery"` |
| `topup_template_detected` | `lead_recovery.processors.template.TemplateDetectionProcessor` | `template_type: "topup", skip_recovery_template: true` |
| `pre_validacion_detected` | `lead_recovery.processors.validation.ValidationProcessor` | `{}` |
| `conversation_state` | `lead_recovery.processors.conversation_state.ConversationStateProcessor` | `{}` |
| `human_transfer` | `lead_recovery.processors.human_transfer.HumanTransferProcessor` | `{}` |

## Appendix B: Mapping from `python_flags: {skip_...}` to Processors

This table maps the skip flags from old recipes to the appropriate processor modules and parameters.

| Python Flag Skip Pattern | Processor Module | Parameters |
|--------------------------|------------------|------------|
| `skip_temporal_flags: false` | `lead_recovery.processors.temporal.TemporalProcessor` | `timezone: "America/Mexico_City"` |
| `skip_detailed_temporal: false` | `lead_recovery.processors.temporal.TemporalProcessor` | `skip_detailed_temporal: false` |
| `skip_hours_minutes: false` | `lead_recovery.processors.temporal.TemporalProcessor` | `skip_hours_minutes: false` |
| `skip_reactivation_flags: false` | `lead_recovery.processors.temporal.TemporalProcessor` | `skip_reactivation_flags: false` |
| `skip_timestamps: false` | `lead_recovery.processors.temporal.TemporalProcessor` | `skip_timestamps: false` |
| `skip_user_message_flag: false` | `lead_recovery.processors.temporal.TemporalProcessor` | `skip_user_message_flag: false` |
| `skip_metadata_extraction: false` | `lead_recovery.processors.metadata.MessageMetadataProcessor` | `max_message_length: 150` |
| `skip_handoff_detection: false` | `lead_recovery.processors.handoff.HandoffProcessor` | `{}` |
| `skip_handoff_invitation: false` | `lead_recovery.processors.handoff.HandoffProcessor` | `skip_handoff_invitation: false` |
| `skip_handoff_started: false` | `lead_recovery.processors.handoff.HandoffProcessor` | `skip_handoff_started: false` |
| `skip_handoff_finalized: false` | `lead_recovery.processors.handoff.HandoffProcessor` | `skip_handoff_finalized: false` |
| `skip_recovery_template_detection: false` | `lead_recovery.processors.template.TemplateDetectionProcessor` | `template_type: "recovery"` |
| `skip_topup_template_detection: false` | `lead_recovery.processors.template.TemplateDetectionProcessor` | `template_type: "topup"` |
| `skip_consecutive_templates_count: false` | `lead_recovery.processors.template.TemplateDetectionProcessor` | `skip_consecutive_count: false` |
| `skip_pre_validacion_detection: false` | `lead_recovery.processors.validation.ValidationProcessor` | `skip_validacion_detection: false` |
| `skip_conversation_state: false` | `lead_recovery.processors.conversation_state.ConversationStateProcessor` | `skip_state_determination: false` |
| `skip_human_transfer_detection: false` | `lead_recovery.processors.human_transfer.HumanTransferProcessor` | `skip_human_transfer_detection: false` |

## Guide to Processor Configuration

For a complete guide to the processor system including detailed descriptions of all available processors, their parameters, and generated columns, please refer to the `documentation/python_processors_guide.md` file.

* **Note:** The old python_flags_manager.py and all flag-based logic are deprecated and removed. Migrate all recipes to use processor-level controls and output_columns. 