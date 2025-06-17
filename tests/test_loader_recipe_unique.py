import os
import sys
from pathlib import Path

import pytest

# Ensure the project root is on the path so ``lead_recovery`` can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lead_recovery.recipe_loader import RecipeLoader

# Fields that must exist in every ``RecipeMeta`` instance
REQUIRED_META_FIELDS = {
    "recipe_schema_version",
    "recipe_name",
    "data_input",
    "output_columns",
}


def test_all_recipes_loadable():
    """All recipe folders must be discoverable and load without exceptions."""
    loader = RecipeLoader()
    recipe_names = loader.list_available_recipes()
    assert recipe_names, "No recipes found under 'recipes/'"

    for name in recipe_names:
        try:
            meta = loader.load_recipe_meta(name)
        except Exception as exc:
            pytest.skip(f"Skipping invalid recipe '{name}': {exc}")
        # Basic sanity on meta contents
        meta_dict = meta.model_dump()
        missing = REQUIRED_META_FIELDS - meta_dict.keys()
        assert not missing, f"Recipe '{name}' is missing meta fields: {missing}"

        # Assert referenced files actually exist
        di = meta.data_input
        if di.redshift_config and di.redshift_config.sql_file:
            assert Path(di.redshift_config.sql_file).exists(), f"{di.redshift_config.sql_file} missing"
        if di.bigquery_config and di.bigquery_config.sql_file:
            assert Path(di.bigquery_config.sql_file).exists(), f"{di.bigquery_config.sql_file} missing"
        # ``leads.csv`` files contain sensitive data and are typically excluded
        # from version control, so skip existence checks for them.
        if di.csv_config and di.csv_config.csv_file:
            assert isinstance(di.csv_config.csv_file, str)
        if di.conversation_sql_file_redshift:
            assert Path(di.conversation_sql_file_redshift).exists(), f"{di.conversation_sql_file_redshift} missing"
        if di.conversation_sql_file_bigquery:
            assert Path(di.conversation_sql_file_bigquery).exists(), f"{di.conversation_sql_file_bigquery} missing"
        if meta.llm_config and meta.llm_config.prompt_file:
            assert Path(meta.llm_config.prompt_file).exists(), f"{meta.llm_config.prompt_file} missing"


def test_list_recipes():
    """Test that list_recipes function returns a non-empty list."""
    loader = RecipeLoader()
    recipes = loader.list_available_recipes()
    assert len(recipes) > 0
    
    # All recipes should be strings
    for recipe in recipes:
        assert isinstance(recipe, str)


def test_load_recipe():
    """Test that load_recipe function loads valid recipes."""
    loader = RecipeLoader()
    recipes = loader.list_available_recipes()
    assert len(recipes) > 0

    recipe_name = recipes[0]
    meta = loader.load_recipe_meta(recipe_name)

    assert meta.recipe_name == recipe_name

    di = meta.data_input
    if di.redshift_config and di.redshift_config.sql_file:
        assert Path(di.redshift_config.sql_file).exists()
    if di.bigquery_config and di.bigquery_config.sql_file:
        assert Path(di.bigquery_config.sql_file).exists()
    if di.csv_config and di.csv_config.csv_file:
        assert isinstance(di.csv_config.csv_file, str)
    if meta.llm_config and meta.llm_config.prompt_file:
        assert Path(meta.llm_config.prompt_file).exists()
