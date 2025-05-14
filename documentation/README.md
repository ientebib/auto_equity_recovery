# Lead Recovery Project Documentation

Welcome to the Lead Recovery Project documentation. This directory contains comprehensive documentation about various aspects of the project.

## Documentation Sections

### [Python Flags System](./python_flags/INDEX.md)

Documentation about the Python flags system used throughout the project:

- **[Overview](./python_flags/README.md)**: General introduction to the Python flags system
- **[Architecture](./python_flags/ARCHITECTURE.md)**: Detailed explanation of the flags architecture
- **[Adding New Flags](./python_flags/ADDING_NEW_FLAG.md)**: Step-by-step guide for adding flags
- **[Modifying Flags](./python_flags/MODIFYING_EXISTING_FLAG.md)**: Guide for modifying existing flags
- **[Flag Removal Case Study](./python_flags/FLAG_REMOVAL_CASE_STUDY.md)**: Real-world example of removing a flag

## Project Overview

The Lead Recovery Project is designed to analyze conversations with leads, determine their status, and enable appropriate follow-up actions. The project includes:

1. **Data Fetching**: Retrieving lead data from Redshift and conversation data from BigQuery
2. **Conversation Analysis**: Analyzing conversations using various techniques including Python-based flag detection
3. **Summarization**: Using OpenAI to generate summaries of conversations
4. **Reporting**: Generating reports about lead status and recommended actions

## Additional Resources

- **Project README**: See the main project README in the root directory for general usage instructions
- **Recipe Configuration**: Check `recipes/` directory for specific recipe configurations
- **API Reference**: Documentation for key modules and functions is available in docstrings

## How to Use This Documentation

This documentation is organized into sections focused on specific aspects of the project. Each section contains multiple files addressing different topics within that area.

For new users:
1. Start with the main README in the project root
2. Follow the installation and setup instructions
3. Read the documentation sections relevant to your tasks

For contributors:
1. Review the architecture documentation for the area you want to modify
2. Follow the guides for adding, modifying, or removing components
3. Ensure you understand how your changes fit into the overall system

## Contributing to Documentation

If you find issues or want to improve this documentation:

1. Create a new branch for your changes
2. Update the relevant documentation files
3. Submit a pull request with a clear description of your changes

## Command-Line Reference

Here are some common commands for working with the Lead Recovery Project:

```bash
# Run a recipe with default settings
python -m lead_recovery.cli.main run --recipe recipe_name

# Run a recipe skipping Redshift data fetch
python -m lead_recovery.cli.main run --recipe recipe_name --skip-redshift

# Run a recipe with a fresh cache
python -m lead_recovery.cli.main run --recipe recipe_name --no-cache

# Generate reports only
python -m lead_recovery.cli.main report --output-dir output_dir/recipe_name
```

## Troubleshooting

For common issues or errors, please refer to the troubleshooting section in the main README or check the logs for detailed error messages. 