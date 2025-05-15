from typing import Dict, Any, List, Optional
import pandas as pd

from .base import BaseProcessor
from lead_recovery.processors.utils import convert_df_to_message_list
from lead_recovery.processors.validation import ValidationProcessor
from lead_recovery.processors.handoff import HandoffProcessor

class ConversationStateProcessor(BaseProcessor):
    """
    Processor for determining the overall state of a conversation.
    
    Analyzes the conversation to determine its current state based on
    pre-validation and handoff detection. Uses other processors to make
    its determination.
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
        
        # Check if we already have pre_validacion_detected in existing_results
        if "pre_validacion_detected" in existing_results:
            pre_validacion_detected = existing_results["pre_validacion_detected"]
        else:
            # Use ValidationProcessor to check for pre-validation
            validation_processor = ValidationProcessor(self.recipe_config, {})
            validation_result = validation_processor.process(lead_data, conversation_data, {})
            pre_validacion_detected = validation_result.get("pre_validacion_detected", False)
        
        # Update state if pre-validation detected
        if pre_validacion_detected:
            state = "POST_VALIDACION"
        
        # Check if we already have handoff_invitation_detected in existing_results
        if "handoff_invitation_detected" in existing_results:
            handoff_invitation_detected = existing_results["handoff_invitation_detected"]
        else:
            # Use HandoffProcessor to check for handoff invitation
            handoff_processor = HandoffProcessor(self.recipe_config, {})
            handoff_result = handoff_processor.process(lead_data, conversation_data, {})
            handoff_invitation_detected = handoff_result.get("handoff_invitation_detected", False)
        
        # If handoff invitation was detected, override to HANDOFF state regardless of pre-validation
        if handoff_invitation_detected:
            state = "HANDOFF"
        
        result["conversation_state"] = state
        return result 