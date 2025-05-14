"""Tests for python_flags_manager module"""
import os
import pytest
from pathlib import Path
from lead_recovery.python_flags_manager import get_python_flag_columns

def test_get_python_flag_columns_all_enabled():
    """Test getting columns with all flags enabled"""
    columns = get_python_flag_columns(
        skip_temporal_flags=False,
        skip_metadata_extraction=False,
        skip_handoff_detection=False,
        skip_human_transfer=False,
        skip_recovery_template_detection=False,
        skip_topup_template_detection=False,
        skip_consecutive_templates_count=False,
        skip_handoff_invitation=False,
        skip_handoff_started=False,
        skip_handoff_finalized=False,
        skip_detailed_temporal=False,
        skip_hours_minutes=False,
        skip_reactivation_flags=False,
        skip_timestamps=False,
        skip_user_message_flag=False
    )
    
    # Verify all expected columns are included
    assert "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE" in columns
    assert "HOURS_MINUTES_SINCE_LAST_MESSAGE" in columns
    assert "IS_WITHIN_REACTIVATION_WINDOW" in columns
    assert "IS_RECOVERY_PHASE_ELIGIBLE" in columns
    assert "LAST_USER_MESSAGE_TIMESTAMP_TZ" in columns
    assert "LAST_MESSAGE_TIMESTAMP_TZ" in columns
    assert "NO_USER_MESSAGES_EXIST" in columns
    assert "last_message_sender" in columns
    assert "last_user_message_text" in columns
    assert "last_kuna_message_text" in columns
    assert "handoff_finalized" in columns
    assert "human_transfer" in columns
    assert "consecutive_recovery_templates_count" in columns

def test_get_python_flag_columns_skip_temporal():
    """Test getting columns with temporal flags skipped"""
    columns = get_python_flag_columns(
        skip_temporal_flags=True,
        skip_metadata_extraction=False,
        skip_handoff_detection=False,
        skip_human_transfer=False,
        skip_recovery_template_detection=False,
        skip_topup_template_detection=False,
        skip_consecutive_templates_count=False
    )
    
    # Verify temporal columns are not included
    assert "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE" not in columns
    assert "HOURS_MINUTES_SINCE_LAST_MESSAGE" not in columns
    assert "IS_WITHIN_REACTIVATION_WINDOW" not in columns
    assert "IS_RECOVERY_PHASE_ELIGIBLE" not in columns
    assert "LAST_USER_MESSAGE_TIMESTAMP_TZ" not in columns
    assert "LAST_MESSAGE_TIMESTAMP_TZ" not in columns
    assert "NO_USER_MESSAGES_EXIST" not in columns
    
    # Verify other columns are still included
    assert "last_message_sender" in columns
    assert "last_user_message_text" in columns
    assert "handoff_finalized" in columns

def test_get_python_flag_columns_skip_hours_minutes():
    """Test getting columns with hours and minutes skipped"""
    columns = get_python_flag_columns(
        skip_hours_minutes=True
    )
    
    # Verify hours/minutes columns are not included
    assert "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE" not in columns
    assert "HOURS_MINUTES_SINCE_LAST_MESSAGE" not in columns
    
    # Verify other temporal columns are still included
    assert "IS_WITHIN_REACTIVATION_WINDOW" in columns
    assert "IS_RECOVERY_PHASE_ELIGIBLE" in columns
    assert "LAST_USER_MESSAGE_TIMESTAMP_TZ" in columns

def test_get_python_flag_columns_skip_multiple_functions():
    """Test getting columns with multiple functions disabled"""
    columns = get_python_flag_columns(
        skip_metadata_extraction=True,
        skip_handoff_detection=True,
        skip_human_transfer=True
    )
    
    # Verify all temporal columns are included
    assert "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE" in columns
    assert "HOURS_MINUTES_SINCE_LAST_MESSAGE" in columns
    assert "IS_WITHIN_REACTIVATION_WINDOW" in columns
    
    # Verify skipped function columns are not included
    assert "last_message_sender" not in columns
    assert "last_user_message_text" not in columns
    assert "last_kuna_message_text" not in columns
    assert "handoff_invitation_detected" not in columns
    assert "handoff_response" not in columns
    assert "handoff_finalized" not in columns
    assert "human_transfer" not in columns 