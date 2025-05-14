import pytest

from lead_recovery.recipe_loader import list_recipes, load_recipe

REQUIRED_META_FIELDS = {
    "name",
    "dashboard_title",
    "summary_format",
    "output_columns",
    "redshift_sql",
    "prompt_file",
}


def test_all_recipes_loadable():
    """All recipe folders must be discoverable and load without exceptions."""
    recipe_names = list_recipes()
    assert recipe_names, "No recipes found under 'recipes/'"

    for name in recipe_names:
        recipe = load_recipe(name)  # should not raise
        # Basic sanity on meta contents
        missing = REQUIRED_META_FIELDS - recipe.meta.keys()
        assert not missing, f"Recipe '{name}' is missing meta fields: {missing}"

        # Assert referenced files actually exist
        assert recipe.redshift_sql_path.exists(), f"{recipe.redshift_sql_path} missing"
        if recipe.bigquery_sql_path:  # optional
            assert recipe.bigquery_sql_path.exists(), f"{recipe.bigquery_sql_path} missing"
        assert recipe.prompt_path.exists(), f"{recipe.prompt_path} missing" 