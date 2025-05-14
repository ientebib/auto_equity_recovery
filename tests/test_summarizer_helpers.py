import pytest

from lead_recovery.summarizer_helpers import clean_response_text, parse_yaml_dict


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("```yaml\nkey: value\n```", "key: value"),
        ("```\nkey: value\n```", "key: value"),
        ("key: value", "key: value"),
    ],
)
def test_clean_response_text_strips_fences(raw: str, expected: str):
    assert clean_response_text(raw) == expected


def test_clean_response_text_fix_quotes():
    raw = 'reason: "User said \\"hello\\" yesterday"'
    cleaned = clean_response_text(raw)
    # Top-level quotes should be switched to single quotes
    assert cleaned.startswith("reason: '")
    assert cleaned.endswith("yesterday'")


def test_parse_yaml_dict_success():
    text = "a: 1\nb: two"
    data = parse_yaml_dict(text)
    assert data == {"a": 1, "b": "two"}


def test_parse_yaml_dict_failure():
    with pytest.raises(ValueError):
        parse_yaml_dict("- just a list\n- 2\n") 