"""
Function Discovery Module

Utilities for discovering Python functions in the lead recovery project.
This includes both global functions in analysis.py and recipe-specific functions in analyzer.py files.
"""
import os
import sys
import re
import inspect
import importlib.util
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Add project root to path for imports
PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(str(PROJECT_ROOT))

# Import the FUNCTION_COLUMNS dictionary from python_flags
from lead_recovery.python_flags import FUNCTION_COLUMNS

RECIPE_ROOT = PROJECT_ROOT / "recipes"

# Global function definitions and their descriptions
GLOBAL_FUNCTIONS = [
    {
        "name": "temporal_flags", 
        "description": "Calculate time-based flags for conversation analysis",
        "trigger": "Executed for every conversation group",
        "patterns": ["HOURS_MINUTES_SINCE_LAST_MESSAGE", "IS_WITHIN_REACTIVATION_WINDOW", "IS_RECOVERY_PHASE_ELIGIBLE"],
        "output_columns": FUNCTION_COLUMNS.get("calculate_temporal_flags", []),
        "config_params": {
            "skip_temporal_flags": {
                "type": "bool",
                "default": False,
                "description": "Skip calculating all temporal flags"
            },
            "skip_detailed_temporal": {
                "type": "bool",
                "default": False,
                "description": "Skip detailed temporal processing (use simplified time calculations)"
            }
        }
    },
    {
        "name": "handoff_invitation", 
        "description": "Detect if a handoff invitation was sent to the user",
        "trigger": "Checks bot messages for handoff invitation patterns",
        "patterns": ["un paso de la aprobacion", "Completa el proceso ahora", "asegura tu prestamo en minutos"],
        "output_columns": ["handoff_invitation_detected"],
        "config_params": {
            "skip_handoff_invitation": {
                "type": "bool",
                "default": False,
                "description": "Skip handoff invitation detection"
            }
        }
    },
    {
        "name": "handoff_started", 
        "description": "Check if user started the handoff process after invitation",
        "trigger": "Checks user response after handoff invitation",
        "patterns": ["STARTED_HANDOFF", "DECLINED_HANDOFF", "IGNORED_HANDOFF", "Empezar", "De momento no"],
        "output_columns": ["handoff_response"],
        "config_params": {
            "skip_handoff_started": {
                "type": "bool",
                "default": False,
                "description": "Skip handoff started detection"
            }
        }
    },
    {
        "name": "handoff_finalized", 
        "description": "Check if the handoff process was completed successfully",
        "trigger": "Executed after handoff is started",
        "patterns": ["Seguro que tu taza de café", "Hemos finalizado el proceso de onboarding", "Tu perfil ha sido aprobado"],
        "output_columns": FUNCTION_COLUMNS.get("handoff_finalized", []),
        "config_params": {
            "skip_handoff_finalized": {
                "type": "bool",
                "default": False,
                "description": "Skip handoff finalized detection"
            }
        }
    },
    {
        "name": "detect_human_transfer", 
        "description": "Check if conversation was transferred to a human agent",
        "trigger": "Executed for messages containing transfer patterns",
        "patterns": ["un momento, estoy teniendo problemas", "un supervisor te asistirá"],
        "output_columns": FUNCTION_COLUMNS.get("detect_human_transfer", []),
        "config_params": {
            "skip_human_transfer": {
                "type": "bool",
                "default": False,
                "description": "Skip human transfer detection"
            }
        }
    },
    {
        "name": "extract_message_metadata", 
        "description": "Extract last message content and sender information",
        "trigger": "Executed for every conversation group",
        "patterns": ["last_message_sender", "last_user_message_text", "last_kuna_message_text"],
        "output_columns": FUNCTION_COLUMNS.get("extract_message_metadata", []),
        "config_params": {
            "skip_metadata_extraction": {
                "type": "bool",
                "default": False,
                "description": "Skip extraction of message metadata"
            }
        }
    },
    {
        "name": "detect_recovery_template", 
        "description": "Detect recovery templates in simulation_to_handoff recipe",
        "trigger": "Executed when simulation_to_handoff recipe is used",
        "patterns": ["last_bot_message_is_recovery_template", "préstamo por tu auto", "oferta pre aprobada"],
        "output_columns": FUNCTION_COLUMNS.get("detect_recovery_template", []),
        "config_params": {
            "skip_recovery_template_detection": {
                "type": "bool",
                "default": False,
                "description": "Skip recovery template detection (simulation_to_handoff recipe)"
            }
        }
    },
    {
        "name": "detect_topup_template", 
        "description": "Detect top-up template messages in top_up_may recipe",
        "trigger": "Executed when top_up_may recipe is used",
        "patterns": ["contains_top_up_template", "pre-approved loan", "credit message"],
        "output_columns": FUNCTION_COLUMNS.get("detect_topup_template", []),
        "config_params": {
            "skip_topup_template_detection": {
                "type": "bool",
                "default": False,
                "description": "Skip top-up template detection (top_up_may recipe)"
            }
        }
    },
    {
        "name": "count_consecutive_recovery_templates", 
        "description": "Count how many recovery templates were sent in sequence",
        "trigger": "Executed when recipe has template detection enabled",
        "patterns": ["consecutive_recovery_templates_count", "recovery template count"],
        "output_columns": FUNCTION_COLUMNS.get("count_consecutive_recovery_templates", []),
        "config_params": {
            "skip_consecutive_templates_count": {
                "type": "bool",
                "default": False,
                "description": "Skip counting consecutive recovery templates"
            }
        }
    }
]

# Recipe-specific function patterns to look for
RECIPE_FUNCTION_PATTERNS = {
    "simulation_to_handoff": {
        "detect_recovery_template": {
            "description": "Detect recovery templates in messages",
            "patterns": ["last_bot_message_is_recovery_template", "recovery_phrases"],
            "output_columns": FUNCTION_COLUMNS.get("detect_recovery_template", [])
        },
        "count_consecutive_recovery_templates": {
            "description": "Count consecutive recovery templates at the end of a conversation",
            "patterns": ["consecutive_recovery_templates_count", "count consecutive templates"],
            "output_columns": FUNCTION_COLUMNS.get("count_consecutive_recovery_templates", [])
        }
    },
    "top_up_may": {
        "detect_topup_template": {
            "description": "Detect top-up template messages",
            "patterns": ["contains_top_up_template", "TOP_UP_TEMPLATE_PATTERNS"],
            "output_columns": FUNCTION_COLUMNS.get("detect_topup_template", [])
        }
    }
}

def discover_global_functions() -> List[Dict[str, Any]]:
    """
    Returns a list of global functions from the predefined list
    with their description, trigger condition, and configuration parameters.
    """
    return GLOBAL_FUNCTIONS

def extract_functions_from_analyzer(file_path: Path) -> List[Dict[str, Any]]:
    """
    Extract functions from a recipe's analyzer.py file
    
    Args:
        file_path: Path to the analyzer.py file
        
    Returns:
        List of dictionaries with function information
    """
    if not file_path.exists():
        return []
    
    try:
        # Parse the python file
        with open(file_path, 'r') as f:
            source = f.read()
        
        parsed = ast.parse(source)
        
        functions = []
        for node in ast.walk(parsed):
            if isinstance(node, ast.FunctionDef):
                # Skip private functions (starting with _)
                if node.name.startswith('_'):
                    continue
                    
                # Extract docstring if available
                full_docstring = ast.get_docstring(node) or "No description available"
                docstring_lines = full_docstring.split('\n')
                
                # Extract the first paragraph (not just the first line)
                description = docstring_lines[0].strip()
                
                # If there are more lines, add them to create a more detailed description
                if len(docstring_lines) > 1:
                    # Skip empty lines and join the rest
                    additional_lines = [line.strip() for line in docstring_lines[1:] if line.strip()]
                    if additional_lines:
                        description += " " + " ".join(additional_lines)
                
                # Extract function arguments
                args = []
                for arg in node.args.args:
                    if arg.arg != 'self':  # Skip 'self' for class methods
                        args.append(arg.arg)
                
                # Extract function content to find patterns and output columns
                function_body = source[node.body[0].lineno:node.body[-1].end_lineno]
                patterns = []
                output_columns = []
                
                # Look for output columns in return statements and dictionary assignments
                # Check for patterns like 'return {"column_name": value}' or 'result["column_name"] = value'
                column_patterns = [
                    r'["\']([a-zA-Z0-9_]+)["\']:\s*',  # Keys in dictionaries
                    r'result\[["\']([a-zA-Z0-9_]+)["\']\]\s*=',  # Assignments to result dict
                    r'flags\[["\']([a-zA-Z0-9_]+)["\']\]\s*=',   # Assignments to flags dict
                    r'data\[["\']([a-zA-Z0-9_]+)["\']\]\s*='     # Assignments to data dict
                ]
                
                for pattern in column_patterns:
                    matches = re.findall(pattern, function_body)
                    output_columns.extend(matches)
                
                # Look for common detection patterns in string literals
                common_patterns = [
                    r"(['\"])(.+?handoff.+?)(\1)",  # Handoff related
                    r"(['\"])(.+?template.+?)(\1)",  # Template related
                    r"(['\"])(.+?offer.+?)(\1)",     # Offer related
                    r"(['\"])(.+?transfer.+?)(\1)",  # Transfer related
                    r"(['\"])(.+?interest.+?)(\1)",  # Interest related
                    r"(['\"])(.+?decline.+?)(\1)"    # Decline related
                ]
                
                for pattern in common_patterns:
                    matches = re.findall(pattern, function_body, re.IGNORECASE)
                    for match in matches:
                        if len(match) >= 3:  # Ensure we have a match with captured groups
                            patterns.append(match[1])
                
                # Create more descriptive function information
                enhanced_description = description
                if output_columns:
                    enhanced_description += f"\n\nOutput columns: {', '.join(output_columns)}"
                
                functions.append({
                    "name": node.name,
                    "description": enhanced_description,
                    "args": args,
                    "patterns": patterns[:5],  # Limit to first 5 patterns for brevity
                    "output_columns": list(set(output_columns)),  # Remove duplicates
                    "config_params": {},  # No config params for now
                    "file_path": str(file_path)
                })
                
        return functions
        
    except Exception as e:
        logger.error(f"Error parsing analyzer.py at {file_path}: {e}")
        return []

def discover_recipe_analyzers(recipe_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Discover recipe-specific analyzer functions
    
    Args:
        recipe_name: Optional recipe name to filter results
        
    Returns:
        Dictionary mapping recipe names to lists of function information
    """
    recipe_functions = {}
    
    # If a specific recipe is requested
    if recipe_name:
        analyzer_path = RECIPE_ROOT / recipe_name / "analyzer.py"
        if analyzer_path.exists():
            functions = extract_functions_from_analyzer(analyzer_path)
            recipe_functions[recipe_name] = functions
        return recipe_functions
    
    # Otherwise, scan all recipes
    for recipe_dir in RECIPE_ROOT.iterdir():
        if not recipe_dir.is_dir() or recipe_dir.name.startswith('.'):
            continue
            
        analyzer_path = recipe_dir / "analyzer.py"
        if analyzer_path.exists():
            functions = extract_functions_from_analyzer(analyzer_path)
            if functions:
                recipe_functions[recipe_dir.name] = functions
    
    return recipe_functions

def get_built_in_recipe_functions(recipe_name: str) -> List[Dict[str, Any]]:
    """
    Get built-in functions specific to a recipe in analysis.py
    
    Args:
        recipe_name: Name of the recipe
        
    Returns:
        List of function information dictionaries
    """
    built_in_functions = []
    
    # Check if this recipe has built-in functions defined in analysis.py
    if recipe_name in RECIPE_FUNCTION_PATTERNS:
        for func_name, func_info in RECIPE_FUNCTION_PATTERNS[recipe_name].items():
            built_in_functions.append({
                "name": func_name,
                "description": func_info.get("description", "No description available"),
                "trigger": f"Executed for {recipe_name} recipe",
                "patterns": func_info.get("patterns", []),
                "output_columns": func_info.get("output_columns", []),
                "config_params": {},
                "built_in": True
            })
    
    return built_in_functions

def get_all_functions_for_recipe(recipe_name: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all functions applicable to a recipe, including:
    - Global functions
    - Recipe-specific analyzers
    - Built-in recipe functions in analysis.py
    
    Args:
        recipe_name: Name of the recipe
        
    Returns:
        Dictionary with 'global', 'recipe', and 'built_in' keys mapping to function lists
    """
    return {
        "global": discover_global_functions(),
        "recipe": discover_recipe_analyzers(recipe_name).get(recipe_name, []),
        "built_in": get_built_in_recipe_functions(recipe_name)
    }

if __name__ == "__main__":
    # Test the function discovery
    global_funcs = discover_global_functions()
    print(f"Found {len(global_funcs)} global functions")
    
    recipe_funcs = discover_recipe_analyzers()
    print(f"Found functions in {len(recipe_funcs)} recipes")
    
    for recipe, functions in recipe_funcs.items():
        print(f"Recipe {recipe}: {len(functions)} functions")
        for func in functions:
            print(f"  - {func['name']}: {func['description']}")
            print(f"    Patterns: {func['patterns']}")
            print(f"    Output columns: {func['output_columns']}") 