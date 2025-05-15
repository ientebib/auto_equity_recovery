import pytest
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from lead_recovery.recipe_loader import RecipeLoader
from lead_recovery.exceptions import RecipeConfigurationError

def test_path_traversal_prevention():
    """Test that the recipe loader prevents path traversal attacks."""
    with TemporaryDirectory() as tmpdir:
        # Create a temporary project structure
        project_root = Path(tmpdir)
        recipes_dir = project_root / "recipes"
        recipes_dir.mkdir()
        
        # Create a recipe directory
        recipe_dir = recipes_dir / "test_recipe"
        recipe_dir.mkdir()
        
        # Create a file inside the recipe directory
        (recipe_dir / "valid_file.txt").touch()
        
        # Create a file outside the recipe directory
        (project_root / "outside_file.txt").touch()
        
        # Initialize the recipe loader
        loader = RecipeLoader(project_root=project_root)
        
        # Test valid file access
        valid_path = loader._resolve_recipe_file_path(recipe_dir, "valid_file.txt")
        assert valid_path.exists()
        
        # Test that direct path traversal is caught
        with pytest.raises(RecipeConfigurationError, match="Invalid file path"):
            loader._resolve_recipe_file_path(recipe_dir, "../outside_file.txt")
        
        # Test that absolute paths are caught
        with pytest.raises(RecipeConfigurationError, match="Invalid file path"):
            loader._resolve_recipe_file_path(recipe_dir, "/tmp/some_file.txt")
        
        # Test more complex path traversal attempts with symlinks
        if os.name != 'nt':  # Skip on Windows where symlinks might need special permissions
            symlink_file = recipe_dir / "symlink_to_outside.txt"
            os.symlink(project_root / "outside_file.txt", symlink_file)
            
            with pytest.raises(RecipeConfigurationError, match="Security violation"):
                loader._resolve_recipe_file_path(recipe_dir, "symlink_to_outside.txt")
                
        # Test directory path
        subdir = recipe_dir / "subdir"
        subdir.mkdir()
        (subdir / "subfile.txt").touch()
        
        valid_subpath = loader._resolve_recipe_file_path(recipe_dir, "subdir/subfile.txt")
        assert valid_subpath.exists() 