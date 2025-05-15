"""
Python Flags Module - Streamlined Version

This module now only contains the FUNCTION_COLUMNS mapping and utility functions.
All flag-generating functions have been moved to individual processors.
"""


def strip_accents(text: str) -> str:
    """Remove accents from Spanish text to simplify pattern matching."""
    accent_map = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ü': 'u', 'Ü': 'U', 'ñ': 'n', 'Ñ': 'N'
    }
    for accented, plain in accent_map.items():
        text = text.replace(accented, plain)
    return text

# Mapping of Python flag functions to the columns they produce
# This allows the pipeline to dynamically include or exclude columns
# based on which functions are skipped
FUNCTION_COLUMNS = {
    "calculate_temporal_flags": [
        "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE", 
        "HOURS_MINUTES_SINCE_LAST_MESSAGE",
        "IS_WITHIN_REACTIVATION_WINDOW",
        "IS_RECOVERY_PHASE_ELIGIBLE",
        "LAST_USER_MESSAGE_TIMESTAMP_TZ",
        "LAST_MESSAGE_TIMESTAMP_TZ",
        "NO_USER_MESSAGES_EXIST"
    ],
    "extract_message_metadata": [
        "last_message_sender",
        "last_user_message_text",
        "last_kuna_message_text",
        "last_message_ts"
    ],
    "detect_human_transfer": [
        "human_transfer"
    ],
    "handoff_finalized": [
        "handoff_finalized"
    ],
    "analyze_handoff_process": [
        "handoff_invitation_detected",
        "handoff_response",
        "handoff_finalized"
    ],
    "count_consecutive_recovery_templates": [
        "consecutive_recovery_templates_count"
    ],
    "detect_recovery_template": [
        "recovery_template_detected"
    ],
    "detect_pre_validacion": [
        "pre_validacion_detected"
    ],
    "determine_conversation_state": [
        "conversation_state"
    ]
} 