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


# Agent asked the customer to say something again -> mild annoyance at repeating.
_REPEAT_CUES = [
    "repeat that", "say that again", "come again", "didn't catch", "did not catch",
    "didn't get that", "what was that", "can you repeat", "could you repeat",
    "sorry?", "pardon", "one more time",
]
# Empty filler that doesn't move things forward -> impatience if overused.
_FILLER_CUES = [
    "one moment", "please hold", "hold on", "bear with me", "let me check",
    "give me a moment", "just a sec", "just a second", "please wait", "moment please",
    "hang on", "let me look into",
]

# Mood text -> starting frustration (0 = calm, 10 = furious).
_MOOD_SCORES = [
    ("eager", 0), ("curious", 1), ("self-conscious", 1),
    ("worried", 3), ("anxious", 3), ("confused", 3), ("defensive", 3),
    ("stressed", 4), ("time-pressured", 4),
    ("annoyed", 5), ("frustrated", 5),
    ("upset", 6), ("wronged", 6), ("shaken", 6),
]


def _mood_baseline(mood: str) -> int:
    low = (mood or "").lower()
    score = 2
    for key, val in _MOOD_SCORES:
        if key in low:
            score = max(score, val)
    if "mildly" in low or "slightly" in low or "a little" in low:
        score -= 1
    if "civil" in low or "polite" in low:
        score -= 1
    if "very" in low or "really" in low:
        score += 1
    return max(0, min(7, score))


def _pick(options: list[str], used: list[str]) -> str:
    """Choose a line, preferring one that hasn't been said yet this conversation."""
    said = " ".join(used).lower()
    fresh = [o for o in options if o.lower() not in said]
    if fresh:
        return random.choice(fresh)
    # Pool exhausted: at minimum, don't echo the most recent line verbatim.
    last = used[-1].lower() if used else ""
    non_repeat = [o for o in options if o.lower() not in last]
    return random.choice(non_repeat or options)


# Generic phrases that, on their own, don't constitute real help.
_WEAK_SOLUTION = {"let me", "i'll", "i will", "i can", "you can"}


def _concrete_help(text: str) -> bool:
    """True if the message names an actual action, not just 'let me...' filler."""
    return any((w in text) and (w not in _WEAK_SOLUTION) for w in _SOLUTION_WORDS)


def _is_filler_stall(text: str) -> bool:
    """Filler ('one moment', 'let me check') with no concrete action attached."""
    return _contains_any(text, _FILLER_CUES) > 0 and not _concrete_help(text)


# Short lead-ins placed before a freshly revealed fact (no "as I said" — it's new).
_ACK_BEFORE_FACT = {
    "calm": ["Sure —", "Okay —", "Of course —", "Right,"],
    "impatient": ["Okay, so", "Alright,", "Right, well —", "Yeah,"],
    "irritated": ["Look,", "Okay, fine —", "Honestly,", "Right —"],
}

_REPEAT_REPLIES = {
    "calm": [
        "Sure, no problem. Like I said, I just need help getting this sorted.",
        "Of course — I'll go over it again: I really just want this fixed.",
        "No worries — to recap, I just want to get this resolved.",
    ],
    "impatient": [
        "Okay… I feel like I just explained this. Can we keep moving?",
        "I did just say all this. Anyway — can we get to a fix, please?",
        "I've been over this already. Can we not go back to the start?",
    ],
    "irritated": [
        "I've already gone over this twice. I really don't want to keep repeating myself.",
        "Seriously? I just explained all of this. Please, can you just help me fix it?",
        "I'm not going to keep saying the same thing. Are you actually listening to me?",
    ],
}

_UNSAFE_REPLIES = {
    "calm": [
        "I'd rather not share that — I'm not comfortable giving my password or full card number over chat. Is there another way to verify me?",
        "Hmm, I don't think I should hand that over. Can we confirm my identity some other way?",
        "I'd prefer not to give my password out. Is there a safer way to check it's me?",
    ],
    "impatient": [
        "No, I'm not giving out my password or full card number. Isn't there a safer way to check who I am?",
        "I'd really prefer not to share that. There must be another way to verify me, surely?",
        "I'm not comfortable with that. Can't you verify me without my password?",
    ],
    "irritated": [
        "Absolutely not — I'm not handing over my password or full card number over chat. That doesn't feel right at all.",
        "No way. You really shouldn't be asking me for that. Please find another way to verify me.",
        "I'm not giving you my password, full stop. Support should never ask for that.",
    ],
}

_ALREADY_TOLD = {
    "calm": [
        "I think I've shared everything I know at this point — so what happens next?",
        "That's honestly all the detail I have. Where does that leave us?",
        "I've given you all I've got — what's the next step from here?",
    ],
    "impatient": [
        "I've told you everything already. Can we actually get to a solution now?",
        "I don't have anything more to add — can we move on to fixing it?",
        "There's nothing else to tell. Can we please get to the fix?",
    ],
    "irritated": [
        "I've answered all of this already. We're going in circles — can you please just resolve it?",
        "We keep covering the same ground. I've told you everything I can. Please just help me.",
        "I've said everything there is to say. I need this sorted, not more questions.",
    ],
}

_FOLLOWUPS = {
    "calm": [
        "Okay, that helps. Is there anything I need to do on my end?",
        "Got it. Will this happen automatically, or do I need to do something?",
        "Alright, thanks. Can you confirm what happens next?",
    ],
    "impatient": [
        "Okay… and is that actually going to fix it, or is there more to it?",
        "Right, but what do I need to do now — anything on my side?",
        "So is that it, or are there more steps? I'd like to wrap this up.",
    ],
    "irritated": [
        "Okay, but is that really going to solve it this time? I just want it done.",
        "And that'll actually fix it? I've heard 'try this' before and it didn't help.",
        "Fine — but I need to know this is actually resolved, not just another step.",
    ],
}

_EMPATHY_NUDGE = {
    "calm": [
        "Thanks, I appreciate that. So what can we do to fix it?",
        "That's kind of you, thank you. What are the next steps?",
        "I appreciate you saying that. How do we sort it out?",
    ],
    "impatient": [
        "I appreciate that, but I really just need this fixed. What's the plan?",
        "Thanks — though what I really need is a solution. Where do we start?",
        "That's nice to hear, but can we focus on actually fixing it?",
    ],
    "irritated": [
        "I appreciate the sympathy, but I need action, not just apologies. What are you going to do about it?",
        "Look, the kind words are fine, but can we actually fix this? What's the next step?",
        "Please stop apologizing and just help me — what are you actually going to do?",
    ],
}

_STALL_NUDGE = {
    "calm": [
        "I'm not quite sure what to do here — can you walk me through the next step?",
        "Okay… so how do we actually sort this out?",
        "I'm a bit lost, to be honest. What should I do now?",
    ],
    "impatient": [
        "We don't seem to be getting anywhere — can you give me an actual next step?",
        "Okay, but what do we DO about it? I need something concrete.",
        "Can we move this along? I still don't know what happens now.",
    ],
    "irritated": [
        "Honestly, we're just going round in circles. Can you please give me a real answer?",
        "This is getting frustrating — I still don't have a solution. What are you actually doing to help me?",
        "I've been at this a while now and nothing's happening. Can you please just help me?",
    ],
}

_CLOSERS = {
    "calm": [
        "That makes sense — thank you so much, that really helps. I think I'm all set now.",
        "Perfect, that's exactly what I needed. I really appreciate your help!",
        "Great, I understand now. Thanks for sorting this out for me.",
    ],
    "relieved": [
        "Oh — okay, that actually works. Thank you, I appreciate you sticking with it.",
        "Finally, that makes sense. Sorry if I was a bit short earlier — thanks for getting it sorted.",
        "Right, that's what I needed. Thanks for pushing through and fixing it.",
    ],
}


def demo_customer_reply(sub: dict[str, Any], history: list[dict[str, str]]) -> tuple[str, bool]:
    """Return (customer_reply_text, resolved) adapting to the latest candidate message.

    The customer has a mood-driven baseline and a running frustration level that
    rises when the agent stalls, loops, asks them to repeat, or requests unsafe
    info, and eases with genuine empathy and concrete help. Phrasing varies by
    tone (calm / impatient / irritated) and avoids repeating lines already used.
    """
    cand = _candidate_msgs(history)
    if not cand:
        return sub["opening_message"], False

    used = _customer_msgs(history)
    prior_customer = " ".join(used).lower()
    last = cand[-1].lower()

    facts = sub["hidden_facts"]
    revealed = sum(1 for f in facts if _extract_quote(f).lower()[:25] in prior_customer)

    is_question = ("?" in last) or _contains_any(last, _QUESTION_HINTS) > 0
    empathetic = _contains_any(last, _EMPATHY_WORDS) > 0
    unsafe = _is_unsafe_request(last)
    asked_repeat = _contains_any(last, _REPEAT_CUES) > 0
    filler_stall = _is_filler_stall(last)
    solutionish = _contains_any(last, _SOLUTION_WORDS) > 0 and not filler_stall
    # Count only genuine help: ignore pure filler and unsafe asks that happen to
    # contain a keyword like "verify".
    help_total = sum(
        _contains_any(c.lower(), _SOLUTION_WORDS)
        for c in cand
        if not _is_filler_stall(c.lower()) and not _is_unsafe_request(c.lower())
    )

    # Count turns that went nowhere (no question, no solution, or pure filler).
    stalls = 0
    for c in cand:
        lo = c.lower()
        went_somewhere = ("?" in lo) or _contains_any(lo, _QUESTION_HINTS) > 0 or _contains_any(lo, _SOLUTION_WORDS) > 0
        if (not went_somewhere) or _is_filler_stall(lo):
            stalls += 1

    frustration = _mood_baseline(sub.get("mood", ""))
    frustration += 2 * max(0, stalls - 1)
    frustration += 3 if unsafe else 0
    frustration += 2 if asked_repeat else 0
    frustration -= 2 if empathetic else 0
    frustration -= 3 if help_total >= 1 else 0
    frustration = max(0, min(10, frustration))
    tone = "calm" if frustration <= 3 else ("impatient" if frustration <= 6 else "irritated")

    # 0) Agent asked the customer to repeat themselves -> they dislike re-explaining.
    if asked_repeat:
        return _pick(_REPEAT_REPLIES[tone], used), False

    # 1) Unsafe request -> reluctance/refusal (tests compliance).
    if unsafe:
        return _pick(_UNSAFE_REPLIES[tone], used), False

    # 2) A question that can surface a not-yet-revealed hidden fact.
    if is_question and revealed < len(facts):
        reveal = _extract_quote(facts[revealed])
        opener = _pick(_ACK_BEFORE_FACT[tone], used)
        return f"{opener} {reveal}", False

    # 2b) Still probing, but everything has already been shared -> going in circles.
    if is_question and revealed >= len(facts):
        return _pick(_ALREADY_TOLD[tone], used), False

    # 2c) Pure filler ("one moment", "let me check") with no concrete action.
    if filler_stall:
        return _pick(_STALL_NUDGE[tone], used), False

    # 3) The candidate proposed a solution / actionable guidance.
    if solutionish:
        enough_facts = revealed >= min(2, len(facts))
        if help_total >= 2 and enough_facts:
            closer = _pick(_CLOSERS["relieved" if frustration >= 5 else "calm"], used)
            return f"{closer} [RESOLVED]", True
        return _pick(_FOLLOWUPS[tone], used), False

    # 4) Empathy/acknowledgement with no concrete info yet -> nudge for action.
    if empathetic:
        return _pick(_EMPATHY_NUDGE[tone], used), False

    # 5) Fallback: nothing useful landed -> nudge, increasingly impatiently.
    return _pick(_STALL_NUDGE[tone], used), False


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
