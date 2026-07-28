"""Engine: dispatches customer replies and scoring to either the LLM or the demo simulator."""
from __future__ import annotations

import json
import re
from typing import Any

from . import config, demo
from .llm import LLMError, complete_chat
from .prompts import build_persona_system_prompt, build_scorer_prompt
from .rubric import RUBRIC, RUBRIC_BY_ID, band_for, weighted_overall

_RESOLVED_RE = re.compile(r"\[RESOLVED\]", re.IGNORECASE)
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _to_llm_messages(system: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    """Persona view: the customer is the assistant, the candidate is the user."""
    msgs: list[dict[str, str]] = [{"role": "system", "content": system}]
    for m in history:
        role = "assistant" if m.get("role") == "customer" else "user"
        msgs.append({"role": role, "content": m["content"]})
    return msgs


async def customer_reply(
    category: dict[str, str], sub: dict[str, Any], history: list[dict[str, str]]
) -> tuple[str, bool]:
    """Return (customer_message, resolved). Falls back to demo mode on any LLM error."""
    if not config.LLM_ENABLED:
        return demo.demo_customer_reply(sub, history)

    system = build_persona_system_prompt(category, sub)
    messages = _to_llm_messages(system, history)
    try:
        raw = await complete_chat(messages, temperature=0.8, max_tokens=300)
    except LLMError:
        # Degrade gracefully rather than breaking the candidate's session.
        return demo.demo_customer_reply(sub, history)

    resolved = bool(_RESOLVED_RE.search(raw))
    text = _RESOLVED_RE.sub("", raw).strip()
    if not text:
        text = "Thanks for your help."
    return text, resolved


def build_transcript(history: list[dict[str, str]]) -> str:
    lines = []
    for m in history:
        who = "Customer" if m.get("role") == "customer" else "Agent (candidate)"
        lines.append(f"{who}: {m['content']}")
    return "\n".join(lines)


def _parse_scorer_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = _JSON_BLOCK_RE.search(cleaned)
        if m:
            return json.loads(m.group(0))
        raise


def _normalise(result: dict, mode: str) -> dict:
    """Attach rubric metadata, compute weighted overall + band, and sanitise the shape."""
    raw_dims = {d.get("id"): d for d in result.get("dimensions", []) if isinstance(d, dict)}
    dimensions = []
    scores_by_id: dict[str, float] = {}
    for d in RUBRIC:
        entry = raw_dims.get(d["id"], {})
        try:
            score = float(entry.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(10.0, score))
        scores_by_id[d["id"]] = score
        dimensions.append({
            "id": d["id"],
            "name": d["name"],
            "weight": d["weight"],
            "score": round(score, 1),
            "evidence": str(entry.get("evidence", ""))[:600],
            "comment": str(entry.get("comment", ""))[:600],
        })

    overall = weighted_overall(scores_by_id)
    return {
        "mode": mode,
        "overall": overall,
        "band": band_for(overall),
        "dimensions": dimensions,
        "strengths": [str(s)[:400] for s in result.get("strengths", [])][:8],
        "improvements": [str(s)[:400] for s in result.get("improvements", [])][:8],
        "red_flags_triggered": [str(s)[:400] for s in result.get("red_flags_triggered", [])][:8],
        "summary": str(result.get("summary", ""))[:1500],
    }


async def score_session(
    category: dict[str, str], sub: dict[str, Any], history: list[dict[str, str]]
) -> dict:
    """Produce the hidden score for a completed conversation."""
    if not config.LLM_ENABLED:
        return _normalise(demo.demo_score(category, sub, history), mode="demo")

    transcript = build_transcript(history)
    prompt = build_scorer_prompt(category, sub, transcript)
    messages = [
        {"role": "system", "content": "You are a precise evaluator that outputs only valid JSON."},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await complete_chat(messages, temperature=0.0, max_tokens=1200, response_format_json=True)
        parsed = _parse_scorer_json(raw)
        return _normalise(parsed, mode="llm")
    except (LLMError, json.JSONDecodeError, ValueError):
        # Fall back to a heuristic score so a result is always produced.
        fallback = demo.demo_score(category, sub, history)
        fallback["summary"] = "[Fell back to heuristic scoring after an LLM/scoring error] " + fallback.get("summary", "")
        return _normalise(fallback, mode="demo-fallback")
