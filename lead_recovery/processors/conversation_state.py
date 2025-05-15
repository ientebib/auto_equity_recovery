from typing import Dict, Any, List, Optional
import pandas as pd
import logging

from .base import BaseProcessor
from lead_recovery.processors.utils import convert_df_to_message_list
from lead_recovery.processors.validation import ValidationProcessor
from lead_recovery.processors.handoff import HandoffProcessor

logger = logging.getLogger(__name__)

class ConversationStateProcessor(BaseProcessor):
    """
    Processor for determining the overall state of a conversation.
    
    Analyzes the conversation to determine its current state based on
    pre-validation and handoff detection.
    
    This processor respects the user's configuration choices:
    - If ValidationProcessor was skipped in the recipe, pre-validation is assumed false
    - If HandoffProcessor was skipped in the recipe, handoff invitation is assumed false
    - Only uses the values calculated by processors that were explicitly included in the recipe
    """
    
    GENERATED_COLUMNS = [
        "conversation_state"
    ]
    
    def _validate_params(self):
        """Validate processor-specific parameters."""
        known_params = {"skip_state_determination"}
        for param in self.params:
            if param not in known_params:
                raise ValueError(f"Unknown parameter '{param}' for {self.__class__.__name__}")
    
    def process(self, 
                lead_data: pd.Series, 
                conversation_data: Optional[pd.DataFrame],
                existing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine the current state of a conversation.
        
        Respects processor configuration - will not run additional processors if they
        were not included in the recipe configuration.
        
        Args:
            lead_data: Series containing lead information
            conversation_data: DataFrame with conversation messages
            existing_results: Dictionary of results from previous processors
            
        Returns:
            Dictionary containing the conversation state
        """
        # Initialize default result
        result = {
            "conversation_state": "UNKNOWN"
        }
        
        # Get skip parameter with default
        skip_state_determination = self.params.get("skip_state_determination", False)
        
        # Skip determination if requested
        if skip_state_determination:
            return result
            
        # Return early if no conversation data
        if conversation_data is None or conversation_data.empty:
            return result
            
        # Convert DataFrame to message list for compatibility
        conversation_messages = convert_df_to_message_list(conversation_data)
        if not conversation_messages:
            return result
        
        # Default state
        state = "PRE_VALIDACION"
        
        # Check if pre_validacion_detected exists in existing_results
        # If it doesn't exist, assume pre-validation was not detected (or the processor was skipped)
        pre_validacion_detected = existing_results.get("pre_validacion_detected", False)
        
        # Update state if pre-validation detected
        if pre_validacion_detected:
            state = "POST_VALIDACION"
            logger.debug("Setting conversation state to POST_VALIDACION based on pre_validacion_detected=True")
        
        # Check if handoff_invitation_detected exists in existing_results
        # If it doesn't exist, assume handoff invitation was not detected (or the processor was skipped)
        handoff_invitation_detected = existing_results.get("handoff_invitation_detected", False)
        
        # If handoff invitation was detected, override to HANDOFF state regardless of pre-validation
        if handoff_invitation_detected:
            state = "HANDOFF"
            logger.debug("Setting conversation state to HANDOFF based on handoff_invitation_detected=True")
        
        logger.info(f"Determined conversation state: {state}")
        result["conversation_state"] = state
        return result 