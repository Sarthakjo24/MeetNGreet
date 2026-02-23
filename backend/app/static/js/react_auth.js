(() => {
  const root = document.getElementById("root");
  if (!root) return;

  root.innerHTML = `
    <main class="auth-fallback-main relative min-h-screen overflow-hidden">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_15%_10%,rgba(22,173,217,.22),transparent_38%),radial-gradient(circle_at_90%_90%,rgba(126,221,250,.16),transparent_44%)]"></div>
      <section class="relative mx-auto flex min-h-screen w-full max-w-6xl items-center justify-center p-6">
        <div class="auth-fallback-panel w-full max-w-md rounded-2xl border border-brand-400/40 bg-slate-900/80 p-8 shadow-[0_25px_80px_rgba(0,0,0,.45)] backdrop-blur-xl">
          <div class="mb-6 text-center">
            <p class="mb-2 inline-flex rounded-full border border-brand-400/45 bg-brand-500/15 px-3 py-1 text-xs font-semibold tracking-[.22em] text-brand-400">
              AUTHENTICATION
            </p>
            <h1 id="login-heading" class="text-3xl font-extrabold uppercase tracking-wide text-white">
              MEETNGREET SYSTEM LOGIN
            </h1>
          </div>

          <div class="space-y-4" role="group" aria-label="Single Sign-On providers">
            <a
              id="google-sso-btn"
              href="/api/auth/auth0/login?provider=google&next=/interview"
              class="flex h-14 items-center gap-3 rounded-xl border border-[#bbf451]/65 bg-gradient-to-b from-[#6bb535] to-[#4a8f24] px-4 text-base font-semibold text-white shadow-[0_14px_30px_rgba(106,181,53,.35)] transition hover:-translate-y-0.5 hover:brightness-105 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#e4ff4f]"
            >
              <span class="grid h-9 w-9 place-items-center rounded-lg border border-white/30 bg-white/15 text-lg font-black">G+</span>
              <span>Sign in with Google</span>
            </a>

            <a
              id="microsoft-sso-btn"
              href="/api/auth/auth0/login?provider=microsoft&next=/interview"
              class="flex h-14 items-center gap-3 rounded-xl border border-brand-400/70 bg-gradient-to-b from-[#2b7fff] to-[#1f63cb] px-4 text-base font-semibold text-white shadow-[0_14px_30px_rgba(43,127,255,.35)] transition hover:-translate-y-0.5 hover:brightness-105 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            >
              <span class="grid h-9 w-9 place-items-center rounded-lg border border-white/30 bg-white/15 text-lg font-black">M</span>
              <span>Sign in with Microsoft</span>
            </a>
          </div>

          <p
            id="auth-status"
            class="mt-4 min-h-5 text-center text-sm text-slate-300"
            aria-live="polite"
          ></p>
        </div>
      </section>
    </main>
  `;
})();
