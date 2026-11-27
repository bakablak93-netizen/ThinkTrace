"""FastAPI app.

Stage 1 endpoints (all under /api):
  POST /sessions                                  start session {nickname, lang}
  POST /sessions/{sid}/problems                   new problem {demo: bool}
  GET  /sessions/{sid}/problems/{pid}             problem with steps
  POST /sessions/{sid}/problems/{pid}/steps       submit step {text, confidence}
  POST /sessions/{sid}/problems/{pid}/hint        request hint
  POST /sessions/{sid}/transfer                   transfer problem (after a solved one)
  POST /sessions/{sid}/disagree                   "I disagree with the assessment"
  POST /sessions/{sid}/finish                     finish session
  GET  /sessions/{sid}/report                     report
  POST /parse                                     live preview {text} -> latex / error
  GET  /health                                    liveness check (outside /api)
Stage 2: delete my data, modes independent / exam, teacher view.

If the built frontend exists (frontend/dist, or STATIC_DIR), it is served at "/" by the
same app: one service, one URL. Local development with Vite keeps working unchanged.
Endpoints that will call the LLM (steps, hint, report) are rate limited (ratelimit.py).

The session id (random uuid4) acts as the access token for the session's data.
Run: uvicorn thinktrace.api:create_app --factory --port 8000
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterator, Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db, tutor
from .expr import eq_latex, eq_text
from .i18n import tr
from .parser import ParseError, parse_equation
from .ratelimit import RateLimiter
from .report import build_report

Lang = Literal["ru", "kk", "en"]


class StartIn(BaseModel):
    nickname: str = Field(min_length=2, max_length=24)
    lang: Lang = "ru"
    mode: Literal["smart_tutor"] = "smart_tutor"


class ProblemIn(BaseModel):
    demo: bool = False


class StepIn(BaseModel):
    text: str = Field(max_length=200)
    confidence: Literal["low", "medium", "high"]


class ParseIn(BaseModel):
    text: str = Field(max_length=200)


class DisagreeIn(BaseModel):
    event_id: int
    comment: str = Field(default="", max_length=500)


DEFAULT_STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(db_path: str | None = None, static_dir: str | None = None,
               limiter: RateLimiter | None = None) -> FastAPI:
    load_dotenv()
    path = db_path or os.getenv("DATABASE_PATH", "thinktrace.sqlite3")
    db.init(path)
    limiter = limiter or RateLimiter(
        per_session=int(os.getenv("RATE_LIMIT_PER_SESSION", "300")),
        per_day=int(os.getenv("RATE_LIMIT_PER_DAY", "5000")),
    )

    app = FastAPI(title="ThinkTrace AI")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_conn() -> Iterator[sqlite3.Connection]:
        conn = db.connect(path)
        try:
            yield conn
        finally:
            conn.close()

    def limited(sid: str) -> None:
        if not limiter.hit(sid):
            raise tutor.TutorError("rate_limited", 429)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.exception_handler(tutor.TutorError)
    def _tutor_error(_: Request, exc: tutor.TutorError):
        return JSONResponse({"error": exc.code}, status_code=exc.status)

    @app.post("/api/parse")
    def parse(body: ParseIn, lang: Lang = "ru"):
        try:
            eq = parse_equation(body.text)
        except ParseError as err:
            return {"ok": False, "code": err.code, "message": tr(f"parse.{err.code}", lang, **err.params)}
        return {"ok": True, "text": eq_text(eq), "latex": eq_latex(eq)}

    @app.post("/api/sessions")
    def start(body: StartIn, conn=Depends(get_conn)):
        return tutor.create_session(conn, body.nickname, body.lang, body.mode)

    @app.post("/api/sessions/{sid}/problems")
    def new_problem(sid: str, body: ProblemIn, conn=Depends(get_conn)):
        return tutor.new_problem(conn, sid, demo=body.demo)

    @app.get("/api/sessions/{sid}/problems/{pid}")
    def get_problem(sid: str, pid: str, conn=Depends(get_conn)):
        tutor.get_session(conn, sid)
        return tutor.problem_view(conn, sid, pid)

    @app.post("/api/sessions/{sid}/problems/{pid}/steps")
    def submit_step(sid: str, pid: str, body: StepIn, lang: Lang = "ru", conn=Depends(get_conn)):
        limited(sid)
        return tutor.submit_step(conn, sid, pid, body.text, body.confidence, lang)

    @app.post("/api/sessions/{sid}/problems/{pid}/hint")
    def hint(sid: str, pid: str, lang: Lang = "ru", conn=Depends(get_conn)):
        limited(sid)
        return tutor.request_hint(conn, sid, pid, lang)

    @app.post("/api/sessions/{sid}/transfer")
    def transfer(sid: str, conn=Depends(get_conn)):
        return tutor.new_transfer(conn, sid)

    @app.post("/api/sessions/{sid}/disagree")
    def disagree(sid: str, body: DisagreeIn, conn=Depends(get_conn)):
        tutor.disagree(conn, sid, body.event_id, body.comment)
        return {"ok": True}

    @app.post("/api/sessions/{sid}/finish")
    def finish(sid: str, conn=Depends(get_conn)):
        tutor.finish(conn, sid)
        return {"ok": True}

    @app.get("/api/sessions/{sid}/report")
    def report(sid: str, lang: Lang = "ru", conn=Depends(get_conn)):
        limited(sid)
        return build_report(conn, sid, lang)

    # Built frontend at "/" -- registered last, so /api/* and /health take precedence.
    static = Path(static_dir or os.getenv("STATIC_DIR") or DEFAULT_STATIC_DIR)
    if (static / "index.html").is_file():
        app.mount("/", StaticFiles(directory=static, html=True), name="frontend")

    return app

