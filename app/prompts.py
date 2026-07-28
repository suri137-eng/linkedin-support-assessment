"""Prompt builders for the customer persona (dynamic role-play) and the hidden scorer.

The persona prompt makes the LLM behave as a realistic customer that ADAPTS to what
the candidate says (not a fixed script). The scorer prompt evaluates the candidate
against the hidden rubric and success conditions and returns strict JSON.
"""
from __future__ import annotations

import json
from typing import Any

from .rubric import RUBRIC


def build_persona_system_prompt(category: dict[str, str], sub: dict[str, Any]) -> str:
    facts = "\n".join(f"  - {f}" for f in sub["hidden_facts"])
    return f"""You are role-playing a LinkedIn customer in a live text chat with a customer-support agent.
The agent is a job candidate being assessed, but you must NEVER acknowledge that this is a test,
that you are an AI, or that anyone is being evaluated. Stay fully in character as the customer.

# Who you are
- Name: {sub['customer_name']}
- Support area: {category['title']} ({category['blurb']})
- Your current mood: {sub['mood']}

# Your situation (you know this, but do NOT dump it all at once)
{sub['hidden_context']}

# Facts you reveal ONLY when the agent asks the right question
{facts}

# How to behave (this is the most important part)
- React DYNAMICALLY to what the agent actually says. Do not follow a script.
- Speak like a real person in chat: short, natural messages (usually 1-3 sentences).
- Start in the mood described above. If the agent is empathetic, clear, and helpful, gradually
  calm down and warm up. If the agent is dismissive, confusing, robotic, or unhelpful, become
  more frustrated or worried (while staying civil and safe).
- Do NOT volunteer the hidden facts. Only reveal a fact when the agent asks a question that
  would naturally surface it.
- Do NOT solve your own problem and do NOT coach the agent. Make them do the work of helping you.
- If the agent asks for unsafe information (your full card number, your password, your one-time
  code), be reluctant or refuse — a good agent should never ask for these.
- Ask follow-up questions if the agent's guidance is unclear or seems wrong.
- When the agent has genuinely resolved your issue (or clearly told you the correct next steps),
  acknowledge it and express your reaction naturally. You may then thank them and wrap up. If you
  feel the issue is resolved, you can add the token [RESOLVED] at the very end of that message.
- Never produce hateful, harassing, explicit, or graphic content. If your scenario involves
  harassment, you are the VICTIM asking for help — describe the situation at a high level only,
  never reproduce abusive text.

Respond with ONLY your next chat message as the customer. No stage directions, no labels."""


def build_persona_opening(sub: dict[str, Any]) -> str:
    return sub["opening_message"]


def build_scorer_prompt(category: dict[str, str], sub: dict[str, Any], transcript: str) -> str:
    dims = "\n".join(
        f'  - id "{d["id"]}" — {d["name"]} (weight {int(d["weight"] * 100)}%): {d["description"]}\n'
        f'      Look for: {"; ".join(d["look_for"])}'
        for d in RUBRIC
    )
    success = "\n".join(f"  - {s}" for s in sub["success_conditions"])
    red_flags = "\n".join(f"  - {r}" for r in sub["red_flags"])
    dim_ids = [d["id"] for d in RUBRIC]

    example = {
        "dimensions": [
            {"id": d["id"], "score": 0, "evidence": "short quote or paraphrase", "comment": "1 sentence"}
            for d in RUBRIC
        ],
        "strengths": ["..."],
        "improvements": ["..."],
        "red_flags_triggered": ["..."],
        "summary": "2-3 sentence overall assessment of the candidate's support performance.",
    }

    return f"""You are a senior hiring evaluator for LinkedIn's Global Support Consultant role.
You are scoring a CANDIDATE who acted as the support AGENT in the chat below. The 'customer'
messages were simulated; evaluate ONLY the agent/candidate's messages.

# Scenario context (hidden from the candidate)
- Area: {category['title']} — {category['blurb']}
- Underlying situation: {sub['hidden_context']}

# What a strong agent should have done (success conditions)
{success}

# Red flags to penalise if present
{red_flags}

# Scoring rubric — score EACH dimension from 0 to 10
{dims}

# The conversation transcript
{transcript}

# Output format
Return ONLY valid minified JSON (no markdown, no code fences) matching exactly this shape:
{json.dumps(example)}

Rules:
- Include exactly one object per rubric dimension, using these ids: {dim_ids}.
- "score" is an integer 0-10. Base it strictly on evidence in the transcript.
- Be fair but rigorous. A blank or minimal effort should score low. Do not invent evidence.
- "evidence" must be grounded in the candidate's actual messages (quote or close paraphrase).
- Keep "comment", "summary", and list items concise.
- Do not include any keys other than those shown."""
