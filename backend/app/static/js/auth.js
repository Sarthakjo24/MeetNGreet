const authDom = {
  status: document.getElementById("auth-status"),
  googleBtn: document.getElementById("google-sso-btn"),
  microsoftBtn: document.getElementById("microsoft-sso-btn")
};

const nextPath = safeNextPath(new URLSearchParams(window.location.search).get("next"));

initializeAuthPage();

async function initializeAuthPage() {
  bindProviderButtons();

  const session = await AuthClient.getSession();
  if (session) {
    window.location.href = nextPath;
    return;
  }

  setAuthStatus("");
}

function bindProviderButtons() {
  if (authDom.googleBtn) {
    authDom.googleBtn.addEventListener("click", (event) => {
      event.preventDefault();
      redirectToProvider("google", authDom.googleBtn);
    });
  }

  if (authDom.microsoftBtn) {
    authDom.microsoftBtn.addEventListener("click", (event) => {
      event.preventDefault();
      redirectToProvider("microsoft", authDom.microsoftBtn);
    });
  }
}

function redirectToProvider(provider, button) {
  setButtonsLoading(true, button);
  setAuthStatus(`Redirecting to ${provider === "google" ? "Google" : "Microsoft"}...`);
  window.location.href = buildSsoUrl(provider);
}

function buildSsoUrl(provider) {
  const params = new URLSearchParams();
  params.set("provider", provider);
  params.set("next", nextPath);
  return `/api/auth/auth0/login?${params.toString()}`;
}

function setButtonsLoading(isLoading, activeButton) {
  const buttons = [authDom.googleBtn, authDom.microsoftBtn].filter(Boolean);
  buttons.forEach((btn) => {
    btn.classList.toggle("loading", isLoading);
    btn.setAttribute("aria-disabled", isLoading ? "true" : "false");
  });

  if (activeButton && isLoading) {
    activeButton.classList.add("loading");
  }
}

function setAuthStatus(message, isError = false) {
  authDom.status.textContent = message;
  authDom.status.style.color = isError ? "#fb2c36" : "#e2e8f0";
}

function safeNextPath(value) {
  if (!value) return "/interview";
  if (!value.startsWith("/") || value.startsWith("//")) return "/interview";
  return value;
}
