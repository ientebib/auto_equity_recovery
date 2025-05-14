#!/usr/bin/env python
"""Test script to verify auto-fixing behavior for invalid values for multiple fields"""

import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

# Create validation enums
validation_enums = {
    'primary_stall_reason_code': [
        'GHOSTING', 'PROCESO_EN_CURSO', 'FINANCIAMIENTO_ACTIVO'
    ],
    'next_action_code': [
        'CERRAR', 'ESPERAR', 'ENVIAR_REACTIVACION'
    ]
}

# Create a mock parsed_data with invalid values
parsed_data = {
    'primary_stall_reason_code': 'COMPLETELY_INVALID_VALUE',
    'next_action_code': '"REACTIVACION_TARDIA_NECESITA_INTENTO_1"'  # Invalid value with quotes
}

print("TESTING BOTH FIELDS:\n")

# Test both fields
for enum_key in ['primary_stall_reason_code', 'next_action_code']:
    print(f"\nTESTING FIELD: {enum_key}")
    value = parsed_data.get(enum_key)
    allowed_values_list = validation_enums.get(enum_key, [])

    print(f"Current value: '{value}'")
    print(f"Allowed values: {allowed_values_list}")

    # Check if the value has quotes
    if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
        # Strip the quotes and check if this stripped value is valid
        stripped_value = value.strip('"')
        print(f"QUOTE CHECK: Found quoted value '{value}', stripped to '{stripped_value}'")
        
        if stripped_value in allowed_values_list:
            # Use the stripped value if it's valid
            print(f"Auto-fixing quoted value '{value}' to '{stripped_value}' which is valid")
            parsed_data[enum_key] = stripped_value
            continue  # Skip the default handling for this value
        else:
            print(f"QUOTE CHECK: Stripped value '{stripped_value}' is not in allowed list")
    
    # Only proceed with default handling if the value is still not valid
    if value not in allowed_values_list and allowed_values_list:
        # Set appropriate defaults based on the enum key
        if enum_key == "primary_stall_reason_code" or enum_key == "next_action_code":
            default_value = "N/A"
            print(f"Auto-fixing invalid value '{value}' for '{enum_key}' to '{default_value}'")
            parsed_data[enum_key] = default_value
        else:
            # Use the first allowed value as a safe default for other fields
            print(f"Auto-fixing invalid value '{value}' for '{enum_key}' to '{allowed_values_list[0]}'")
            parsed_data[enum_key] = allowed_values_list[0]

print("\nFINAL VALUES:")
print(f"primary_stall_reason_code: {parsed_data['primary_stall_reason_code']}")
print(f"next_action_code: {parsed_data['next_action_code']}") 