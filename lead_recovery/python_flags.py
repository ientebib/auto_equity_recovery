"""
Python Flags Module

Central functions for analyzing message content in lead recovery conversations.
Contains detection for handoffs, templates, and other message features.
All functions support skip flags to control execution.
"""

import re
import json
import logging
import pandas as pd
import pytz
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

# Setup logger
logger = logging.getLogger("lead_recovery.python_flags")

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

def detect_recovery_template(message_text: str, skip: bool = False) -> bool:
    """Detect if a message is a recovery template for the simulation_to_handoff recipe.
    
    Args:
        message_text: The text of the message to check
        skip: If True, skip detection and return False
        
    Returns:
        True if the message is a recovery template, False otherwise
    """
    # Skip detection if requested
    if skip:
        return False
        
    # Recovery template key phrases
    recovery_phrases = [
        "préstamo por tu auto",
        "oferta pre aprobada",
        "aprovecha tu oferta",
        "espera de que nos proporciones tus documentos",
        "template:"
    ]
    
    # Check for any of the recovery phrases
    message_text_lower = message_text.lower()
    for phrase in recovery_phrases:
        if phrase in message_text_lower:
            return True
    
    return False

def detect_topup_template(message_text: str, skip: bool = False) -> bool:
    """Detect if a message is a top-up template for the top_up_may recipe.
    
    Args:
        message_text: The text of the message to check
        skip: If True, skip detection and return False
        
    Returns:
        True if the message is a top-up template, False otherwise
    """
    # Skip detection if requested
    if skip:
        return False
        
    # Top-up template regex patterns
    topup_patterns = [
        # Pattern for template message about pre-approved loan
        r"(?i)template:.*pre\s*aprobado",
        # Pattern for Hola + name + wave + pre-approved/credit message
        r"(?i)¡?hola\s+[\w\s]+!?\s+:?wave:?.*crédito\s+pre\s*aprobado",
        # Pattern for recognition of good payment behavior
        r"(?i).*reconocer\s+tu\s+excelente\s+comportamiento\s+de\s+pago",
        # Pattern for thanking for good client history
        r"(?i).*agradecerte\s+por\s+mantener\s+un\s+buen\s+historial\s+como\s+cliente"
    ]
    
    # Check for any of the top-up patterns
    for pattern in topup_patterns:
        if re.search(pattern, message_text):
            return True
    
    return False

def count_consecutive_recovery_templates(conversation_messages: List[Dict[str, Any]], skip: bool = False) -> int:
    """Count consecutive recovery templates at the end of a conversation.
    
    Args:
        conversation_messages: List of conversation message dictionaries
        skip: If True, skip counting and return 0
        
    Returns:
        Number of consecutive recovery templates
    """
    # Skip counting if requested
    if skip:
        return 0
        
    count = 0
    # Start from the end and go backwards
    for i in range(len(conversation_messages) - 1, -1, -1):
        msg = conversation_messages[i]
        if msg.get('msg_from') == 'bot':
            message_text = msg.get('message', '')
            if detect_recovery_template(message_text):
                count += 1
            else:
                # Break the count if a non-recovery template is found
                break
        else:
            # Break the count if a user message is found
            break
    
    return count

def detect_human_transfer(conversation_messages: List[Dict[str, Any]], skip: bool = False) -> bool:
    """Detect if a conversation was transferred to a human agent.
    
    Args:
        conversation_messages: List of conversation message dictionaries
        skip: If True, skip detection and return False
        
    Returns:
        True if human transfer was detected, False otherwise
    """
    # Skip detection if requested
    if skip:
        return False
        
    # Phrases that indicate human transfer
    human_transfer_patterns = [
        re.compile(r"transferirte con un asesor humano", re.IGNORECASE),
        re.compile(r"conectarte con un agente humano", re.IGNORECASE),
        re.compile(r"hablar con un asesor", re.IGNORECASE),
        re.compile(r"comunicarte con un asesor", re.IGNORECASE),
        re.compile(r"transferir con un ejecutivo", re.IGNORECASE),
        re.compile(r"un momento, estoy teniendo problemas", re.IGNORECASE),
        re.compile(r"un supervisor te asistirá", re.IGNORECASE),
        re.compile(r"transferirte con una persona", re.IGNORECASE)
    ]
    
    phone = conversation_messages[0].get('cleaned_phone_number', 'unknown')
    
    # Check all bot messages
    for i, msg in enumerate(conversation_messages):
        if msg.get('msg_from') == 'bot':
            message_content = msg.get('message', '')
            stripped_message_content = strip_accents(message_content)
            
            for pattern in human_transfer_patterns:
                if pattern.search(stripped_message_content):
                    logger.info(f"Human transfer detected in message {i} for phone {phone}")
                    return True
    
    return False

def handoff_invitation(conversation_messages: List[Dict[str, Any]], 
                       offer_message_index: int = -1,
                       skip: bool = False) -> bool:
    """Detect if a handoff invitation was sent to the user.
    
    Args:
        conversation_messages: List of conversation message dictionaries
        offer_message_index: Index of the offer message, if known (to only check after this)
        skip: If True, skip detection and return False
        
    Returns:
        True if handoff invitation was detected, False otherwise
    """
    # Skip detection if requested
    if skip:
        return False
        
    # Regex to detect handoff invitation - using a significant portion of text without emojis
    handoff_invitation_pattern = re.compile(
        r"Estas a un paso de la aprobacion de tu prestamo personal|"
        r"un paso de la aprobacion|"
        r"Esta oferta es por tiempo limitado|"
        r"Completa el proceso ahora|"
        r"asegura tu prestamo en minutos|"
        r"No pierdas la oportunidad", 
        re.IGNORECASE
    )
    
    phone = conversation_messages[0].get('cleaned_phone_number', 'unknown')
    
    for i, msg in enumerate(conversation_messages):
        # Only check bot messages
        if msg.get('msg_from') == 'bot' and (offer_message_index == -1 or i > offer_message_index):
            message_content = msg.get('message', '')
            stripped_message_content = strip_accents(message_content)
            
            if handoff_invitation_pattern.search(stripped_message_content):
                logger.info(f"Handoff invitation detected in message {i} for phone {phone}")
                return True
    
    logger.debug(f"No handoff invitation found for phone {phone}")
    return False

def handoff_started(conversation_messages: List[Dict[str, Any]], 
                   handoff_invitation_index: int,
                   skip: bool = False) -> str:
    """Check if user started the handoff process after receiving an invitation.
    
    Args:
        conversation_messages: List of conversation message dictionaries
        handoff_invitation_index: Index of the message containing handoff invitation
        skip: If True, skip detection and return "IGNORED_HANDOFF"
        
    Returns:
        Response type: "STARTED_HANDOFF", "DECLINED_HANDOFF", or "IGNORED_HANDOFF"
    """
    # Skip detection if requested
    if skip:
        return "IGNORED_HANDOFF"
        
    # Default response
    handoff_response = "IGNORED_HANDOFF"
    phone = conversation_messages[0].get('cleaned_phone_number', 'unknown')
    
    # Check if there's a user message after the handoff invitation
    if handoff_invitation_index + 1 < len(conversation_messages):
        next_message = conversation_messages[handoff_invitation_index + 1]
        
        if next_message.get('msg_from') == 'user':
            try:
                # User message is expected to be a JSON string with a "button" key
                raw_user_message = next_message.get('message', '{}')
                user_message_data = json.loads(raw_user_message)
                button_clicked = user_message_data.get('button')
                
                if button_clicked == "Empezar":
                    handoff_response = "STARTED_HANDOFF"
                    logger.info(f"User {phone} clicked 'Empezar' to start handoff")
                elif button_clicked == "De momento no":
                    handoff_response = "DECLINED_HANDOFF"
                    logger.info(f"User {phone} clicked 'De momento no' to decline handoff")
            except (json.JSONDecodeError, AttributeError):
                # If message is not valid JSON or other issues, consider "IGNORED_HANDOFF"
                logger.debug(f"Could not parse button response for phone {phone}: {raw_user_message}")
    
    return handoff_response

def handoff_finalized(conversation_messages: List[Dict[str, Any]], 
                     start_index: int = 0,
                     skip: bool = False) -> bool:
    """Check if the handoff process was completed successfully.
    
    Args:
        conversation_messages: List of conversation message dictionaries
        start_index: Index to start checking from (usually after handoff started)
        skip: If True, skip detection and return False
        
    Returns:
        True if handoff was finalized, False otherwise
    """
    # Skip detection if requested
    if skip:
        return False
        
    # Phrase that indicates handoff was finalized - only using the key signature phrase
    handoff_finalized_pattern = re.compile(r"Seguro que tu taza de café", re.IGNORECASE)
    
    phone = conversation_messages[0].get('cleaned_phone_number', 'unknown')
    
    # Check all bot messages after the start_index
    for i, msg in enumerate(conversation_messages):
        if msg.get('msg_from') == 'bot' and i > start_index:
            message_content = msg.get('message', '')
            stripped_message_content = strip_accents(message_content)
            
            if handoff_finalized_pattern.search(stripped_message_content):
                logger.info(f"Handoff finalization detected in message {i} for phone {phone}")
                return True
    
    return False

def analyze_handoff_process(conversation_messages: List[Dict[str, Any]], 
                          skip_handoff_invitation: bool = False,
                          skip_handoff_started: bool = False,
                          skip_handoff_finalized: bool = False) -> Dict[str, Any]:
    """Full analysis of the handoff process in a conversation.
    
    Args:
        conversation_messages: List of conversation message dictionaries
        skip_handoff_invitation: If True, skip handoff invitation detection
        skip_handoff_started: If True, skip handoff started detection
        skip_handoff_finalized: If True, skip handoff finalized detection
        
    Returns:
        Dictionary with handoff analysis results
    """
    result = {
        "handoff_invitation_detected": False,
        "handoff_response": "NO_INVITATION",
        "handoff_finalized": False
    }
    
    # Skip the whole process if all stages are skipped
    if skip_handoff_invitation and skip_handoff_started and skip_handoff_finalized:
        return result
        
    # First check if handoff invitation was sent (unless skipped)
    invitation_index = -1
    if not skip_handoff_invitation:
        for i, msg in enumerate(conversation_messages):
            if msg.get('msg_from') == 'bot':
                # Use the handoff_invitation function internally
                if handoff_invitation([msg], -1):
                    result["handoff_invitation_detected"] = True
                    invitation_index = i
                    break
    
    # If invitation was detected, check user response (unless skipped)
    if result["handoff_invitation_detected"] and not skip_handoff_started:
        result["handoff_response"] = handoff_started(conversation_messages, invitation_index)
        
        # If user started handoff, check if it was finalized (unless skipped)
        if result["handoff_response"] == "STARTED_HANDOFF" and not skip_handoff_finalized:
            result["handoff_finalized"] = handoff_finalized(conversation_messages, invitation_index)
    
    return result

def extract_message_metadata(conversation_df, skip: bool = False) -> Dict[str, Any]:
    """Extract metadata from conversation messages like last sender, last message content, etc.
    
    Args:
        conversation_df: DataFrame containing conversation messages
        skip: If True, skip extraction and return default values
        
    Returns:
        Dictionary with extracted metadata
    """
    # Default values
    metadata = {
        "last_message_sender": "N/A",
        "last_user_message_text": "N/A",
        "last_kuna_message_text": "N/A",
        "last_message_ts": None
    }
    
    # Skip extraction if requested
    if skip or conversation_df.empty:
        return metadata
        
    # Check for required columns
    required_cols = ['msg_from', 'message']
    if not all(col in conversation_df.columns for col in required_cols):
        return metadata
        
    try:
        # Sort by creation time if available
        if 'creation_time' in conversation_df.columns:
            sorted_df = conversation_df.sort_values('creation_time')
        else:
            sorted_df = conversation_df
            
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
        max_length = 150  # Truncate to this length
        if len(metadata["last_user_message_text"]) > max_length:
            metadata["last_user_message_text"] = metadata["last_user_message_text"][:max_length] + "..."
        if len(metadata["last_kuna_message_text"]) > max_length:
            metadata["last_kuna_message_text"] = metadata["last_kuna_message_text"][:max_length] + "..."
            
    except Exception as e:
        logger.warning(f"Error extracting message metadata: {e}")
        
    return metadata 

def calculate_temporal_flags(
    conversation_history: pd.DataFrame, 
    target_timezone_str: str = 'America/Mexico_City', 
    skip_detailed_temporal: bool = False,
    skip_hours_minutes: bool = False,
    skip_reactivation_flags: bool = False,
    skip_timestamps: bool = False,
    skip_user_message_flag: bool = False
) -> Dict[str, Any]:
    """Calculate temporal flags and deltas from a conversation history dataframe.
    
    This function analyzes the timestamps in a conversation history and returns
    time-related flags and values that can be passed to the LLM prompt.
    
    Args:
        conversation_history: DataFrame containing conversation messages.
                             Should have columns: 'creation_time', 'msg_from'.
        target_timezone_str: Timezone to convert timestamps to (default: 'America/Mexico_City')
        skip_detailed_temporal: If True, skips ALL detailed calculations except basic flags,
                                overriding all other skip parameters.
        skip_hours_minutes: If True, skips calculation of hour/minute deltas
                           (HOURS_MINUTES_SINCE_LAST_USER_MESSAGE, HOURS_MINUTES_SINCE_LAST_MESSAGE)
        skip_reactivation_flags: If True, skips calculation of reactivation window flags
                                (IS_WITHIN_REACTIVATION_WINDOW, IS_RECOVERY_PHASE_ELIGIBLE)
        skip_timestamps: If True, skips calculation of timestamp values
                        (LAST_USER_MESSAGE_TIMESTAMP_TZ, LAST_MESSAGE_TIMESTAMP_TZ)
        skip_user_message_flag: If True, skips checking if user has never sent a message
                               (NO_USER_MESSAGES_EXIST)
        
    Returns:
        Dictionary containing temporal flags.
    """
    # Minimize logging when skipping
    if skip_detailed_temporal:
        # Just use debug level to reduce log noise, don't log every call
        logger.debug(f"calculate_temporal_flags called with skip_detailed_temporal={skip_detailed_temporal}")
    else:
        # Only log normal info level when actually calculating
        logger.debug(f"calculate_temporal_flags called with skip_detailed_temporal={skip_detailed_temporal}")
    
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
    
    # Return minimal data if skip_detailed_temporal is True
    if skip_detailed_temporal:
        logger.debug("Skipping temporal flags calculation due to skip_detailed_temporal=True")
        return result
    
    # Early return if input data is invalid
    if conversation_history.empty or 'creation_time' not in conversation_history.columns or 'msg_from' not in conversation_history.columns:
        logger.warning("Cannot calculate temporal flags: conversation history is empty or missing required columns")
        return result
    
    try:
        target_tz = pytz.timezone(target_timezone_str)
        now = datetime.now(target_tz)
        
        conversation_history = conversation_history.copy()
        conversation_history['creation_time_dt'] = pd.to_datetime(conversation_history['creation_time'], errors='coerce')
        
        valid_times = conversation_history.dropna(subset=['creation_time_dt'])
        if valid_times.empty:
            logger.warning("No valid timestamps found in conversation history")
            return result
        
        valid_times = valid_times.sort_values('creation_time_dt')
        
        # --- LAST_MESSAGE_TIMESTAMP_TZ calculation (group c) ---
        if not skip_timestamps:
            last_message = valid_times.iloc[-1]
            last_message_ts = last_message['creation_time_dt']
            if last_message_ts.tzinfo is None:
                last_message_ts = last_message_ts.tz_localize('UTC')
            last_message_ts_tz = last_message_ts.astimezone(target_tz)
            result["LAST_MESSAGE_TIMESTAMP_TZ"] = last_message_ts_tz.isoformat()
        else:
            last_message = valid_times.iloc[-1]
            last_message_ts = last_message['creation_time_dt']
            if last_message_ts.tzinfo is None:
                last_message_ts = last_message_ts.tz_localize('UTC')
            last_message_ts_tz = last_message_ts.astimezone(target_tz)
        
        # --- NO_USER_MESSAGES_EXIST calculation (group d) ---
        user_messages = valid_times[valid_times['msg_from'].str.lower() == 'user']
        if not skip_user_message_flag:
            result["NO_USER_MESSAGES_EXIST"] = user_messages.empty
        
        # --- HOURS_MINUTES_SINCE_LAST_MESSAGE calculation (group a) ---
        if not skip_hours_minutes:
            delta = now - last_message_ts_tz
            total_seconds = delta.total_seconds()
            hours_since_last = total_seconds / 3600
            hours = int(hours_since_last)
            minutes = int((hours_since_last - hours) * 60)
            result["HOURS_MINUTES_SINCE_LAST_MESSAGE"] = f"{hours}h {minutes}m"
        
        # If there are no user messages, we're done
        if user_messages.empty:
            return result
            
        # --- Process user-specific flags only if user messages exist ---
        # Get last user message timestamp
        last_user_message = user_messages.iloc[-1]
        last_user_message_ts = last_user_message['creation_time_dt']
        if last_user_message_ts.tzinfo is None:
            last_user_message_ts = last_user_message_ts.tz_localize('UTC')
        last_user_message_ts_tz = last_user_message_ts.astimezone(target_tz)
        
        # --- LAST_USER_MESSAGE_TIMESTAMP_TZ calculation (group c) ---
        if not skip_timestamps:
            result["LAST_USER_MESSAGE_TIMESTAMP_TZ"] = last_user_message_ts_tz.isoformat()
        
        # --- HOURS_MINUTES_SINCE_LAST_USER_MESSAGE calculation (group a) ---
        if not skip_hours_minutes:
            delta_user = now - last_user_message_ts_tz
            total_seconds_user = delta_user.total_seconds()
            hours_since_last_user = total_seconds_user / 3600
            user_hours = int(hours_since_last_user)
            user_minutes = int((hours_since_last_user - user_hours) * 60)
            result["HOURS_MINUTES_SINCE_LAST_USER_MESSAGE"] = f"{user_hours}h {user_minutes}m"
            
            # Save hours_since_last_user for reactivation window calculations
            hours_since_last_user = total_seconds_user / 3600
        else:
            # Calculate hours_since_last_user if needed for reactivation flags but not saved in result
            delta_user = now - last_user_message_ts_tz
            hours_since_last_user = delta_user.total_seconds() / 3600
        
        # --- Reactivation window flags calculation (group b) ---
        if not skip_reactivation_flags:
            result["IS_WITHIN_REACTIVATION_WINDOW"] = hours_since_last_user < 24
            result["IS_RECOVERY_PHASE_ELIGIBLE"] = hours_since_last_user >= 24
        
        # Only log the results when we're actually calculating them
        if not skip_detailed_temporal:
            phone = conversation_history.get(CLEANED_PHONE_COLUMN_NAME, ['unknown'])[0] if CLEANED_PHONE_COLUMN_NAME in conversation_history else 'unknown'
            logger.debug(f"[DEBUG] Calculated temporal flags for phone {phone} (skip_detailed={skip_detailed_temporal}): {result}")
        
        return result
    
    except Exception as e:
        logger.error(f"Error calculating temporal flags: {e}", exc_info=True)
        # Return the initialized dict with whatever could be populated if an error occurs mid-way
        return result 

def detect_pre_validacion(message_text: str, skip: bool = False) -> bool:
    """Detect if a message contains pre-validation questions about a vehicle.
    
    Looks for specific phrases that indicate the start of a pre-validation process
    for vehicle loans.
    
    Args:
        message_text: The text of the message to check
        skip: If True, skip detection and return False
        
    Returns:
        True if pre-validation message is detected, False otherwise
    """
    # Skip detection if requested
    if skip:
        return False
    
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

def determine_conversation_state(conversation_messages: List[Dict[str, Any]], 
                                skip: bool = False) -> str:
    """Determine the current state of a conversation based on pre-validation and handoff detection.
    
    States:
    - PRE_VALIDACION: Initial state before eligibility questions are sent
    - POST_VALIDACION: Eligibility questions were sent but handoff invitation not yet sent
    - HANDOFF: Any handoff state (invitation sent, accepted, rejected, etc.)
    
    Args:
        conversation_messages: List of conversation message dictionaries
        skip: If True, skip determination and return "UNKNOWN"
        
    Returns:
        String indicating the conversation state: "PRE_VALIDACION", "POST_VALIDACION", "HANDOFF", or "UNKNOWN"
    """
    # Skip determination if requested
    if skip:
        return "UNKNOWN"
        
    # Default state
    state = "PRE_VALIDACION"
    
    # Flag to track if pre-validation message was detected
    pre_validacion_detected = False
    
    # Check for pre-validation messages
    for msg in conversation_messages:
        if msg.get('msg_from') == 'bot':
            message_text = msg.get('message', '')
            if detect_pre_validacion(message_text):
                pre_validacion_detected = True
                state = "POST_VALIDACION"  # Update state if pre-validation detected
                break
    
    # Check for handoff using the existing analyze_handoff_process function
    handoff_status = analyze_handoff_process(conversation_messages)
    
    # If handoff invitation was detected, override to HANDOFF state regardless of pre-validation
    if handoff_status.get("handoff_invitation_detected", False):
        state = "HANDOFF"
    
    return state

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