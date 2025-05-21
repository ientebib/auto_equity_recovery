from typing import Any, Dict, Optional

import pandas as pd

from ._registry import register_processor
from .base import BaseProcessor


@register_processor
class MessageMetadataProcessor(BaseProcessor):
    """
    Processor for extracting metadata from conversation messages.
    
    Extracts information such as last sender, message content, and timestamps
    to provide context about the conversation state.
    """
    
    GENERATED_COLUMNS = [
        "last_message_sender",
        "last_user_message_text",
        "last_kuna_message_text",
        "last_message_ts"
    ]
    
    def _validate_params(self):
        """Validate processor-specific parameters."""
        known_params = {"max_message_length"}
        for param in self.params:
            if param not in known_params:
                raise ValueError(f"Unknown parameter '{param}' for {self.__class__.__name__}")
    
    def process(self, 
                lead_data: pd.Series, 
                conversation_data: Optional[pd.DataFrame],
                existing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from conversation messages.
        
        Args:
            lead_data: Series containing lead information
            conversation_data: DataFrame with conversation messages
            existing_results: Dictionary of results from previous processors
            
        Returns:
            Dictionary of extracted metadata
        """
        # Default values
        metadata = {
            "last_message_sender": "N/A",
            "last_user_message_text": "N/A",
            "last_kuna_message_text": "N/A",
            "last_message_ts": None
        }
        
        # Return early if no conversation data
        if conversation_data is None or conversation_data.empty:
            return metadata
            
        # Check for required columns
        required_cols = ['msg_from', 'message']
        if not all(col in conversation_data.columns for col in required_cols):
            return metadata
            
        try:
            # Get max message length parameter with default
            max_length = self.params.get("max_message_length", 150)
            
            # Sort by creation time if available
            if 'creation_time' in conversation_data.columns:
                sorted_df = conversation_data.sort_values('creation_time')
            else:
                sorted_df = conversation_data
                
            # Get last message info
            last_row = sorted_df.iloc[-1]
            sender = str(last_row['msg_from']).lower()
            metadata["last_message_sender"] = 'user' if sender == 'user' else 'kuna'
            
            # Get last message timestamp if available
            if 'creation_time' in sorted_df.columns:
                metadata["last_message_ts"] = last_row['creation_time']
                
            # Get last user message
            user_messages = sorted_df[sorted_df['msg_from'].str.lower() == 'user']
            if not user_messages.empty:
                metadata["last_user_message_text"] = str(user_messages.iloc[-1]['message'])
                
            # Get last kuna message
            kuna_messages = sorted_df[sorted_df['msg_from'].str.lower().isin(['bot', 'operator'])]
            if not kuna_messages.empty:
                metadata["last_kuna_message_text"] = str(kuna_messages.iloc[-1]['message'])
                
            # Truncate long messages
            if len(metadata["last_user_message_text"]) > max_length:
                metadata["last_user_message_text"] = metadata["last_user_message_text"][:max_length] + "..."
            if len(metadata["last_kuna_message_text"]) > max_length:
                metadata["last_kuna_message_text"] = metadata["last_kuna_message_text"][:max_length] + "..."
                
            return metadata
                
        except Exception:
            # Return default values in case of error
            return metadata 