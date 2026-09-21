"""Provider-neutral LLM oracle for semantic translation evaluation.

The oracle is advisory evidence: the local Meaning IR comparator remains the
authority.  Network calls are explicit and no provider SDK is required.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .meaning_ir import Meaning
from .sanitize import sanitize

Provider = Literal["gemini", "openai-compatible"]
Verdict = Literal["PASS", "FAIL", "UNCERTAIN"]

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_CREDENTIAL_PATH = Path.home() / ".config" / "intentlang" / "oracle_credentials.json"


@dataclass(frozen=True, slots=True)
class OracleConfig:
    provider: Provider | str
    api_key: str
    model: str
    base_url: str | None = None
    google_search: bool = False
    timeout_seconds: float = 45.0

    def endpoint(self) -> str:
        if self.provider == "gemini":
            return "https://generativelanguage.googleapis.com/v1beta/models/" f"{self.model}:generateContent"
        return (self.base_url or DEFAULT_OPENAI_BASE_URL).rstrip("/") + "/chat/completions"


@dataclass(frozen=True, slots=True)
class OracleVerdict:
    verdict: Verdict
    changed_features: tuple[str, ...]
    reason: str | None
    confidence: float


def infer_provider(api_key: str, explicit: str | None = None) -> Provider:
    """Infer common providers; explicit selection wins for compatible vendors."""
    if explicit:
        if explicit not in {"gemini", "openai-compatible"}:
            raise ValueError(f"unsupported oracle provider: {explicit}")
        return explicit  # type: ignore[return-value]
    if api_key.startswith("AIza"):
        return "gemini"
    return "openai-compatible"


class CredentialStore:
    """Explicit file store for tests/portable environments only."""

    def __init__(self, path: Path = DEFAULT_CREDENTIAL_PATH) -> None:
        self.path = path

    def save(self, config: OracleConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.parent.chmod(0o700)
        payload = {
            "provider": config.provider,
            "api_key": config.api_key,
            "model": config.model,
            "base_url": config.base_url,
            "google_search": config.google_search,
            "timeout_seconds": config.timeout_seconds,
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.path.chmod(0o600)

    def load(self) -> OracleConfig:
        if not self.path.exists():
            raise FileNotFoundError(f"oracle credentials not configured: {self.path}")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return OracleConfig(**data)


class KeyringCredentialStore:
    """Use the operating system credential store; the key never enters the repo."""

    def __init__(self, service: str = "intentlang", account: str = "oracle") -> None:
        self.service = service
        self.account = account

    @staticmethod
    def _backend():
        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError(
                "OS keyring support is unavailable; install the security extra or use env vars"
            ) from exc
        return keyring

    def save(self, config: OracleConfig) -> None:
        payload = json.dumps({
            "provider": config.provider, "api_key": config.api_key, "model": config.model,
            "base_url": config.base_url, "google_search": config.google_search,
            "timeout_seconds": config.timeout_seconds,
        }, ensure_ascii=False)
        self._backend().set_password(self.service, self.account, payload)

    def load(self) -> OracleConfig:
        payload = self._backend().get_password(self.service, self.account)
        if not payload:
            raise FileNotFoundError(f"oracle credentials not configured in OS keyring: {self.service}/{self.account}")
        return OracleConfig(**json.loads(payload))

    def delete(self) -> None:
        self._backend().delete_password(self.service, self.account)

    def exists(self) -> bool:
        try:
            return bool(self._backend().get_password(self.service, self.account))
        except Exception:
            return False


def config_from_environment() -> OracleConfig:
    """Build config from env without requiring users to enter endpoints."""
    api_key = os.environ.get("INTENTLANG_ORACLE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("set INTENTLANG_ORACLE_API_KEY or configure CredentialStore")
    explicit = os.environ.get("INTENTLANG_ORACLE_PROVIDER")
    provider = infer_provider(api_key, explicit)
    default_model = DEFAULT_GEMINI_MODEL if provider == "gemini" else DEFAULT_OPENAI_MODEL
    return OracleConfig(
        provider=provider,
        api_key=api_key,
        model=os.environ.get("INTENTLANG_ORACLE_MODEL", default_model),
        base_url=os.environ.get("INTENTLANG_ORACLE_BASE_URL"),
        google_search=os.environ.get("INTENTLANG_ORACLE_GOOGLE_SEARCH", "0") == "1",
    )


def parse_verdict(raw: str) -> OracleVerdict:
    """Parse only the tiny JSON contract; reject prose and unknown fields."""
    data = json.loads(raw)
    required = {"verdict", "changed_features", "reason", "confidence"}
    if set(data) != required:
        raise ValueError("oracle response must contain exactly the verdict schema")
    if data["verdict"] not in {"PASS", "FAIL", "UNCERTAIN"}:
        raise ValueError("invalid oracle verdict")
    if not isinstance(data["changed_features"], list) or not all(isinstance(x, str) for x in data["changed_features"]):
        raise ValueError("changed_features must be a string list")
    if data["reason"] is not None and not isinstance(data["reason"], str):
        raise ValueError("reason must be null or string")
    confidence = float(data["confidence"])
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    return OracleVerdict(data["verdict"], tuple(data["changed_features"]), data["reason"], confidence)


def _prompt(expected: Meaning, source_text: str, candidate: str, target_language: str) -> str:
    return (
        "You are a semantic translation evaluator. Do not translate, rewrite, or explain. "
        "Return only the JSON object requested. Mark PASS only when predicate, roles, "
        "entities, polarity, tense, aspect, modality, and quantifiers are preserved.\n\n"
        f"Target language: {target_language}\n"
        f"Source: {sanitize(source_text)}\n"
        f"Expected Meaning IR: {sanitize(json.dumps(expected.to_dict(), ensure_ascii=False, sort_keys=True))}\n"
        f"Candidate translation: {sanitize(candidate)}\n\n"
        'JSON schema: {"verdict":"PASS|FAIL|UNCERTAIN",'
        '"changed_features":["string"],"reason":"string or null","confidence":0.0}'
    )


class LLMOracle:
    """Call Gemini or an OpenAI-compatible chat endpoint as an external judge."""

    def __init__(self, config: OracleConfig) -> None:
        self.config = config

    def verify(self, expected: Meaning, source_text: str, candidate: str, target_language: str) -> OracleVerdict:
        prompt = _prompt(expected, source_text, candidate, target_language)
        payload, headers = self._request_payload(prompt)
        request = urllib.request.Request(
            self.config.endpoint(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"oracle provider request failed: {sanitize(str(exc))}") from exc
        return parse_verdict(self._extract_text(body))

    def _request_payload(self, prompt: str) -> tuple[dict[str, Any], dict[str, str]]:
        if self.config.provider == "gemini":
            payload: dict[str, Any] = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"},
            }
            if self.config.google_search:
                payload["tools"] = [{"google_search": {}}]
            return payload, {"Content-Type": "application/json", "x-goog-api-key": self.config.api_key}
        return {
            "model": self.config.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Return only the requested JSON object."},
                {"role": "user", "content": prompt},
            ],
        }, {"Content-Type": "application/json", "Authorization": f"Bearer {self.config.api_key}"}

    @staticmethod
    def _extract_text(body: dict[str, Any]) -> str:
        if "candidates" in body:
            return body["candidates"][0]["content"]["parts"][0]["text"]
        return body["choices"][0]["message"]["content"]


__all__ = [
    "CredentialStore", "KeyringCredentialStore", "LLMOracle", "OracleConfig", "OracleVerdict",
    "config_from_environment", "infer_provider", "parse_verdict",
]
