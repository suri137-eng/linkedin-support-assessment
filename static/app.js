"use strict";

const state = {
  sessionId: null,
  category: null,
  customerName: "Customer",
  minTurns: 4,
  maxTurns: 18,
  candidateTurns: 0,
  awaiting: false,
  finished: false,
  // timers
  overallEndsAt: null,
  overallTimer: null,
  turnStartedAt: null,
  turnTimer: null,
  timeUp: false,
};

const $ = (id) => document.getElementById(id);
const screens = ["intro", "scenarios", "chat", "done"];
function showScreen(name) {
  screens.forEach((s) => $(`screen-${s}`).classList.toggle("active", s === name));
}

async function api(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

// ---------- Intro ----------
function initIntro() {
  const consent = $("consent");
  const name = $("name");
  const cont = $("to-scenarios");
  const validate = () => { cont.disabled = !(name.value.trim() && consent.checked); };
  name.addEventListener("input", validate);
  consent.addEventListener("change", validate);
  cont.addEventListener("click", () => showScreen("scenarios"));
  $("back-intro").addEventListener("click", () => showScreen("intro"));
}

// ---------- Scenario grid ----------
async function loadConfig() {
  const res = await fetch("/api/config");
  const cfg = await res.json();
  state.minTurns = cfg.min_turns;
  state.maxTurns = cfg.max_turns;
  const grid = $("scenario-grid");
  grid.innerHTML = "";
  cfg.categories.forEach((c) => {
    const el = document.createElement("button");
    el.className = "scenario";
    el.innerHTML = `<span class="emoji">${c.emoji}</span>
      <h3>${escapeHtml(c.title)}</h3>
      <p>${escapeHtml(c.blurb)}</p>`;
    el.addEventListener("click", () => startSession(c.id));
    grid.appendChild(el);
  });
}

// ---------- Session / chat ----------
async function startSession(categoryId) {
  $("scenario-error").textContent = "";
  try {
    const data = await api("/api/session", {
      name: abbreviateName($("name").value.trim()),
      linkedin_url: $("linkedin").value.trim(),
      category_id: categoryId,
    });
    state.sessionId = data.session_id;
    state.category = data.category;
    state.customerName = data.customer_name || "Customer";
    state.candidateTurns = 0;
    state.finished = false;

    $("cust-name").textContent = state.customerName;
    $("cust-avatar").textContent = (state.customerName[0] || "C").toUpperCase();
    $("chat-ctx").textContent = `${data.category.emoji} ${data.category.title}`;
    $("messages").innerHTML = "";
    $("resolved-banner").style.display = "none";
    $("timesup-banner").style.display = "none";
    $("finish").disabled = true;
    resetTimerDisplays();
    updateTurnPill();
    updateHint();

    addMessage("customer", data.opening_message, state.customerName);
    showScreen("chat");
    startTimers();
    $("input").focus();
  } catch (e) {
    $("scenario-error").textContent = e.message;
  }
}

function addMessage(role, text, name, elapsedSec) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const label = role === "customer" ? (name || state.customerName) : "You";
  let meta = "";
  if (role === "candidate" && typeof elapsedSec === "number") {
    meta = `<span class="meta">⏱ ${fmtClock(elapsedSec)} to reply</span>`;
  }
  wrap.innerHTML = `<span class="name">${escapeHtml(label)}</span>${escapeHtml(text)}${meta}`;
  $("messages").appendChild(wrap);
  scrollMessages();
}

function showTyping() {
  const t = document.createElement("div");
  t.className = "typing"; t.id = "typing";
  t.innerHTML = "<span></span><span></span><span></span>";
  $("messages").appendChild(t);
  scrollMessages();
}
function hideTyping() { const t = $("typing"); if (t) t.remove(); }
function scrollMessages() { const m = $("messages"); m.scrollTop = m.scrollHeight; }

async function sendMessage() {
  if (state.awaiting || state.finished || state.timeUp) return;
  const input = $("input");
  const text = input.value.trim();
  if (!text) return;
  $("chat-error").textContent = "";

  const elapsedSec = stopTurnTimer(); // time spent composing this reply
  state.awaiting = true;
  $("send").disabled = true;
  addMessage("candidate", text, null, elapsedSec);
  input.value = "";
  autoGrow(input);
  showTyping();

  try {
    const data = await api("/api/chat", { session_id: state.sessionId, message: text });
    if (state.finished || state.timeUp) { hideTyping(); return; }
    hideTyping();
    addMessage("customer", data.reply, state.customerName);
    state.candidateTurns = data.candidate_turns;
    updateTurnPill();
    if (data.can_submit) $("finish").disabled = false;
    if (data.resolved) $("resolved-banner").style.display = "block";
    if (data.limit_reached) {
      $("send").disabled = true;
      input.disabled = true;
      $("chat-hint").textContent = "Message limit reached — please finish and submit.";
    } else {
      startTurnTimer(); // begin timing the next reply
    }
    updateHint();
  } catch (e) {
    hideTyping();
    $("chat-error").textContent = e.message;
    if (!state.timeUp && !state.finished) startTurnTimer();
  } finally {
    state.awaiting = false;
    if (!$("input").disabled) $("send").disabled = false;
    $("input").focus();
  }
}

function updateTurnPill() {
  $("turn-pill").textContent = `${state.candidateTurns} message${state.candidateTurns === 1 ? "" : "s"}`;
}
function updateHint() {
  const hint = $("chat-hint");
  if (state.candidateTurns < state.minTurns) {
    const left = state.minTurns - state.candidateTurns;
    hint.textContent = `Have a proper conversation (at least ${left} more message${left === 1 ? "" : "s"} before you can submit).`;
  } else {
    hint.textContent = "When you're satisfied you've helped the customer, click Finish & Submit.";
  }
}

async function finish(force = false) {
  if (state.finished) return;
  if (!force) {
    const ok = window.confirm("Submit this assessment? You won't be able to continue the conversation afterwards.");
    if (!ok) return;
  }
  state.finished = true;
  clearTimers();
  $("finish").disabled = true;
  $("send").disabled = true;
  $("input").disabled = true;
  try {
    const data = await api("/api/submit", { session_id: state.sessionId });
    $("done-msg").textContent = data.message || "Your responses have been recorded.";
    showScreen("done");
  } catch (e) {
    $("chat-error").textContent = e.message;
    if (!force) {
      state.finished = false;
      $("send").disabled = false;
      $("input").disabled = false;
    }
  }
}

// ---------- Timers ----------
const TOTAL_SECONDS = 300; // 5 minutes to complete the chat

function fmtClock(totalSec) {
  const s = Math.max(0, Math.round(totalSec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function resetTimerDisplays() {
  state.timeUp = false;
  $("overall-time").textContent = fmtClock(TOTAL_SECONDS);
  $("resp-time").textContent = fmtClock(0);
  $("overall-clock").className = "countdown ok";
}

function startTimers() {
  clearTimers();
  state.timeUp = false;
  state.overallEndsAt = Date.now() + TOTAL_SECONDS * 1000;
  tickOverall();
  state.overallTimer = setInterval(tickOverall, 250);
  startTurnTimer();
}

function tickOverall() {
  const remaining = (state.overallEndsAt - Date.now()) / 1000;
  $("overall-time").textContent = fmtClock(remaining);
  const el = $("overall-clock");
  el.classList.remove("ok", "warn", "danger");
  if (remaining <= 15) el.classList.add("danger");
  else if (remaining <= 60) el.classList.add("warn");
  else el.classList.add("ok");
  if (remaining <= 0) handleTimeUp();
}

function startTurnTimer() {
  clearInterval(state.turnTimer);
  state.turnStartedAt = Date.now();
  tickTurn();
  state.turnTimer = setInterval(tickTurn, 250);
}
function tickTurn() {
  if (!state.turnStartedAt) return;
  $("resp-time").textContent = fmtClock((Date.now() - state.turnStartedAt) / 1000);
}
function stopTurnTimer() {
  clearInterval(state.turnTimer);
  state.turnTimer = null;
  const elapsed = state.turnStartedAt ? (Date.now() - state.turnStartedAt) / 1000 : 0;
  state.turnStartedAt = null;
  $("resp-time").textContent = fmtClock(0);
  return elapsed;
}
function clearTimers() {
  clearInterval(state.overallTimer);
  clearInterval(state.turnTimer);
  state.overallTimer = null;
  state.turnTimer = null;
  state.turnStartedAt = null;
}

async function handleTimeUp() {
  if (state.timeUp || state.finished) return;
  state.timeUp = true;
  clearTimers();
  $("overall-time").textContent = "0:00";
  $("overall-clock").className = "countdown danger";
  $("resp-time").textContent = fmtClock(0);
  $("input").disabled = true;
  $("send").disabled = true;
  $("chat-hint").textContent = "Time's up.";
  $("timesup-banner").style.display = "block";
  await finish(true);
}

// ---------- utils ----------
function abbreviateName(full) {
  const parts = String(full || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "";
  if (parts.length === 1) return parts[0];
  const first = parts[0];
  const lastInitial = parts[parts.length - 1].charAt(0).toUpperCase();
  return `${first} ${lastInitial}`;
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
function autoGrow(el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 140) + "px"; }

function wireChat() {
  const input = $("input");
  input.addEventListener("input", () => autoGrow(input));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  $("send").addEventListener("click", sendMessage);
  $("finish").addEventListener("click", () => finish());
}

// ---------- boot ----------
initIntro();
wireChat();
loadConfig().catch((e) => { $("intro-error").textContent = "Could not load scenarios: " + e.message; });
