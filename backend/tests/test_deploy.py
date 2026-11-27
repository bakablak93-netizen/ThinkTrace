"""Deployment features: /health, built frontend served by FastAPI, request limits."""
from fastapi.testclient import TestClient

from thinktrace.api import create_app
from thinktrace.ratelimit import RateLimiter


def _app(tmp_path, **kw):
    return TestClient(create_app(str(tmp_path / "t.sqlite3"), static_dir=str(tmp_path / "none"), **kw))


def _session(c, nick="nick_1"):
    sid = c.post("/api/sessions", json={"nickname": nick}).json()["session_id"]
    pid = c.post(f"/api/sessions/{sid}/problems", json={"demo": True}).json()["id"]
    return sid, pid


def test_health(tmp_path):
    assert _app(tmp_path).get("/health").json() == {"status": "ok"}


def test_serves_built_frontend_and_keeps_api(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>ThinkTrace</html>", encoding="utf-8")
    c = TestClient(create_app(str(tmp_path / "t.sqlite3"), static_dir=str(dist)))
    assert "ThinkTrace" in c.get("/").text
    assert c.get("/health").json() == {"status": "ok"}
    assert c.post("/api/parse", json={"text": "x=1"}).json()["ok"]


def test_no_frontend_build_means_api_only(tmp_path):
    assert _app(tmp_path).get("/").status_code == 404


def test_per_session_limit(tmp_path):
    c = _app(tmp_path, limiter=RateLimiter(per_session=3, per_day=100))
    sid, pid = _session(c)
    url = f"/api/sessions/{sid}/problems/{pid}"
    assert c.post(f"{url}/hint").status_code == 200
    assert c.post(f"{url}/steps", json={"text": "2x+6=14", "confidence": "low"}).status_code == 200
    assert c.get(f"/api/sessions/{sid}/report").status_code == 200
    r = c.post(f"{url}/hint")
    assert r.status_code == 429 and r.json() == {"error": "rate_limited"}
    # endpoints without LLM are not limited
    assert c.post("/api/parse", json={"text": "x=1"}).status_code == 200
    # another session still works
    sid2, pid2 = _session(c, "nick_2")
    assert c.post(f"/api/sessions/{sid2}/problems/{pid2}/hint").status_code == 200


def test_daily_limit_is_global_and_resets_next_day():
    day = ["2026-12-01"]
    lim = RateLimiter(per_session=100, per_day=2, today=lambda: day[0])
    assert lim.hit("a") and lim.hit("b")
    assert not lim.hit("c")
    day[0] = "2026-12-02"
    assert lim.hit("c")


def test_limits_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_SESSION", "1")
    c = _app(tmp_path)
    sid, pid = _session(c)
    assert c.post(f"/api/sessions/{sid}/problems/{pid}/hint").status_code == 200
    assert c.post(f"/api/sessions/{sid}/problems/{pid}/hint").status_code == 429
