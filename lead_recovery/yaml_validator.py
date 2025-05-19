"""yaml_validator.py
Validation utilities for YAML responses from LLM.
"""
from __future__ import annotations

import logging
import warnings
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class YamlValidator:
    """Validates and fixes YAML data according to schema defined in meta_config."""
    
    def __init__(self, meta_config: Optional[Dict[str, Any]] = None):
        """Initialize the validator with meta configuration.
        
        Args:
            meta_config: Configuration dictionary from the recipe's meta.yml
        """
        self.meta_config = meta_config or {}
        logger.info(f"YamlValidator initialized with meta_config keys: {list(self.meta_config.keys())}")
        # Support both old and new schema
        if 'expected_yaml_keys' in self.meta_config:
            self.expected_yaml_keys = set(self.meta_config.get('expected_yaml_keys', []))
        elif 'expected_llm_keys' in self.meta_config:
            self.expected_yaml_keys = set(self.meta_config['expected_llm_keys'].keys())
        elif 'llm_config' in self.meta_config and 'expected_llm_keys' in self.meta_config['llm_config']:
            self.expected_yaml_keys = set(self.meta_config['llm_config']['expected_llm_keys'].keys())
        else:
            self.expected_yaml_keys = set()
        # Extract validation_enums if present, else auto-extract from llm_config.expected_llm_keys
        if 'validation_enums' in self.meta_config:
            self.validation_enums = self.meta_config['validation_enums']
        else:
            self.validation_enums = {}
            llm_cfg = self.meta_config.get('llm_config', {})
            expected_llm_keys = llm_cfg.get('expected_llm_keys', {})
            for key, cfg in expected_llm_keys.items():
                if cfg.get('enum_values'):
                    self.validation_enums[key] = cfg['enum_values']
        
    def validate_yaml(self, parsed_data: Dict[str, Any]) -> List[str]:
        """Validate parsed YAML data against expected keys and enums.
        
        Args:
            parsed_data: The parsed YAML data as a dictionary
            
        Returns:
            List of validation error messages
        """
        validation_errors = []
        actual_keys = set(parsed_data.keys())

        # Key validation
        if self.expected_yaml_keys:
            missing_keys = self.expected_yaml_keys - actual_keys
            if missing_keys:
                validation_errors.append(f"Missing keys: {missing_keys}")
            
            extra_keys = actual_keys - self.expected_yaml_keys
            if extra_keys:
                logger.warning("Found extra keys in YAML output: %s", extra_keys)
        else:
            logger.warning("No expected_yaml_keys or expected_llm_keys provided for validation. Skipping key check.")

        # Enum value validation
        for enum_key, allowed_values_list in self.validation_enums.items():
            if enum_key in parsed_data:
                value_to_check = parsed_data.get(enum_key)
                allowed_values_set = set(allowed_values_list) 
                if value_to_check not in allowed_values_set:
                    validation_errors.append(f"Invalid value for '{enum_key}': '{value_to_check}'. Allowed: {allowed_values_set}")
                    
        return validation_errors
    
    def fix_yaml(self, parsed_data: Dict[str, Any], temporal_flags: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fix YAML validation issues.
        
        Args:
            parsed_data: The parsed YAML data
            temporal_flags: Dictionary of Python-calculated flags
            
        Returns:
            Fixed YAML data dictionary
        """
        validation_errors = self.validate_yaml(parsed_data)
        
        if not validation_errors:
            return parsed_data
            
        # Auto-fix invalid values
        warnings.warn(f"YAML Validation issues detected: {validation_errors}. Attempting to fix automatically.")
        
        # Special handling for cases where no user messages exist
        if temporal_flags and temporal_flags.get('NO_USER_MESSAGES_EXIST', False):
            logger.info("FOUND NO_USER_MESSAGES_EXIST=True in temporal_flags")
            # If no user messages exist, always set these values regardless of LLM output
            if 'primary_stall_reason_code' in parsed_data:
                logger.warning("Auto-fixing primary_stall_reason_code to 'NUNCA_RESPONDIO' for conversation with NO_USER_MESSAGES_EXIST=True")
                parsed_data['primary_stall_reason_code'] = 'NUNCA_RESPONDIO'
            
            if 'next_action_code' in parsed_data:
                # Check how long since last message
                hours_mins = temporal_flags.get('HOURS_MINUTES_SINCE_LAST_MESSAGE', '')
                logger.info(f"HOURS_MINUTES_SINCE_LAST_MESSAGE = {hours_mins}")
                if hours_mins and hours_mins.startswith(('0h', '1h')):
                    # If less than 2 hours, set to ESPERAR
                    logger.warning("Auto-fixing next_action_code to 'ESPERAR' for conversation with NO_USER_MESSAGES_EXIST=True and recent message")
                    parsed_data['next_action_code'] = 'ESPERAR'
                else:
                    # Otherwise, call the lead
                    logger.warning("Auto-fixing next_action_code to 'LLAMAR_LEAD_NUNCA_RESPONDIO' for conversation with NO_USER_MESSAGES_EXIST=True")
                    parsed_data['next_action_code'] = 'LLAMAR_LEAD_NUNCA_RESPONDIO'
        else:
            logger.info(f"NO_USER_MESSAGES_EXIST condition not met. temporal_flags: {temporal_flags}")
            # Auto-fix missing keys by adding defaults
            if self.expected_yaml_keys:
                for key in self.expected_yaml_keys:
                    if key not in parsed_data:
                        parsed_data[key] = "N/A"  # Default placeholder for missing keys
                        logger.warning(f"Auto-fixing missing key '{key}' by setting to N/A")
            
            # Auto-fix invalid enum values
            for enum_key, allowed_values_list in self.validation_enums.items():
                if enum_key in parsed_data:
                    self._fix_enum_value(parsed_data, enum_key, allowed_values_list)
                    
        # One more validation pass to ensure everything is fixed
        final_validation_errors = self.validate_yaml(parsed_data)
        if final_validation_errors:
            logger.warning(f"FINAL VALIDATION ISSUES DETECTED: {final_validation_errors}. Fixing critical fields.")
            # Special handling for critical fields that must be fixed
            for enum_key in ["primary_stall_reason_code", "next_action_code"]:
                if enum_key in parsed_data:
                    parsed_data.get(enum_key)
                    if any([error.startswith(f"Invalid value for '{enum_key}'") for error in final_validation_errors]):
                        parsed_data[enum_key] = "N/A"
                        logger.warning(f"Critical field forced to N/A: {enum_key}")
                        
        # Process any NUNCA_RESPONDIO special case
        if temporal_flags and temporal_flags.get('NO_USER_MESSAGES_EXIST'):
            logger.info("NO_USER_MESSAGES_EXIST condition met. Setting special values for nunca respondio case.")
            parsed_data['inferred_stall_stage'] = "PRE_VALIDACION"
            
        return parsed_data
    
    def _fix_enum_value(self, parsed_data: Dict[str, Any], enum_key: str, allowed_values_list: List[str]) -> None:
        """Helper method to fix invalid enum values.
        
        Args:
            parsed_data: The parsed YAML data
            enum_key: The key of the enum field to fix
            allowed_values_list: List of allowed values for this enum field
        """
        value = parsed_data.get(enum_key)
        original_value_for_logging = str(value) # Keep original for logging/comparison

        # 1. Attempt to strip common quotes and whitespace if value is a string
        if isinstance(value, str):
            stripped_value = value.strip() # Remove leading/trailing whitespace first
            if stripped_value: # Ensure not an empty string after stripping whitespace
                if (stripped_value.startswith("'") and stripped_value.endswith("'")) or \
                   (stripped_value.startswith('"') and stripped_value.endswith('"')):
                    # Remove one layer of quotes
                    stripped_value = stripped_value[1:-1]
            
            if value != stripped_value: # If stripping changed the value
                 logger.info(f"Stripped quotes/whitespace from '{original_value_for_logging}' to '{stripped_value}' for key '{enum_key}'")
            value = stripped_value # Use the potentially stripped value for further checks
        
        # 2. Check if (potentially stripped) value is valid
        if value in allowed_values_list:
            if parsed_data.get(enum_key) != value: # Update only if different from original in parsed_data
                logger.info(f"Corrected value for '{enum_key}' to (stripped and valid) '{value}' from '{original_value_for_logging}'")
                parsed_data[enum_key] = value
            return # Value is now valid and stored, exit early

        # 3. If still not valid after stripping, apply defaulting logic:
        default_value_to_set: Optional[str] = None

        if enum_key in ["primary_stall_reason_code", "next_action_code"]:
            default_value_to_set = "N/A"
        elif allowed_values_list: # For non-critical fields, use the first allowed value
            default_value_to_set = allowed_values_list[0]
        else: # Fallback if no allowed values (should not happen with good config)
            logger.error(f"No allowed values defined for enum_key '{enum_key}' in meta.yml. Cannot set a default for original value '{original_value_for_logging}'. Using 'ERROR_NO_DEFAULTS'.")
            default_value_to_set = "ERROR_NO_DEFAULTS"
        
        if parsed_data.get(enum_key) != default_value_to_set: # Log and set only if different
            logger.warning(f"Auto-fixing invalid value '{original_value_for_logging}' (after stripping attempts yielded '{value}') for field '{enum_key}' to default '{default_value_to_set}'.")
            parsed_data[enum_key] = default_value_to_set 