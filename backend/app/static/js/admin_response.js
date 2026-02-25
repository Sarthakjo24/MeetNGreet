const api = {
  sessionDetail: (sessionId) => `/api/admin/sessions/${sessionId}`
};

const dom = {
  candidateName: document.getElementById("meta-candidate-name"),
  candidateId: document.getElementById("meta-candidate-id"),
  candidateEmail: document.getElementById("meta-candidate-email"),
  session: document.getElementById("meta-session"),
  score: document.getElementById("meta-score"),
  communicationAvg: document.getElementById("meta-communication-avg"),
  contentAvg: document.getElementById("meta-content-avg"),
  confidenceAvg: document.getElementById("meta-confidence-avg"),
  created: document.getElementById("meta-created"),
  submitted: document.getElementById("meta-submitted"),
  list: document.getElementById("response-list"),
  status: document.getElementById("response-status")
};

const sessionId = readSessionIdFromPath();
let pendingPollTimer = null;

if (!sessionId) {
  setStatus("Session id missing in URL.", true);
} else {
  loadSessionDetail(sessionId);
}

function readSessionIdFromPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (parts.length < 3) return "";
  if (parts[0] !== "admin" || parts[1] !== "sessions") return "";
  return decodeURIComponent(parts[2]);
}

async function loadSessionDetail(id) {
  clearPendingPoll();
  setStatus("Loading candidate responses...");

  try {
    const res = await fetch(api.sessionDetail(encodeURIComponent(id)));
    if (!res.ok) {
      throw new Error(await res.text());
    }

    const data = await res.json();
    renderSession(data);

    if (data.final_score === null || data.final_score === undefined) {
      setStatus("Evaluation pending. Scores and feedback will appear automatically.");
      schedulePendingPoll(id);
    } else {
      setStatus(`Loaded ${data.responses.length} response(s).`);
    }
  } catch (err) {
    setStatus(`Failed to load session: ${err.message}`, true);
    schedulePendingPoll(id);
  }
}

function schedulePendingPoll(id) {
  pendingPollTimer = window.setTimeout(() => {
    loadSessionDetail(id);
  }, 10000);
}

function clearPendingPoll() {
  if (!pendingPollTimer) return;
  window.clearTimeout(pendingPollTimer);
  pendingPollTimer = null;
}

function renderSession(data) {
  dom.candidateName.textContent = data.candidate_name || "Candidate";
  dom.candidateId.textContent = data.candidate_id || "-";
  dom.candidateEmail.textContent = data.candidate_email || "";
  dom.session.textContent = data.session_id || "-";
  dom.score.textContent = formatScore(data.final_score);
  dom.communicationAvg.textContent = formatScore(data.communication_avg);
  dom.contentAvg.textContent = formatScore(data.content_avg);
  dom.confidenceAvg.textContent = formatScore(data.confidence_avg);
  dom.submitted.textContent = formatDate(data.submitted_at);

  dom.list.innerHTML = "";

  if (!data.responses.length) {
    const panel = document.createElement("section");
    panel.className = "rounded-2xl border border-brand-400/35 bg-slate-900/80 p-5";
    panel.innerHTML = "<p class=\"text-slate-300\">No uploaded responses found for this session.</p>";
    dom.list.appendChild(panel);
    return;
  }

  data.responses.forEach((item) => {
    const strengths = Array.isArray(item.strengths) ? item.strengths : [];
    const weaknesses = Array.isArray(item.weaknesses) ? item.weaknesses : [];

    const section = document.createElement("section");
    section.className = "rounded-2xl border border-brand-400/35 bg-slate-900/80 p-5 shadow-[0_20px_55px_rgba(0,0,0,.38)]";

    section.innerHTML = `
      <div class="mb-3">
        <h3 class="flex flex-wrap items-center justify-between gap-2 text-base font-semibold text-white">
          Q${item.order_index}: ${escapeHtml(item.question_text)}
          <span class="inline-flex rounded-full border border-brand-400/55 bg-brand-500/15 px-3 py-1 text-xs font-semibold text-brand-400">
            Score: ${formatScore(item.final_score)}
          </span>
        </h3>
      </div>

      <div class="mb-3 grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
        <div><strong class="text-slate-200">Question ID:</strong> ${escapeHtml(item.question_id)}</div>
        <div><strong class="text-slate-200">Uploaded:</strong> ${formatDate(item.uploaded_at)}</div>
      </div>

      <div class="mb-3 grid gap-2 text-sm sm:grid-cols-3">
        <div class="rounded-lg border border-brand-400/30 bg-slate-800/65 p-3"><strong class="text-slate-200">Communication:</strong> <span class="text-brand-400">${formatScore(item.communication_score)}</span></div>
        <div class="rounded-lg border border-brand-400/30 bg-slate-800/65 p-3"><strong class="text-slate-200">Content:</strong> <span class="text-brand-400">${formatScore(item.content_score)}</span></div>
        <div class="rounded-lg border border-brand-400/30 bg-slate-800/65 p-3"><strong class="text-slate-200">Confidence:</strong> <span class="text-brand-400">${formatScore(item.confidence_score)}</span></div>
      </div>

      <div class="mb-3 overflow-hidden rounded-xl border border-brand-400/40 bg-black/80">
        <video class="w-full max-h-[420px]" src="${item.media_url}" controls preload="metadata"></video>
      </div>

      <div class="mb-3 rounded-xl border border-brand-400/30 bg-slate-800/65 p-4">
        <strong class="text-white">Transcript</strong>
        <p class="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-200">${escapeHtml(item.transcript || "No transcript available.")}</p>
      </div>

      <div class="mb-3 rounded-xl border border-brand-400/30 bg-slate-800/65 p-4">
        <strong class="text-white">Feedback</strong>
        <p class="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-200">${escapeHtml(item.feedback || "Feedback will appear after evaluation.")}</p>
      </div>

      <div class="rounded-xl border border-brand-400/30 bg-slate-800/65 p-4">
        <strong class="text-white">Insights</strong>
        <div class="mt-2 grid gap-3 sm:grid-cols-2">
          <div class="rounded-lg border border-brand-400/20 bg-slate-900/40 p-3">
            <span class="text-sm font-semibold text-brand-400">Strengths</span>
            ${renderInsightList(strengths, "No strengths extracted yet.")}
          </div>
          <div class="rounded-lg border border-brand-400/20 bg-slate-900/40 p-3">
            <span class="text-sm font-semibold text-brand-400">Weaknesses</span>
            ${renderInsightList(weaknesses, "No weaknesses extracted yet.")}
          </div>
        </div>
      </div>
    `;

    dom.list.appendChild(section);
  });
}

function renderInsightList(items, fallback) {
  if (!items.length) {
    return `<p class="mt-2 text-sm text-slate-300">${escapeHtml(fallback)}</p>`;
  }

  const lines = items
    .map((item) => `<li class="leading-relaxed">${escapeHtml(item)}</li>`)
    .join("");

  return `<ul class="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-200">${lines}</ul>`;
}

function formatScore(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "Pending";
  return `${Number(value).toFixed(2)} / 10`;
}

function formatDate(isoText) {
  if (!isoText) return "-";
  const dt = parseAsUtcDate(isoText);
  if (Number.isNaN(dt.getTime())) return "-";
  const ist = dt.toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });
  const est = dt.toLocaleString("en-US", { timeZone: "America/New_York" });
  return `${ist} (IST) | ${est} (EST)`;
}

function parseAsUtcDate(value) {
  const text = String(value || "").trim();
  if (!text) return new Date("");

  const hasZone = /(?:Z|[+\-]\d{2}:\d{2})$/i.test(text);
  const normalized = hasZone ? text : `${text}Z`;
  return new Date(normalized);
}

function setStatus(message, isError = false) {
  dom.status.textContent = message;
  dom.status.style.color = isError ? "#fb2c36" : "#e2e8f0";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
