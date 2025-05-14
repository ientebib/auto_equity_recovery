import pytest

from lead_recovery.utils import clean_email

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("FooBar@example.com", "foobar@example.com"),
        ("Foo+Alias@Example.com", "foo@example.com"),
        ("", ""),
        (None, ""),
    ],
)
def test_clean_email(raw, expected):
    """clean_email should lower-case and strip plus-aliases."""
    assert clean_email(raw) == expected 