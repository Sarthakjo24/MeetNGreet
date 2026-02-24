const api = {
  results: "/api/admin/results",
  sessionJson: (sessionId) => `/api/admin/sessions/${sessionId}/json`,
  sessionDelete: (sessionId) => `/api/admin/sessions/${sessionId}`,
  sessionStandard: (sessionId) => `/admin/sessions/${sessionId}`
};
const RESULTS_LIMIT = 200;
const ADMIN_FETCH_TIMEOUT_MS = 15000;

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
      <td class="px-4 py-3 text-slate-200 font-medium text-center w-[72px] whitespace-nowrap">${formatCategoryTotal(row.confidence_total)}</td>
      <td class="px-4 py-3 text-slate-200 font-medium text-center w-[56px] whitespace-nowrap">${formatCategoryTotal(row.communication_total)}</td>
      <td class="px-4 py-3 text-slate-200 font-medium text-center w-[72px] whitespace-nowrap">${formatCategoryTotal(row.content_total)}</td>
      <td class="px-4 py-3 font-semibold text-brand-400 text-center w-[72px] whitespace-normal break-words">${formatScore(row.final_score, row.status_label)}</td>

      <!-- Evaluator editable columns -->
      <td class="px-2 py-2 text-center w-[72px]"><input data-session-id="${escapeAttr(row.session_id)}" data-eval-field="eval_confidence" type="number" min="0" max="10" step="1" class="w-full bg-transparent text-slate-100 text-center outline-none" value="${row.eval_confidence ?? ""}"/></td>
      <td class="px-2 py-2 text-center w-[56px]"><input data-session-id="${escapeAttr(row.session_id)}" data-eval-field="eval_communication" type="number" min="0" max="10" step="1" class="w-full bg-transparent text-slate-100 text-center outline-none" value="${row.eval_communication ?? ""}"/></td>
      <td class="px-2 py-2 text-center w-[72px]"><input data-session-id="${escapeAttr(row.session_id)}" data-eval-field="eval_content" type="number" min="0" max="10" step="1" class="w-full bg-transparent text-slate-100 text-center outline-none" value="${row.eval_content ?? ""}"/></td>
      <td class="px-2 py-2 text-center w-[72px]"><input data-session-id="${escapeAttr(row.session_id)}" data-eval-field="eval_score" type="number" min="0" max="10" step="1" class="w-full bg-transparent text-slate-100 text-center outline-none" value="${row.eval_score ?? ""}"/></td>
      <td class="px-4 py-3">
        <div class="flex flex-wrap gap-2">
          <a class="rounded-lg border border-[#7eddfa]/70 bg-gradient-to-b from-[#2b7fff] to-[#235fbd] px-3 py-1.5 text-xs font-semibold text-white hover:brightness-105" href="${api.sessionJson(encodeURIComponent(row.session_id))}" target="_blank" rel="noopener">View JSON</a>
          <a class="rounded-lg border border-[#bbf451]/70 bg-gradient-to-b from-[#68b32f] to-[#4d8f21] px-3 py-1.5 text-xs font-semibold text-white hover:brightness-105" href="${api.sessionStandard(encodeURIComponent(row.session_id))}">View Standard Response</a>
        </div>
      </td>
      <td class="px-4 py-3 text-slate-300">${formatDate(row.created_at)}</td>
      <td class="px-4 py-3 text-slate-300">${formatDate(row.submitted_at)}</td>
      <td class="px-4 py-3 text-slate-200">${escapeHtml(row.session_id || "-")}</td>
      <td class="px-4 py-3 max-w-[120px] whitespace-normal break-words">${escapeHtml(row.candidate_id || "")}</td>
      <td class="px-4 py-3">
        <button type="button" class="delete-btn rounded-lg border border-[#fb2c36]/65 bg-[#fb2c36]/90 px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#fb2c36]" data-session-id="${escapeAttr(row.session_id)}">
          Delete
        </button>
      </td>
    `;
    dom.body.appendChild(tr);
  });
}

async function onTableClick(event) {
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

  // allow only digits, remove other characters
  const raw = String(input.value || "");
  const cleaned = raw.replace(/[^0-9]/g, "");
  if (cleaned !== raw) {
    input.value = cleaned;
  }

  // clamp to allowed range
  const min = Number(input.getAttribute('min') || 0);
  const max = Number(input.getAttribute('max') || 9999);
  let v = cleaned === "" ? null : parseInt(cleaned, 10);
  if (v !== null) {
    if (v < min) v = min;
    if (v > max) v = max;
    input.value = String(v);
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
