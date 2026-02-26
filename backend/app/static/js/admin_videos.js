const api = {
  sessionDetail: (sessionId) => `/api/admin/sessions/${sessionId}`
};

const dom = {
  topCandidateName: document.getElementById("top-candidate-name"),
  topCandidateEmail: document.getElementById("top-candidate-email"),
  candidateName: document.getElementById("meta-candidate-name"),
  candidateId: document.getElementById("meta-candidate-id"),
  candidateEmail: document.getElementById("meta-candidate-email"),
  session: document.getElementById("meta-session"),
  list: document.getElementById("video-response-list"),
  status: document.getElementById("video-status")
};

const sessionId = readSessionIdFromPath();

if (!sessionId) {
  setStatus("Session id missing in URL.", true);
} else {
  loadSessionDetail(sessionId);
}

function readSessionIdFromPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (parts.length < 4) return "";
  if (parts[0] !== "admin" || parts[1] !== "sessions" || parts[3] !== "videos") return "";
  return decodeURIComponent(parts[2]);
}

async function loadSessionDetail(id) {
  setStatus("Loading candidate video responses...");

  try {
    const res = await fetch(api.sessionDetail(encodeURIComponent(id)));
    if (!res.ok) {
      throw new Error(await res.text());
    }

    const data = await res.json();
    renderSession(data);
    setStatus(`Loaded ${data.responses.length} video response(s).`);
  } catch (err) {
    setStatus(`Failed to load video responses: ${err.message}`, true);
  }
}

function renderSession(data) {
  dom.topCandidateName.textContent = data.candidate_name || "Candidate";
  dom.topCandidateEmail.textContent = data.candidate_email || "-";
  dom.candidateName.textContent = data.candidate_name || "Candidate";
  dom.candidateId.textContent = data.candidate_id || "-";
  dom.candidateEmail.textContent = data.candidate_email || "-";
  dom.session.textContent = data.session_id || "-";

  dom.list.innerHTML = "";

  if (!data.responses.length) {
    const panel = document.createElement("section");
    panel.className = "rounded-2xl border border-brand-400/35 bg-slate-900/80 p-5";
    panel.innerHTML = "<p class=\"text-slate-300\">No uploaded video responses found for this session.</p>";
    dom.list.appendChild(panel);
    return;
  }

  data.responses.forEach((item) => {
    const section = document.createElement("section");
    section.className = "rounded-2xl border border-brand-400/35 bg-slate-900/80 p-5 shadow-[0_20px_55px_rgba(0,0,0,.38)]";

    section.innerHTML = `
      <div class="mb-3">
        <h3 class="text-base font-semibold text-white">
          Q${item.order_index}: ${escapeHtml(item.question_text)}
        </h3>
      </div>

      <div class="mb-3 grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
        <div><strong class="text-slate-200">Question ID:</strong> ${escapeHtml(item.question_id)}</div>
        <div><strong class="text-slate-200">Uploaded:</strong> ${formatDate(item.uploaded_at)}</div>
      </div>

      <div class="overflow-hidden rounded-xl border border-brand-400/40 bg-black/80">
        <video class="w-full max-h-[460px]" src="${item.media_url}" controls preload="metadata"></video>
      </div>
    `;

    dom.list.appendChild(section);
  });
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
