"""Test utilities from lead_recovery."""
import os
import tempfile
from pathlib import Path

import pytest

from lead_recovery.utils import clean_phone, clean_email, load_sql_file


def test_clean_phone():
    """Test phone number cleaning function."""
    # Test with various phone number formats
    assert clean_phone("+1 (555) 123-4567") == "15551234567"
    assert clean_phone("555-123-4567") == "5551234567"
    assert clean_phone("(555) 123.4567") == "5551234567"
    assert clean_phone("1-555-123-4567") == "15551234567"
    assert clean_phone("555 123 4567") == "5551234567"
    
    # Test with invalid inputs
    assert clean_phone("") == ""
    assert clean_phone(None) == ""
    assert clean_phone("not a phone number") == ""
    assert clean_phone("123") == "123"  # Too short but has digits


def test_clean_email():
    assert clean_email("Foo+bar@Example.com") == "foo@example.com"


def test_load_sql_file():
    """Test SQL file loading function."""
    # Create temp SQL file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
        sql_content = "SELECT * FROM table WHERE x = @param"
        f.write(sql_content)
        temp_sql_path = f.name
    
    try:
        # Test loading
        loaded_sql = load_sql_file(temp_sql_path)
        assert loaded_sql == sql_content
        
        # Test loading nonexistent file
        with pytest.raises(FileNotFoundError):
            load_sql_file("nonexistent.sql")
    finally:
        # Clean up
        os.unlink(temp_sql_path)


def test_load_sql_file_empty(tmp_path: Path):
    empty = tmp_path / "empty.sql"
    empty.write_text("")
    with pytest.raises(FileNotFoundError):
        load_sql_file(empty) 