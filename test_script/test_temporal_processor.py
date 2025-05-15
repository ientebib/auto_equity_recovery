#!/usr/bin/env python
"""
Test script to directly test the TemporalProcessor class
"""
import os
import sys
from datetime import datetime, timedelta

import pandas as pd

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the processor class
from lead_recovery.processors.temporal import TemporalProcessor
from lead_recovery.recipe_schema import DataInputConfig, DataInputSQL, RecipeMeta


def create_test_df(with_user_messages=True):
    """Create a test DataFrame with or without user messages"""
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    
    # Create a DataFrame with messages
    if with_user_messages:
        data = [
            {'msg_from': 'bot', 'creation_time': yesterday - timedelta(hours=2), 'message': 'Hello!'},
            {'msg_from': 'user', 'creation_time': yesterday - timedelta(hours=1), 'message': 'Hi there!'},
            {'msg_from': 'bot', 'creation_time': yesterday, 'message': 'How can I help?'},
            {'msg_from': 'user', 'creation_time': now - timedelta(hours=2), 'message': 'I need assistance'},
            {'msg_from': 'bot', 'creation_time': now - timedelta(hours=1), 'message': 'I can help you with that'}
        ]
    else:
        # DataFrame with only bot messages
        data = [
            {'msg_from': 'bot', 'creation_time': yesterday - timedelta(hours=2), 'message': 'Hello!'},
            {'msg_from': 'bot', 'creation_time': yesterday, 'message': 'Are you there?'},
            {'msg_from': 'bot', 'creation_time': now - timedelta(hours=2), 'message': 'Just checking in'},
            {'msg_from': 'bot', 'creation_time': now - timedelta(hours=1), 'message': 'Please respond'}
        ]
        
    return pd.DataFrame(data)

def main():
    """Run test for both cases"""
    # Initialize the processor with valid RecipeMeta parameters
    mock_recipe_config = RecipeMeta(
        recipe_name="test_recipe",
        version="1.0",
        description="Test recipe",
        data_input=DataInputConfig(
            lead_source_type="redshift", 
            redshift_config=DataInputSQL(sql_file="test.sql")
        ),
        output_columns=["test_column"]
    )
    processor = TemporalProcessor(
        recipe_config=mock_recipe_config,
        processor_params={},
        global_config={}
    )
    
    print("=== Testing with user messages ===")
    df_with_user = create_test_df(with_user_messages=True)
    flags_with_user = processor.process(None, df_with_user, {})
    print(f"FLAGS:\n{flags_with_user}")
    print(f"NO_USER_MESSAGES_EXIST: {flags_with_user.get('NO_USER_MESSAGES_EXIST', 'Not found')}")
    
    print("\n=== Testing without user messages ===")
    df_without_user = create_test_df(with_user_messages=False)
    flags_without_user = processor.process(None, df_without_user, {})
    print(f"FLAGS:\n{flags_without_user}")
    print(f"NO_USER_MESSAGES_EXIST: {flags_without_user.get('NO_USER_MESSAGES_EXIST', 'Not found')}")
    
    # Check for old fields that should be gone
    print("\n=== Checking for removed fields ===")
    print(f"HOURS_SINCE_LAST_USER_MESSAGE: {flags_with_user.get('HOURS_SINCE_LAST_USER_MESSAGE', 'Not found (good)')}")
    print(f"MINUTES_SINCE_LAST_USER_MESSAGE: {flags_with_user.get('MINUTES_SINCE_LAST_USER_MESSAGE', 'Not found (good)')}")
    print(f"HOURS_SINCE_LAST_MESSAGE: {flags_with_user.get('HOURS_SINCE_LAST_MESSAGE', 'Not found (good)')}")
    print(f"MINUTES_SINCE_LAST_MESSAGE: {flags_with_user.get('MINUTES_SINCE_LAST_MESSAGE', 'Not found (good)')}")

if __name__ == "__main__":
    main() 