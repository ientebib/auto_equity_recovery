# Documentation Maintenance Guide

This guide provides instructions for maintaining and extending the Lead Recovery project documentation. Following these guidelines ensures that documentation remains useful for both human users and LLM agents.

## Documentation Structure

The documentation is organized into the following structure:

```
documentation/
├── README.md                     # Overview of documentation
├── execution_guide.md            # CLI usage guide
├── meta_yml_migration_procedure.md  # Migration guide
├── meta_yml_schema_guide.md      # Schema reference
├── python_processors_guide.md    # Processor system guide
├── guides/                       # Specialized guides
    ├── running_recipes/          # Guides for running recipes
    ├── creating_recipes/         # Guides for creating recipes
    ├── configuration/            # Guides for configuration
    └── llm_agent_guide.md        # Guide for LLM agents
```

## LLM-Friendly Documentation Principles

To maintain LLM-friendly documentation:

1. **Use consistent formats**: Keep heading levels and formatting consistent
2. **Provide clear examples**: Include code snippets with specific examples
3. **Include complete command samples**: Show full commands rather than partial ones
4. **Use explicit heading hierarchies**: Clear hierarchical structure helps LLMs understand content organization
5. **Add clear cross-references**: Reference other documentation files with full paths
6. **Update all relevant files**: When adding or changing functionality, update all relevant guides
7. **Include troubleshooting sections**: Add common issues and their solutions
8. **Avoid ambiguity**: Be explicit rather than implicit about requirements and procedures

## Updating Documentation for New Features

When adding new features to the codebase:

1. **Identify affected guides**: Determine which documentation files need updating
2. **Update schema references**: If changing the schema, update `meta_yml_schema_guide.md`
3. **Update processor documentation**: If adding/modifying processors, update `python_processors_guide.md`
4. **Add examples**: Include concrete examples of the new functionality
5. **Add CLI options**: If adding CLI options, update `execution_guide.md`
6. **Update LLM agent guide**: Ensure the `llm_agent_guide.md` includes the new functionality

## Adding New Documentation

When creating new documentation:

1. **Follow the established structure**: Place files in the appropriate directories
2. **Match the formatting style**: Follow the style of existing documents
3. **Include all sections**: Each guide should have:
   - Clear introduction
   - Step-by-step instructions
   - Examples
   - Troubleshooting (if applicable)
4. **Cross-reference**: Link to other relevant documentation
5. **Update README.md**: Add references to new documentation in the main README

## Documentation Format Guidelines

To maintain consistency:

### Markdown Formatting

- Use `#` for main titles
- Use `##` for major sections
- Use `###` for subsections
- Use code blocks with language specifiers:
  ````
  ```yaml
  example: content
  ```
  ````

### Code Examples

- Include language specifiers in code blocks
- Use real, runnable examples rather than abstract ones
- For SQL, include comments explaining key parts of queries
- For YAML, include comments explaining significant fields

### Command Line Examples

- Always include the full command
- Use `<placeholder>` format for variables
- Include example output where helpful
- Add common options with explanations

## Updating Documentation for LLM Agents

The `llm_agent_guide.md` should be kept up-to-date with:

1. **Common tasks**: All frequently performed tasks
2. **File locations**: Paths to key files
3. **Example answers**: Templates for answering common questions
4. **Troubleshooting**: Solutions to common problems
5. **Parameter usage**: Guidelines for suggesting parameters

## Documentation Testing

Before committing documentation changes:

1. **Verify links**: Ensure all cross-references are correct
2. **Check examples**: Confirm code examples are correct and runnable
3. **Validate completeness**: Ensure all aspects of the feature are documented
4. **Check for clarity**: Ensure explanations are clear and unambiguous
5. **Test with an LLM**: If possible, confirm an LLM can correctly interpret the documentation

## Documentation Version Control

When making significant changes:

1. **Note in commit message**: Clearly indicate documentation changes
2. **Tag versions**: For major documentation overhauls, consider tagging the repository
3. **Maintain backwards compatibility**: Keep information about older systems when applicable
4. **Archive outdated guides**: Don't delete old guides; move them to an archive section 