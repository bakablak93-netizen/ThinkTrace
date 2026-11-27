"""LLM layer: wording of hints only. The LLM never decides correctness or the bug id.

Architecture
  LLMClient            interface: write_hint(HintRequest) -> HintResult,
                       explain_feedback(FeedbackRequest) -> FeedbackResult
  TemplateClient       offline: returns the deterministic template text
  ProviderClient       shared logic for real providers: prompt, JSON parsing, validation,
                       guard, fallback to the template on ANY problem
  OpenAIClient         ProviderClient for OpenAI (chat completions, JSON schema output)
  PROVIDERS            name -> class; a new provider = a new ProviderClient subclass here
  get_client()         picks a client from LLM_PROVIDER / LLM_API_KEY / LLM_MODEL

What is sent to the model: problem text, the student's lines, hint level, language, error id
and its catalog description, the template text and (for feedback) the student's own
explanation. Never nicknames, session ids or any other identifiers (the request
dataclasses have no field for them).

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
EXPLAIN_PROMPT = (Path(__file__).parent / "prompts" / "explain.md").read_text(encoding="utf-8")
MAX_FEEDBACK_CHARS = 300

HINT_SCHEMA = {
    "type": "object",
    "properties": {"hint": {"type": "string"}},
    "required": ["hint"],
    "additionalProperties": False,
}
FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {"correct": {"type": "string"}, "attention": {"type": "string"}},
    "required": ["correct", "attention"],
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


@dataclass(frozen=True)
class FeedbackRequest:
    """'Explain in your own words' after a corrected error."""
    language: str
    problem: str
    previous_step: str
    wrong_step: str
    corrected_step: str
    student_explanation: str
    template_rule: str                 # catalog rule, used for the fallback
    error: dict | None = None
    root: object = field(default=None, compare=False)  # for the guard only, never sent

    def payload(self) -> dict:
        d = asdict(self)
        d.pop("root")
        d.pop("template_rule")
        if d["error"] is None:
            d.pop("error")
        return d


@dataclass(frozen=True)
class FeedbackResult:
    source: Literal["llm", "template"]
    correct: str = ""                  # llm: what is right in the explanation
    attention: str = ""                # llm: what to pay attention to
    rule: str = ""                     # template: catalog rule to compare with
    fallback_reason: str | None = None


class LLMClient(ABC):
    @abstractmethod
    def write_hint(self, req: HintRequest) -> HintResult: ...

    @abstractmethod
    def explain_feedback(self, req: FeedbackRequest) -> FeedbackResult: ...


class TemplateClient(LLMClient):
    def __init__(self, reason: str = "no_provider"):
        self.reason = reason

    def write_hint(self, req: HintRequest) -> HintResult:
        return HintResult(req.template_hint, "template", self.reason)

    def explain_feedback(self, req: FeedbackRequest) -> FeedbackResult:
        return FeedbackResult("template", rule=req.template_rule, fallback_reason=self.reason)


class LLMCallError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ProviderClient(LLMClient):
    """Real provider: subclasses implement _complete(system, user, schema_name, schema)
    and return the raw JSON text of the model's answer."""

    name = "provider"

    @abstractmethod
    def _complete(self, system: str, user: str, schema_name: str, schema: dict) -> str: ...

    def _call_json(self, system: str, payload: dict, schema_name: str, schema: dict,
                   max_chars: int, root, context: list[str]) -> tuple[dict | None, str | None]:
        """One model call -> (validated dict of strings, None) or (None, fallback reason).
        Checks: JSON, exact keys from the schema, string values, length, guard."""
        try:
            raw = self._complete(system, json.dumps(payload, ensure_ascii=False), schema_name, schema)
        except LLMCallError as e:
            return None, e.reason
        except Exception:  # never let a provider problem break the lesson
            log.exception("LLM call failed")
            return None, "error"
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return None, "invalid_json"
        keys = set(schema["required"])
        if not isinstance(data, dict) or set(data) != keys or not all(isinstance(data[k], str) for k in keys):
            return None, "invalid_schema"
        data = {k: v.strip() for k, v in data.items()}
        if any(not v or len(v) > max_chars for v in data.values()):
            return None, "invalid_length"
        if any(leaks_answer(v, root, context) for v in data.values()):
            return None, "guard"
        return data, None

    def write_hint(self, req: HintRequest) -> HintResult:
        context = [req.problem, req.previous_step, req.student_step, *req.accepted_steps]
        data, reason = self._call_json(SYSTEM_PROMPT, req.payload(), "hint", HINT_SCHEMA,
                                       MAX_HINT_CHARS, req.root, context)
        if data is None:
            log.info("LLM fallback to template: %s", reason)
            return HintResult(req.template_hint, "template", reason)
        return HintResult(data["hint"], "llm")

    def explain_feedback(self, req: FeedbackRequest) -> FeedbackResult:
        # the student's own text is NOT part of the guard context: echoing the answer from
        # it would still reveal it to anyone reading the feedback
        context = [req.problem, req.previous_step, req.wrong_step, req.corrected_step]
        data, reason = self._call_json(EXPLAIN_PROMPT, req.payload(), "feedback", FEEDBACK_SCHEMA,
                                       MAX_FEEDBACK_CHARS, req.root, context)
        if data is None:
            log.info("LLM fallback to template (feedback): %s", reason)
            return FeedbackResult("template", rule=req.template_rule, fallback_reason=reason)
        return FeedbackResult("llm", correct=data["correct"], attention=data["attention"])


class OpenAIClient(ProviderClient):
    name = "openai"

    def __init__(self, api_key: str, model: str, sdk_client=None):
        self.model = model
        if sdk_client is None:
            from openai import OpenAI
            sdk_client = OpenAI(api_key=api_key, timeout=TIMEOUT_SEC, max_retries=0)
        self._sdk = sdk_client

    def _complete(self, system: str, user: str, schema_name: str, schema: dict) -> str:
        import openai

        try:
            resp = self._sdk.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
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
