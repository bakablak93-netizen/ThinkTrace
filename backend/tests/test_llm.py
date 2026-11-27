"""LLM layer with mocked clients only: no real API calls."""
import json

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from thinktrace.api import create_app
from thinktrace.llm import (
    HintRequest, OpenAIClient, ProviderClient, TemplateClient, get_client,
)
from thinktrace.ratelimit import RateLimiter

TEMPLATE = "Шаблонная подсказка"


class FakeProvider(ProviderClient):
    """Returns a fixed raw response (or raises) and records what was sent."""
    name = "fake"

    def __init__(self, raw=None, exc=None):
        self.raw, self.exc, self.calls = raw, exc, []

    def _complete(self, system, user, schema_name=None, schema=None):
        self.calls.append({"system": system, "user": json.loads(user)})
        if self.exc:
            raise self.exc
        return self.raw


def req(**kw):
    import sympy
    base = dict(task="hint", language="ru", level=1, problem="2(x + 3) = 14", accepted_steps=[],
                previous_step="2(x + 3) = 14", student_step="2x + 3 = 14", template_hint=TEMPLATE,
                error={"id": "DIST_FIRST_ONLY", "name": "n", "description": "d"}, root=sympy.Integer(4))
    base.update(kw)
    return HintRequest(**base)


# ---------- validation, guard, fallback ----------

def test_valid_json_is_used():
    r = FakeProvider('{"hint": "На что ты умножил число перед скобкой?"}').write_hint(req())
    assert r.source == "llm" and r.fallback_reason is None and r.text.startswith("На что")


@pytest.mark.parametrize("raw, reason", [
    ("это не JSON", "invalid_json"),
    ("", "invalid_json"),
    ('["hint"]', "invalid_schema"),
    ('{"text": "привет"}', "invalid_schema"),
    ('{"hint": "a", "answer": 4}', "invalid_schema"),
    ('{"hint": 5}', "invalid_schema"),
    ('{"hint": "   "}', "invalid_length"),
    (json.dumps({"hint": "a" * 401}), "invalid_length"),
])
def test_invalid_responses_fall_back_to_template(raw, reason):
    r = FakeProvider(raw).write_hint(req())
    assert (r.text, r.source, r.fallback_reason) == (TEMPLATE, "template", reason)


@pytest.mark.parametrize("spoiler", [
    "Получится x = 4.", "Ответ: х=4", "Проверь: 4 = x", "Значение корня 4, проверь вычисления.",
    "x = 8/2", "x равен 4,0",
])
def test_guard_replaces_spoilers(spoiler):
    r = FakeProvider(json.dumps({"hint": spoiler})).write_hint(req())
    assert (r.text, r.source, r.fallback_reason) == (TEMPLATE, "template", "guard")


def test_guard_allows_numbers_from_the_problem():
    r = FakeProvider('{"hint": "Ты умножил 2 на 3?"}').write_hint(req())
    assert r.source == "llm"


def test_provider_exception_falls_back():
    r = FakeProvider(exc=RuntimeError("boom")).write_hint(req())
    assert (r.source, r.fallback_reason) == ("template", "error")


# ---------- OpenAI client with a fake SDK object ----------

class FakeSDK:
    def __init__(self, content=None, exc=None, finish="stop"):
        self.kwargs, self._content, self._exc, self._finish = None, content, exc, finish
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self._exc:
            raise self._exc
        msg = type("M", (), {"content": self._content})
        choice = type("C", (), {"message": msg, "finish_reason": self._finish})
        return type("R", (), {"choices": [choice]})


def test_openai_request_parameters():
    sdk = FakeSDK('{"hint": "Посмотри на скобки."}')
    r = OpenAIClient("k", "some-model", sdk_client=sdk).write_hint(req())
    assert r.source == "llm"
    kw = sdk.kwargs
    assert kw["model"] == "some-model" and kw["timeout"] == 5.0 and kw["max_completion_tokens"] == 300
    assert kw["response_format"]["type"] == "json_schema"
    assert kw["messages"][0]["role"] == "system" and "NEVER give the final answer" in kw["messages"][0]["content"]


def test_openai_timeout_falls_back():
    exc = openai.APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))
    r = OpenAIClient("k", "m", sdk_client=FakeSDK(exc=exc)).write_hint(req())
    assert (r.text, r.source, r.fallback_reason) == (TEMPLATE, "template", "timeout")


def test_openai_truncated_answer_falls_back():
    r = OpenAIClient("k", "m", sdk_client=FakeSDK('{"hint": "На что', finish="length")).write_hint(req())
    assert (r.source, r.fallback_reason) == ("template", "invalid_length")


# ---------- client selection from environment ----------

def test_no_provider_or_no_key_means_templates(monkeypatch):
    assert isinstance(get_client(), TemplateClient)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "m")
    c = get_client()
    assert isinstance(c, TemplateClient) and c.reason == "no_key"
    monkeypatch.setenv("LLM_PROVIDER", "unknown")
    monkeypatch.setenv("LLM_API_KEY", "k")
    assert get_client().reason == "unknown_provider"


def test_full_env_selects_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("LLM_MODEL", "m")
    assert isinstance(get_client(), OpenAIClient)  # constructing it makes no network call


# ---------- through the API ----------

def _client(tmp_path, llm, limiter=None):
    return TestClient(create_app(str(tmp_path / "t.sqlite3"), static_dir=str(tmp_path / "none"),
                                 llm=llm, limiter=limiter))


def _start(c, nick="secret_nick"):
    sid = c.post("/api/sessions", json={"nickname": nick}).json()["session_id"]
    pid = c.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()["id"]
    return sid, pid


def _step(c, sid, pid, text):
    return c.post(f"/api/sessions/{sid}/problems/{pid}/steps", json={"text": text, "confidence": "high"}).json()


def test_api_llm_hint_source_and_no_personal_data(tmp_path):
    fake = FakeProvider('{"hint": "Проверь, на что умножено каждое слагаемое в скобках."}')
    c = _client(tmp_path, fake)
    sid, pid = _start(c)
    r = _step(c, sid, pid, "2x+3=14")
    assert r["hint"]["source"] == "llm" and r["hint"]["text"].startswith("Проверь")
    h = c.post(f"/api/sessions/{sid}/problems/{pid}/hint?lang=kk").json()
    assert h["source"] == "llm" and h["level"] == 2

    sent = fake.calls[0]["user"]
    assert set(sent) == {"task", "language", "level", "problem", "accepted_steps", "previous_step",
                         "student_step", "template_hint", "error"}
    assert sent["error"]["id"] == "DIST_FIRST_ONLY" and sent["problem"] == "2(x + 3) = 14"
    assert fake.calls[1]["user"]["language"] == "kk"
    everything = json.dumps([call["user"] for call in fake.calls], ensure_ascii=False)
    assert "secret_nick" not in everything and sid not in everything and pid not in everything

    rep = c.get(f"/api/sessions/{sid}/report").json()
    assert [h["source"] for h in rep["problems"][0]["hints"]] == ["llm", "llm"]


def test_api_unknown_error_goes_to_llm_as_unknown_task(tmp_path):
    fake = FakeProvider('{"hint": "Возможно, ошибка в вычислении правой части. Проверь его."}')
    c = _client(tmp_path, fake)
    sid, pid = _start(c)
    _step(c, sid, pid, "2x+6=14")
    r = _step(c, sid, pid, "2x=7")            # arithmetic slip -> UNKNOWN
    assert r["diagnosis"]["unknown"] and r["hint"]["source"] == "llm"
    assert fake.calls[-1]["user"]["task"] == "unknown_error" and "error" not in fake.calls[-1]["user"]


def test_api_spoiler_is_replaced_and_logged_as_template(tmp_path):
    c = _client(tmp_path, FakeProvider('{"hint": "Здесь x = 4."}'))
    sid, pid = _start(c)
    r = _step(c, sid, pid, "2x+3=14")
    assert r["hint"]["source"] == "template" and "4" not in r["hint"]["text"]
    rep = c.get(f"/api/sessions/{sid}/report").json()
    assert rep["problems"][0]["hints"][0]["source"] == "template"


def test_templates_only_where_llm_does_not_apply(tmp_path):
    fake = FakeProvider('{"hint": "текст"}')
    c = _client(tmp_path, fake)
    sid, pid = _start(c)
    stuck = c.post(f"/api/sessions/{sid}/problems/{pid}/hint").json()       # no error yet
    assert stuck["source"] == "template" and not fake.calls
    # level 4 is a template: after 3 wrong attempts and levels 1..3 shown
    for _ in range(3):
        _step(c, sid, pid, "2x+3=14")
    n = len(fake.calls)
    h = c.post(f"/api/sessions/{sid}/problems/{pid}/hint").json()
    assert h["level"] == 4 and h["source"] == "template" and len(fake.calls) == n


def test_ambiguous_diagnosis_is_not_sent_to_llm():
    from thinktrace.diagnose import diagnose
    from thinktrace.hints import error_hint
    from thinktrace.parser import parse_equation as p
    from thinktrace.tutor import State, _phrase
    eq = p("2x+2=4")
    d = diagnose(eq, p("x=3"))
    assert d.is_ambiguous
    fake = FakeProvider('{"hint": "текст"}')
    r = _phrase(fake, State(problem=None, original=eq, current=eq), d, error_hint(d, 1, eq, "x = 3", "ru"),
                "x = 3", "ru")
    assert r.source == "template" and not fake.calls


def test_rate_limit_blocks_llm_calls(tmp_path):
    fake = FakeProvider('{"hint": "Посмотри на скобки."}')
    c = _client(tmp_path, fake, limiter=RateLimiter(per_session=2, per_day=100))
    sid, pid = _start(c)
    _step(c, sid, pid, "2x+3=14")                                    # 1: LLM call
    c.post(f"/api/sessions/{sid}/problems/{pid}/hint")               # 2: LLM call
    assert len(fake.calls) == 2
    r = c.post(f"/api/sessions/{sid}/problems/{pid}/hint")           # 3: blocked before the LLM
    assert r.status_code == 429 and len(fake.calls) == 2
    r = c.post(f"/api/sessions/{sid}/problems/{pid}/steps", json={"text": "2x+3=14", "confidence": "low"})
    assert r.status_code == 429 and len(fake.calls) == 2


def test_without_key_everything_works_on_templates(tmp_path):
    c = TestClient(create_app(str(tmp_path / "t.sqlite3"), static_dir=str(tmp_path / "none")))
    sid, pid = _start(c)
    r = _step(c, sid, pid, "2x+3=14")
    assert r["hint"]["source"] == "template" and r["hint"]["text"]
