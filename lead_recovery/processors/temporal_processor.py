"""temporal_processor.py
Processor for calculating temporal analysis flags from conversation history.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
import pytz

from lead_recovery.processors.base import BaseProcessor
from lead_recovery.recipe_schema import RecipeMeta

logger = logging.getLogger(__name__)

class TemporalProcessor(BaseProcessor):
    """Process conversation history to generate temporal flags and metrics."""
    
    # Define generated columns
    GENERATED_COLUMNS = [
        "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE",
        "HOURS_MINUTES_SINCE_LAST_MESSAGE",
        "IS_WITHIN_REACTIVATION_WINDOW",
        "IS_RECOVERY_PHASE_ELIGIBLE",
        "LAST_USER_MESSAGE_TIMESTAMP_TZ",
        "LAST_MESSAGE_TIMESTAMP_TZ",
        "NO_USER_MESSAGES_EXIST"
    ]

    def __init__(self, recipe_config: RecipeMeta, processor_params: Dict[str, Any], global_config: Optional[Dict[str, Any]] = None):
        """Initialize the processor.
        
        Args:
            recipe_config: The recipe configuration
            processor_params: Configuration specific to this processor instance
            global_config: System-wide configuration
        """
        super().__init__(recipe_config, processor_params, global_config)
        
        # Get configuration from params
        self.target_timezone = self.params.get('target_timezone', 'America/Mexico_City')
        self.skip_hours_minutes = self.params.get('skip_hours_minutes', False)
        self.skip_reactivation_flags = self.params.get('skip_reactivation_flags', False)
        self.skip_timestamps = self.params.get('skip_timestamps', False)
        self.skip_user_message_flag = self.params.get('skip_user_message_flag', False)
    
    def process(self, lead_data: pd.Series, conversation_data: pd.DataFrame, 
                existing_results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate temporal flags from conversation history.
        
        Args:
            lead_data: Series containing lead information
            conversation_data: DataFrame with conversation messages
            existing_results: Dictionary of results from previous processors
            
        Returns:
            Dictionary with temporal flags and metrics
        """
        # Initialize default return values
        temporal_flags = {
            "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE": None, 
            "HOURS_MINUTES_SINCE_LAST_MESSAGE": None,
            "IS_WITHIN_REACTIVATION_WINDOW": False,
            "IS_RECOVERY_PHASE_ELIGIBLE": False,
            "LAST_USER_MESSAGE_TIMESTAMP_TZ": None,
            "LAST_MESSAGE_TIMESTAMP_TZ": None,
            "NO_USER_MESSAGES_EXIST": True  # Default to True (no user messages)
        }
        
        if conversation_data is None or conversation_data.empty or 'creation_time' not in conversation_data.columns or 'msg_from' not in conversation_data.columns:
            logger.warning("Cannot calculate temporal flags: conversation history is empty or missing required columns")
            return temporal_flags
        
        try:
            target_tz = pytz.timezone(self.target_timezone)
            now = datetime.now(target_tz)
            
            conversation_data = conversation_data.copy()
            conversation_data['creation_time_dt'] = pd.to_datetime(conversation_data['creation_time'], errors='coerce')
            
            valid_times = conversation_data.dropna(subset=['creation_time_dt'])
            if valid_times.empty:
                logger.warning("No valid timestamps found in conversation history")
                return temporal_flags
            
            valid_times = valid_times.sort_values('creation_time_dt')
            
            last_message = valid_times.iloc[-1]
            last_message_ts = last_message['creation_time_dt']
            if last_message_ts.tzinfo is None:
                last_message_ts = last_message_ts.tz_localize('UTC')
            last_message_ts_tz = last_message_ts.astimezone(target_tz)
            
            if not self.skip_timestamps:
                temporal_flags["LAST_MESSAGE_TIMESTAMP_TZ"] = last_message_ts_tz.isoformat()
            
            user_messages = valid_times[valid_times['msg_from'].str.lower() == 'user']
            if not self.skip_user_message_flag:
                temporal_flags["NO_USER_MESSAGES_EXIST"] = user_messages.empty

            # Only calculate hours/minutes if not skipped and we have data
            if not self.skip_hours_minutes:
                delta = now - last_message_ts_tz
                total_seconds = delta.total_seconds()
                hours_since_last = total_seconds / 3600
                hours = int(hours_since_last)
                minutes = int((hours_since_last - hours) * 60)
                temporal_flags["HOURS_MINUTES_SINCE_LAST_MESSAGE"] = f"{hours}h {minutes}m"
            
            if not user_messages.empty:
                last_user_message = user_messages.iloc[-1]
                last_user_message_ts = last_user_message['creation_time_dt']
                if last_user_message_ts.tzinfo is None:
                    last_user_message_ts = last_user_message_ts.tz_localize('UTC')
                last_user_message_ts_tz = last_user_message_ts.astimezone(target_tz)
                
                if not self.skip_timestamps:
                    temporal_flags["LAST_USER_MESSAGE_TIMESTAMP_TZ"] = last_user_message_ts_tz.isoformat()
                
                if not self.skip_hours_minutes:
                    delta_user = now - last_user_message_ts_tz
                    total_seconds_user = delta_user.total_seconds()
                    hours_since_last_user = total_seconds_user / 3600
                    user_hours = int(hours_since_last_user)
                    user_minutes = int((hours_since_last_user - user_hours) * 60)
                    temporal_flags["HOURS_MINUTES_SINCE_LAST_USER_MESSAGE"] = f"{user_hours}h {user_minutes}m"
                
                if not self.skip_reactivation_flags:
                    hours_since_last_user = delta_user.total_seconds() / 3600
                    temporal_flags["IS_WITHIN_REACTIVATION_WINDOW"] = hours_since_last_user < 24
                    temporal_flags["IS_RECOVERY_PHASE_ELIGIBLE"] = hours_since_last_user >= 24
            
            return temporal_flags
        
        except Exception as e:
            logger.error(f"Error calculating temporal flags: {e}", exc_info=True)
            # Return the initialized dict with whatever could be populated if an error occurs mid-way
            return temporal_flags 