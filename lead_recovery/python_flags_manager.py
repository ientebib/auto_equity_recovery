"""
Python Flags Manager Module

Manages the relationship between Python flag functions and their output columns.
This module provides utilities to dynamically include or exclude columns 
based on which Python flag functions are enabled or disabled.
"""

import logging
from pathlib import Path
from typing import Dict, List

import yaml

from .python_flags import FUNCTION_COLUMNS

logger = logging.getLogger(__name__)

def get_python_flag_columns(
    skip_temporal_flags: bool = False,
    skip_metadata_extraction: bool = False,
    skip_handoff_detection: bool = False,
    skip_human_transfer: bool = False,
    skip_recovery_template_detection: bool = False,
    skip_consecutive_templates_count: bool = False,
    skip_handoff_invitation: bool = False,
    skip_handoff_started: bool = False,
    skip_handoff_finalized: bool = False,
    skip_detailed_temporal: bool = False,
    skip_hours_minutes: bool = False,
    skip_reactivation_flags: bool = False,
    skip_timestamps: bool = False,
    skip_user_message_flag: bool = False,
    skip_pre_validacion_detection: bool = False,
    skip_conversation_state: bool = False
) -> List[str]:
    """
    Get a list of columns produced by Python flag functions based on skip flags.
    
    Args:
        skip_temporal_flags: Skip all temporal flag calculations
        skip_metadata_extraction: Skip message metadata extraction
        skip_handoff_detection: Skip all handoff detection
        skip_human_transfer: Skip human transfer detection
        skip_recovery_template_detection: Skip recovery template detection
        skip_consecutive_templates_count: Skip counting consecutive recovery templates
        skip_handoff_invitation: Skip handoff invitation detection
        skip_handoff_started: Skip handoff started detection
        skip_handoff_finalized: Skip handoff finalized detection
        skip_detailed_temporal: Skip detailed temporal flag calculations
        skip_hours_minutes: Skip hour/minute delta calculations
        skip_reactivation_flags: Skip reactivation window flag calculations
        skip_timestamps: Skip timestamp formatting
        skip_user_message_flag: Skip user message existence flag
        skip_pre_validacion_detection: Skip pre-validation detection
        skip_conversation_state: Skip conversation state determination
        
    Returns:
        List of column names that will be included in the output
    """
    included_columns = set()
    
    # Calculate temporal flags
    if not skip_temporal_flags:
        temporal_columns = set(FUNCTION_COLUMNS["calculate_temporal_flags"])
        
        # Handle detailed skip flags for temporal calculations
        if skip_detailed_temporal:
            # Remove detailed temporal columns, keep only basic ones
            temporal_columns.discard("HOURS_MINUTES_SINCE_LAST_USER_MESSAGE")
            temporal_columns.discard("HOURS_MINUTES_SINCE_LAST_MESSAGE")
            temporal_columns.discard("IS_WITHIN_REACTIVATION_WINDOW")
            temporal_columns.discard("IS_RECOVERY_PHASE_ELIGIBLE")
        else:
            # Handle granular skip flags
            if skip_hours_minutes:
                temporal_columns.discard("HOURS_MINUTES_SINCE_LAST_USER_MESSAGE")
                temporal_columns.discard("HOURS_MINUTES_SINCE_LAST_MESSAGE")
            
            if skip_reactivation_flags:
                temporal_columns.discard("IS_WITHIN_REACTIVATION_WINDOW")
                temporal_columns.discard("IS_RECOVERY_PHASE_ELIGIBLE")
            
        if skip_timestamps:
            temporal_columns.discard("LAST_USER_MESSAGE_TIMESTAMP_TZ")
            temporal_columns.discard("LAST_MESSAGE_TIMESTAMP_TZ")
            
        if skip_user_message_flag:
            temporal_columns.discard("NO_USER_MESSAGES_EXIST")
            
        included_columns.update(temporal_columns)
    
    # Message metadata extraction
    if not skip_metadata_extraction:
        included_columns.update(FUNCTION_COLUMNS["extract_message_metadata"])
    
    # Human transfer detection
    if not skip_human_transfer:
        included_columns.update(FUNCTION_COLUMNS["detect_human_transfer"])
    
    # Recovery template detection
    if not skip_recovery_template_detection:
        included_columns.update(FUNCTION_COLUMNS["detect_recovery_template"])
    
    # Pre-validation detection
    if not skip_pre_validacion_detection:
        included_columns.update(FUNCTION_COLUMNS["detect_pre_validacion"])
    
    # Conversation state determination
    if not skip_conversation_state:
        included_columns.update(FUNCTION_COLUMNS["determine_conversation_state"])
    
    # Consecutive templates count
    if not skip_consecutive_templates_count:
        included_columns.update(FUNCTION_COLUMNS["count_consecutive_recovery_templates"])
    
    # Handoff detection (updated to use HandoffProcessor columns directly)
    if not skip_handoff_detection:
        if not skip_handoff_finalized:
            included_columns.update(FUNCTION_COLUMNS["handoff_finalized"])
        
        if not (skip_handoff_invitation and skip_handoff_started and skip_handoff_finalized):
            # Define handoff columns directly from HandoffProcessor
            handoff_process_columns = set(["handoff_invitation_detected", "handoff_response", "handoff_finalized"])
            
            # Adjust based on specific skips
            if skip_handoff_invitation:
                handoff_process_columns.discard("handoff_invitation_detected")
            
            if skip_handoff_started:
                handoff_process_columns.discard("handoff_response")
            
            if skip_handoff_finalized and "handoff_finalized" in handoff_process_columns:
                # Don't add duplicate handoff_finalized if we already have it
                handoff_process_columns.discard("handoff_finalized")
                
            included_columns.update(handoff_process_columns)
    
    return list(included_columns)

def update_meta_yml_for_python_flags(recipe_path: Path, python_columns: List[str]) -> bool:
    """
    Update a recipe's meta.yml to include Python flag columns in output_columns.
    
    Args:
        recipe_path: Path to the recipe directory
        python_columns: List of Python flag columns to include
        
    Returns:
        True if the update was successful, False otherwise
    """
    meta_path = recipe_path / "meta.yml"
    if not meta_path.exists():
        logger.warning(f"No meta.yml found at {meta_path}")
        return False
    
    try:
        # Load existing meta.yml
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f)
        
        if not meta:
            logger.warning(f"Empty or invalid meta.yml at {meta_path}")
            return False
        
        # Add python_flag_columns section if it doesn't exist
        if "python_flag_columns" not in meta:
            meta["python_flag_columns"] = python_columns
            logger.info(f"Added python_flag_columns section to {meta_path}")
        else:
            # Update existing python_flag_columns section
            meta["python_flag_columns"] = python_columns
            logger.info(f"Updated python_flag_columns section in {meta_path}")
        
        # Get existing output_columns or create an empty list
        output_columns = meta.get("output_columns", [])
        
        # Add any missing Python columns to output_columns
        for col in python_columns:
            if col not in output_columns:
                output_columns.append(col)
                logger.info(f"Added column {col} to output_columns in {meta_path}")
        
        # Update output_columns
        meta["output_columns"] = output_columns
        
        # Save updated meta.yml
        with open(meta_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(meta, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Successfully updated {meta_path} with Python flag columns")
        return True
        
    except Exception as e:
        logger.error(f"Error updating meta.yml at {meta_path}: {e}")
        return False

def get_python_flags_from_meta(recipe_path: Path) -> Dict[str, bool]:
    """
    Extract Python flag skip settings from a recipe's meta.yml.
    
    Args:
        recipe_path: Path to the recipe directory
        
    Returns:
        Dictionary of skip flag settings
    """
    # Default values for all skip flags (don't skip by default)
    skip_flags = {
        "skip_temporal_flags": False,
        "skip_metadata_extraction": False,
        "skip_handoff_detection": False,
        "skip_human_transfer": False,
        "skip_recovery_template_detection": False,
        "skip_consecutive_templates_count": False,
        "skip_handoff_invitation": False,
        "skip_handoff_started": False,
        "skip_handoff_finalized": False,
        "skip_detailed_temporal": False,
        "skip_hours_minutes": False,
        "skip_reactivation_flags": False,
        "skip_timestamps": False,
        "skip_user_message_flag": False,
        "skip_pre_validacion_detection": False,
        "skip_conversation_state": False
    }
    
    meta_path = recipe_path / "meta.yml"
    if not meta_path.exists():
        logger.warning(f"No meta.yml found at {meta_path}")
        return skip_flags
    
    try:
        # Load meta.yml
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f)
        
        if not meta:
            logger.warning(f"Empty or invalid meta.yml at {meta_path}")
            return skip_flags
        
        # Extract skip flags from python_flags section if it exists
        python_flags = meta.get("python_flags", {})
        if isinstance(python_flags, dict):
            for flag, value in python_flags.items():
                if flag in skip_flags:
                    skip_flags[flag] = bool(value)
                    logger.debug(f"Found flag {flag}={value} in meta.yml")
        
        # For backward compatibility, also check for behavior_flags
        behavior_flags = meta.get("behavior_flags", {})
        if isinstance(behavior_flags, dict):
            # Map behavior_flags to the corresponding skip_flags
            if "skip_detailed_temporal_processing" in behavior_flags:
                skip_flags["skip_detailed_temporal"] = bool(behavior_flags["skip_detailed_temporal_processing"])
                logger.debug(f"Found legacy flag skip_detailed_temporal_processing={behavior_flags['skip_detailed_temporal_processing']} in meta.yml")
        
        return skip_flags
        
    except Exception as e:
        logger.error(f"Error reading meta.yml at {meta_path}: {e}")
        return skip_flags 