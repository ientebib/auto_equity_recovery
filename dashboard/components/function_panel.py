"""
Function Panel Component

UI components for Python Function Control Panel.
"""
import logging
from typing import List

import streamlit as st

from dashboard.utils.function_controller import FunctionController

logger = logging.getLogger(__name__)

def render_function_panel(recipe_name: str) -> List[str]:
    """
    Render the Python Function Control Panel for a recipe.
    
    Args:
        recipe_name: Name of the recipe
        
    Returns:
        List of CLI arguments based on user selections
    """
    if not recipe_name:
        st.warning("Please select a recipe first.")
        return []
    
    # Initialize or get the function controller for this recipe
    controller_key = f"function_controller_{recipe_name}"
    if controller_key not in st.session_state:
        st.session_state[controller_key] = FunctionController(recipe_name)
    controller = st.session_state[controller_key]
    
    # Create a session state key for the panel expanded state
    panel_expanded_key = f"function_panel_expanded_{recipe_name}"
    if panel_expanded_key not in st.session_state:
        st.session_state[panel_expanded_key] = False
    
    # Create a container for the panel
    with st.expander("🧠 Python Function Control Panel", expanded=st.session_state[panel_expanded_key]):
        # Toggle the expanded state
        st.session_state[panel_expanded_key] = True
        
        # Render the presets selection
        st.subheader("Function Presets")
        col1, col2 = st.columns([3, 1])
        
        # Preset selection
        with col1:
            preset_options = controller.get_preset_names()
            selected_preset = st.selectbox(
                "Load Preset",
                options=preset_options,
                index=0,
                help="Select a predefined set of function configurations",
                key=f"preset_select_{recipe_name}"
            )
        
        # Apply preset button
        with col2:
            if st.button("Apply Preset", use_container_width=True, key=f"apply_preset_btn_{recipe_name}"):
                controller.load_preset(selected_preset)
                st.success(f"Applied '{selected_preset}' preset")
                st.rerun()
        
        # Recipe-specific preset management
        st.subheader("Recipe Preset")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Save Current Config", use_container_width=True, key=f"save_config_btn_{recipe_name}"):
                if controller.save_recipe_preset():
                    st.success(f"Saved configuration for {recipe_name}")
                else:
                    st.error("Failed to save configuration")
        
        with col2:
            if st.button("Load Recipe Config", use_container_width=True, key=f"load_config_btn_{recipe_name}"):
                if controller.load_recipe_preset():
                    st.success(f"Loaded configuration for {recipe_name}")
                    st.rerun()
                else:
                    st.warning(f"No saved configuration for {recipe_name}")
        
        # Function configuration
        st.subheader("Function Configuration")
        
        # Get all function info
        functions = controller.functions
        function_states = controller.get_function_states()
        
        # Global Functions
        st.markdown("#### Global Functions")
        st.caption("These functions apply to all recipes")
        
        for idx, func in enumerate(functions["global"]):
            func_name = func["name"]
            if func_name in function_states:
                state = function_states[func_name]
                
                # Create a unique key for each toggle - add unique index for each global function
                toggle_key = f"global_{func_name}_enabled_{recipe_name}_{idx}"
                config_key = f"global_{func_name}_config_{recipe_name}_{idx}"
                
                # Function container with toggle and info
                with st.container():
                    col1, col2 = st.columns([1, 4])
                    
                    # Enable/disable toggle
                    with col1:
                        enabled = st.toggle(
                            "Enable",
                            value=state["enabled"],
                            key=toggle_key,
                            help=f"Enable/disable {func_name}"
                        )
                        
                        # Update state when toggle changes
                        if toggle_key in st.session_state and enabled != state["enabled"]:
                            controller.update_function_state(func_name, enabled, None)
                    
                    # Function information
                    with col2:
                        st.markdown(f"**{func_name}**")
                        st.caption(func["description"])
                        st.caption(f"Trigger: {func.get('trigger', 'Not specified')}")
                        
                        # Show patterns if available
                        if func.get("patterns"):
                            pattern_text = " | ".join(func["patterns"][:3])
                            if len(func["patterns"]) > 3:
                                pattern_text += " | ..."
                            st.caption(f"Patterns: {pattern_text}")
                        
                        # Show output columns if available
                        if func.get("output_columns"):
                            columns_text = ", ".join(func["output_columns"][:5])
                            if len(func["output_columns"]) > 5:
                                columns_text += ", ..."
                            st.caption(f"📊 Output columns: {columns_text}")
                    
                    # Configuration parameters if any
                    if func.get("config_params"):
                        st.markdown("**Configuration:**")
                        for param_idx, (param_name, param_info) in enumerate(func["config_params"].items()):
                            if param_info["type"] == "bool":
                                current_value = state["config"].get(param_name, param_info["default"])
                                new_value = st.checkbox(
                                    param_info["description"],
                                    value=current_value,
                                    key=f"{config_key}_{param_name}_{param_idx}"
                                )
                                
                                # Update config when value changes
                                if new_value != current_value:
                                    controller.update_function_state(
                                        func_name, 
                                        state["enabled"], 
                                        {param_name: new_value}
                                    )
                    
                    # Special handling for temporal_flags function
                    if func_name == "temporal_flags" or func_name == "calculate_temporal_flags":
                        if state["enabled"]:
                            st.markdown("#### Temporal Flags Configuration")
                            
                            # Master toggle for skip_temporal_flags
                            st.markdown("**Master Toggle**")
                            skip_temporal_key = f"global_{func_name}_{config_key}_skip_temporal_flags_{idx}"
                            current_skip_temporal = state["config"].get("skip_temporal_flags", False)
                            new_skip_temporal = st.checkbox(
                                "Skip ALL temporal flags (overrides all groups below)",
                                value=current_skip_temporal,
                                key=skip_temporal_key,
                                help="Completely disable all temporal flag calculations"
                            )
                            if new_skip_temporal != current_skip_temporal:
                                controller.update_function_state(
                                    func_name,
                                    state["enabled"],
                                    {"skip_temporal_flags": new_skip_temporal}
                                )
                                # If turning on skip_temporal_flags, refresh UI
                                if new_skip_temporal:
                                    st.rerun()
                            
                            # Show other groups only if skip_temporal_flags is False
                            if not current_skip_temporal:
                                # Group A: Hours and minutes formatting
                                st.markdown("**Group A: Hours & Minutes**")
                                skip_hours_key = f"global_{func_name}_{config_key}_skip_hours_minutes_{idx}"
                                current_skip_hours = state["config"].get("skip_hours_minutes", False)
                                new_skip_hours = st.checkbox(
                                    "Skip hours/minutes calculations (HOURS_MINUTES_SINCE_LAST_USER_MESSAGE, HOURS_MINUTES_SINCE_LAST_MESSAGE)",
                                    value=current_skip_hours,
                                    key=skip_hours_key,
                                    help="Skip calculation of formatted hour/minute deltas like '5h 30m'"
                                )
                                if new_skip_hours != current_skip_hours:
                                    controller.update_function_state(
                                        func_name,
                                        state["enabled"],
                                        {"skip_hours_minutes": new_skip_hours}
                                    )
                                
                                # Group B: Reactivation window flags
                                st.markdown("**Group B: Reactivation Flags**")
                                skip_reactivation_key = f"global_{func_name}_{config_key}_skip_reactivation_flags_{idx}"
                                current_skip_reactivation = state["config"].get("skip_reactivation_flags", False)
                                new_skip_reactivation = st.checkbox(
                                    "Skip reactivation flags (IS_WITHIN_REACTIVATION_WINDOW, IS_RECOVERY_PHASE_ELIGIBLE)",
                                    value=current_skip_reactivation,
                                    key=skip_reactivation_key,
                                    help="Skip calculation of flags that determine if a lead is within reactivation window"
                                )
                                if new_skip_reactivation != current_skip_reactivation:
                                    controller.update_function_state(
                                        func_name,
                                        state["enabled"],
                                        {"skip_reactivation_flags": new_skip_reactivation}
                                    )
                                
                                # Group C: Timestamps
                                st.markdown("**Group C: Timestamps**")
                                skip_timestamps_key = f"global_{func_name}_{config_key}_skip_timestamps_{idx}"
                                current_skip_timestamps = state["config"].get("skip_timestamps", False)
                                new_skip_timestamps = st.checkbox(
                                    "Skip timestamp formatting (LAST_USER_MESSAGE_TIMESTAMP_TZ, LAST_MESSAGE_TIMESTAMP_TZ)",
                                    value=current_skip_timestamps,
                                    key=skip_timestamps_key,
                                    help="Skip calculation of ISO timestamps for last messages"
                                )
                                if new_skip_timestamps != current_skip_timestamps:
                                    controller.update_function_state(
                                        func_name,
                                        state["enabled"],
                                        {"skip_timestamps": new_skip_timestamps}
                                    )
                                
                                # Group D: User message existence
                                st.markdown("**Group D: User Message Flag**")
                                skip_user_flag_key = f"global_{func_name}_{config_key}_skip_user_message_flag_{idx}"
                                current_skip_user_flag = state["config"].get("skip_user_message_flag", False)
                                new_skip_user_flag = st.checkbox(
                                    "Skip user flag (NO_USER_MESSAGES_EXIST)",
                                    value=current_skip_user_flag,
                                    key=skip_user_flag_key,
                                    help="Skip checking if user has never sent a message"
                                )
                                if new_skip_user_flag != current_skip_user_flag:
                                    controller.update_function_state(
                                        func_name,
                                        state["enabled"],
                                        {"skip_user_message_flag": new_skip_user_flag}
                                    )
                                
                                # Legacy option for backward compatibility
                                st.markdown("**Legacy Option**")
                                skip_detailed_key = f"global_{func_name}_{config_key}_skip_detailed_temporal_{idx}"
                                current_skip_detailed = state["config"].get("skip_detailed_temporal", False)
                                new_skip_detailed = st.checkbox(
                                    "Legacy: Skip detailed temporal calculations (overrides groups A & B)",
                                    value=current_skip_detailed,
                                    key=skip_detailed_key,
                                    help="Legacy option that sets both Group A and B to skip"
                                )
                                if new_skip_detailed != current_skip_detailed:
                                    # When setting skip_detailed_temporal, automatically set A & B skips
                                    controller.update_function_state(
                                        func_name,
                                        state["enabled"],
                                        {
                                            "skip_detailed_temporal": new_skip_detailed,
                                            "skip_hours_minutes": new_skip_detailed,
                                            "skip_reactivation_flags": new_skip_detailed
                                        }
                                    )
                                    # Refresh the UI to show updated values
                                    st.rerun()
                            else:
                                # If skip_temporal_flags is True, show a message explaining that all flags are skipped
                                st.info("All temporal flag calculations are skipped. Uncheck the master toggle above to enable granular control.")
                    
                    # Add separator
                    st.divider()
        
        # Recipe-specific functions if available
        if functions["recipe"]:
            st.markdown("#### Recipe-Specific Functions")
            st.caption(f"These functions are specific to the {recipe_name} recipe")
            
            for idx, func in enumerate(functions["recipe"]):
                func_name = func["name"]
                if func_name in function_states:
                    state = function_states[func_name]
                    
                    # Create a unique key for each toggle
                    toggle_key = f"recipe_{func_name}_enabled_{recipe_name}_{idx}"
                    
                    # Function container with toggle and info
                    with st.container():
                        col1, col2 = st.columns([1, 4])
                        
                        # Enable/disable toggle
                        with col1:
                            enabled = st.toggle(
                                "Enable",
                                value=state["enabled"],
                                key=toggle_key,
                                help=f"Enable/disable {func_name}"
                            )
                            
                            # Update state when toggle changes
                            if toggle_key in st.session_state and enabled != state["enabled"]:
                                controller.update_function_state(func_name, enabled, None)
                        
                        # Function information
                        with col2:
                            st.markdown(f"**{func_name}**")
                            st.caption(func["description"])
                            
                            # Show arguments if available
                            if func.get("args"):
                                args_text = ", ".join(func["args"])
                                st.caption(f"Args: {args_text}")
                            
                            # Show patterns if available
                            if func.get("patterns"):
                                pattern_text = " | ".join(func["patterns"][:3])
                                if len(func["patterns"]) > 3:
                                    pattern_text += " | ..."
                                st.caption(f"Patterns: {pattern_text}")
                            
                            # Show output columns if available
                            if func.get("output_columns"):
                                columns_text = ", ".join(func["output_columns"][:5])
                                if len(func["output_columns"]) > 5:
                                    columns_text += ", ..."
                                st.caption(f"📊 Output columns: {columns_text}")
                        
                        # Add separator
                        st.divider()
        
        # Built-in recipe functions if available
        if functions["built_in"]:
            st.markdown("#### Built-In Recipe Functions")
            st.caption(f"These functions are built into the analysis system for {recipe_name}")
            
            for idx, func in enumerate(functions["built_in"]):
                func_name = func["name"]
                if func_name in function_states:
                    state = function_states[func_name]
                    
                    # Create a unique key for each toggle
                    toggle_key = f"built_in_{func_name}_enabled_{recipe_name}_{idx}"
                    
                    # Function container with toggle and info
                    with st.container():
                        col1, col2 = st.columns([1, 4])
                        
                        # Enable/disable toggle
                        with col1:
                            enabled = st.toggle(
                                "Enable",
                                value=state["enabled"],
                                key=toggle_key,
                                help=f"Enable/disable {func_name}"
                            )
                            
                            # Update state when toggle changes
                            if toggle_key in st.session_state and enabled != state["enabled"]:
                                controller.update_function_state(func_name, enabled, None)
                        
                        # Function information
                        with col2:
                            st.markdown(f"**{func_name}**")
                            st.caption(func["description"])
                            st.caption(f"Trigger: {func.get('trigger', 'Not specified')}")
                            
                            # Show patterns if available
                            if func.get("patterns"):
                                pattern_text = " | ".join(func["patterns"][:3])
                                if len(func["patterns"]) > 3:
                                    pattern_text += " | ..."
                                st.caption(f"Patterns: {pattern_text}")
                            
                            # Show output columns if available
                            if func.get("output_columns"):
                                columns_text = ", ".join(func["output_columns"][:5])
                                if len(func["output_columns"]) > 5:
                                    columns_text += ", ..."
                                st.caption(f"📊 Output columns: {columns_text}")
                        
                        # Add separator
                        st.divider()
        
        # CLI arguments preview
        st.subheader("Preview CLI Arguments")
        cli_args = controller.generate_cli_args()
        
        if cli_args:
            st.code(" ".join(cli_args), language="bash")
        else:
            st.info("No CLI arguments will be added (using default function behavior)")
    
    # Return the CLI arguments
    return controller.generate_cli_args()

if __name__ == "__main__":
    # This will not be executed when imported as a module
    st.set_page_config(page_title="Function Panel Test", layout="wide")
    st.title("Function Panel Test")
    
    # Test the function panel with a sample recipe
    test_recipe = "marzo_cohorts_live"
    st.write(f"Testing function panel for recipe: {test_recipe}")
    
    cli_args = render_function_panel(test_recipe)
    
    st.write("Returned CLI arguments:")
    st.code(" ".join(cli_args), language="bash") 