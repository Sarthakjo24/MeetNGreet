const AuthClient = (() => {
  async function getSession() {
    const res = await fetch("/api/auth/session", {
      method: "GET",
      credentials: "same-origin"
    });
    if (!res.ok) {
      return null;
    }
    return res.json();
  }

  async function requireAuth() {
    const session = await getSession();
    if (!session) {
      window.location.href = "/auth?next=/interview";
      throw new Error("Authentication required.");
    }
    return session;
  }

  async function logout() {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin"
    });
  }

  return {
    getSession,
    requireAuth,
    logout
  };
})();

window.AuthClient = AuthClient;
