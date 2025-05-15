"""
Processor Runner Module

Handles dynamic loading and execution of processor classes for recipes.
This module provides the infrastructure to discover, instantiate, and run
processor classes based on configuration in the recipe's meta.yml.
"""

import importlib
import logging
from typing import List, Dict, Any, Optional
import pandas as pd
from lead_recovery.recipe_schema import RecipeMeta, PythonProcessorConfig
from lead_recovery.processors.base import BaseProcessor
from lead_recovery.exceptions import RecipeConfigurationError

logger = logging.getLogger(__name__)

class ProcessorRunner:
    """
    Manages the dynamic loading and execution of processor classes for a recipe.
    
    This class is responsible for:
    1. Importing processor classes based on their module paths
    2. Instantiating processors with appropriate configuration
    3. Running processors in sequence
    4. Collecting and merging results
    """
    
    def __init__(self, recipe_config: RecipeMeta, global_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ProcessorRunner.
        
        Args:
            recipe_config: The parsed recipe configuration (meta.yml)
            global_config: Optional dictionary with system-wide configuration
        """
        self.recipe_config = recipe_config
        self.global_config = global_config or {}
        self.processors: List[BaseProcessor] = []
        self._load_processors()

    def _load_processors(self):
        """Load processors based on recipe configuration."""
        processors = []
        
        # Handle both RecipeMeta objects and dictionaries
        if hasattr(self.recipe_config, 'python_processors'):
            # This is a RecipeMeta object
            processors_config = self.recipe_config.python_processors
        elif isinstance(self.recipe_config, dict) and 'python_processors' in self.recipe_config:
            # This is a dictionary with python_processors key
            processors_config = self.recipe_config['python_processors']
        else:
            logger.warning("No python_processors found in recipe configuration")
            self.processors = []
            return
            
        if not processors_config:
            logger.info("No Python processors configured in recipe")
            self.processors = []
            return

        for proc_config in processors_config:
            try:
                # For RecipeMeta objects
                if hasattr(proc_config, 'module'):
                    module_path, class_name = proc_config.module.rsplit('.', 1)
                    params = proc_config.params if hasattr(proc_config, 'params') else {}
                # For dict objects
                elif isinstance(proc_config, dict) and 'module' in proc_config:
                    module_path, class_name = proc_config['module'].rsplit('.', 1)
                    params = proc_config.get('params', {})
                else:
                    logger.error(f"Invalid processor configuration: {proc_config}")
                    continue
                
                # Import the module dynamically
                try:
                    module = importlib.import_module(module_path)
                except ImportError as import_err:
                    # Specific handling for module import failures
                    logger.error(f"Failed to import processor module '{module_path}': {import_err}")
                    raise RecipeConfigurationError(
                        f"Processor module '{module_path}' could not be imported. "
                        f"Check that the module exists and is correctly specified in meta.yml. Error: {import_err}"
                    ) from import_err
                
                try:
                    # Get the processor class
                    processor_class = getattr(module, class_name)
                except AttributeError as attr_err:
                    # Specific handling for class not found in module
                    logger.error(f"Processor class '{class_name}' not found in module '{module_path}': {attr_err}")
                    raise RecipeConfigurationError(
                        f"Processor class '{class_name}' not found in module '{module_path}'. "
                        f"Check that the class name is correct in meta.yml. Error: {attr_err}"
                    ) from attr_err
                
                # Ensure params is a dict (even if empty)
                if params is None:
                    params = {}
                
                # Verify processor class inherits from BaseProcessor
                if not issubclass(processor_class, BaseProcessor):
                    raise RecipeConfigurationError(
                        f"Processor class {module_path}.{class_name} does not inherit from BaseProcessor."
                    )
                
                try:
                    # STRICT ENFORCEMENT: Processors must follow BaseProcessor init signature
                    processor_instance = processor_class(
                        recipe_config=self.recipe_config, 
                        processor_params=params,
                        global_config=self.global_config
                    )
                    processors.append(processor_instance)
                    logger.debug(f"Loaded processor: {processor_instance.__class__.__name__}")
                except TypeError as type_err:
                    # Specific handling for initialization signature errors
                    logger.error(f"Processor initialization error for '{module_path}.{class_name}': {type_err}")
                    raise RecipeConfigurationError(
                        f"Failed to initialize processor '{module_path}.{class_name}'. "
                        f"Ensure its __init__ signature matches BaseProcessor. Error: {type_err}"
                    ) from type_err
                
            except (RecipeConfigurationError, ImportError, AttributeError, TypeError):
                # Let these specific errors propagate as they already have context
                raise
            except Exception as e:
                # Catch-all for any other unexpected errors
                error_msg = (
                    f"CRITICAL ERROR: Failed to initialize processor '{module_path}.{class_name}'. "
                    f"Unexpected error: {e}"
                )
                logger.error(error_msg, exc_info=True)
                # Raise with preserved stack trace
                raise RecipeConfigurationError(
                    f"Failed to initialize configured processor '{module_path}.{class_name}'. Error: {e}"
                ) from e
        
        self.processors = processors
        logger.info(f"Loaded {len(processors)} Python processors")

    def run_all(self, 
                lead_data: pd.Series, 
                conversation_data: Optional[pd.DataFrame],
                initial_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run all configured processors sequentially for a single lead.

        Args:
            lead_data: Series containing data for the current lead
            conversation_data: DataFrame containing conversation messages for the lead
            initial_results: Optional initial results (from LLM or previous stages)

        Returns:
            Dictionary containing all accumulated results from the processors
        """
        lead_id = lead_data.get('lead_id', str(lead_data.name)) if hasattr(lead_data, 'name') else 'Unknown'
        logger.info(f"Running processors for lead: {lead_id}")
        
        # Initialize results with existing data or empty dict
        current_results = initial_results.copy() if initial_results else {}

        # Run each processor in sequence
        for processor_instance in self.processors:
            processor_name = processor_instance.__class__.__name__
            logger.debug(f"Running processor: {processor_name} for lead: {lead_id}")
            
            try:
                # Process the lead and conversation data
                processor_output = processor_instance.process(
                    lead_data, 
                    conversation_data, 
                    current_results 
                )
                
                # Validate processor output
                if not isinstance(processor_output, dict):
                    logger.warning(f"Processor {processor_name} returned non-dictionary result: {type(processor_output)}")
                    continue
                
                # Log generated columns
                expected_cols = set(processor_instance.GENERATED_COLUMNS)
                actual_cols = set(processor_output.keys())
                missing_cols = expected_cols - actual_cols
                extra_cols = actual_cols - expected_cols
                
                if missing_cols:
                    logger.warning(f"Processor {processor_name} is missing expected columns: {missing_cols}")
                if extra_cols:
                    logger.warning(f"Processor {processor_name} produced unexpected columns: {extra_cols}")
                
                # Merge results
                current_results.update(processor_output)
                logger.debug(f"Processor {processor_name} completed successfully")
                
            except Exception as e:
                error_msg = f"Error in processor {processor_name} for lead {lead_id}: {e}"
                logger.error(error_msg, exc_info=True)
                # Store the error in current_results for debugging/reporting
                error_key = f"{processor_name.lower()}_error"
                current_results[error_key] = str(e)
                # Continue to next processor without failing the entire pipeline
                # This allows some processors to fail while still getting results from others
        
        logger.info(f"Successfully ran all processors for lead: {lead_id}, generated {len(current_results)} results")
        return current_results

    def get_expected_output_columns(self) -> List[str]:
        """
        Get a list of all expected output columns from all processors.
        
        Returns:
            List of column names that processors are expected to generate
        """
        columns = []
        for processor in self.processors:
            columns.extend(processor.GENERATED_COLUMNS)
        return columns 