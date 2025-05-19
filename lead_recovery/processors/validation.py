from typing import Any, Dict, Optional

import pandas as pd

from lead_recovery.processors.utils import convert_df_to_message_list, strip_accents

from .base import BaseProcessor
from ._registry import register_processor


@register_processor
class ValidationProcessor(BaseProcessor):
    """
    Processor for detecting pre-validation questions in conversations.
    
    Identifies when pre-validation questions about vehicle loans or
    other eligibility criteria are present in the conversation.
    """
    
    GENERATED_COLUMNS = [
        "pre_validacion_detected"
    ]
    
    def _validate_params(self):
        """Validate processor-specific parameters."""
        known_params = {"skip_validacion_detection"}
        for param in self.params:
            if param not in known_params:
                raise ValueError(f"Unknown parameter '{param}' for {self.__class__.__name__}")
    
    def process(self, 
                lead_data: pd.Series, 
                conversation_data: Optional[pd.DataFrame],
                existing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect pre-validation questions in conversation data.
        
        Args:
            lead_data: Series containing lead information
            conversation_data: DataFrame with conversation messages
            existing_results: Dictionary of results from previous processors
            
        Returns:
            Dictionary containing validation detection results
        """
        # Initialize default result
        result = {
            "pre_validacion_detected": False
        }
        
        # Get skip parameter with default
        skip_validacion_detection = self.params.get("skip_validacion_detection", False)
        
        # Skip detection if requested
        if skip_validacion_detection:
            return result
            
        # Return early if no conversation data
        if conversation_data is None or conversation_data.empty:
            return result
            
        # Convert DataFrame to message list for compatibility
        conversation_messages = convert_df_to_message_list(conversation_data)
        if not conversation_messages:
            return result
        
        # Check for pre-validation messages in bot messages
        for msg in conversation_messages:
            if msg.get('msg_from') == 'bot':
                message_text = msg.get('message', '')
                if self._detect_pre_validacion(message_text):
                    result["pre_validacion_detected"] = True
                    break
        
        return result
    
    def _detect_pre_validacion(self, message_text: str) -> bool:
        """
        Detect if a message contains pre-validation questions about a vehicle.
        
        Args:
            message_text: The text of the message to check
            
        Returns:
            True if pre-validation message is detected, False otherwise
        """
        # Normalize message text - removing accents and whitespace differences
        message_text = strip_accents(message_text.lower())
        
        # Specific pre-validation phrases to detect
        pre_validacion_phrases = [
            "antes de continuar, necesito confirmar tres detalles importantes sobre tu auto",
            "necesito confirmar algunos detalles sobre tu auto y tu elegibilidad para el credito"
        ]
        
        # Check for phrases
        for phrase in pre_validacion_phrases:
            if phrase in message_text:
                return True
        
        return False 