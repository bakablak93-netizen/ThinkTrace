"""LLM layer: wording of hints only. The LLM never decides correctness or the bug id.

Architecture
  LLMClient            interface: write_hint(HintRequest) -> HintResult
  TemplateClient       offline: returns the deterministic template text
  ProviderClient       shared logic for real providers: prompt, JSON parsing, validation,
                       guard, fallback to the template on ANY problem
  OpenAIClient         ProviderClient for OpenAI (chat completions, JSON schema output)
  PROVIDERS            name -> class; a new provider = a new ProviderClient subclass here
  get_client()         picks a client from LLM_PROVIDER / LLM_API_KEY / LLM_MODEL

What is sent to the model: problem text, the student's lines, hint level, language, error id
and its catalog description, and the template hint. Never nicknames, session ids or any
other personal data (HintRequest has no field for them).

Fallback to the template (source="template") when: no provider configured, timeout or any
API error, invalid JSON, wrong schema, text too long or empty, or the guard detects that the
text reveals the answer. The reason is returned for the event log.
"""
from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from .hints import leaks_answer

log = logging.getLogger(__name__)

TIMEOUT_SEC = 5.0
MAX_OUTPUT_TOKENS = 300
MAX_HINT_CHARS = 400
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")

HINT_SCHEMA = {
    "type": "object",
    "properties": {"hint": {"type": "string"}},
    "required": ["hint"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class HintRequest:
    task: Literal["hint", "unknown_error"]
    language: str
    level: int
    problem: str
    accepted_steps: list[str]
    previous_step: str
    student_step: str
    template_hint: str
    error: dict | None = None          # {"id", "name", "description"} from the catalog
    root: object = field(default=None, compare=False)  # for the guard only, never sent

    def payload(self) -> dict:
        d = asdict(self)
        d.pop("root")
        if d["error"] is None:
            d.pop("error")
        return d


@dataclass(frozen=True)
class HintResult:
    text: str
    source: Literal["llm", "template"]
    fallback_reason: str | None = None   # why the template was used (None if llm)


class LLMClient(ABC):
    @abstractmethod
    def write_hint(self, req: HintRequest) -> HintResult: ...


class TemplateClient(LLMClient):
    def __init__(self, reason: str = "no_provider"):
        self.reason = reason

    def write_hint(self, req: HintRequest) -> HintResult:
        return HintResult(req.template_hint, "template", self.reason)


class LLMCallError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ProviderClient(LLMClient):
    """Real provider: subclasses implement _complete(system, user) -> raw JSON text."""

    name = "provider"

    @abstractmethod
    def _complete(self, system: str, user: str) -> str: ...

    def write_hint(self, req: HintRequest) -> HintResult:
        def fallback(reason: str) -> HintResult:
            log.info("LLM fallback to template: %s", reason)
            return HintResult(req.template_hint, "template", reason)

        try:
            raw = self._complete(SYSTEM_PROMPT, json.dumps(req.payload(), ensure_ascii=False))
        except LLMCallError as e:
            return fallback(e.reason)
        except Exception:  # never let a provider problem break the lesson
            log.exception("LLM call failed")
            return fallback("error")
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return fallback("invalid_json")
        if not isinstance(data, dict) or set(data) != {"hint"} or not isinstance(data["hint"], str):
            return fallback("invalid_schema")
        text = data["hint"].strip()
        if not text or len(text) > MAX_HINT_CHARS:
            return fallback("invalid_length")
        context = [req.problem, req.previous_step, req.student_step, *req.accepted_steps]
        if leaks_answer(text, req.root, context):
            return fallback("guard")
        return HintResult(text, "llm")


class OpenAIClient(ProviderClient):
    name = "openai"

    def __init__(self, api_key: str, model: str, sdk_client=None):
        self.model = model
        if sdk_client is None:
            from openai import OpenAI
            sdk_client = OpenAI(api_key=api_key, timeout=TIMEOUT_SEC, max_retries=0)
        self._sdk = sdk_client

    def _complete(self, system: str, user: str) -> str:
        import openai

        try:
            resp = self._sdk.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": "hint", "strict": True, "schema": HINT_SCHEMA}},
                max_completion_tokens=MAX_OUTPUT_TOKENS,
                timeout=TIMEOUT_SEC,
            )
        except openai.APITimeoutError as e:
            raise LLMCallError("timeout") from e
        except openai.APIError as e:
            raise LLMCallError("api_error") from e
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            raise LLMCallError("invalid_length")
        return choice.message.content or ""


PROVIDERS: dict[str, type[ProviderClient]] = {"openai": OpenAIClient}


def get_client() -> LLMClient:
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    if not provider:
        return TemplateClient("no_provider")
    if provider not in PROVIDERS:
        log.warning("Unknown LLM_PROVIDER %r, using templates", provider)
        return TemplateClient("unknown_provider")
    if not key or not model:
        log.warning("LLM_PROVIDER=%s but LLM_API_KEY or LLM_MODEL is empty, using templates", provider)
        return TemplateClient("no_key")
    return PROVIDERS[provider](api_key=key, model=model)
