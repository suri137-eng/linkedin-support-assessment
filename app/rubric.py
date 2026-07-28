"""Hidden scoring rubric for the LinkedIn Global Support Consultant assessment.

These competencies are derived from the core requirements of a Global Support
Consultant role (customer obsession, clear written communication, troubleshooting,
policy/product knowledge, ownership, sound judgment, and composure).

IMPORTANT: This rubric is server-side only. It must never be serialized to the
candidate-facing client. It is used only by the scoring engine and the recruiter view.
"""
from __future__ import annotations

from typing import TypedDict


class Dimension(TypedDict):
    id: str
    name: str
    weight: float
    description: str
    look_for: list[str]


RUBRIC: list[Dimension] = [
    {
        "id": "empathy",
        "name": "Empathy & Customer Focus",
        "weight": 0.16,
        "description": "Acknowledges the customer's feelings and situation, builds rapport, and keeps the customer at the centre of the interaction.",
        "look_for": [
            "Opens by acknowledging the customer's concern or frustration",
            "Uses warm, human, non-robotic language",
            "Reassures the customer they will be helped",
        ],
    },
    {
        "id": "communication",
        "name": "Communication Clarity & Professionalism",
        "weight": 0.16,
        "description": "Writes clearly, concisely, and professionally with correct grammar and an appropriate tone for a global audience.",
        "look_for": [
            "Clear, well-structured, easy-to-follow messages",
            "Professional tone, correct spelling/grammar",
            "Avoids jargon or explains it",
        ],
    },
    {
        "id": "discovery",
        "name": "Problem Discovery & Diagnosis",
        "weight": 0.15,
        "description": "Asks relevant, targeted questions to understand the real issue before jumping to a solution.",
        "look_for": [
            "Asks clarifying / probing questions",
            "Confirms understanding before solving",
            "Identifies the true root cause, not just the surface symptom",
        ],
    },
    {
        "id": "solution",
        "name": "Solution Accuracy & Product/Policy Knowledge",
        "weight": 0.18,
        "description": "Provides correct, actionable, LinkedIn-appropriate guidance grounded in accurate product and policy knowledge.",
        "look_for": [
            "Gives correct, specific, actionable steps",
            "Accurate about LinkedIn features, billing, and policies",
            "Tailors the solution to the customer's actual context",
        ],
    },
    {
        "id": "ownership",
        "name": "Resolution & Ownership",
        "weight": 0.13,
        "description": "Drives the issue toward resolution, takes ownership, sets clear expectations, and confirms the customer is satisfied.",
        "look_for": [
            "Takes ownership rather than deflecting",
            "Sets expectations (timelines, next steps, follow-up)",
            "Confirms resolution / offers further help before closing",
        ],
    },
    {
        "id": "judgment",
        "name": "Compliance & Judgment",
        "weight": 0.12,
        "description": "Follows privacy/security best practices, respects policy boundaries, and escalates appropriately.",
        "look_for": [
            "Verifies identity appropriately without requesting unsafe data (never full card number or password)",
            "Respects privacy and policy; does not over-promise",
            "Escalates or routes correctly when needed (safety, fraud, restrictions)",
        ],
    },
    {
        "id": "composure",
        "name": "Composure & De-escalation",
        "weight": 0.10,
        "description": "Stays calm, patient, and constructive, especially with upset or difficult customers.",
        "look_for": [
            "Remains calm and professional under pressure",
            "De-escalates frustration constructively",
            "Never blames, argues, or becomes defensive",
        ],
    },
]

RUBRIC_BY_ID = {d["id"]: d for d in RUBRIC}
MAX_DIMENSION_SCORE = 10.0


def band_for(overall_0_100: float) -> str:
    """Map an overall 0-100 score to a hiring recommendation band."""
    if overall_0_100 >= 85:
        return "Strong Hire"
    if overall_0_100 >= 70:
        return "Hire"
    if overall_0_100 >= 55:
        return "Lean Hire"
    if overall_0_100 >= 40:
        return "Lean No Hire"
    return "No Hire"


def weighted_overall(scores_by_id: dict[str, float]) -> float:
    """Compute weighted overall on a 0-100 scale from per-dimension 0-10 scores."""
    total = 0.0
    weight_sum = 0.0
    for dim in RUBRIC:
        raw = scores_by_id.get(dim["id"])
        if raw is None:
            continue
        clamped = max(0.0, min(MAX_DIMENSION_SCORE, float(raw)))
        total += (clamped / MAX_DIMENSION_SCORE) * dim["weight"] * 100.0
        weight_sum += dim["weight"]
    if weight_sum == 0:
        return 0.0
    # Normalise in case some dimensions were missing.
    return round(total / weight_sum, 1)
