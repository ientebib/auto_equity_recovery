# PATH: ientebib/auto_equity_recovery/auto_equity_recovery-02438837e55c18926cc3aa72ef3febf0f2c0c976/test_load_migrated_recipe.py
import sys
from pathlib import Path

from lead_recovery.exceptions import RecipeConfigurationError
from lead_recovery.recipe_loader import RecipeLoader
from lead_recovery.recipe_schema import RecipeMeta  # For type hinting, optional here

# Ensure the lead_recovery package is discoverable.
# This adds the project root to the Python path.
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    print("Attempting to load migrated recipe 'simulation_to_handoff'...")
    print(f"Using PROJECT_ROOT: {PROJECT_ROOT}")

    try:
        # Instantiate RecipeLoader.
        # Since recipe_loader.py's _DEFAULT_PROJECT_ROOT should correctly resolve
        # to this script's parent if lead_recovery is a direct subdir,
        # explicitly passing project_root might be redundant but is safer for a test script.
        # If your RecipeLoader's default project root detection is robust,
        # you might not need to pass project_root here.
        # For this test, let's be explicit if RecipeLoader's default isn't working as expected from this script's location.
        # Based on RecipeLoader's current __init__, its default should work if this script is at project root.
        loader = RecipeLoader() # Relies on RecipeLoader's default PROJECT_ROOT detection
        # Alternatively, to be super explicit:
        # loader = RecipeLoader(project_root=PROJECT_ROOT)


        recipe_name_to_test = "top_up_may"
        
        # Load the specific recipe
        parsed_meta: RecipeMeta = loader.load_recipe_meta(recipe_name_to_test)

        print(f"\nSUCCESS! Recipe '{recipe_name_to_test}' loaded and validated successfully.")
        print("--------------------------------------------------")
        print(f"Recipe Name from object: {parsed_meta.recipe_name}")
        print(f"Version: {parsed_meta.version}")
        print(f"Description: {parsed_meta.description}")

        print("\nData Input Configuration:")
        print(f"  Lead Source Type: {parsed_meta.data_input.lead_source_type}")
        if parsed_meta.data_input.redshift_config:
            print(f"  Redshift SQL File (resolved path): {parsed_meta.data_input.redshift_config.sql_file}")
        if parsed_meta.data_input.conversation_sql_file_bigquery:
            print(f"  BigQuery Conversation SQL File (resolved path): {parsed_meta.data_input.conversation_sql_file_bigquery}")

        if parsed_meta.llm_config:
            print("\nLLM Configuration:")
            print(f"  Prompt File (resolved path): {parsed_meta.llm_config.prompt_file}")
            print(f"  Expected LLM Keys count: {len(parsed_meta.llm_config.expected_llm_keys)}")
            # print(f"  First expected LLM key details: {next(iter(parsed_meta.llm_config.expected_llm_keys.items())) if parsed_meta.llm_config.expected_llm_keys else 'N/A'}")


        if parsed_meta.python_processors:
            print("\nPython Processors Configured:")
            for i, processor_config in enumerate(parsed_meta.python_processors):
                print(f"  Processor {i+1}: Module='{processor_config.module}', Params={processor_config.params}")
        
        print(f"\nOutput Columns count: {len(parsed_meta.output_columns)}")
        # print(f"  First few output columns: {parsed_meta.output_columns[:5]}")
        print("--------------------------------------------------")

    except RecipeConfigurationError as e:
        print(f"\nVALIDATION FAILED for recipe '{recipe_name_to_test}':")
        print("--------------------------------------------------")
        print(e)
        print("--------------------------------------------------")
        print("\nPlease check the recipes/simulation_to_handoff/meta.yml against documentation/meta_yml_schema_guide.md")
    except Exception as e:
        print(f"\nAn UNEXPECTED ERROR occurred while trying to load recipe '{recipe_name_to_test}':")
        print("--------------------------------------------------")
        print(type(e).__name__, e)
        print("--------------------------------------------------")

if __name__ == "__main__":
    main() 