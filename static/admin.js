"use strict";

const $ = (id) => document.getElementById(id);
let currentId = null;

function bandClass(band) {
  return {
    "Strong Hire": "b-strong", "Hire": "b-hire", "Lean Hire": "b-lean",
    "Lean No Hire": "b-leanno", "No Hire": "b-no",
  }[band] || "b-pending";
}

function token() { return $("token").value.trim(); }

async function adminGet(path) {
  const res = await fetch(path, { headers: { "X-Admin-Token": token() } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

async function loadResults() {
  $("admin-error").textContent = "";
  if (!token()) { $("admin-error").textContent = "Please enter the admin token."; return; }
  localStorage.setItem("admin_token", token());
  try {
    const data = await adminGet("/api/admin/results");
    renderList(data.results);
  } catch (e) {
    $("admin-error").textContent = e.message;
    $("list").innerHTML = `<div class="row"><em style="color:var(--danger)">${escapeHtml(e.message)}</em></div>`;
  }
}

function renderList(results) {
  const list = $("list");
  if (!results.length) {
    list.innerHTML = `<div class="row"><em style="color:var(--muted)">No assessments yet.</em></div>`;
    return;
  }
  list.innerHTML = "";
  results.forEach((r) => {
    const row = document.createElement("div");
    row.className = "row" + (r.id === currentId ? " active" : "");
    const band = r.status === "submitted" ? (r.band || "—") : "In progress";
    const bcls = r.status === "submitted" ? bandClass(r.band) : "b-pending";
    const score = (r.overall != null) ? `${r.overall}` : "—";
    row.innerHTML = `
      <div class="r-name">${escapeHtml(r.candidate_name || "Unknown")}
        <span class="badge ${bcls}" style="float:right">${escapeHtml(band)}</span></div>
      <div class="r-meta">
        <span>${escapeHtml(r.category_title || "")}</span>
        <span>${r.status === "submitted" ? "Score " + score + "/100" : "…"}</span>
      </div>
      <div class="r-meta"><span>${linkedinLink(r.candidate_linkedin, {stop:true})}</span>
        <span>${fmtDate(r.created_at)}</span></div>`;
    row.addEventListener("click", () => openDetail(r.id));
    list.appendChild(row);
  });
}

async function openDetail(id) {
  currentId = id;
  document.querySelectorAll(".row").forEach((r) => r.classList.remove("active"));
  try {
    const d = await adminGet(`/api/admin/results/${id}`);
    renderDetail(d);
    // re-highlight
    loadResults();
  } catch (e) {
    $("detail").innerHTML = `<p class="error-toast">${escapeHtml(e.message)}</p>`;
  }
}

function renderDetail(d) {
  const s = d.session;
  const score = d.score;
  const detail = $("detail");
  let html = `<div class="score-hero">`;
  if (score) {
    html += `<div class="score-num">${score.overall}<span style="font-size:16px;color:var(--muted)">/100</span></div>
      <div><span class="badge ${bandClass(score.band)}">${escapeHtml(score.band)}</span>
      <span class="mode-tag" title="How this was scored">${escapeHtml(score.mode || "")}</span>
      <div style="font-size:13px;color:var(--muted);margin-top:4px">${escapeHtml(s.candidate_name)} · ${escapeHtml(s.category_title)}${s.candidate_linkedin ? " · " + linkedinLink(s.candidate_linkedin) : ""}</div></div>`;
  } else {
    html += `<div><span class="badge b-pending">Not submitted</span>
      <div style="font-size:13px;color:var(--muted);margin-top:4px">${escapeHtml(s.candidate_name)} · ${escapeHtml(s.category_title)}${s.candidate_linkedin ? " · " + linkedinLink(s.candidate_linkedin) : ""}</div></div>`;
  }
  html += `</div>`;

  if (score) {
    html += `<div class="section-h">Competency breakdown</div>`;
    score.dimensions.forEach((dim) => {
      const pct = Math.round((dim.score / 10) * 100);
      html += `<div class="dim">
        <div class="top"><span>${escapeHtml(dim.name)} <span style="color:var(--muted)">(${Math.round(dim.weight*100)}%)</span></span>
          <strong>${dim.score}/10</strong></div>
        <div class="bar"><i style="width:${pct}%"></i></div>
        ${dim.evidence ? `<div class="ev">${escapeHtml(dim.evidence)}</div>` : ""}
      </div>`;
    });

    if (score.strengths?.length) {
      html += `<div class="section-h">Strengths</div><div class="chips">` +
        score.strengths.map((x) => `<span class="chip good">✓ ${escapeHtml(x)}</span>`).join("") + `</div>`;
    }
    if (score.improvements?.length) {
      html += `<div class="section-h">Areas to improve</div><div class="chips">` +
        score.improvements.map((x) => `<span class="chip warn">▲ ${escapeHtml(x)}</span>`).join("") + `</div>`;
    }
    if (score.red_flags_triggered?.length) {
      html += `<div class="section-h">Red flags</div><div class="chips">` +
        score.red_flags_triggered.map((x) => `<span class="chip bad">⚑ ${escapeHtml(x)}</span>`).join("") + `</div>`;
    }
    if (score.summary) {
      html += `<div class="section-h">Evaluator summary</div><p style="font-size:14px">${escapeHtml(score.summary)}</p>`;
    }
  }

  html += `<div class="transcript"><div class="section-h">Full transcript</div>`;
  d.history.forEach((m) => {
    const who = m.role === "customer" ? s.candidate_name ? "Customer" : "Customer" : "Candidate (Agent)";
    html += `<div class="t-msg ${m.role}">
      <div class="lbl">${m.role === "customer" ? "Customer" : "Candidate (Agent)"}</div>
      <div class="body">${escapeHtml(m.content)}</div></div>`;
  });
  html += `</div>`;
  detail.innerHTML = html;
}

function fmtDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
function linkedinHref(url) {
  const u = String(url || "").trim();
  if (!u) return "";
  return /^https?:\/\//i.test(u) ? u : "https://" + u;
}
function linkedinLink(url, opts) {
  const href = linkedinHref(url);
  if (!href) return "";
  const stop = opts && opts.stop ? ' onclick="event.stopPropagation()"' : "";
  return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer"${stop}>LinkedIn ↗</a>`;
}

$("load").addEventListener("click", loadResults);
$("refresh").addEventListener("click", loadResults);
$("token").addEventListener("keydown", (e) => { if (e.key === "Enter") loadResults(); });

const saved = localStorage.getItem("admin_token");
if (saved) { $("token").value = saved; loadResults(); }
