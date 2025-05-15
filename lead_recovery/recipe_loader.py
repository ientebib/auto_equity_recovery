from __future__ import annotations

"""recipe_loader.py
Utility helpers to discover and load *recipe* folders.

A *recipe* is a directory under the project‑root `recipes/` folder that
contains the following files:
    meta.yml       – Human‑friendly metadata and configuration for the recipe

The meta.yml file follows a strict schema defined in recipe_schema.py.
"""

import yaml
from pathlib import Path
from typing import List, Optional
from pydantic import ValidationError

# Import the schema and custom exceptions
from .recipe_schema import RecipeMeta 
from .exceptions import RecipeConfigurationError

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
# Default project structure constants
_DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent.parent 
_DEFAULT_RECIPES_DIR_NAME = "recipes"
_DEFAULT_META_YML_FILENAME = "meta.yml"

class RecipeLoader:
    def __init__(self, project_root: Optional[Path] = None, recipes_dir_name: Optional[str] = None):
        # Allow overriding for testing, but default to sensible project structure
        self.project_root = project_root if project_root else _DEFAULT_PROJECT_ROOT
        self.recipes_base_dir = self.project_root / (recipes_dir_name if recipes_dir_name else _DEFAULT_RECIPES_DIR_NAME)
        if not self.recipes_base_dir.is_dir():
            # This is a critical setup error, should ideally not happen in a valid deployment
            raise RecipeConfigurationError(
                f"Recipes base directory not found or is not a directory: {self.recipes_base_dir}"
            )

    def _resolve_recipe_file_path(self, recipe_dir: Path, file_name: Optional[str]) -> Optional[Path]:
        """Resolves a filename relative to the given recipe directory."""
        if file_name is None:
            return None
        
        # Prevent directory traversal attempts for security and simplicity
        if ".." in file_name or file_name.startswith("/"):
            raise RecipeConfigurationError(
                f"Invalid file path '{file_name}' in recipe. Paths must be relative and within the recipe directory."
            )
        
        resolved_path = (recipe_dir / file_name).resolve()
        
        # Double-check it's still within the recipe_dir (or a subdirectory)
        # This is a stricter check after resolving symlinks etc.
        if recipe_dir.resolve() not in resolved_path.parents and resolved_path != recipe_dir.resolve():
             # This check might be too strict if symlinks legitimately point outside,
             # but for simple recipe assets, it's a good safety measure.
             # Consider if this strictness is needed or if just `(recipe_dir / file_name).exists()` is enough later.
             # For now, let's assume files are directly within or in subfolders of recipe_dir.
             pass # Simplified: we'll let existence checks happen when file is actually used.

        return resolved_path # Return the resolved, absolute path

    def load_recipe_meta(self, recipe_name: str) -> RecipeMeta:
        """
        Loads, validates, and resolves paths for a recipe's meta.yml file.
        Returns a RecipeMeta Pydantic model instance.
        """
        recipe_dir = self.recipes_base_dir / recipe_name
        meta_file_path = recipe_dir / _DEFAULT_META_YML_FILENAME

        if not recipe_dir.is_dir():
            raise RecipeConfigurationError(f"Recipe directory not found: {recipe_dir}")
        if not meta_file_path.exists():
            raise RecipeConfigurationError(f"Recipe meta file not found: {meta_file_path}")

        try:
            with open(meta_file_path, 'r', encoding='utf-8') as f:
                raw_meta_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise RecipeConfigurationError(f"Error parsing YAML from {meta_file_path}: {e}")
        except Exception as e:
            raise RecipeConfigurationError(f"Error reading file {meta_file_path}: {e}")

        if not raw_meta_data:
            raise RecipeConfigurationError(f"Meta file {meta_file_path} is empty or not valid YAML content.")

        try:
            # --- Schema Validation ---
            # Ensure recipe_name from directory matches if present in YAML, or inject it.
            # The schema now requires recipe_name in the YAML.
            if 'recipe_name' not in raw_meta_data:
                 raise RecipeConfigurationError(f"'recipe_name' is missing in {meta_file_path}.")
            if raw_meta_data['recipe_name'] != recipe_name:
                 raise RecipeConfigurationError(
                     f"Recipe name in {meta_file_path} ('{raw_meta_data['recipe_name']}') "
                     f"does not match directory name ('{recipe_name}')."
                 )

            parsed_meta = RecipeMeta(**raw_meta_data)

            # --- Path Resolution post-validation ---
            # Resolve file paths to be absolute paths for easier use by other modules.
            
            # Data Input files
            if parsed_meta.data_input:
                if parsed_meta.data_input.redshift_config and parsed_meta.data_input.redshift_config.sql_file:
                    parsed_meta.data_input.redshift_config.sql_file = str(self._resolve_recipe_file_path(
                        recipe_dir, parsed_meta.data_input.redshift_config.sql_file
                    ))
                if parsed_meta.data_input.bigquery_config and parsed_meta.data_input.bigquery_config.sql_file:
                    parsed_meta.data_input.bigquery_config.sql_file = str(self._resolve_recipe_file_path(
                        recipe_dir, parsed_meta.data_input.bigquery_config.sql_file
                    ))
                if parsed_meta.data_input.csv_config and parsed_meta.data_input.csv_config.csv_file:
                    parsed_meta.data_input.csv_config.csv_file = str(self._resolve_recipe_file_path(
                        recipe_dir, parsed_meta.data_input.csv_config.csv_file
                    ))
                if parsed_meta.data_input.conversation_sql_file_redshift:
                    parsed_meta.data_input.conversation_sql_file_redshift = str(self._resolve_recipe_file_path(
                         recipe_dir, parsed_meta.data_input.conversation_sql_file_redshift
                    ))
                if parsed_meta.data_input.conversation_sql_file_bigquery:
                    parsed_meta.data_input.conversation_sql_file_bigquery = str(self._resolve_recipe_file_path(
                         recipe_dir, parsed_meta.data_input.conversation_sql_file_bigquery
                    ))

            # LLM prompt file
            if parsed_meta.llm_config and parsed_meta.llm_config.prompt_file:
                parsed_meta.llm_config.prompt_file = str(self._resolve_recipe_file_path(
                    recipe_dir, parsed_meta.llm_config.prompt_file
                ))
            
            return parsed_meta

        except ValidationError as e:
            error_messages = []
            for error in e.errors():
                loc_str = " -> ".join(map(str, error['loc'])) if error['loc'] else "root"
                error_messages.append(f"  - Field '{loc_str}': {error['msg']} (value: {error.get('input')})")
            detailed_errors = "\n".join(error_messages)
            raise RecipeConfigurationError(
                f"Invalid recipe configuration in {meta_file_path}:\n{detailed_errors}"
            )
        except Exception as e: # Catch other unexpected errors
            raise RecipeConfigurationError(f"Unexpected error processing meta file {meta_file_path}: {e}")

    def list_available_recipes(self) -> List[str]:
        """Lists all available recipe names based on directory structure."""
        if not self.recipes_base_dir.is_dir():
            return []
        return [
            d.name
            for d in self.recipes_base_dir.iterdir()
            if d.is_dir() and (d / _DEFAULT_META_YML_FILENAME).exists()
        ] 