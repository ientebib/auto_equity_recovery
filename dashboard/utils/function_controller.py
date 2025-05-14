"""
Function Controller Module

Utilities for managing function states and generating CLI arguments based on user selections.
"""
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
import yaml
import sys
import os

# Add project root to path for imports
PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(str(PROJECT_ROOT))

from .function_discovery import get_all_functions_for_recipe
from lead_recovery.cli.column_manager import generate_column_excludes

logger = logging.getLogger(__name__)

class FunctionController:
    """
    Controller for managing Python function configurations and generating CLI arguments.
    """
    
    def __init__(self, recipe_name: str):
        """
        Initialize the function controller for a specific recipe.
        
        Args:
            recipe_name: Name of the recipe
        """
        self.recipe_name = recipe_name
        self.functions = get_all_functions_for_recipe(recipe_name)
        self.function_states = self._initialize_function_states()
        
    def _initialize_function_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Initialize the state of all functions with their default values.
        
        Returns:
            Dictionary mapping function names to their state dictionaries
        """
        states = {}
        
        # Global functions
        for func in self.functions["global"]:
            states[func["name"]] = {
                "enabled": True,  # Default: enabled
                "config": {
                    param_name: param_info["default"]
                    for param_name, param_info in func.get("config_params", {}).items()
                }
            }
            
            # Add skip_temporal_flags to temporal_flags function
            if func["name"] == "temporal_flags" or func["name"] == "calculate_temporal_flags":
                states[func["name"]]["config"]["skip_temporal_flags"] = False
        
        # Recipe-specific functions
        for func in self.functions["recipe"]:
            states[func["name"]] = {
                "enabled": True,  # Default: enabled
                "config": {}
            }
        
        # Built-in recipe functions
        for func in self.functions["built_in"]:
            states[func["name"]] = {
                "enabled": True,  # Default: enabled
                "config": {}
            }
            
        return states
    
    def load_preset(self, preset_name: str) -> bool:
        """
        Load a predefined preset configuration for functions.
        
        Args:
            preset_name: Name of the preset to load
            
        Returns:
            True if preset was loaded successfully, False otherwise
        """
        # Define some common presets
        presets = {
            "default": {
                "temporal_flags": {
                    "enabled": True, 
                    "config": {
                        "skip_temporal_flags": False,
                        "skip_detailed_temporal": False,
                        "skip_hours_minutes": False,
                        "skip_reactivation_flags": False,
                        "skip_timestamps": False,
                        "skip_user_message_flag": False
                    }
                },
                "calculate_temporal_flags": {
                    "enabled": True, 
                    "config": {
                        "skip_temporal_flags": False,
                        "skip_detailed_temporal": False,
                        "skip_hours_minutes": False,
                        "skip_reactivation_flags": False,
                        "skip_timestamps": False,
                        "skip_user_message_flag": False
                    }
                },
                "handoff_invitation": {"enabled": True, "config": {}},
                "handoff_started": {"enabled": True, "config": {}},
                "handoff_finalized": {"enabled": True, "config": {}},
                "extract_message_metadata": {"enabled": True, "config": {"skip_metadata_extraction": False}},
                "detect_human_transfer": {"enabled": True, "config": {}},
                "count_consecutive_recovery_templates": {"enabled": True, "config": {}}
            },
            "performance": {
                "temporal_flags": {
                    "enabled": True, 
                    "config": {
                        "skip_temporal_flags": False,
                        "skip_detailed_temporal": True,
                        "skip_hours_minutes": True,
                        "skip_reactivation_flags": True,
                        "skip_timestamps": False,
                        "skip_user_message_flag": False
                    }
                },
                "calculate_temporal_flags": {
                    "enabled": True, 
                    "config": {
                        "skip_temporal_flags": False,
                        "skip_detailed_temporal": True,
                        "skip_hours_minutes": True,
                        "skip_reactivation_flags": True,
                        "skip_timestamps": False,
                        "skip_user_message_flag": False
                    }
                },
                "handoff_invitation": {"enabled": True, "config": {}},
                "handoff_started": {"enabled": True, "config": {}},
                "handoff_finalized": {"enabled": True, "config": {}},
                "extract_message_metadata": {"enabled": True, "config": {"skip_metadata_extraction": False}},
                "detect_human_transfer": {"enabled": True, "config": {}},
                "count_consecutive_recovery_templates": {"enabled": True, "config": {}}
            },
            "minimal": {
                "temporal_flags": {
                    "enabled": True, 
                    "config": {
                        "skip_temporal_flags": True,
                        "skip_detailed_temporal": True,
                        "skip_hours_minutes": True,
                        "skip_reactivation_flags": True,
                        "skip_timestamps": True,
                        "skip_user_message_flag": False
                    }
                },
                "calculate_temporal_flags": {
                    "enabled": True, 
                    "config": {
                        "skip_temporal_flags": True,
                        "skip_detailed_temporal": True,
                        "skip_hours_minutes": True,
                        "skip_reactivation_flags": True,
                        "skip_timestamps": True,
                        "skip_user_message_flag": False
                    }
                },
                "handoff_invitation": {"enabled": False, "config": {}},
                "handoff_started": {"enabled": False, "config": {}},
                "handoff_finalized": {"enabled": False, "config": {}},
                "extract_message_metadata": {"enabled": False, "config": {"skip_metadata_extraction": True}},
                "detect_human_transfer": {"enabled": False, "config": {}},
                "count_consecutive_recovery_templates": {"enabled": False, "config": {}}
            },
            "full_analysis": {
                "temporal_flags": {
                    "enabled": True, 
                    "config": {
                        "skip_temporal_flags": False,
                        "skip_detailed_temporal": False,
                        "skip_hours_minutes": False,
                        "skip_reactivation_flags": False,
                        "skip_timestamps": False,
                        "skip_user_message_flag": False
                    }
                },
                "calculate_temporal_flags": {
                    "enabled": True, 
                    "config": {
                        "skip_temporal_flags": False,
                        "skip_detailed_temporal": False,
                        "skip_hours_minutes": False,
                        "skip_reactivation_flags": False,
                        "skip_timestamps": False,
                        "skip_user_message_flag": False
                    }
                },
                "handoff_invitation": {"enabled": True, "config": {}},
                "handoff_started": {"enabled": True, "config": {}},
                "handoff_finalized": {"enabled": True, "config": {}},
                "extract_message_metadata": {"enabled": True, "config": {"skip_metadata_extraction": False}},
                "detect_human_transfer": {"enabled": True, "config": {}},
                "count_consecutive_recovery_templates": {"enabled": True, "config": {}}
            },
            "timestamps_only": {
                "temporal_flags": {
                    "enabled": True, 
                    "config": {
                        "skip_temporal_flags": False,
                        "skip_detailed_temporal": False,
                        "skip_hours_minutes": True,
                        "skip_reactivation_flags": True,
                        "skip_timestamps": False,
                        "skip_user_message_flag": False
                    }
                },
                "calculate_temporal_flags": {
                    "enabled": True, 
                    "config": {
                        "skip_temporal_flags": False,
                        "skip_detailed_temporal": False,
                        "skip_hours_minutes": True,
                        "skip_reactivation_flags": True,
                        "skip_timestamps": False,
                        "skip_user_message_flag": False
                    }
                },
                "handoff_invitation": {"enabled": True, "config": {}},
                "handoff_started": {"enabled": True, "config": {}},
                "handoff_finalized": {"enabled": True, "config": {}},
                "extract_message_metadata": {"enabled": True, "config": {"skip_metadata_extraction": False}},
                "detect_human_transfer": {"enabled": True, "config": {}},
                "count_consecutive_recovery_templates": {"enabled": True, "config": {}}
            }
        }
        
        if preset_name not in presets:
            logger.warning(f"Preset '{preset_name}' not found")
            return False
            
        # Apply the preset to the existing function states
        preset_config = presets[preset_name]
        for func_name, state in preset_config.items():
            if func_name in self.function_states:
                self.function_states[func_name]["enabled"] = state["enabled"]
                for param, value in state.get("config", {}).items():
                    if param in self.function_states[func_name]["config"]:
                        self.function_states[func_name]["config"][param] = value
        
        logger.info(f"Loaded '{preset_name}' preset for recipe '{self.recipe_name}'")
        return True
    
    def save_recipe_preset(self) -> bool:
        """
        Save the current function states as a preset for this recipe.
        
        Returns:
            True if preset was saved successfully, False otherwise
        """
        try:
            # Create presets directory if it doesn't exist
            presets_dir = Path(__file__).resolve().parent.parent / "presets"
            presets_dir.mkdir(exist_ok=True)
            
            # Save the preset file
            preset_path = presets_dir / f"{self.recipe_name}_preset.json"
            with open(preset_path, 'w') as f:
                json.dump(self.function_states, f, indent=2)
                
            logger.info(f"Saved preset for recipe '{self.recipe_name}' to {preset_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving preset: {e}")
            return False
    
    def load_recipe_preset(self) -> bool:
        """
        Load a previously saved preset for this recipe.
        
        Returns:
            True if preset was loaded successfully, False otherwise
        """
        preset_path = Path(__file__).resolve().parent.parent / "presets" / f"{self.recipe_name}_preset.json"
        
        if not preset_path.exists():
            logger.warning(f"No preset found for recipe '{self.recipe_name}'")
            return False
            
        try:
            with open(preset_path, 'r') as f:
                preset = json.load(f)
                
            for func_name, state in preset.items():
                if func_name in self.function_states:
                    self.function_states[func_name] = state
                    
            logger.info(f"Loaded preset for recipe '{self.recipe_name}' from {preset_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading preset: {e}")
            return False
    
    def update_function_state(self, function_name: str, enabled: bool, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update the state of a function.
        
        Args:
            function_name: Name of the function
            enabled: Whether the function should be enabled
            config: Optional configuration parameters
            
        Returns:
            True if function state was updated successfully, False otherwise
        """
        if function_name not in self.function_states:
            logger.warning(f"Function '{function_name}' not found")
            return False
            
        self.function_states[function_name]["enabled"] = enabled
        
        if config:
            self.function_states[function_name]["config"].update(config)
            
        return True
    
    def generate_cli_args(self) -> List[str]:
        """
        Generate CLI arguments based on the current function states.
        
        Returns:
            List of CLI arguments to be added to the command
        """
        cli_args = []
        
        # Keep track of enabled and disabled functions
        enabled_functions = []
        disabled_functions = []
        
        # Handle global functions
        for func in self.functions["global"]:
            func_name = func["name"]
            if func_name in self.function_states:
                state = self.function_states[func_name]
                
                # Track enabled/disabled state
                if state["enabled"]:
                    enabled_functions.append(func_name)
                else:
                    disabled_functions.append(func_name)
                
                # Global function CLI mappings
                if func_name == "temporal_flags" or func_name == "calculate_temporal_flags":
                    # Skip the entire calculation if disabled
                    if not state["enabled"]:
                        cli_args.append("--skip-temporal-flags")
                    else:
                        # Check for skip_temporal_flags config parameter
                        if state["config"].get("skip_temporal_flags", False):
                            cli_args.append("--skip-temporal-flags")
                        else:
                            # Otherwise, handle granular skip flags
                            if state["config"].get("skip_detailed_temporal", False):
                                cli_args.append("--skip-detailed-temporal")
                            
                            # New granular temporal flags
                            if state["config"].get("skip_hours_minutes", False):
                                cli_args.append("--skip-hours-minutes")
                                
                            if state["config"].get("skip_reactivation_flags", False):
                                cli_args.append("--skip-reactivation-flags")
                                
                            if state["config"].get("skip_timestamps", False):
                                cli_args.append("--skip-timestamps")
                                
                            if state["config"].get("skip_user_message_flag", False):
                                cli_args.append("--skip-user-message-flag")
                
                # Only handles active functions (deprecated detect_handoff_finalization is removed)
                if func_name == "handoff_invitation" and not state["enabled"]:
                    cli_args.append("--skip-handoff-invitation")
                
                if func_name == "handoff_started" and not state["enabled"]:
                    cli_args.append("--skip-handoff-started")
                
                if func_name == "handoff_finalized" and not state["enabled"]:
                    cli_args.append("--skip-handoff-finalized")
                
                if func_name == "extract_message_metadata" and not state["enabled"]:
                    cli_args.append("--skip-metadata-extraction")
                
                if func_name == "detect_human_transfer" and not state["enabled"]:
                    cli_args.append("--skip-human-transfer")
                
                if func_name == "detect_recovery_template" and not state["enabled"]:
                    cli_args.append("--skip-recovery-template-detection")
                
                if func_name == "detect_topup_template" and not state["enabled"]:
                    cli_args.append("--skip-topup-template-detection")
                
                if func_name == "count_consecutive_recovery_templates" and not state["enabled"]:
                    cli_args.append("--skip-consecutive-templates-count")
        
        # Handle recipe-specific and built-in functions
        for func_category in ["recipe", "built_in"]:
            for func in self.functions[func_category]:
                func_name = func["name"]
                if func_name in self.function_states:
                    state = self.function_states[func_name]
                    
                    # Track enabled/disabled state
                    if state["enabled"]:
                        enabled_functions.append(func_name)
                    else:
                        disabled_functions.append(func_name)
        
        # Generate column exclude arguments based on disabled functions
        column_args = generate_column_excludes(self.recipe_name, disabled_functions)
        cli_args.extend(column_args)
        
        # Only for logging purposes
        logger.info(f"Enabled functions: {enabled_functions}")
        logger.info(f"Disabled functions: {disabled_functions}")
        
        return cli_args
    
    def get_function_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the current state of all functions.
        
        Returns:
            Dictionary mapping function names to their state dictionaries
        """
        return self.function_states
    
    def get_preset_names(self) -> List[str]:
        """
        Get a list of available preset names.
        
        Returns:
            List of preset names
        """
        return ["default", "performance", "minimal", "full_analysis", "timestamps_only"]


# Example usage
if __name__ == "__main__":
    controller = FunctionController("marzo_cohorts_live")
    print(f"Initial function states: {json.dumps(controller.get_function_states(), indent=2)}")
    
    # Load a preset
    controller.load_preset("minimal")
    print(f"After loading 'minimal' preset: {json.dumps(controller.get_function_states(), indent=2)}")
    
    # Generate CLI arguments
    cli_args = controller.generate_cli_args()
    print(f"CLI arguments: {' '.join(cli_args)}")
    
    # Update a function state
    controller.update_function_state(
        "calculate_temporal_flags", 
        True, 
        {"skip_detailed_temporal": False}
    )
    print(f"Updated function state: {json.dumps(controller.get_function_states()['calculate_temporal_flags'], indent=2)}")
    
    # Generate CLI arguments again
    cli_args = controller.generate_cli_args()
    print(f"Updated CLI arguments: {' '.join(cli_args)}") 