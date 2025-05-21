#!/usr/bin/env python3
"""
Test script for all recipes with updated processor paths
"""

import logging
import os

import pandas as pd

from lead_recovery.processor_runner import ProcessorRunner
from lead_recovery.recipe_loader import RecipeLoader
from lead_recovery.yaml_validator import YamlValidator

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_recipe_test(recipe_name: str) -> bool:
    """Test the ProcessorRunner with the specified recipe and validate referenced files and enums."""
    logger.info(f"\n==== TESTING RECIPE: {recipe_name} ====")
    
    try:
        logger.info(f"Loading recipe configuration for {recipe_name}...")
        recipe_loader = RecipeLoader()
        recipe_config = recipe_loader.load_recipe_meta(recipe_name)
        meta_dict = recipe_config.dict() if hasattr(recipe_config, 'dict') else dict(recipe_config)

        # 1. Check referenced files exist (prompt, SQL, leads)
        files_to_check = []
        if meta_dict.get('llm_config') and meta_dict['llm_config'].get('prompt_file'):
            files_to_check.append(meta_dict['llm_config']['prompt_file'])
        if meta_dict.get('data_input'):
            di = meta_dict['data_input']
            if di.get('csv_config') and di['csv_config'].get('csv_file'):
                files_to_check.append(di['csv_config']['csv_file'])
            if di.get('redshift_config') and di['redshift_config'].get('sql_file'):
                files_to_check.append(di['redshift_config']['sql_file'])
            if di.get('bigquery_config') and di['bigquery_config'].get('sql_file'):
                files_to_check.append(di['bigquery_config']['sql_file'])
            if di.get('conversation_sql_file_redshift'):
                files_to_check.append(di['conversation_sql_file_redshift'])
            if di.get('conversation_sql_file_bigquery'):
                files_to_check.append(di['conversation_sql_file_bigquery'])
        for f in files_to_check:
            if f and not os.path.exists(f):
                logger.warning(f"Referenced file does not exist: {f}")
                return False

        logger.info(f"Creating ProcessorRunner for {recipe_config.recipe_name}...")
        processor_runner = ProcessorRunner(recipe_config=recipe_config)
        processor_names = [p.__class__.__name__ for p in processor_runner.processors]
        logger.info(f"Loaded processors: {', '.join(processor_names)}")
        lead_data = pd.Series({
            "lead_id": f"test-{recipe_name}",
            "cleaned_phone": "5551234567",
            "name": "Test User"
        }, name=f"test-{recipe_name}")
        conversation_data = pd.DataFrame([
            {
                "msg_from": "bot", 
                "message": "¡Hola! ¿Cómo puedo ayudarte con tu préstamo?",
                "cleaned_phone": "5551234567",
                "creation_time": "2023-06-01T10:00:00"
            },
            {
                "msg_from": "user", 
                "message": "Quiero más información sobre el préstamo",
                "cleaned_phone": "5551234567",
                "creation_time": "2023-06-01T10:05:00"
            }
        ])
        results = processor_runner.run_all(
            lead_data=lead_data,
            conversation_data=conversation_data
        )
        logger.info(f"Processors executed successfully for {recipe_name}!")
        logger.info(f"Generated {len(results)} results")
        expected_columns = processor_runner.get_expected_output_columns()
        logger.info(f"Expected output columns: {len(expected_columns)} columns")
        missing_columns = set(expected_columns) - set(results.keys())
        if missing_columns:
            logger.warning(f"Missing expected columns: {missing_columns}")
            return False
        else:
            logger.info(f"All expected columns were generated successfully for {recipe_name}!")
        # 2. Test YamlValidator enum enforcement if enums are defined
        if meta_dict.get('llm_config') and meta_dict['llm_config'].get('expected_llm_keys'):
            enums = {k: v.get('enum_values') for k, v in meta_dict['llm_config']['expected_llm_keys'].items() if v.get('enum_values')}
            if enums:
                dummy = {k: (v[0] if v else 'N/A') for k, v in enums.items()}
                # Intentionally set one to an invalid value
                for k in enums:
                    dummy[k] = 'INVALID_ENUM_VALUE'
                    break
                validator = YamlValidator(meta_dict)
                errors = validator.validate_yaml(dummy)
                if not errors:
                    logger.warning(f"YamlValidator did not catch invalid enum for {recipe_name}")
                    return False
                fixed = validator.fix_yaml(dummy.copy())
                for k, allowed in enums.items():
                    if fixed[k] == 'INVALID_ENUM_VALUE':
                        logger.warning(f"YamlValidator did not fix invalid enum for {k} in {recipe_name}")
                        return False
        return True
    except Exception as e:
        logger.exception(f"Error testing recipe {recipe_name}: {e}")
        return False

def test_all_recipes():
    """Test all recipes with updated processor paths"""
    recipes = [
        "simulation_to_handoff",
        "fede_abril_preperfilamiento",
        "marzo_cohorts",
        "marzo_cohorts_live",
        "top_up_may"
    ]
    
    results = {}
    for recipe in recipes:
        results[recipe] = run_recipe_test(recipe)
    
    # Print summary
    logger.info("\n==== TEST SUMMARY ====")
    all_passed = True
    for recipe, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        logger.info(f"Recipe {recipe}: {status}")
        if not passed:
            all_passed = False
    
    return all_passed

if __name__ == "__main__":
    logger.info("Starting tests for all recipes...")
    try:
        success = test_all_recipes()
        if success:
            logger.info("All tests completed successfully!")
        else:
            logger.error("Some tests failed! See log for details.")
    except Exception as e:
        logger.exception(f"Error during testing: {e}")
        raise 