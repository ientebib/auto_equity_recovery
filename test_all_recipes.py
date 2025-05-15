#!/usr/bin/env python3
"""
Test script for all recipes with updated processor paths
"""

import pandas as pd
import logging
from lead_recovery.processor_runner import ProcessorRunner
from lead_recovery.recipe_loader import RecipeLoader

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_recipe(recipe_name: str) -> bool:
    """Test the ProcessorRunner with the specified recipe"""
    logger.info(f"\n==== TESTING RECIPE: {recipe_name} ====")
    
    try:
        logger.info(f"Loading recipe configuration for {recipe_name}...")
        recipe_loader = RecipeLoader()
        recipe_config = recipe_loader.load_recipe_meta(recipe_name)
        
        logger.info(f"Creating ProcessorRunner for {recipe_config.recipe_name}...")
        processor_runner = ProcessorRunner(recipe_config=recipe_config)
        
        # Log loaded processors
        processor_names = [p.__class__.__name__ for p in processor_runner.processors]
        logger.info(f"Loaded processors: {', '.join(processor_names)}")
        
        # Create mock test data
        lead_data = pd.Series({
            "lead_id": f"test-{recipe_name}",
            "cleaned_phone": "5551234567",
            "name": "Test User"
        }, name=f"test-{recipe_name}")
        
        # Create sample conversation data (two messages)
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
        
        # Process the mock data
        logger.info(f"Processing mock conversation data for {recipe_name}...")
        results = processor_runner.run_all(
            lead_data=lead_data,
            conversation_data=conversation_data
        )
        
        # Log results
        logger.info(f"Processors executed successfully for {recipe_name}!")
        logger.info(f"Generated {len(results)} results")
        
        # Check expected output columns
        expected_columns = processor_runner.get_expected_output_columns()
        logger.info(f"Expected output columns: {len(expected_columns)} columns")
        
        # Verify that all expected columns are in the results
        missing_columns = set(expected_columns) - set(results.keys())
        if missing_columns:
            logger.warning(f"Missing expected columns: {missing_columns}")
            return False
        else:
            logger.info(f"All expected columns were generated successfully for {recipe_name}!")
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
        results[recipe] = test_recipe(recipe)
    
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