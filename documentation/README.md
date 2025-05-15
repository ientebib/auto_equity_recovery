# Lead Recovery Project Documentation

Welcome to the Lead Recovery Project documentation. This directory contains comprehensive documentation about various aspects of the project, organized to be accessible to both humans and LLM agents (like Claude) working through Cursor.

## Documentation Structure

### Core Reference Documentation

These documents provide detailed reference information about key components of the system:

- **[Schema Guide](./meta_yml_schema_guide.md)**: Detailed explanation of the Pydantic-validated recipe schema
- **[Migration Procedure](./meta_yml_migration_procedure.md)**: Guide for migrating legacy recipes to the new schema
- **[Processor System](./python_processors_guide.md)**: Comprehensive guide to using and extending the processor system
- **[Execution Guide](./execution_guide.md)**: Detailed CLI command reference for the Lead Recovery Pipeline

### Task-Oriented Guides

These guides are organized by task and are designed to be LLM-friendly:

#### Running Recipes
- **[CLI Commands](./guides/running_recipes/cli_commands.md)**: Guide to running recipes with CLI commands
- **[Understanding Processors](./guides/running_recipes/understanding_processors.md)**: Guide to understanding processors and their outputs

#### Creating Recipes
- **[Creating New Recipes](./guides/creating_recipes/creating_new_recipe.md)**: Step-by-step guide to creating new recipes
- **[Writing Effective Prompts](./guides/creating_recipes/writing_effective_prompts.md)**: Guide to writing effective LLM prompts

#### Configuration
- **[meta.yml Explained](./guides/configuration/meta_yml_explained.md)**: Practical guide to meta.yml configuration

#### For LLM Agents
- **[LLM Agent Guide](./guides/llm_agent_guide.md)**: Specific guidance for LLM agents using Cursor
- **[Documentation Maintenance](./guides/documentation_maintenance.md)**: Guide for maintaining documentation

## Project Overview

The Lead Recovery Project is designed to analyze conversations with leads, determine their status, and enable appropriate follow-up actions. The project includes:

1. **Data Fetching**: Retrieving lead data from Redshift/BigQuery or CSV files
2. **Conversation Analysis**: Analyzing conversations using modular processors that extract features
3. **Summarization**: Using OpenAI to generate summaries of conversations
4. **Reporting**: Generating reports about lead status and recommended actions

## Project Architecture

The project uses a modular architecture with the following key components:

1. **Recipe Configuration**: Pydantic-validated YAML configuration files (`meta.yml`)
2. **Processor System**: Modular, extensible components for conversation analysis
3. **ProcessorRunner**: Dynamic execution engine for processor chains
4. **Analysis Pipeline**: End-to-end pipeline integrating all components

## Command-Line Reference

Here are some common commands for working with the Lead Recovery Project:

```bash
# Run a recipe with default settings
python -m lead_recovery.cli.main run --recipe recipe_name

# Run a recipe skipping data fetch
python -m lead_recovery.cli.main run --recipe recipe_name --skip-redshift

# Run a recipe with a fresh cache
python -m lead_recovery.cli.main run --recipe recipe_name --no-cache

# Run a recipe with limited data (for testing)
python -m lead_recovery.cli.main run --recipe recipe_name --limit 10
```

For detailed command information, see the [CLI Commands Guide](./guides/running_recipes/cli_commands.md).

## How to Use This Documentation

This documentation is organized to support different user needs:

### For New Users

1. Start with the [Project Overview](#project-overview) above
2. Read the [Creating New Recipes](./guides/creating_recipes/creating_new_recipe.md) guide
3. Review the [CLI Commands](./guides/running_recipes/cli_commands.md) guide

### For Recipe Development

1. Review the [meta.yml Explained](./guides/configuration/meta_yml_explained.md) guide
2. Check the [Writing Effective Prompts](./guides/creating_recipes/writing_effective_prompts.md) guide
3. Understand available processors in the [Understanding Processors](./guides/running_recipes/understanding_processors.md) guide

### For LLM Agents

The [LLM Agent Guide](./guides/llm_agent_guide.md) provides specific guidance for LLM agents using Cursor to help users with the Lead Recovery codebase.

## Contributing to Documentation

If you want to improve this documentation:

1. Follow the guidelines in the [Documentation Maintenance](./guides/documentation_maintenance.md) guide
2. Create a new branch for your changes
3. Update the relevant documentation files
4. Submit a pull request with a clear description of your changes

## Troubleshooting

For common issues or errors, please refer to the troubleshooting sections in each guide or check the logs for detailed error messages. 