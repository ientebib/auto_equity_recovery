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


def test_list_recipes():
    """Test that list_recipes function returns a non-empty list."""
    recipes = list_recipes()
    assert len(recipes) > 0
    
    # All recipes should be strings
    for recipe in recipes:
        assert isinstance(recipe, str)


def test_load_recipe():
    """Test that load_recipe function loads valid recipes."""
    # Load a test recipe
    recipes = list_recipes()
    assert len(recipes) > 0
    
    # Load the first recipe to test
    recipe_name = recipes[0]
    recipe = load_recipe(recipe_name)
    
    # Ensure required attributes are present
    assert recipe.name == recipe_name
    assert recipe.path.exists()
    assert recipe.meta_path.exists(), f"{recipe.meta_path} missing"
    
    # Validate existence of referenced files
    assert recipe.redshift_sql_path.exists(), f"{recipe.redshift_sql_path} missing"
    if recipe.bigquery_sql_path:  # optional
        assert recipe.bigquery_sql_path.exists(), f"{recipe.bigquery_sql_path} missing"
    assert recipe.prompt_path.exists(), f"{recipe.prompt_path} missing" 
