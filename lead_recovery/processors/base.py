from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import pandas as pd # Assuming conversation data might be a DataFrame

from lead_recovery.recipe_schema import RecipeMeta # For type hinting of recipe_config

class BaseProcessor(ABC):
    """
    Abstract Base Class for all Python processors.
    Each processor performs a specific analysis or data transformation task.
    """

    # Class attribute to define which output columns this processor can generate.
    # Subclasses should override this. This helps with documentation and validation.
    GENERATED_COLUMNS: List[str] = []

    def __init__(self, recipe_config: RecipeMeta, processor_params: Dict[str, Any], global_config: Optional[Dict[str, Any]] = None):
        """
        Initializes the processor.

        Args:
            recipe_config: The full parsed RecipeMeta object for the current recipe.
                           Processors can access any part of the recipe's configuration.
            processor_params: A dictionary of parameters specific to this processor instance,
                              as defined in the recipe's meta.yml `python_processors` section.
            global_config: Optional dictionary for system-wide configurations 
                           (e.g., API keys, global thresholds) if needed.
        """
        self.recipe_config = recipe_config
        self.params = processor_params
        self.global_config = global_config if global_config else {}

        # Validate that provided params are expected by the processor (optional, advanced)
        self._validate_params()

    def _validate_params(self):
        """
        Optional method for subclasses to validate their specific parameters.
        Can raise RecipeConfigurationError or ValueError for invalid params.
        """
        # Example:
        # known_params = {"threshold", "mode"}
        # for param in self.params:
        #     if param not in known_params:
        #         # from lead_recovery.exceptions import RecipeConfigurationError (if needed)
        #         raise ValueError(f"Unknown parameter '{param}' for {self.__class__.__name__}")
        pass

    @abstractmethod
    def process(self, 
                lead_data: pd.Series, 
                conversation_data: Optional[pd.DataFrame],
                existing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a single lead and its associated data.

        Args:
            lead_data: A pandas Series containing the data for the current lead 
                       (e.g., from Redshift, BigQuery, or CSV).
            conversation_data: An optional pandas DataFrame containing conversation messages
                               for the lead, typically sorted by timestamp.
            existing_results: A dictionary of results already computed by previous 
                              processors or the LLM for this lead in the current run. 
                              Processors can use these or add to them.

        Returns:
            A dictionary where keys are new column names (or existing ones to be updated)
            and values are the computed results for this lead. These results will be
            merged with `existing_results`. It's crucial that keys in the returned
            dictionary match entries in this processor's `GENERATED_COLUMNS` list
            or are well-understood shared keys.
        """
        pass 