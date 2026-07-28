"""FastAPI application.

Candidate endpoints expose ONLY safe data (public scenario cards, the customer's chat
messages). The rubric, persona internals, success conditions, and scores never reach the
candidate client — they are available only via the token-protected /api/admin endpoints.
"""
from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, engine, scenarios, storage

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="LinkedIn Support Consultant — Chat Assessment", docs_url=None, redoc_url=None)


@app.on_event("startup")
def _startup() -> None:
    storage.init_db()
    print("=" * 70)
    print("LinkedIn Global Support Consultant — Chat Assessment")
    print(f"  LLM provider : {config.provider_summary()}")
    print(f"  Candidate URL: http://localhost:{config.PORT}/")
    print(f"  Recruiter URL: http://localhost:{config.PORT}/admin  (token below)")
    print(f"  ADMIN_TOKEN  : {config.ADMIN_TOKEN}")
    print("=" * 70)


# --------------------------- request models ---------------------------
class StartSession(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    linkedin_url: str = Field(default="", max_length=200)
    category_id: str = Field(min_length=1, max_length=40)


class ChatTurn(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=1, max_length=4000)


class SubmitBody(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)


# --------------------------- candidate API ---------------------------
def _abbreviate_name(full: str) -> str:
    """Record only first name + last initial for privacy (e.g. "Alex Morgan" -> "Alex M").

    Idempotent: "Alex M" -> "Alex M". Mirrors abbreviateName() in static/app.js.
    """
    parts = (full or "").split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0].upper()}"


@app.get("/api/config")
def api_config() -> dict:
    return {
        "categories": scenarios.get_categories(),
        "min_turns": config.MIN_CANDIDATE_TURNS,
        "max_turns": config.MAX_CANDIDATE_TURNS,
    }


@app.get("/api/health")
def api_health() -> dict:
    return {"status": "ok", "mode": "llm" if config.LLM_ENABLED else "demo"}


@app.post("/api/session")
def start_session(body: StartSession) -> dict:
    category = scenarios.CATEGORY_BY_ID.get(body.category_id)
    if not category:
        raise HTTPException(status_code=400, detail="Unknown scenario category.")
    sub = scenarios.pick_subscenario(body.category_id)
    if not sub:
        raise HTTPException(status_code=400, detail="No scenario available for that category.")

    sid = storage.create_session(
        candidate_name=_abbreviate_name(body.name),
        linkedin_url=body.linkedin_url.strip(),
        category_id=category["id"],
        category_title=category["title"],
        sub_id=sub["id"],
    )
    storage.add_message(sid, "customer", sub["opening_message"])

    return {
        "session_id": sid,
        "category": category,  # public card only
        "opening_message": sub["opening_message"],
        "customer_name": sub["customer_name"],
        "min_turns": config.MIN_CANDIDATE_TURNS,
        "max_turns": config.MAX_CANDIDATE_TURNS,
    }


@app.post("/api/chat")
async def chat(body: ChatTurn) -> dict:
    session = storage.get_session(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] != "active":
        raise HTTPException(status_code=409, detail="This assessment has already been submitted.")

    turns = storage.count_candidate_turns(body.session_id)
    if turns >= config.MAX_CANDIDATE_TURNS:
        raise HTTPException(status_code=409, detail="Message limit reached. Please finish and submit.")

    category = scenarios.CATEGORY_BY_ID.get(session["category_id"])
    sub = scenarios.get_subscenario(session["category_id"], session["sub_id"])
    if not category or not sub:
        raise HTTPException(status_code=500, detail="Scenario configuration error.")

    storage.add_message(body.session_id, "candidate", body.message.strip())
    history = storage.get_history(body.session_id)
    reply, resolved = await engine.customer_reply(category, sub, history)
    storage.add_message(body.session_id, "customer", reply)

    new_turns = turns + 1
    return {
        "reply": reply,
        "resolved": resolved,
        "candidate_turns": new_turns,
        "can_submit": new_turns >= config.MIN_CANDIDATE_TURNS,
        "limit_reached": new_turns >= config.MAX_CANDIDATE_TURNS,
    }


@app.post("/api/submit")
async def submit(body: SubmitBody) -> dict:
    session = storage.get_session(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] == "submitted":
        # Never expose scores to the candidate — just confirm.
        return {"status": "submitted", "message": "Your assessment has already been submitted."}

    category = scenarios.CATEGORY_BY_ID.get(session["category_id"])
    sub = scenarios.get_subscenario(session["category_id"], session["sub_id"])
    if not category or not sub:
        raise HTTPException(status_code=500, detail="Scenario configuration error.")

    history = storage.get_history(body.session_id)
    score = await engine.score_session(category, sub, history)
    storage.mark_submitted(body.session_id, score)

    # IMPORTANT: no score data returned to the candidate.
    return {
        "status": "submitted",
        "message": "Thank you — your responses have been recorded. Our team will review them.",
    }


# --------------------------- recruiter API (token protected) ---------------------------
def require_admin(x_admin_token: str = Header(default="")) -> None:
    if not x_admin_token or not secrets.compare_digest(x_admin_token, config.ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing admin token.")


@app.get("/api/admin/results", dependencies=[Depends(require_admin)])
def admin_results() -> dict:
    return {"results": storage.list_results()}


@app.get("/api/admin/results/{session_id}", dependencies=[Depends(require_admin)])
def admin_result_detail(session_id: str) -> dict:
    detail = storage.get_result_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Result not found.")
    return detail


# --------------------------- static pages ---------------------------
@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
