(() => {
  const root = document.getElementById("root");
  if (!root) return;

  root.innerHTML = `
    <main class="relative min-h-screen overflow-hidden px-4 py-6 sm:px-6">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_15%_10%,rgba(22,173,217,.22),transparent_38%),radial-gradient(circle_at_90%_90%,rgba(126,221,250,.16),transparent_44%)]"></div>
      <div class="relative mx-auto w-full max-w-7xl space-y-5">
        <header class="rounded-2xl border border-brand-400/35 bg-slate-900/80 p-5 shadow-[0_24px_70px_rgba(0,0,0,.42)] backdrop-blur-xl">
          <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p class="text-xs font-semibold tracking-[.18em] text-brand-400">ADMIN PORTAL</p>
              <h1 class="mt-1 text-2xl font-bold text-white sm:text-3xl">MeetnGreet Admin Dashboard</h1>
              <p class="mt-1 text-sm text-slate-300">Session overview, score tracking and candidate records</p>
            </div>
            <div class="flex flex-wrap gap-3">
              <a href="/interview" class="inline-flex items-center rounded-lg border border-brand-400/60 bg-brand-500/15 px-4 py-2 text-sm font-semibold text-brand-400 hover:bg-brand-500/25">
                Open Candidate Panel
              </a>
              <button id="refresh-btn" type="button" class="rounded-lg border border-[#ffb15c]/75 bg-gradient-to-b from-[#ff9f2e] to-[#d97800] px-4 py-2 text-sm font-semibold text-white shadow-[0_12px_30px_rgba(255,137,4,.35)]">
                Refresh
              </button>
            </div>
          </div>
        </header>

        <section class="rounded-2xl border border-brand-400/35 bg-slate-900/80 p-5 shadow-[0_20px_55px_rgba(0,0,0,.38)]">
          <p id="admin-status" class="status mb-4 rounded-lg border border-brand-400/25 bg-slate-800/65 p-3 text-sm text-slate-200" aria-live="polite">
            Loading sessions...
          </p>
          <div class="overflow-x-auto rounded-xl border border-brand-400/30">
            <table class="min-w-full divide-y divide-brand-400/25 text-left text-sm">
              <thead class="bg-slate-800/85 text-xs font-semibold uppercase tracking-wide text-brand-400">
                <tr>
                  <th class="px-4 py-3">Candidate ID</th>
                  <th class="px-4 py-3">Email</th>
                  <th class="px-4 py-3">Delete</th>
                  <th class="px-4 py-3">Session ID</th>
                  <th class="px-4 py-3">Score</th>
                  <th class="px-4 py-3">Created Date and Time</th>
                  <th class="px-4 py-3">Submitted Date and Time</th>
                  <th class="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody id="admin-results-body" class="divide-y divide-brand-400/20 bg-slate-900/65 text-slate-100"></tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  `;
})();
