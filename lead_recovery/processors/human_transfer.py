import re
from typing import Any, Dict, Optional

import pandas as pd

from lead_recovery.processors.utils import convert_df_to_message_list, strip_accents
from .patterns import HUMAN_TRANSFER_PATTERNS

from .base import BaseProcessor
from ._registry import register_processor


@register_processor
class HumanTransferProcessor(BaseProcessor):
    """
    Processor for detecting human transfer events in conversations.
    
    Identifies when a conversation was transferred to a human agent
    based on specific phrases in bot messages.
    """
    
    GENERATED_COLUMNS = [
        "human_transfer"
    ]
    
    def _validate_params(self):
        """Validate processor-specific parameters."""
        known_params = {"skip_human_transfer_detection"}
        for param in self.params:
            if param not in known_params:
                raise ValueError(f"Unknown parameter '{param}' for {self.__class__.__name__}")
    
    def process(self, 
                lead_data: pd.Series, 
                conversation_data: Optional[pd.DataFrame],
                existing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect human transfer events in conversation data.
        
        Args:
            lead_data: Series containing lead information
            conversation_data: DataFrame with conversation messages
            existing_results: Dictionary of results from previous processors
            
        Returns:
            Dictionary containing human transfer detection result
        """
        # Initialize default result
        result = {
            "human_transfer": False
        }
        
        # Get skip parameter with default
        skip_human_transfer_detection = self.params.get("skip_human_transfer_detection", False)
        
        # Skip detection if requested
        if skip_human_transfer_detection:
            return result
            
        # Return early if no conversation data
        if conversation_data is None or conversation_data.empty:
            return result
            
        # Convert DataFrame to message list for compatibility
        conversation_messages = convert_df_to_message_list(conversation_data)
        if not conversation_messages:
            return result
        
        # Compile patterns from the imported list
        compiled_transfer_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in HUMAN_TRANSFER_PATTERNS
        ]
        
        # Check all bot messages
        for msg in conversation_messages:
            if msg.get('msg_from') == 'bot':
                message_content = msg.get('message', '')
                stripped_message_content = strip_accents(message_content)
                
                for pattern in compiled_transfer_patterns:
                    if pattern.search(stripped_message_content):
                        result["human_transfer"] = True
                        return result
        
        return result 