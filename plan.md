# LinkedIn Global Support Consultant — Chat Assessment

A shareable web app where external candidates complete a **live chat support simulation**.
An AI plays a realistic LinkedIn customer; the candidate acts as the Support Consultant.
The conversation is **dynamic** (LLM-driven, not a fixed script). Scoring happens
**server-side against a hidden rubric** — assessment parameters are never sent to the browser.

## Roles
- **Candidate** = plays the Support Consultant (the person being assessed).
- **AI** = plays the customer with a problem in the chosen category.
- **Recruiter** = views scores/transcripts in a token-protected admin page.

## Scenario categories (candidate picks one)
- 💎 Premium Subscriptions — Billing, upgrades, cancellations & refunds
- 🛡️ Trust & Safety — Harassment, fake profiles & content policy
- 🖥️ Platform Usage — Features, tools & how-to guidance
- 🔐 Account Issues — Login, restrictions, access & recovery

Each category has several hidden sub-scenarios (randomized) with a persona, hidden
backstory, hidden facts revealed only when asked, and hidden success conditions.

## Hidden scoring rubric (Global Support Consultant competencies)
1. Empathy & Customer Focus
2. Communication Clarity & Professionalism
3. Problem Discovery / Diagnosis
4. Solution Accuracy & Product/Policy Knowledge
5. Resolution & Ownership
6. Compliance & Judgment (privacy, policy, escalation)
7. Composure & De-escalation
→ Weighted overall 0–100 + recommendation band + evidence + improvement notes.

## Tech
- Backend: Python 3.11, FastAPI + Uvicorn, SQLite (stdlib), httpx.
- LLM: OpenAI-compatible chat completions (OpenAI / Azure OpenAI / any compatible base URL),
  configured via env. Graceful **demo mode** (adaptive heuristic persona + heuristic scorer)
  when no API key is set, so it runs/tests offline.
- Frontend: vanilla HTML/CSS/JS SPA (no build step) → portable, easy to deploy.

## Privacy guarantees
- `/api/chat` returns ONLY the customer's next message.
- Persona hidden details, success conditions, rubric, and scores are server-side only.
- Candidate sees a neutral confirmation on submit — no scores, no rubric.
- Admin results protected by `ADMIN_TOKEN`.

## Shareable
- Binds 0.0.0.0. Dockerfile + README with: quick share (Cloudflare/ngrok tunnel) and
  production deploy (Render/Railway/Azure App Service).

## Files
- app/: config, llm, scenarios, rubric, prompts, scoring, storage, main
- static/: index.html, styles.css, app.js, admin.html, admin.js
- requirements.txt, .env.example, .gitignore, Dockerfile, README.md, run.ps1
