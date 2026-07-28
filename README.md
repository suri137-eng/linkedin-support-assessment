# LinkedIn Global Support Consultant — Chat Assessment

A **shareable web app** that assesses external candidates for a *Global Support Consultant*
role through a **live, AI-driven chat role-play**. The candidate plays the support consultant;
an AI plays a realistic LinkedIn customer with a problem. The conversation is **dynamic** —
the customer reacts to what the candidate actually says, not a fixed script.

Every candidate is **scored server-side against a hidden competency rubric**. The scoring
parameters, personas, and results are **never exposed to the candidate** — they are visible
only in the token-protected recruiter console.

---

## ✨ Features

- **Scenario picker** — "Choose a Support Scenario" with four categories:
  - 💎 **Premium Subscriptions** — Billing, upgrades, cancellations & refunds
  - 🛡️ **Trust & Safety** — Harassment, fake profiles & content policy
  - 🖥️ **Platform Usage** — Features, tools & how-to guidance
  - 🔐 **Account Issues** — Login, restrictions, access & recovery
- **Dynamic AI customer** — each category randomly assigns one of several hidden sub-scenarios
  (e.g. "charged after cancelling", "locked out with 2FA", "feed is irrelevant"). The customer
  reveals details only when asked, gets calmer when handled well, and resists unsafe requests.
- **Hidden scoring** — 7 weighted competencies (empathy, communication, diagnosis, solution
  accuracy, ownership, compliance/judgment, composure) → overall 0–100 + hire recommendation.
- **Recruiter console** (`/admin`) — scored transcripts, evidence, strengths, red flags.
- **Runs with or without an LLM** — plug in an API key for full dynamic behaviour, or run the
  built-in **demo simulator** offline for local testing.

---

## 🚀 Quick start (local)

```powershell
cd C:\Users\slepaksh\linkedin-support-assessment
./run.ps1
```

Then open **http://localhost:8000/** (candidate) and **http://localhost:8000/admin** (recruiter).
The admin token is printed in the server console on startup.

> Without an API key the app runs in **DEMO mode** (adaptive heuristic customer + heuristic
> scorer) so you can click through the whole flow immediately.

### Enable the real AI (recommended for real assessments)

Copy `.env.example` → `.env` and set **one** provider:

```ini
# OpenAI (or any OpenAI-compatible endpoint)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```
or
```ini
# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=your-deployment
```

Restart the server. The console will confirm the active provider.

---

## 🔗 Make it shareable to external candidates

The server binds `0.0.0.0`, so it's ready to expose. Two paths:

### A) Instant public link (quick demo / interviews) — tunnel
No deployment needed; share a temporary HTTPS URL:

```powershell
# Cloudflare (no signup):  https://github.com/cloudflare/cloudflared
cloudflared tunnel --url http://localhost:8000

# or ngrok:  https://ngrok.com
ngrok http 8000
```
Send candidates the printed `https://…` link. Keep `/admin` private (share the token only
with recruiters).

### B) Production hosting (persistent link)
The included **Dockerfile** deploys anywhere that runs containers:

```bash
docker build -t support-assessment .
docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/app/data support-assessment
```

- **Render / Railway / Fly.io** — point at this repo (or image), set the env vars, expose port 8000.
- **Azure Container Apps / App Service** — deploy the image, set env vars, mount a volume for `/app/data`.

Set a strong `ADMIN_TOKEN` in the environment for any shared/production deployment, and put the
app behind HTTPS (tunnels and the platforms above provide this automatically).

---

## 🔒 What the candidate can and cannot see

| Server-side only (hidden)                     | Sent to candidate browser        |
|-----------------------------------------------|----------------------------------|
| Scoring rubric & weights                      | Scenario **cards** (emoji/title) |
| Persona backstory, hidden facts, success conds| The customer's chat messages     |
| Scores, evidence, recommendations             | A neutral "recorded" confirmation|

`/api/chat` returns only the customer's next message. Scores are produced on **submit** and
stored; the candidate only sees a thank-you. Results live behind `/api/admin/*`, protected by
`X-Admin-Token`.

---

## 🧠 How scoring works

On submit, the full transcript + the scenario's hidden success conditions are sent to the
evaluator (LLM in strict-JSON mode, or the heuristic scorer in demo mode). Each of the 7
competencies is scored 0–10, combined by weight into an overall 0–100, then mapped to a band:

`Strong Hire ≥85 · Hire ≥70 · Lean Hire ≥55 · Lean No Hire ≥40 · No Hire <40`

Edit weights/competencies in `app/rubric.py`.

---

## 🛠️ Customising

- **Scenarios / personas:** `app/scenarios.py` (add sub-scenarios, tweak hidden facts & success conditions).
- **Rubric:** `app/rubric.py`.
- **Persona & scorer prompts:** `app/prompts.py`.
- **Conversation length:** `MIN_CANDIDATE_TURNS` / `MAX_CANDIDATE_TURNS` env vars.

---

## 📁 Project structure

```
app/
  config.py      env config & provider detection
  scenarios.py   hidden categories, personas, sub-scenarios, success conditions
  rubric.py      hidden scoring rubric (7 weighted competencies)
  prompts.py     dynamic persona prompt + strict-JSON scorer prompt
  llm.py         OpenAI/Azure-compatible client
  demo.py        offline adaptive customer + heuristic scorer
  engine.py      dispatch (LLM ↔ demo) for replies & scoring
  storage.py     SQLite persistence
  main.py        FastAPI app (candidate + admin APIs, static serving)
static/
  index.html / styles.css / app.js   candidate SPA
  admin.html / admin.js               recruiter console
Dockerfile, requirements.txt, .env.example, run.ps1
```

---

## API summary

| Method | Path                         | Auth        | Purpose                                  |
|--------|------------------------------|-------------|------------------------------------------|
| GET    | `/api/config`                | –           | Public scenario cards + turn limits      |
| POST   | `/api/session`               | –           | Start a session (assigns hidden scenario)|
| POST   | `/api/chat`                  | –           | Send candidate message → customer reply  |
| POST   | `/api/submit`                | –           | End & score (returns only a confirmation)|
| GET    | `/api/admin/results`         | `X-Admin-Token` | List all results                     |
| GET    | `/api/admin/results/{id}`    | `X-Admin-Token` | One scored transcript                |

---

*Personas, scenarios, and scoring criteria are illustrative and derived from the public
requirements of a Global Support Consultant role. Not affiliated with or endorsed by LinkedIn.*
