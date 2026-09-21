from intentlang.sanitize import sanitize


def test_sanitize_redacts_provider_keys_and_bearer_headers():
    raw = "Authorization: Bearer nvapi-abcdefghijklmnop1234 sk-abcdefghijklmnop1234 AIzaabcdefghijklmnopqrstuv"
    clean = sanitize(raw)
    assert "nvapi-" not in clean
    assert "sk-" not in clean
    assert "AIza" not in clean
    assert "Bearer [REDACTED]" in clean


def test_sanitize_keeps_normal_text():
    assert sanitize("Alice saw the rabbit") == "Alice saw the rabbit"
