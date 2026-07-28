"""
Recruiter dashboard for the LinkedIn Global Support Consultant chat assessment.

Reads results through the app's TOKEN-PROTECTED admin API (never the candidate
endpoints), so the hidden rubric/scores stay server-side. Works against a local
server (http://localhost:8010) or the deployed Azure URL — just point the sidebar
at the right base URL and paste the admin token.

Run:
    .\.venv-streamlit\Scripts\streamlit run streamlit_app.py
"""
from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

DEFAULT_API = os.getenv("ASSESSMENT_API_URL", "http://localhost:8010")
DEFAULT_TOKEN = os.getenv("ADMIN_TOKEN", "")

BAND_STYLE = {
    "Strong Hire": ("🟢", "#1a7f37"),
    "Hire": ("🟢", "#2da44e"),
    "Lean Hire": ("🟡", "#bf8700"),
    "Lean No Hire": ("🟠", "#bc4c00"),
    "No Hire": ("🔴", "#cf222e"),
}
BAND_ORDER = ["Strong Hire", "Hire", "Lean Hire", "Lean No Hire", "No Hire"]

st.set_page_config(
    page_title="Support Assessment — Recruiter Dashboard",
    page_icon="🎯",
    layout="wide",
)


# --------------------------- API helpers ---------------------------
def _headers(token: str) -> dict:
    return {"X-Admin-Token": token}


@st.cache_data(ttl=15, show_spinner=False)
def fetch_results(api_base: str, token: str) -> tuple[bool, object]:
    """Return (ok, data|error_message)."""
    try:
        r = requests.get(f"{api_base}/api/admin/results", headers=_headers(token), timeout=15)
    except requests.exceptions.RequestException as exc:
        return False, f"Could not reach the server at {api_base} ({exc.__class__.__name__})."
    if r.status_code == 401:
        return False, "Invalid or missing admin token (401)."
    if r.status_code != 200:
        return False, f"Unexpected response {r.status_code}: {r.text[:200]}"
    return True, r.json().get("results", [])


@st.cache_data(ttl=15, show_spinner=False)
def fetch_detail(api_base: str, token: str, session_id: str) -> tuple[bool, object]:
    try:
        r = requests.get(
            f"{api_base}/api/admin/results/{session_id}", headers=_headers(token), timeout=15
        )
    except requests.exceptions.RequestException as exc:
        return False, f"Could not reach the server ({exc.__class__.__name__})."
    if r.status_code == 401:
        return False, "Invalid or missing admin token (401)."
    if r.status_code == 404:
        return False, "Result not found."
    if r.status_code != 200:
        return False, f"Unexpected response {r.status_code}: {r.text[:200]}"
    return True, r.json()


def band_badge(band: str | None) -> str:
    if not band:
        return "—"
    emoji, _ = BAND_STYLE.get(band, ("⚪", "#57606a"))
    return f"{emoji} {band}"


# --------------------------- Sidebar ---------------------------
st.sidebar.title("🎯 Recruiter Console")
st.sidebar.caption("Reads the hidden scores via the token-protected admin API.")
api_base = st.sidebar.text_input("API base URL", value=DEFAULT_API).rstrip("/")
admin_token = st.sidebar.text_input("Admin token", value=DEFAULT_TOKEN, type="password")
if st.sidebar.button("🔄 Refresh now", use_container_width=True):
    st.cache_data.clear()

st.sidebar.markdown("---")
st.sidebar.caption(
    "Tip: point the URL at your deployed Azure app "
    "(https://…azurecontainerapps.io) to review live candidates."
)

st.title("LinkedIn Global Support Consultant — Assessment Results")

if not admin_token:
    st.info("Enter the **admin token** in the sidebar to load results.")
    st.stop()

ok, data = fetch_results(api_base, admin_token)
if not ok:
    st.error(data)
    st.stop()

results: list[dict] = data
if not results:
    st.warning("No assessment sessions yet. Once candidates complete the chat, they'll appear here.")
    st.stop()

df = pd.DataFrame(results)
for col in ["candidate_name", "candidate_email", "category_title", "sub_id", "status", "band"]:
    if col not in df.columns:
        df[col] = None
df["overall"] = pd.to_numeric(df.get("overall"), errors="coerce")

# --------------------------- Summary metrics ---------------------------
submitted = df[df["status"] == "submitted"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total sessions", len(df))
c2.metric("Completed", len(submitted))
c3.metric("In progress", int((df["status"] != "submitted").sum()))
c4.metric("Avg score", f"{submitted['overall'].mean():.1f}" if len(submitted) else "—")

if len(submitted):
    dist = (
        submitted["band"].value_counts().reindex(BAND_ORDER).fillna(0).astype(int)
    )
    st.caption("Recommendation distribution")
    st.bar_chart(dist, height=180)

st.markdown("---")

# --------------------------- Filters + table ---------------------------
left, right = st.columns([1, 3])
with left:
    st.subheader("Filters")
    categories = ["All"] + sorted([c for c in df["category_title"].dropna().unique()])
    f_cat = st.selectbox("Category", categories)
    f_bands = st.multiselect("Recommendation", BAND_ORDER)
    f_status = st.selectbox("Status", ["All", "submitted", "active"])
    f_search = st.text_input("Search name / email")

view = df.copy()
if f_cat != "All":
    view = view[view["category_title"] == f_cat]
if f_bands:
    view = view[view["band"].isin(f_bands)]
if f_status != "All":
    view = view[view["status"] == f_status]
if f_search:
    s = f_search.lower()
    view = view[
        view["candidate_name"].fillna("").str.lower().str.contains(s)
        | view["candidate_email"].fillna("").str.lower().str.contains(s)
    ]

with right:
    st.subheader(f"Candidates ({len(view)})")
    table = view.copy()
    table["Recommendation"] = table["band"].apply(band_badge)
    table = table.rename(
        columns={
            "candidate_name": "Candidate",
            "candidate_email": "Email",
            "category_title": "Category",
            "status": "Status",
            "overall": "Score",
            "submitted_at": "Submitted",
        }
    )
    show_cols = ["Candidate", "Email", "Category", "Status", "Score", "Recommendation", "Submitted"]
    show_cols = [c for c in show_cols if c in table.columns]
    st.dataframe(
        table[show_cols].sort_values("Score", ascending=False, na_position="last"),
        use_container_width=True,
        hide_index=True,
        column_config={"Score": st.column_config.NumberColumn(format="%.1f")},
    )

st.markdown("---")

# --------------------------- Detail view ---------------------------
st.subheader("Candidate detail")
if view.empty:
    st.info("No candidates match the current filters.")
    st.stop()

options = view.to_dict("records")


def _label(rec: dict) -> str:
    name = rec.get("candidate_name") or "(no name)"
    cat = rec.get("category_title") or "?"
    score = rec.get("overall")
    score_txt = f"{score:.1f}" if pd.notna(score) else "—"
    return f"{name} · {cat} · {band_badge(rec.get('band'))} ({score_txt})"


selected = st.selectbox("Select a candidate", options, format_func=_label)
if not selected:
    st.stop()

ok, detail = fetch_detail(api_base, admin_token, selected["id"])
if not ok:
    st.error(detail)
    st.stop()

session = detail.get("session", {})
score = detail.get("score")
history = detail.get("history", [])

meta1, meta2, meta3 = st.columns(3)
meta1.markdown(f"**Candidate:** {session.get('candidate_name') or '—'}")
meta1.markdown(f"**Email:** {session.get('candidate_email') or '—'}")
meta2.markdown(f"**Category:** {session.get('category_title') or '—'}")
meta2.markdown(f"**Scenario variant:** `{session.get('sub_id') or '—'}`")
meta3.markdown(f"**Status:** {session.get('status') or '—'}")
meta3.markdown(f"**Submitted:** {session.get('submitted_at') or '—'}")

tab_score, tab_chat = st.tabs(["📊 Scorecard", "💬 Transcript"])

with tab_score:
    if not score:
        st.info("This session hasn't been submitted/scored yet.")
    else:
        overall = score.get("overall", 0.0)
        band = score.get("band", "—")
        emoji, color = BAND_STYLE.get(band, ("⚪", "#57606a"))
        top = st.columns([1, 2])
        top[0].metric("Overall", f"{overall:.1f} / 100")
        top[1].markdown(
            f"<div style='padding:14px;border-radius:10px;background:{color};color:white;"
            f"font-size:20px;font-weight:700;text-align:center'>{emoji} {band}</div>",
            unsafe_allow_html=True,
        )
        if score.get("mode"):
            st.caption(f"Scoring mode: {score['mode']}")

        dims = score.get("dimensions", [])
        if dims:
            ddf = pd.DataFrame(dims)
            chart_df = ddf.set_index("name")["score"]
            st.markdown("**Competency scores (0–10)**")
            st.bar_chart(chart_df, height=280)
            with st.expander("Evidence & comments per competency", expanded=False):
                for d in dims:
                    st.markdown(
                        f"**{d.get('name')}** — {d.get('score')}/10  "
                        f"_(weight {int(round(d.get('weight', 0) * 100))}%)_"
                    )
                    if d.get("evidence"):
                        st.markdown(f"> {d['evidence']}")
                    if d.get("comment"):
                        st.caption(d["comment"])
                    st.markdown("")

        cols = st.columns(2)
        with cols[0]:
            if score.get("strengths"):
                st.markdown("**✅ Strengths**")
                for s in score["strengths"]:
                    st.markdown(f"- {s}")
        with cols[1]:
            if score.get("improvements"):
                st.markdown("**🔧 Areas to improve**")
                for s in score["improvements"]:
                    st.markdown(f"- {s}")

        if score.get("red_flags_triggered"):
            st.markdown("**🚩 Red flags**")
            for s in score["red_flags_triggered"]:
                st.error(s)

        if score.get("summary"):
            st.markdown("**Summary**")
            st.write(score["summary"])

with tab_chat:
    if not history:
        st.info("No messages recorded.")
    for m in history:
        role = m.get("role")
        if role == "customer":
            with st.chat_message("assistant", avatar="🧑‍💼"):
                st.markdown(f"**Customer**")
                st.write(m.get("content", ""))
        else:
            with st.chat_message("user", avatar="🎧"):
                st.markdown(f"**Candidate (support agent)**")
                st.write(m.get("content", ""))
