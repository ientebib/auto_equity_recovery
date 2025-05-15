#!/usr/bin/env python3
"""
Test script for ProcessorRunner with top_up_may recipe
"""

import pandas as pd
import logging
from lead_recovery.processor_runner import ProcessorRunner
from lead_recovery.recipe_loader import RecipeLoader

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_topup_processor():
    """Test the ProcessorRunner with top_up_may recipe"""
    logger.info("Loading top_up_may recipe configuration...")
    recipe_loader = RecipeLoader()
    recipe_config = recipe_loader.load_recipe_meta("top_up_may")
    
    logger.info(f"Creating ProcessorRunner for {recipe_config.recipe_name}...")
    processor_runner = ProcessorRunner(recipe_config=recipe_config)
    
    # Log loaded processors
    processor_names = [p.__class__.__name__ for p in processor_runner.processors]
    logger.info(f"Loaded processors: {processor_names}")
    
    # Create mock test data
    lead_data = pd.Series({
        "lead_id": "topup-test-1",
        "cleaned_phone": "5559876543",
        "name": "Topup User"
    }, name="topup-test-1")
    
    # Create sample conversation data with a topup template message that matches our detector patterns
    conversation_data = pd.DataFrame([
        {
            "msg_from": "bot", 
            "message": "¡Hola Juan! 👋 Nos gustaría reconocer tu excelente comportamiento de pago. Te informamos que tienes un crédito pre-aprobado disponible para ti.",
            "cleaned_phone": "5559876543",
            "creation_time": "2023-06-01T10:00:00"
        },
        {
            "msg_from": "user", 
            "message": "Gracias, me interesa saber más",
            "cleaned_phone": "5559876543",
            "creation_time": "2023-06-01T10:05:00"
        }
    ])
    
    # Process the mock data
    logger.info("Processing mock topup conversation data...")
    results = processor_runner.run_all(
        lead_data=lead_data,
        conversation_data=conversation_data
    )
    
    # Log results
    logger.info("Processors executed successfully!")
    logger.info(f"Generated {len(results)} results:")
    for key, value in results.items():
        logger.info(f"  {key}: {value}")
    
    # Check expected output columns
    expected_columns = processor_runner.get_expected_output_columns()
    logger.info(f"Expected output columns: {expected_columns}")
    
    # Verify that all expected columns are in the results
    missing_columns = set(expected_columns) - set(results.keys())
    if missing_columns:
        logger.warning(f"Missing expected columns: {missing_columns}")
    else:
        logger.info("All expected columns were generated successfully!")
    
    # Verify the topup template was detected
    if results.get('topup_template_detected'):
        logger.info("SUCCESS: Top-up template was correctly detected!")
    else:
        logger.warning("WARNING: Top-up template was not detected in the test message")
    
    return True

if __name__ == "__main__":
    logger.info("Starting Top-up May ProcessorRunner test...")
    try:
        success = test_topup_processor()
        if success:
            logger.info("Test completed successfully!")
        else:
            logger.error("Test failed!")
    except Exception as e:
        logger.exception(f"Error during test: {e}")
        raise 