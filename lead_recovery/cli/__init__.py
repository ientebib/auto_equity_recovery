"""CLI commands for lead recovery package."""
import typer

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

# Re-export app for backwards compatibility
__all__ = ["app"] 