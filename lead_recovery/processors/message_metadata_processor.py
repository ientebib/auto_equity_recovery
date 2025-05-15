"""message_metadata_processor.py
Processor for extracting basic message metadata from conversations.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandas as pd

from lead_recovery.processors.base import BaseProcessor
from lead_recovery.recipe_schema import RecipeMeta

logger = logging.getLogger(__name__)

class MessageMetadataProcessor(BaseProcessor):
    """Extract basic metadata from conversation messages."""
    
    # Define the columns this processor generates
    GENERATED_COLUMNS = [
        "last_message_sender",
        "last_user_message_text",
        "last_kuna_message_text",
        "last_message_ts"
    ]

    def __init__(self, recipe_config: RecipeMeta, processor_params: Dict[str, Any], global_config: Optional[Dict[str, Any]] = None):
        """Initialize the processor.
        
        Args:
            recipe_config: The recipe configuration
            processor_params: Configuration specific to this processor instance
            global_config: System-wide configuration
        """
        super().__init__(recipe_config, processor_params, global_config)
    
    def process(self, lead_data: pd.Series, conversation_data: pd.DataFrame, 
                existing_results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract message metadata from conversation.
        
        Args:
            lead_data: Series containing lead information
            conversation_data: DataFrame with conversation messages
            existing_results: Dictionary of results from previous processors
            
        Returns:
            Dictionary with message metadata
        """
        metadata = {
            "last_message_sender": "N/A",
            "last_user_message_text": "N/A",
            "last_kuna_message_text": "N/A",
            "last_message_ts": None
        }
        
        if conversation_data is None or conversation_data.empty or 'msg_from' not in conversation_data.columns or 'message' not in conversation_data.columns:
            logger.warning("Cannot extract message metadata: conversation data is empty or missing required columns")
            return metadata
        
        try:
            # Ensure datetime for sorting
            conversation_data = conversation_data.copy()
            if 'creation_time' in conversation_data.columns:
                conversation_data['creation_time_dt'] = pd.to_datetime(conversation_data['creation_time'], errors='coerce')
                conversation_data = conversation_data.sort_values('creation_time_dt')
                
                # Get the last message timestamp if available
                last_row = conversation_data.iloc[-1]
                if 'creation_time_dt' in last_row and pd.notna(last_row['creation_time_dt']):
                    metadata["last_message_ts"] = last_row['creation_time_dt']
            
            # Find last message sender
            last_sender = conversation_data['msg_from'].iloc[-1] if len(conversation_data) > 0 else "N/A"
            metadata["last_message_sender"] = str(last_sender).lower()
            
            # Find last user message
            user_messages = conversation_data[conversation_data['msg_from'].str.lower() == 'user']
            if not user_messages.empty:
                metadata["last_user_message_text"] = user_messages['message'].iloc[-1]
            
            # Find last bot/kuna message
            bot_messages = conversation_data[conversation_data['msg_from'].str.lower() == 'bot']
            if not bot_messages.empty:
                metadata["last_kuna_message_text"] = bot_messages['message'].iloc[-1]
                
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting message metadata: {e}", exc_info=True)
            return metadata 