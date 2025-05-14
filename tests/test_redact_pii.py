import re

import pytest

from lead_recovery.db_clients import _redact_pii


@pytest.mark.parametrize(
    "sql, expected_pattern",
    [
        # Phone number with 10+ digits should be replaced
        ("SELECT * FROM users WHERE phone='5512345678'", r"\[PHONE_REDACTED\]"),
        ("INSERT INTO t VALUES (12345678901)", r"\[PHONE_REDACTED\]"),
        # Email address should be replaced
        ("SELECT * FROM users WHERE email='foo.bar+baz@example.com'", r"\[EMAIL_REDACTED\]"),
        # Mixed case email
        ("UPDATE t SET owner='Foo@Example.Com'", r"\[EMAIL_REDACTED\]"),
    ],
)
def test_redact_pii_replaces(sql: str, expected_pattern: str):
    """_redact_pii should substitute sensitive tokens with placeholders."""
    redacted = _redact_pii(sql)
    assert re.search(expected_pattern, redacted), f"Pattern {expected_pattern} not found in {redacted}"


def test_redact_pii_preserves_non_pii():
    """Non-PII parts of the SQL should remain unchanged."""
    original_sql = "SELECT id, created_at FROM table WHERE status = 'ACTIVE'"
    redacted = _redact_pii(original_sql)
    assert original_sql == redacted  # no changes expected 