"""exceptions.py
Custom exception classes for the lead recovery pipeline.
"""

class LeadRecoveryError(Exception):
    """Base class for exceptions in this application."""
    pass

# -- Configuration Errors --
class ConfigurationError(LeadRecoveryError):
    """Exception related to configuration issues (e.g., missing settings, invalid recipe)."""
    pass

class RecipeNotFoundError(ConfigurationError, FileNotFoundError):
    """Exception for when a specified recipe cannot be found."""
    pass

# -- Database Errors --
class DatabaseError(LeadRecoveryError):
    """Base class for database-related errors."""
    pass

class DatabaseConnectionError(DatabaseError):
    """Exception for errors connecting to the database."""
    pass

class DatabaseQueryError(DatabaseError):
    """Exception for errors during database query execution."""
    pass

# -- API Errors --
class ApiError(LeadRecoveryError):
    """Exception related to external API interactions (e.g., OpenAI)."""
    pass

# -- Validation Errors --
class ValidationError(LeadRecoveryError):
    """Exception for data validation errors (e.g., YAML parsing, schema mismatch).

    Accepts arbitrary keyword arguments (e.g., parsed_data, raw_response) so that callers
    can attach contextual information without breaking the exception signature.
    """

    def __init__(self, message: str, **kwargs):
        super().__init__(message)
        # Store extra context for downstream debugging if provided
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __str__(self):
        base = super().__str__()
        # Include extra keys in repr to aid logging
        extras = {k: v for k, v in self.__dict__.items() if k not in ('args',)}
        if extras:
            return f"{base} | Context: {extras}"
        return base

# -- File Errors --
# Using built-in FileNotFoundError is often sufficient, but we could wrap it if needed.
# class FileProcessingError(LeadRecoveryError):
#     """Exception for errors reading or processing files."""
#     pass 