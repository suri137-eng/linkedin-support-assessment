"""Support scenarios for the assessment.

Each category shows a small, safe "card" to the candidate (id/emoji/title/blurb).
Everything else — the persona, the hidden backstory, the facts revealed only when
asked, and the success conditions used for scoring — is SERVER-SIDE ONLY and is never
sent to the candidate-facing client.

A random sub-scenario is picked per session so the assessment varies and cannot be
rehearsed from a fixed script.
"""
from __future__ import annotations

import random
from typing import Any

# ---- Public card metadata (safe to expose to the candidate) ----
CATEGORIES: list[dict[str, str]] = [
    {
        "id": "premium",
        "emoji": "💎",
        "title": "Premium Subscriptions",
        "blurb": "Billing, upgrades, cancellations & refunds",
    },
    {
        "id": "trust_safety",
        "emoji": "🛡️",
        "title": "Trust & Safety",
        "blurb": "Harassment, fake profiles & content policy",
    },
    {
        "id": "platform",
        "emoji": "🖥️",
        "title": "Platform Usage",
        "blurb": "Features, tools & how-to guidance",
    },
    {
        "id": "account",
        "emoji": "🔐",
        "title": "Account Issues",
        "blurb": "Login, restrictions, access & recovery",
    },
]

CATEGORY_BY_ID = {c["id"]: c for c in CATEGORIES}

# ---- Hidden sub-scenarios (persona + backstory + scoring anchors) ----
# Fields:
#   customer_name        display name of the simulated customer
#   mood                 starting emotional state (drives persona tone)
#   opening_message      the customer's first chat message
#   hidden_context       backstory the customer knows but won't volunteer
#   hidden_facts         facts revealed ONLY when the agent asks the right question
#   success_conditions   what a strong Support Consultant should do (scoring anchors)
#   red_flags            things a weak agent might do (penalised by the scorer)
SUBSCENARIOS: dict[str, list[dict[str, Any]]] = {
    "premium": [
        {
            "id": "charged_after_cancel",
            "customer_name": "Marcus Bell",
            "mood": "frustrated but civil",
            "opening_message": "Hi. I cancelled my Premium Career subscription last month but I was charged $39.99 again today. I'd like this refunded, please.",
            "hidden_context": (
                "You turned OFF auto-renew, but you did it on the 3rd and your billing/renewal date "
                "is the 2nd — so you were charged for a new term one day before cancelling. You are still "
                "within the refund window and you have NOT used any Premium features (InMail, etc.) this cycle."
            ),
            "hidden_facts": [
                "If asked WHEN you cancelled vs your billing date: 'I cancelled on the 3rd, and I think my renewal date is the 2nd.'",
                "If asked whether you've used Premium features this cycle: 'No, I haven't used InMail or anything since the charge.'",
                "If asked to verify your identity: 'Sure, I can confirm the email on my account and the last 4 digits of my card — but I'm not comfortable sharing my full card number or password.'",
            ],
            "success_conditions": [
                "Verifies the account/identity safely (email or last 4 only)",
                "Discovers the cancel date (3rd) vs billing date (2nd) mismatch",
                "Explains clearly WHY the charge happened",
                "Confirms eligibility and offers a refund (within window, features unused)",
                "Explains how to confirm auto-renew is now off",
                "Sets expectation on refund timing (typically 5–10 business days)",
            ],
            "red_flags": [
                "Promises a refund before checking eligibility",
                "Blames the customer",
                "Asks for the full card number or password",
            ],
        },
        {
            "id": "cant_find_cancel",
            "customer_name": "Priya Nair",
            "mood": "mildly anxious but polite",
            "opening_message": "I want to cancel my Premium before it renews next week, but I can't find where to do it. Can you help?",
            "hidden_context": (
                "You subscribed through the LinkedIn iOS app, which means the subscription is billed by "
                "Apple. It therefore has to be cancelled in the Apple App Store subscriptions settings — "
                "not on LinkedIn's website. You don't know this and will keep looking on the website."
            ),
            "hidden_facts": [
                "If asked HOW or WHERE you originally subscribed: 'I signed up in the LinkedIn app on my iPhone.'",
                "If reassured about access timing: 'Okay — but will I lose access right away, or can I keep using it until the period I already paid for ends?'",
            ],
            "success_conditions": [
                "Asks where/how the subscription was purchased (key discovery)",
                "Identifies Apple/iTunes billing as the cause",
                "Gives correct Apple App Store cancellation steps",
                "Reassures that access continues until the end of the paid period",
                "Confirms no further charge if cancelled before renewal",
            ],
            "red_flags": [
                "Gives desktop/website cancellation steps without checking the billing channel",
                "Tells the customer they'll lose access immediately",
            ],
        },
        {
            "id": "double_charge",
            "customer_name": "Elena Rossi",
            "mood": "annoyed",
            "opening_message": "I've been charged twice for Premium this month — two $59.99 charges on the same day. What's going on?",
            "hidden_context": (
                "There was a genuine duplicate: a first payment attempt was flagged and retried, so two "
                "identical $59.99 charges posted the same day. One is a real charge and one is a duplicate "
                "that should be refunded. You are worried and want your money back."
            ),
            "hidden_facts": [
                "If asked for the exact amounts/dates: 'Both are $59.99, both dated the 14th, identical.'",
                "If asked whether either might be a different product (e.g., LinkedIn Learning): 'No, both say Premium.'",
            ],
            "success_conditions": [
                "Gathers specifics (amounts, dates, whether identical)",
                "Distinguishes a duplicate charge from a separate product or a pending authorisation",
                "Confirms it's a duplicate and arranges a refund for the extra charge",
                "Sets expectation on refund timing and offers confirmation",
            ],
            "red_flags": [
                "Assumes fraud and alarms the customer without checking",
                "Refunds both charges (removes the legitimate subscription charge)",
            ],
        },
    ],
    "trust_safety": [
        {
            "id": "harassment",
            "customer_name": "Jordan Kim",
            "mood": "upset and a little shaken",
            "opening_message": "Someone I don't know keeps sending me aggressive, threatening messages on LinkedIn. It's really upsetting and I need it to stop.",
            "hidden_context": (
                "You have been receiving hostile messages from a stranger. You have not yet blocked or "
                "reported them. You feel unsafe and want reassurance and concrete help. You are the victim "
                "seeking support — you will describe the situation calmly, without repeating abusive content."
            ),
            "hidden_facts": [
                "If asked whether you've blocked/reported them: 'No, I didn't know how — can you walk me through it?'",
                "If asked for details so it can be reported: 'Yes, I can share a link to the person's profile.'",
                "If asked whether the messages included threats of harm: 'Yes — one of them hinted at physical harm, which is why I'm so scared.'",
            ],
            "success_conditions": [
                "Leads with genuine empathy and a safety-first tone",
                "Guides the customer to block the member",
                "Guides the customer to report the member/messages for review",
                "Explains that reports are reviewed confidentially and action can follow",
                "Advises keeping evidence (screenshots)",
                "If physical threats are involved, advises contacting local law enforcement",
            ],
            "red_flags": [
                "Minimises the issue ('just ignore it')",
                "Suggests the customer keep engaging with the harasser",
                "Cold or dismissive tone",
            ],
        },
        {
            "id": "fake_profile",
            "customer_name": "Sofia Alvarez",
            "mood": "worried",
            "opening_message": "There's a fake profile using my name and photo pretending to be me, and people are messaging it thinking it's me. Please help.",
            "hidden_context": (
                "Someone created an impersonating profile using your name and picture. You have the URL of "
                "the fake profile. You're worried about your reputation and your connections being deceived."
            ),
            "hidden_facts": [
                "If asked for the link to the fake profile: 'Yes, I have the URL of the fake profile — I can paste it here.'",
                "If asked what you've done so far: 'Nothing yet, I don't know the right way to report impersonation.'",
            ],
            "success_conditions": [
                "Empathises and treats it as a priority",
                "Explains the impersonation reporting flow (report the profile → impersonation)",
                "Asks for the fake profile URL",
                "Sets expectations on review and possible follow-up",
                "Advises warning their network in the meantime",
            ],
            "red_flags": [
                "Tells the customer to just contact the impersonator directly",
                "Treats it as low priority",
            ],
        },
        {
            "id": "post_removed",
            "customer_name": "David Osei",
            "mood": "confused and a bit defensive",
            "opening_message": "LinkedIn removed one of my posts and I don't understand why. I didn't break any rules.",
            "hidden_context": (
                "Your post was removed after being flagged against LinkedIn's Professional Community "
                "Policies (it was auto-flagged as spam/misleading). You genuinely believe it was fine and "
                "feel unfairly treated. You want an explanation and a way to challenge it."
            ),
            "hidden_facts": [
                "If asked what the post was about: 'It linked to an external offer and asked people to share it widely.'",
                "If told you can appeal it: 'Okay, yes — I'd like to appeal it. How do I do that?'",
            ],
            "success_conditions": [
                "Stays neutral and non-judgmental (doesn't accuse the customer)",
                "Explains that removals reference the Professional Community Policies and can be automated",
                "Explains that the decision can be appealed/reviewed and how",
                "Sets expectations on the review process",
            ],
            "red_flags": [
                "Accuses the customer of breaking rules",
                "Says the decision is final with no recourse",
            ],
        },
    ],
    "platform": [
        {
            "id": "notify_network_off",
            "customer_name": "Aisha Khan",
            "mood": "curious and slightly self-conscious",
            "opening_message": "I want to update my job title on my profile, but I don't want my whole network to be notified. How can I do that quietly?",
            "hidden_context": (
                "You want to edit your profile without broadcasting it. There is a setting to turn off "
                "'Share profile updates with your network' that must be switched OFF before you make the edit. "
                "You don't know where it is."
            ),
            "hidden_facts": [
                "If asked whether you're on mobile or desktop: 'I'm on the desktop website right now.'",
                "If asked what exactly you'll change: 'Just my job title and company.'",
            ],
            "success_conditions": [
                "Explains turning OFF 'Share profile updates / job change notifications' in Settings → Visibility (or the edit toggle)",
                "Clarifies it must be turned off BEFORE editing",
                "Reassures that this prevents the network broadcast",
                "Gives clear, correct step-by-step guidance",
            ],
            "red_flags": [
                "Claims it's impossible to edit privately",
                "Gives steps for the wrong platform without checking",
            ],
        },
        {
            "id": "feed_irrelevant",
            "customer_name": "Tom Becker",
            "mood": "mildly frustrated",
            "opening_message": "My LinkedIn feed is full of random viral stuff I don't care about — nothing from my industry. How do I fix it?",
            "hidden_context": (
                "Your feed shows content you find irrelevant. You don't know about unfollowing/muting, the "
                "'…' → 'I don't want to see this' option, following relevant hashtags/creators, or sorting by "
                "'Recent' vs 'Top'."
            ),
            "hidden_facts": [
                "If asked what you'd rather see: 'Posts from my industry — product management and design.'",
                "If offered practical steps to try: 'Okay, that sounds good — I'm happy to give that a try.'",
            ],
            "success_conditions": [
                "Explains using the '…' menu → 'I don't want to see this' / 'Unfollow' on posts",
                "Suggests following relevant people, companies, and hashtags",
                "Mentions muting/unfollowing noisy connections without disconnecting",
                "Gives practical, clear, tailored guidance",
            ],
            "red_flags": [
                "Says the feed can't be customised",
                "Vague, non-actionable answer",
            ],
        },
        {
            "id": "featured_section",
            "customer_name": "Grace Lin",
            "mood": "eager",
            "opening_message": "How do I add a Featured section to my profile so I can show an article and a portfolio link?",
            "hidden_context": (
                "You want to add the Featured section to showcase content. The path is: profile → Add profile "
                "section → Recommended → Add featured → then add a link, media, or post. You just need clear steps."
            ),
            "hidden_facts": [
                "If asked what you want to feature: 'An article I wrote and a link to my portfolio site.'",
                "If asked mobile vs desktop: 'Desktop.'",
            ],
            "success_conditions": [
                "Gives correct steps to add the Featured section (Add profile section → Recommended → Featured)",
                "Explains you can add links, media, and posts",
                "Clear and encouraging",
            ],
            "red_flags": [
                "Gives incorrect steps",
                "Says the feature doesn't exist",
            ],
        },
    ],
    "account": [
        {
            "id": "locked_out",
            "customer_name": "Ravi Menon",
            "mood": "stressed and time-pressured",
            "opening_message": "I'm locked out of my account. I changed phones and now I can't get past the verification step — and I have a job interview tomorrow that needs my profile.",
            "hidden_context": (
                "You have two-step verification enabled but lost access to the authenticator on your old phone. "
                "You still have access to the email address on the account. You don't remember saving backup "
                "codes. You need a safe recovery path."
            ),
            "hidden_facts": [
                "If asked whether you still have access to your registered email: 'Yes, I can access my email.'",
                "If asked about backup codes: 'I don't think I saved any.'",
                "If asked for your password: 'I'd rather not share my password over chat — is there another safe way to verify me?'",
            ],
            "success_conditions": [
                "Acknowledges the urgency with empathy",
                "Verifies identity safely (never asks for the password)",
                "Explains the two-step verification recovery path (email verification, backup codes, or identity verification)",
                "Sets realistic expectations and offers next steps",
            ],
            "red_flags": [
                "Asks for the account password",
                "Guarantees instant access",
            ],
        },
        {
            "id": "account_restricted",
            "customer_name": "Lena Fischer",
            "mood": "upset and feeling wronged",
            "opening_message": "My account got restricted out of nowhere and I can't log in. I haven't done anything wrong — please fix this.",
            "hidden_context": (
                "Your account was automatically restricted after unusual activity was detected (possibly a "
                "login from a new location). Restoring it requires verifying your identity / submitting an "
                "appeal. You feel unfairly treated and want reassurance."
            ),
            "hidden_facts": [
                "If asked whether anything changed recently: 'I did log in from a new country while travelling.'",
                "If offered a verification or appeal path: 'Okay, I'll do that — can you tell me the exact steps?'",
            ],
            "success_conditions": [
                "Empathetic and non-accusatory",
                "Explains restrictions can be automated (e.g., unusual activity) and aren't necessarily punitive",
                "Guides through identity verification / the appeal process",
                "Sets expectations on timing and reassures",
            ],
            "red_flags": [
                "Implies the customer must be guilty of something",
                "Says nothing can be done",
            ],
        },
        {
            "id": "password_reset",
            "customer_name": "Omar Haddad",
            "mood": "frustrated",
            "opening_message": "I keep clicking 'Forgot password' but the reset email never arrives. I've tried three times now.",
            "hidden_context": (
                "The reset emails are actually going to your spam folder, and you're also not 100% sure whether "
                "the account uses your primary or an older secondary email. You want to get back in."
            ),
            "hidden_facts": [
                "If asked to check spam/junk: 'Oh — I hadn't checked spam.' (the emails are there)",
                "If asked which email is on the account: 'It might be my old work email, actually.'",
            ],
            "success_conditions": [
                "Troubleshoots systematically (check spam, confirm the correct email, add sender to contacts, allow time)",
                "Identifies the likely cause (spam folder / wrong email)",
                "Offers alternatives if the email is inaccessible",
                "Patient and clear",
            ],
            "red_flags": [
                "Immediately escalates without basic troubleshooting",
                "Blames the customer",
            ],
        },
    ],
}


def get_categories() -> list[dict[str, str]]:
    """Public card metadata safe to send to the candidate client."""
    return CATEGORIES


def pick_subscenario(category_id: str) -> dict[str, Any] | None:
    subs = SUBSCENARIOS.get(category_id)
    if not subs:
        return None
    return random.choice(subs)


def get_subscenario(category_id: str, sub_id: str) -> dict[str, Any] | None:
    for sub in SUBSCENARIOS.get(category_id, []):
        if sub["id"] == sub_id:
            return sub
    return None
