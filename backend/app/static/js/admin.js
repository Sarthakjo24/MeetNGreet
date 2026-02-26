const api = {
  results: "/api/admin/results",
  sessionDelete: (sessionId) => `/api/admin/sessions/${sessionId}`,
  sessionScores: (sessionId) => `/api/admin/sessions/${sessionId}/scores`,
  sessionVideos: (sessionId) => `/admin/sessions/${sessionId}/videos`,
  sessionStandard: (sessionId) => `/admin/sessions/${sessionId}`
};
const RESULTS_LIMIT = 200;
const ADMIN_FETCH_TIMEOUT_MS = 15000;
const EVALUATOR_TOTAL_WEIGHTS = Object.freeze({
  communication: 0.45,
  content: 0.45,
  confidence: 0.10
});

const dom = {
  body: document.getElementById("admin-results-body"),
  refreshBtn: document.getElementById("refresh-btn"),
  status: document.getElementById("admin-status")
};

if (dom.refreshBtn) {
  dom.refreshBtn.addEventListener("click", loadResults);
}
if (dom.body) {
  dom.body.addEventListener("click", onTableClick);
}
if (dom.body) {
  dom.body.addEventListener("input", onEvaluatorInput);
}

loadResults();

async function loadResults() {
  setStatus("Loading sessions...");
  const controller = new AbortController();
  const timerId = window.setTimeout(() => controller.abort(), ADMIN_FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`${api.results}?limit=${RESULTS_LIMIT}`, {
      signal: controller.signal
    });
    if (!res.ok) {
      throw new Error(await res.text());
    }

    const rows = await res.json();
    renderRows(rows);
    setStatus(`Loaded ${rows.length} latest session(s).`);
  } catch (err) {
    const message = err && err.name === "AbortError"
      ? "Request timed out while loading sessions."
      : err.message;
    setStatus(`Failed to load sessions: ${message}`, true);
  } finally {
    window.clearTimeout(timerId);
  }
}

function renderRows(rows) {
  dom.body.innerHTML = "";

    if (!rows.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = "<td colspan=\"16\" class=\"px-4 py-6 text-center text-slate-300\">No sessions found.</td>";
    dom.body.appendChild(tr);
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.className = "hover:bg-slate-800/55 transition";
    tr.innerHTML = `
      <td class="px-4 py-3 text-slate-200">${escapeHtml(row.candidate_name || "")}</td>
      <td class="px-4 py-3 text-slate-200 max-w-[150px] whitespace-normal break-words">${escapeHtml(row.candidate_email || "")}</td>
      <td class="px-4 py-3 text-slate-200 font-medium text-center w-[72px] whitespace-nowrap">${formatScore(row.confidence_avg, row.status_label)}</td>
      <td class="px-4 py-3 text-slate-200 font-medium text-center w-[56px] whitespace-nowrap">${formatScore(row.communication_avg, row.status_label)}</td>
      <td class="px-4 py-3 text-slate-200 font-medium text-center w-[72px] whitespace-nowrap">${formatScore(row.content_avg, row.status_label)}</td>
      <td class="px-4 py-3 font-semibold text-brand-400 text-center w-[72px] whitespace-normal break-words">${formatScore(row.final_score, row.status_label)}</td>

      <!-- Evaluator editable columns -->
      <td class="px-2 py-2 text-center w-[72px]"><input data-session-id="${escapeAttr(row.session_id)}" data-eval-field="eval_confidence" type="number" min="0" max="10" step="0.01" class="w-full bg-transparent text-slate-100 text-center outline-none" value="${row.eval_confidence ?? ""}"/></td>
      <td class="px-2 py-2 text-center w-[56px]"><input data-session-id="${escapeAttr(row.session_id)}" data-eval-field="eval_communication" type="number" min="0" max="10" step="0.01" class="w-full bg-transparent text-slate-100 text-center outline-none" value="${row.eval_communication ?? ""}"/></td>
      <td class="px-2 py-2 text-center w-[72px]"><input data-session-id="${escapeAttr(row.session_id)}" data-eval-field="eval_content" type="number" min="0" max="10" step="0.01" class="w-full bg-transparent text-slate-100 text-center outline-none" value="${row.eval_content ?? ""}"/></td>
      <td class="px-2 py-2 text-center w-[160px]">
        <div class="space-y-2">
          <input data-session-id="${escapeAttr(row.session_id)}" data-eval-field="eval_score" type="number" min="0" max="10" step="0.01" class="w-full bg-transparent text-slate-100 text-center outline-none" value="${row.eval_score ?? ""}"/>
          <button
            type="button"
            class="save-eval-btn w-full rounded-lg border border-[#bbf451] bg-[#bbf451] px-2 py-1.5 text-[11px] font-semibold text-slate-950 hover:brightness-95"
            data-session-id="${escapeAttr(row.session_id)}"
          >
            Save & Calculate
          </button>
        </div>
      </td>
      <td class="px-4 py-3">
        <div class="flex flex-col gap-2">
          <a class="rounded-lg border border-[#ffdf20] bg-[#ffdf20] px-3 py-1.5 text-center text-xs font-semibold text-slate-950 hover:brightness-95" href="${api.sessionVideos(encodeURIComponent(row.session_id))}">View Video Responses</a>
          <a class="rounded-lg border border-[#bbf451]/70 bg-gradient-to-b from-[#68b32f] to-[#4d8f21] px-3 py-1.5 text-xs font-semibold text-white hover:brightness-105" href="${api.sessionStandard(encodeURIComponent(row.session_id))}">View Standard Response</a>
        </div>
      </td>
      <td class="px-4 py-3 text-slate-300">${formatDate(row.created_at)}</td>
      <td class="px-4 py-3 text-slate-300">${formatDate(row.submitted_at)}</td>
      <td class="px-4 py-3 text-slate-200">${escapeHtml(row.session_id || "-")}</td>
      <td class="px-4 py-3 max-w-[120px] whitespace-normal break-words">${escapeHtml(row.candidate_id || "")}</td>
      <td class="px-4 py-3">
        <button type="button" class="delete-btn rounded-lg border border-[#f2efe6]/90 bg-[#f2efe6] px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-[#e8e3d7]" data-session-id="${escapeAttr(row.session_id)}">
          DELETE
        </button>
      </td>
    `;
    dom.body.appendChild(tr);
  });
}

async function onTableClick(event) {
  const saveButton = event.target.closest(".save-eval-btn");
  if (saveButton) {
    const sessionId = saveButton.dataset.sessionId;
    const row = saveButton.closest("tr");
    if (!sessionId || !row) return;

    const communication = _inputScoreValue(row, "eval_communication");
    const content = _inputScoreValue(row, "eval_content");
    const confidence = _inputScoreValue(row, "eval_confidence");
    if (communication === null || content === null || confidence === null) {
      setStatus("Enter Communication, Content, and Confidence evaluator scores first.", true);
      return;
    }

    const total = calculateEvaluatorTotal(communication, content, confidence);
    const totalInput = row.querySelector('input[data-eval-field="eval_score"]');
    if (totalInput) totalInput.value = total.toFixed(2);

    saveButton.disabled = true;
    const shortId = sessionId.length > 8 ? sessionId.slice(0, 8) : sessionId;
    setStatus(`Saving evaluator scores (${shortId})...`);
    try {
      await persistEvaluatorScores(sessionId, row);
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  const button = event.target.closest(".delete-btn");
  if (!button) return;

  const sessionId = button.dataset.sessionId;
  if (!sessionId) return;

  const confirmed = window.confirm(
    `Delete session ${sessionId} permanently? This removes DB records and stored media files.`
  );
  if (!confirmed) return;

  button.disabled = true;
  setStatus(`Deleting ${sessionId}...`);

  try {
    const res = await fetch(api.sessionDelete(sessionId), { method: "DELETE" });
    if (!res.ok) {
      throw new Error(await res.text());
    }

    setStatus(`Deleted session ${sessionId}.`);
    await loadResults();
  } catch (err) {
    button.disabled = false;
    setStatus(`Delete failed: ${err.message}`, true);
  }
}

function formatScore(value, statusLabel) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    if (!statusLabel) return "Evaluat<br/>ing...";
    return "Pending";
  }
  return `${Number(value).toFixed(2)} / 10`;
}

function formatCategoryTotal(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${Number(value).toFixed(2)} / 50`;
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

function onEvaluatorInput(event) {
  const input = event.target.closest && event.target.closest('input[data-eval-field]') || (event.target && event.target.matches && event.target.matches('input[data-eval-field]') ? event.target : null);
  if (!input) return;

  // allow only numeric input with optional decimal point
  const raw = String(input.value || "").trim();
  let cleaned = raw.replace(/[^0-9.]/g, "");
  const firstDot = cleaned.indexOf(".");
  if (firstDot >= 0) {
    cleaned = cleaned.slice(0, firstDot + 1) + cleaned.slice(firstDot + 1).replaceAll(".", "");
    const fractional = cleaned.slice(firstDot + 1);
    if (fractional.length > 2) {
      cleaned = cleaned.slice(0, firstDot + 1) + fractional.slice(0, 2);
    }
  }
  if (cleaned !== raw) input.value = cleaned;

  // clamp to allowed range
  const min = Number(input.getAttribute('min') || 0);
  const max = Number(input.getAttribute('max') || 9999);
  let v = cleaned === "" ? null : Number(cleaned);
  if (v !== null && Number.isNaN(v)) {
    v = null;
  }
  if (v !== null) {
    if (v < min) input.value = String(min);
    if (v > max) input.value = String(max);
  }
}

function _inputScoreValue(row, evalField) {
  const input = row.querySelector(`input[data-eval-field="${evalField}"]`);
  if (!input) return null;
  const text = String(input.value || "").trim();
  if (!text) return null;
  const value = Number(text);
  if (Number.isNaN(value)) return null;
  return value;
}

function buildEvaluatorPayload(row) {
  return {
    communication_score: _inputScoreValue(row, "eval_communication"),
    content_score: _inputScoreValue(row, "eval_content"),
    confidence_score: _inputScoreValue(row, "eval_confidence"),
    total_score: _inputScoreValue(row, "eval_score")
  };
}

function applySavedEvaluatorValues(row, payload) {
  const fieldMap = {
    eval_communication: payload.evaluator_communication_score,
    eval_content: payload.evaluator_content_score,
    eval_confidence: payload.evaluator_confidence_score,
    eval_score: payload.evaluator_total_score
  };

  Object.entries(fieldMap).forEach(([evalField, value]) => {
    const input = row.querySelector(`input[data-eval-field="${evalField}"]`);
    if (!input) return;
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      input.value = "";
      return;
    }
    if (evalField === "eval_score") {
      input.value = Number(value).toFixed(2);
      return;
    }
    input.value = String(Number(value));
  });
}

function calculateEvaluatorTotal(communication, content, confidence) {
  const weighted = (
    (communication * EVALUATOR_TOTAL_WEIGHTS.communication)
    + (content * EVALUATOR_TOTAL_WEIGHTS.content)
    + (confidence * EVALUATOR_TOTAL_WEIGHTS.confidence)
  );
  return Math.max(0, Math.min(10, Math.round(weighted * 100) / 100));
}

async function persistEvaluatorScores(sessionId, row) {
  const payload = buildEvaluatorPayload(row);
  const shortId = sessionId.length > 8 ? sessionId.slice(0, 8) : sessionId;

  try {
    const res = await fetch(api.sessionScores(encodeURIComponent(sessionId)), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      throw new Error(await res.text());
    }

    const saved = await res.json();
    applySavedEvaluatorValues(row, saved);
    setStatus(`Evaluator scores saved (${shortId}).`);
  } catch (err) {
    setStatus(`Failed to save evaluator scores (${shortId}): ${err.message}`, true);
    throw err;
  }
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

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#96;");
}
