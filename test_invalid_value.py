#!/usr/bin/env python
"""Test script to verify auto-fixing behavior for invalid values"""

import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

# Create validation enums
validation_enums = {
    'primary_stall_reason_code': [
        'GHOSTING', 'PROCESO_EN_CURSO', 'FINANCIAMIENTO_ACTIVO'
    ]
}

# Create a mock parsed_data with an invalid value
parsed_data = {
    'primary_stall_reason_code': 'COMPLETELY_INVALID_VALUE'
}

# Simulate the auto-fixing code
print("Testing auto-fixing for invalid primary_stall_reason_code value...")

# Get the value and allowed values list
enum_key = 'primary_stall_reason_code'
value = parsed_data.get(enum_key)
allowed_values_list = validation_enums.get(enum_key, [])

print(f"Current value: '{value}'")
print(f"Allowed values: {allowed_values_list}")

# Check if the value is in the allowed list
if value not in allowed_values_list and allowed_values_list:
    # Set appropriate defaults based on the enum key
    if enum_key == "primary_stall_reason_code":
        default_value = "N/A"
        print(f"Auto-fixing invalid value '{value}' for '{enum_key}' to '{default_value}'")
        parsed_data[enum_key] = default_value
    else:
        # Use the first allowed value as a safe default for other fields
        print(f"Auto-fixing invalid value '{value}' for '{enum_key}' to '{allowed_values_list[0]}'")
        parsed_data[enum_key] = allowed_values_list[0]

print(f"Final value: {parsed_data['primary_stall_reason_code']}") 