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
              <p class="text-xs font-semibold tracking-[.18em] text-brand-400">INTERVIEW PORTAL</p>
              <h1 class="mt-1 text-2xl font-bold text-white sm:text-3xl">MeetnGreet Interview Console</h1>
            </div>
            <div class="flex flex-wrap gap-3">
              <a href="/admin" class="inline-flex items-center rounded-lg border border-[#e4ff4f]/80 bg-[#e4ff4f] px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-[#efff73]">
                Open Admin Dashboard
              </a>
              <button id="logout-btn" type="button" class="rounded-lg border border-[#fb2c36]/70 bg-gradient-to-b from-[#fb2c36] to-[#c51b24] px-4 py-2 text-sm font-semibold text-white shadow-[0_12px_30px_rgba(251,44,54,.32)] hover:brightness-105">
                Logout
              </button>
            </div>
          </div>
        </header>

        <section id="start-panel" class="rounded-2xl border border-brand-400/35 bg-slate-900/80 p-5 shadow-[0_20px_55px_rgba(0,0,0,.38)]">
          <h2 class="text-xl font-bold text-white">Start Interview</h2>
          <div class="mt-4 grid gap-3 sm:grid-cols-2">
            <div class="rounded-xl border border-brand-400/30 bg-slate-800/65 p-3 text-sm">
              <span class="font-semibold text-slate-300">Signed in as: </span>
              <span id="signed-in-email" class="text-white">-</span>
            </div>
            <div class="rounded-xl border border-brand-400/30 bg-slate-800/65 p-3 text-sm">
              <span class="font-semibold text-slate-300">Provider: </span>
              <span id="signed-in-provider" class="text-white">-</span>
            </div>
          </div>
          <button id="start-btn" type="button" class="mt-5 rounded-lg border border-[#bbf451]/75 bg-gradient-to-b from-[#7fcf3e] to-[#5ea92d] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_12px_30px_rgba(94,169,45,.35)]">
            Start Interview
          </button>
          <p id="start-status" class="status hidden mt-3 text-sm text-slate-300"></p>
        </section>

        <section id="interview-panel" class="hidden rounded-2xl border border-brand-400/35 bg-slate-900/80 p-5 shadow-[0_20px_55px_rgba(0,0,0,.38)]">
          <div class="mb-4 grid gap-3 sm:grid-cols-2">
            <div class="rounded-xl border border-brand-400/30 bg-slate-800/65 p-3 text-sm">
              <span class="font-semibold text-slate-300">Session: </span>
              <span id="session-id" class="text-white">-</span>
            </div>
            <div class="rounded-xl border border-brand-400/30 bg-slate-800/65 p-3 text-sm">
              <span class="font-semibold text-slate-300">Progress: </span>
              <span id="progress" class="text-white">0 / 5</span>
            </div>
          </div>

          <div class="grid gap-4 xl:grid-cols-[minmax(380px,1.15fr)_minmax(280px,1fr)]">
            <div class="video-wrap relative overflow-hidden rounded-xl border border-brand-400/45 bg-black/80">
              <video id="preview" autoplay muted playsinline class="h-full min-h-[260px] w-full object-cover"></video>
              <div id="camera-timer" class="camera-timer absolute right-3 top-3 rounded-full border border-brand-400/60 bg-slate-950/85 px-3 py-1 text-xs font-bold text-white">01:30</div>
            </div>

            <div class="space-y-4">
              <div class="question-block rounded-xl border border-brand-400/30 bg-slate-800/70 p-4">
                <h3 id="question-title" class="text-lg font-semibold text-white">Question</h3>
                <p id="question-text" class="mt-2 text-sm leading-relaxed text-slate-200">-</p>
              </div>

              <div class="controls grid gap-2 sm:grid-cols-3">
                <button id="record-btn" type="button" class="rounded-lg border border-[#bbf451]/75 bg-gradient-to-b from-[#7fcf3e] to-[#5ea92d] px-3 py-2 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(94,169,45,.35)]">
                  Start Response
                </button>
                <button id="stop-btn" type="button" disabled class="rounded-lg border border-[#ff8904]/70 bg-gradient-to-b from-[#ff8904] to-[#d96c00] px-3 py-2 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(255,137,4,.32)]">
                  Stop Response
                </button>
                <button id="next-btn" type="button" disabled class="rounded-lg border border-brand-400/75 bg-gradient-to-b from-[#2b7fff] to-[#235fbd] px-3 py-2 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(43,127,255,.32)]">
                  Next Question
                </button>
              </div>

              <p id="record-status" class="status rounded-lg border border-brand-400/25 bg-slate-800/60 p-3 text-sm text-slate-200">Ready</p>
            </div>
          </div>
        </section>

        <section id="thankyou-panel" class="hidden rounded-2xl border border-brand-400/35 bg-slate-900/80 p-8 text-center shadow-[0_20px_55px_rgba(0,0,0,.38)]">
          <div class="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full border border-[#bbf451]/65 bg-[#bbf451]/15 text-lg font-bold">OK</div>
          <h2 class="text-2xl font-bold text-white">Interview Completed</h2>
          <p class="mx-auto mt-3 max-w-xl text-slate-300">
            Thank you for the interview. The team will email you for further enquiry in 48 hours.
          </p>
        </section>
      </div>
    </main>
  `;
})();
