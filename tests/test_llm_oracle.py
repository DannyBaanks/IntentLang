"""Provider-neutral LLM oracle contract; tests never perform network calls."""
from __future__ import annotations

import json

from intentlang.llm_oracle import (
    CredentialStore,
    OracleConfig,
    OracleVerdict,
    infer_provider,
    parse_verdict,
)


def test_provider_inference_uses_key_shape_but_allows_explicit_choice():
    assert infer_provider("AIza-test") == "gemini"
    assert infer_provider("sk-test") == "openai-compatible"
    assert infer_provider("anything", explicit="gemini") == "gemini"


def test_verdict_parser_is_strict_and_minimal():
    verdict = parse_verdict(json.dumps({
        "verdict": "PASS", "changed_features": [], "reason": None, "confidence": 0.9,
    }))
    assert verdict == OracleVerdict("PASS", (), None, 0.9)


def test_credential_store_is_local_and_round_trips(tmp_path):
    path = tmp_path / "credentials.json"
    store = CredentialStore(path)
    store.save(OracleConfig(provider="gemini", api_key="AIza-local", model="gemini-test"))
    loaded = store.load()
    assert loaded.provider == "gemini"
    assert loaded.api_key == "AIza-local"
    assert loaded.model == "gemini-test"
