"""summarizer_helpers.py
Pure helper utilities extracted from summarizer for easier unit-testing.
These functions contain no side-effects (network, file-IO) so they can
be tested without external services.
"""
from __future__ import annotations

import re
from typing import Any, Dict
import logging

import yaml

__all__ = [
    "clean_response_text",
    "parse_yaml_dict",
]

_MARKDOWN_FENCE_RE = re.compile(r"^```(?:yaml)?\n?|```$", re.IGNORECASE)


def _strip_markdown_fences(text: str) -> str:  # noqa: D401
    """Remove leading/trailing ``` or ```yaml fences if present."""
    # Remove the first fence
    text = _MARKDOWN_FENCE_RE.sub("", text, count=1)
    # Remove the last (closing) fence if present
    if text.endswith("```"):
        text = text[: -3]
    return text.strip()


def _attempt_fix_quotes(text: str) -> str:  # noqa: D401
    """Convert problematic double-quotes inside YAML values to single quotes.

    The pattern is heuristic but covers common model mistakes such as:
        reason: "User said "I don't know" yesterday"
    """
    pattern = re.compile(r"^(\s*\w+\s*:\s*)\"(.*\".*)\"(\s*)$", re.MULTILINE)
    try:
        return pattern.sub(r"\g<1>'\g<2>'\g<3>", text)
    except re.error:
        # If regex fails for weird input, return untouched
        return text


def _attempt_fix_multiline_values(text: str) -> str:
    """Fix multiline values that need to be properly indented for YAML.
    
    The pattern looks for values that continue on the next line without proper indentation:
        key: first line
        second line
        third line
        next_key: value
    
    And fixes them by adding indentation:
        key: first line
          second line
          third line
        next_key: value
    """
    lines = text.split('\n')
    result_lines = []
    current_key = None
    
    for i, line in enumerate(lines):
        # Check if this is a key: value line
        key_match = re.match(r'^(\s*)([a-zA-Z0-9_]+)(\s*:\s*.*)$', line)
        
        if key_match:
            # We found a new key
            current_key = key_match.group(2)
            result_lines.append(line)
        elif line.strip() and i > 0 and current_key and not re.match(r'^\s+', line):
            # This is a continuation line without indentation
            result_lines.append(f"  {line}")
        else:
            # Either an indented continuation or something else
            result_lines.append(line)
            
    return '\n'.join(result_lines)


def _attempt_fix_colons_in_values(text: str) -> str:
    """Fix values containing colons that might confuse YAML parser.
    
    YAML often gets confused with values like:
    key: Value with: colon
    
    This attempts to fix by identifying values that aren't properly quoted
    and contain colons.
    """
    pattern = re.compile(r'^(\s*\w+\s*:\s*)([^\'\"](.*?:.*?))((?:\s*#.*)?$)', re.MULTILINE)
    try:
        return pattern.sub(r'\g<1>"\g<2>"\g<4>', text)
    except re.error:
        return text


def _attempt_fix_yaml_format(text: str) -> str:
    """Attempt to fix common YAML formatting issues."""
    # This function is not provided in the original file or the code block
    # It's assumed to exist as it's called in clean_response_text
    return text


def _cleanup_markdown(text: str) -> str:
    """Clean up common markdown artifacts."""
    # This function is not provided in the original file or the code block
    # It's assumed to exist as it's called in clean_response_text
    return text


def clean_response_text(raw_text: str, yaml_terminator_key: str = "suggested_message_es:") -> str:  # noqa: D401
    """Run all cleaning passes on the raw OpenAI response text."""
    cleaned = _strip_markdown_fences(raw_text)
    cleaned = _attempt_fix_quotes(cleaned)
    cleaned = _attempt_fix_colons_in_values(cleaned)
    cleaned = _attempt_fix_multiline_values(cleaned)
    
    # --- REVISED: Regex fixes for "summary:" prefix and key formatting ---
    # 1. Fix the specific pattern 'summary:"" ""VALUE"'
    cleaned = re.sub(r'^(summary:""\s+""([^"]+)")$', r'summary: "\2"', cleaned, flags=re.MULTILINE)
    # 2. Try to fix keys that might have incorrect quoting or spacing around the colon
    cleaned = re.sub(r'^"?([a-zA-Z_]+)"?\s*:\s*(.*)$', r'\1: \2', cleaned, flags=re.MULTILINE)
    # 3. Ensure values with internal quotes are properly single-quoted (re-run after other fixes)
    cleaned = _attempt_fix_quotes(cleaned) # Re-apply quote fixing just in case previous steps messed it up
    # --- END REVISED ---

    # Attempt to remove trailing garbage after the last expected YAML key
    # Default to 'suggested_message_es:' if not specified
    last_key = yaml_terminator_key
    last_key_pos = cleaned.rfind(f"\\n{last_key}") # Find last occurrence preceded by newline
    if last_key_pos == -1:
        last_key_pos = cleaned.find(last_key) # Try finding it anywhere if not preceded by newline
        
    if last_key_pos != -1:
        # Find the end of the line containing the last key
        end_of_line_pos = cleaned.find("\\n", last_key_pos + len(last_key))
        if end_of_line_pos != -1:
            # Keep text up to the end of that line
            cleaned = cleaned[:end_of_line_pos]
        # If no newline after last key, assume it's the very end, keep everything up to its line
        # (The existing cleaning logic might handle this implicitly)
        # else: keep 'cleaned' as is after stripping fences/fixing quotes
    
    # Remove any non-YAML compliant characters or sequences
    # Replace tab characters with spaces
    cleaned = cleaned.replace('\\t', '  ')
    
    # Ensure no blank keys (YAML requires non-empty keys)
    cleaned = re.sub(r'^(\\s*):(\\s*.*)$', r'unknown\\1:\\2', cleaned, flags=re.MULTILINE)
    
    # Make sure transfer_context_analysis has a value if missing (moved this check to after other cleaning)
    if "transfer_context_analysis" not in cleaned:
        cleaned = cleaned.rstrip() + '\\ntransfer_context_analysis: "N/A"'

    return cleaned.strip() # Ensure stripping whitespace again


def parse_yaml_dict(text: str) -> Dict[str, Any]:  # noqa: D401
    """Parse YAML and guarantee a dictionary result.

    Raises:
        ValueError: If YAML cannot be parsed or is not a mapping.
    """
    logging.debug(f"Attempting to parse YAML text:\\n{text}")
    try:
        data = yaml.safe_load(text)
        logging.debug(f"Successfully parsed YAML. Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
    except yaml.YAMLError as exc:  # pragma: no cover – let caller handle
        logging.warning(f"Initial YAML parsing failed: {exc}. Trying line-by-line fallback.")
        # Try a more aggressive approach if normal parsing fails
        try:
            # If normal parsing failed, try line by line to create a simplified YAML
            simplified = {}
            for line in text.split('\n'):
                # Look for key: value patterns
                match = re.match(r'^\s*([a-zA-Z0-9_]+)\s*:\s*(.*)$', line)
                if match:
                    key, value = match.groups()
                    simplified[key] = value.strip() or "N/A"  # Use N/A for empty values
            
            # If we found at least some keys, return the simplified dict
            if simplified:
                logging.debug(f"Fallback parsing successful. Keys: {list(simplified.keys())}")
                return simplified
            
            # Otherwise, raise the original error
            raise ValueError(f"YAML parsing error: {exc}") from exc
        except Exception:
            # If all attempts fail, raise the original error
            raise ValueError(f"YAML parsing error: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping, got {type(data).__name__}")
    return data 