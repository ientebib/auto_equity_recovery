from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
import pytz

from .base import BaseProcessor
from ._registry import register_processor


@register_processor
class TemporalProcessor(BaseProcessor):
    """
    Processor for calculating temporal flags and deltas from conversation history.
    
    Analyzes timestamps in conversation data to calculate time differences,
    reactivation windows, and other time-based features.

    Granular skip flags (skip_hours_minutes, skip_reactivation_flags, skip_timestamps, skip_user_message_flag)
    are deprecated. Use include/exclude columns to control output fields.
    Setting skip_detailed_temporal=True skips all calculations.
    """
    
    GENERATED_COLUMNS = [
        "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE", 
        "HOURS_MINUTES_SINCE_LAST_MESSAGE",
        "IS_WITHIN_REACTIVATION_WINDOW",
        "IS_RECOVERY_PHASE_ELIGIBLE",
        "LAST_USER_MESSAGE_TIMESTAMP_TZ",
        "LAST_MESSAGE_TIMESTAMP_TZ",
        "NO_USER_MESSAGES_EXIST"
    ]
    
    def _validate_params(self):
        """Validate processor-specific parameters."""
        known_params = {"timezone", "skip_detailed_temporal"}
        for param in self.params:
            if param not in known_params:
                raise ValueError(f"Unknown parameter '{param}' for {self.__class__.__name__}")
    
    def process(self, 
                lead_data: pd.Series, 
                conversation_data: Optional[pd.DataFrame],
                existing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate temporal flags from conversation data.
        
        Args:
            lead_data: Series containing lead information
            conversation_data: DataFrame with conversation messages
            existing_results: Dictionary of results from previous processors
            
        Returns:
            Dictionary of calculated temporal flags
        """
        # Initialize default return values
        result = {
            "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE": None, 
            "HOURS_MINUTES_SINCE_LAST_MESSAGE": None,
            "IS_WITHIN_REACTIVATION_WINDOW": False,
            "IS_RECOVERY_PHASE_ELIGIBLE": False,
            "LAST_USER_MESSAGE_TIMESTAMP_TZ": None,
            "LAST_MESSAGE_TIMESTAMP_TZ": None,
            "NO_USER_MESSAGES_EXIST": True  # Default to True (no user messages)
        }
        
        # Get parameters with defaults
        target_timezone_str = self.params.get("timezone", "America/Mexico_City")
        skip_detailed_temporal = self.params.get("skip_detailed_temporal", False)
        
        # Return early if skipping all calculations or no conversation data
        if skip_detailed_temporal or conversation_data is None or conversation_data.empty:
            return result
        
        # Check for required columns
        if 'creation_time' not in conversation_data.columns or 'msg_from' not in conversation_data.columns:
            return result
        
        try:
            target_tz = pytz.timezone(target_timezone_str)
            now = datetime.now(target_tz)
            
            # Convert timestamps to datetime objects
            conversation_data = conversation_data.copy()
            conversation_data['creation_time_dt'] = pd.to_datetime(conversation_data['creation_time'], errors='coerce')
            
            valid_times = conversation_data.dropna(subset=['creation_time_dt'])
            if valid_times.empty:
                return result
                
            valid_times = valid_times.sort_values('creation_time_dt')
            
            # Process last message timestamp
            last_message = valid_times.iloc[-1]
            last_message_ts = last_message['creation_time_dt']
            if last_message_ts.tzinfo is None:
                last_message_ts = last_message_ts.tz_localize('UTC')
            last_message_ts_tz = last_message_ts.astimezone(target_tz)
            result["LAST_MESSAGE_TIMESTAMP_TZ"] = last_message_ts_tz.isoformat()
            
            # Check for user messages
            user_messages = valid_times[valid_times['msg_from'].str.lower() == 'user']
            result["NO_USER_MESSAGES_EXIST"] = user_messages.empty
            
            # Calculate time since last message
            delta = now - last_message_ts_tz
            total_seconds = delta.total_seconds()
            hours_since_last = total_seconds / 3600
            hours = int(hours_since_last)
            minutes = int((hours_since_last - hours) * 60)
            result["HOURS_MINUTES_SINCE_LAST_MESSAGE"] = f"{hours}h {minutes}m"
            
            # If no user messages, we're done
            if user_messages.empty:
                return result
                
            # Process user-specific timestamps
            last_user_message = user_messages.iloc[-1]
            last_user_message_ts = last_user_message['creation_time_dt']
            if last_user_message_ts.tzinfo is None:
                last_user_message_ts = last_user_message_ts.tz_localize('UTC')
            last_user_message_ts_tz = last_user_message_ts.astimezone(target_tz)
            result["LAST_USER_MESSAGE_TIMESTAMP_TZ"] = last_user_message_ts_tz.isoformat()
            
            # Calculate time since last user message
            delta_user = now - last_user_message_ts_tz
            total_seconds_user = delta_user.total_seconds()
            hours_since_last_user = total_seconds_user / 3600
            user_hours = int(hours_since_last_user)
            user_minutes = int((hours_since_last_user - user_hours) * 60)
            result["HOURS_MINUTES_SINCE_LAST_USER_MESSAGE"] = f"{user_hours}h {user_minutes}m"
            
            # Calculate reactivation window flags
            result["IS_WITHIN_REACTIVATION_WINDOW"] = hours_since_last_user < 24
            result["IS_RECOVERY_PHASE_ELIGIBLE"] = hours_since_last_user >= 24
            
            return result
            
        except Exception:
            # Return default values in case of error
            return result 