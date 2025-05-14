"""Tests for CLI functionality."""
import pytest
from typer.testing import CliRunner

from lead_recovery.cli.main import app


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


def test_cli_loads():
    """Test that the CLI app loads without error."""
    # This test just verifies that the app is set up correctly
    assert app is not None


def test_cli_help(runner):
    """Test that the CLI help shows all commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    
    # Check for all expected commands in help output
    assert "fetch-leads" in result.stdout
    assert "fetch-convos" in result.stdout
    assert "summarize" in result.stdout
    assert "report" in result.stdout
    assert "run" in result.stdout 