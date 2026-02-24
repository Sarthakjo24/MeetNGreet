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
              <p class="text-xs font-semibold tracking-[.18em] text-brand-400">CANDIDATE DETAIL</p>
              <h1 class="mt-1 text-2xl font-bold text-white sm:text-3xl">Candidate Standard Response</h1>
              <p class="mt-1 text-sm text-slate-300">Video, transcript, score and evaluation insights</p>
            </div>
            <a href="/admin" class="inline-flex items-center rounded-lg border border-[#fb2c36]/70 bg-gradient-to-b from-[#fb2c36] to-[#c51b24] px-4 py-2 text-sm font-semibold text-white shadow-[0_12px_30px_rgba(251,44,54,.32)] hover:brightness-105">
              Back to Dashboard
            </a>
          </div>
        </header>

        <section class="rounded-2xl border border-brand-400/35 bg-slate-900/80 p-5 shadow-[0_20px_55px_rgba(0,0,0,.38)]">
          <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div class="meta-item rounded-xl border border-brand-400/30 bg-slate-800/65 p-3 text-sm"><span class="font-semibold text-slate-300">Candidate ID: </span><span id="meta-candidate" class="text-white">-</span></div>
            <div class="meta-item rounded-xl border border-brand-400/30 bg-slate-800/65 p-3 text-sm"><span class="font-semibold text-slate-300">Candidate Email: </span><span id="meta-candidate-email" class="text-white">-</span></div>
            <div class="meta-item rounded-xl border border-brand-400/30 bg-slate-800/65 p-3 text-sm"><span class="font-semibold text-slate-300">Session ID: </span><span id="meta-session" class="text-white">-</span></div>
            <div class="meta-item rounded-xl border border-brand-400/30 bg-slate-800/65 p-3 text-sm"><span class="font-semibold text-slate-300">Session Score: </span><span id="meta-score" class="text-white">-</span></div>
            <div class="meta-item rounded-xl border border-brand-400/30 bg-slate-800/65 p-3 text-sm"><span class="font-semibold text-slate-300">Communication Avg: </span><span id="meta-communication-avg" class="text-brand-400">-</span></div>
            <div class="meta-item rounded-xl border border-brand-400/30 bg-slate-800/65 p-3 text-sm"><span class="font-semibold text-slate-300">Content Avg: </span><span id="meta-content-avg" class="text-brand-400">-</span></div>
            <div class="meta-item rounded-xl border border-brand-400/30 bg-slate-800/65 p-3 text-sm"><span class="font-semibold text-slate-300">Confidence Avg: </span><span id="meta-confidence-avg" class="text-brand-400">-</span></div>
            <div class="meta-item rounded-xl border border-brand-400/30 bg-slate-800/65 p-3 text-sm"><span class="font-semibold text-slate-300">Submitted At: </span><span id="meta-submitted" class="text-white">-</span></div>
          </div>

          <p id="response-status" class="status mt-4 rounded-lg border border-brand-400/25 bg-slate-800/65 p-3 text-sm text-slate-200" aria-live="polite">
            Loading candidate responses...
          </p>
        </section>

        <section id="response-list" class="space-y-4"></section>
      </div>
    </main>
  `;
})();
