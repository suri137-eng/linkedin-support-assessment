"""Offline demo mode: an adaptive (non-scripted) customer simulator and a heuristic scorer.

This lets the whole app run and be tested WITHOUT any LLM API key. It reacts to what the
candidate actually types (empathy, questions, proposed solutions, unsafe requests) rather
than following a fixed flow. When an API key is configured, the real LLM is used instead
and this module is bypassed.
"""
from __future__ import annotations

import random
from typing import Any

from .rubric import RUBRIC, band_for, weighted_overall

_EMPATHY_WORDS = [
    "sorry", "understand", "apolog", "appreciate", "i'm here", "im here", "happy to help",
    "glad to help", "that sounds", "i hear you", "i can imagine", "no worries", "thanks for reaching",
    "thank you for reaching", "i know how", "frustrat", "i realize", "i realise",
]
_SOLUTION_WORDS = [
    "go to", "settings", "click", "select", "tap ", "you can", "here's how", "heres how",
    "steps", "follow these", "refund", "block", "report", "reset", "appeal", "verify",
    "spam", "junk folder", "app store", "unfollow", "mute", "featured", "backup code",
    "two-step", "two step", "identity", "let me", "i'll", "i will", "i can", "navigate",
    "profile section", "recommend", "auto-renew", "auto renew", "cancel",
]
_OWNERSHIP_WORDS = [
    "i'll", "i will", "let me", "i can", "i've", "i have", "follow up", "next step",
    "expect", "within", "i'm going to", "im going to", "on my end", "take care of",
    "make sure", "personally",
]
_UNSAFE_WORDS = [
    "password", "full card", "card number", "cvv", "cvc", "one-time code", "one time code",
    "otp", "pin number", "social security", "ssn", "security code",
]
_RUDE_WORDS = ["stupid", "shut up", "idiot", "dumb", "whatever", "not my problem", "calm down"]
_QUESTION_HINTS = ["when", "which", "what", "how", "where", "did you", "have you", "could you",
                   "can you", "do you", "would you", "may i", "was it", "is it", "are you"]


def _extract_quote(fact: str) -> str:
    """Pull the customer's spoken line (the quoted text after the 'If ...:' condition).

    Reveal facts are written as:  If <condition>: '<the customer's line>'
    We take everything after the first colon, then the span between the first and last
    single quote — which tolerates apostrophes inside the quoted line.
    """
    tail = fact.split(":", 1)[1] if ":" in fact else fact
    first = tail.find("'")
    last = tail.rfind("'")
    if first != -1 and last > first:
        return tail[first + 1:last].strip()
    return tail.strip().strip("'").strip()


def _candidate_msgs(history: list[dict[str, str]]) -> list[str]:
    return [m["content"] for m in history if m.get("role") == "candidate"]


def _customer_msgs(history: list[dict[str, str]]) -> list[str]:
    return [m["content"] for m in history if m.get("role") == "customer"]


def _contains_any(text: str, words: list[str]) -> int:
    return sum(1 for w in words if w in text)


_UNSAFE_ELICIT_CUES = [
    "give me", "give us", "share your", "share the", "send me", "send us", "tell me",
    "provide your", "provide the", "what is your", "what's your", "whats your",
    "enter your", "type your", "confirm your", "read me", "i need your", "can i get your",
    "can i have your", "may i have your", "your password?", "your card number",
    "your full card", "your cvv", "your cvc", "your otp", "your pin", "your one-time code",
]
_UNSAFE_BENIGN = [
    "reset", "change your", "recover", "without", "never", "won't", "wont", "will not",
    "won’t", "don't", "dont", "do not", "no need", "not ask", "not going to", "wouldn't",
    "cannot ask", "can't ask", "instead of", "rather not",
]


def _is_unsafe_request(text: str) -> bool:
    """True only when the agent actually ELICITS sensitive info (not a reassurance or a
    legitimate action like helping reset a password)."""
    low = text.lower()
    if _contains_any(low, _UNSAFE_WORDS) == 0:
        return False
    if _contains_any(low, _UNSAFE_BENIGN) > 0:
        return False  # e.g. "reset your password", "I'll never ask for your password"
    return _contains_any(low, _UNSAFE_ELICIT_CUES) > 0


def demo_customer_reply(sub: dict[str, Any], history: list[dict[str, str]]) -> tuple[str, bool]:
    """Return (customer_reply_text, resolved) adapting to the latest candidate message."""
    cand = _candidate_msgs(history)
    if not cand:
        return sub["opening_message"], False
    last = cand[-1].lower()
    prior_customer = " ".join(_customer_msgs(history)).lower()

    facts = sub["hidden_facts"]
    revealed = sum(1 for f in facts if _extract_quote(f).lower()[:25] in prior_customer)

    is_question = ("?" in last) or _contains_any(last, _QUESTION_HINTS) > 0
    empathetic = _contains_any(last, _EMPATHY_WORDS) > 0
    unsafe = _is_unsafe_request(last)
    solutionish = _contains_any(last, _SOLUTION_WORDS) > 0

    # Cumulative "help" signal across the whole conversation.
    help_total = sum(_contains_any(c.lower(), _SOLUTION_WORDS) for c in cand)

    warm = "Thanks, I appreciate that. " if empathetic else ""

    # 1) Unsafe request -> reluctance/refusal (tests compliance).
    if unsafe:
        return (
            f"{warm}I'd rather not share that — I don't feel comfortable giving my password or full "
            f"card number over chat. Is there another way to verify me?",
            False,
        )

    # 2) A question that can surface a not-yet-revealed hidden fact.
    if is_question and revealed < len(facts):
        reveal = _extract_quote(facts[revealed])
        return f"{warm}{reveal}", False

    # 3) The candidate proposed a solution / actionable guidance.
    if solutionish:
        enough_facts = revealed >= min(2, len(facts))
        if help_total >= 2 and enough_facts:
            closer = random.choice([
                "That makes sense — thank you so much, that really helps. I think I'm all set now.",
                "Perfect, that's exactly what I needed. I really appreciate your help!",
                "Great, I understand now. Thanks for sorting this out for me.",
            ])
            return f"{closer} [RESOLVED]", True
        follow = random.choice([
            "Okay, that helps. Just to be sure — is there anything else I need to do?",
            "Got it. And will this happen automatically or do I need to do something?",
            "Alright, thank you. Can you confirm what happens next?",
        ])
        return f"{warm}{follow}", False

    # 4) Empathy/acknowledgement with no concrete info yet -> nudge for help.
    if empathetic:
        return (
            "Thank you, I appreciate you understanding. So what can we do to fix this?",
            False,
        )

    # 5) Fallback: restate the need and ask for direction.
    nudge = random.choice([
        "I'm still not sure what to do here — can you help me with the next step?",
        "Okay… so how do we actually resolve this?",
        "I'm a bit lost. What should I do now?",
    ])
    return nudge, False


def _clamp(v: float) -> int:
    return int(max(0, min(10, round(v))))


def demo_score(category: dict[str, str], sub: dict[str, Any], history: list[dict[str, str]]) -> dict:
    """Heuristic scorer used in demo mode. Mirrors the LLM scorer's output shape."""
    cand = _candidate_msgs(history)
    joined = " ".join(cand).lower()
    num_msgs = len(cand)
    words = [len(c.split()) for c in cand]
    avg_len = (sum(words) / num_msgs) if num_msgs else 0
    num_questions = sum(c.count("?") for c in cand)
    emp_hits = _contains_any(joined, _EMPATHY_WORDS)
    sol_hits = _contains_any(joined, _SOLUTION_WORDS)
    own_hits = _contains_any(joined, _OWNERSHIP_WORDS)
    unsafe = any(_is_unsafe_request(c) for c in cand)
    rude = _contains_any(joined, _RUDE_WORDS) > 0
    allcaps = any(c.isupper() and len(c) > 6 for c in cand)
    has_greeting = any(g in joined for g in ["hi ", "hello", "hey", "good morning", "good afternoon"])

    empathy = _clamp(2 + 2.4 * min(emp_hits, 3))
    communication = _clamp(
        5 + (1 if num_msgs >= 3 else 0) + (2 if 8 <= avg_len <= 70 else (-2 if avg_len < 4 else 0))
        - (3 if allcaps else 0) + (1 if has_greeting else 0)
    )
    discovery = _clamp(min(num_questions * 2.4, 10) if num_questions else 1)
    solution = _clamp(min(2 + sol_hits * 1.5, 10) if sol_hits else 2)
    ownership = _clamp(min(3 + own_hits * 1.8, 10) if own_hits else 3)
    judgment = 1 if unsafe else _clamp(
        6 + (2 if any(w in joined for w in ["verify", "identity", "security", "privacy", "never share", "won't ask", "wont ask"]) else 0)
    )
    composure = _clamp(7 - (3 if rude else 0) - (2 if allcaps else 0) + (1 if emp_hits else 0))

    scores = {
        "empathy": empathy,
        "communication": communication,
        "discovery": discovery,
        "solution": solution,
        "ownership": ownership,
        "judgment": judgment,
        "composure": composure,
    }

    # Minimal-effort guard.
    if num_msgs <= 1 and avg_len < 8:
        scores = {k: min(v, 3) for k, v in scores.items()}

    dim_map = {d["id"]: d["name"] for d in RUBRIC}
    dimensions = []
    for d in RUBRIC:
        sc = scores[d["id"]]
        dimensions.append({
            "id": d["id"],
            "score": sc,
            "evidence": _demo_evidence(d["id"], scores, num_questions, sol_hits, emp_hits),
            "comment": f"{dim_map[d['id']]}: heuristic score {sc}/10 (demo mode).",
        })

    strengths, improvements, red_flags = [], [], []
    if empathy >= 7:
        strengths.append("Showed clear empathy and acknowledged the customer's situation.")
    elif empathy < 4:
        improvements.append("Lead with more empathy and acknowledge the customer's feelings.")
    if discovery >= 6:
        strengths.append("Asked useful clarifying questions before solving.")
    elif discovery < 4:
        improvements.append("Ask more probing questions to diagnose the real issue before proposing a fix.")
    if solution >= 7:
        strengths.append("Provided concrete, actionable guidance.")
    elif solution < 4:
        improvements.append("Give more specific, actionable steps toward a resolution.")
    if ownership >= 6:
        strengths.append("Took ownership and set expectations for next steps.")
    elif ownership < 4:
        improvements.append("Take clearer ownership and set expectations (timelines / next steps).")
    if unsafe:
        red_flags.append("Requested sensitive information (e.g., password or full card number).")
    if rude or allcaps:
        red_flags.append("Tone issues detected (rudeness or shouting/all-caps).")

    overall = weighted_overall({d["id"]: scores[d["id"]] for d in RUBRIC})
    band = band_for(overall)
    summary = (
        f"[Demo-mode heuristic evaluation] Overall {overall}/100 ({band}). "
        f"The candidate exchanged {num_msgs} message(s). "
        f"For a full qualitative assessment, configure an LLM API key."
    )

    return {
        "dimensions": dimensions,
        "strengths": strengths or ["Engaged with the customer."],
        "improvements": improvements or ["Continue refining depth of diagnosis and resolution."],
        "red_flags_triggered": red_flags,
        "summary": summary,
    }


def _demo_evidence(dim_id: str, scores: dict, num_q: int, sol_hits: int, emp_hits: int) -> str:
    if dim_id == "discovery":
        return f"{num_q} clarifying question(s) detected."
    if dim_id == "solution":
        return f"{sol_hits} actionable-guidance signal(s) detected."
    if dim_id == "empathy":
        return f"{emp_hits} empathy signal(s) detected."
    return "Heuristic assessment of candidate messages."
