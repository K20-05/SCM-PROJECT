export function getStoredSession() {
  const token = sessionStorage.getItem("access_token") || localStorage.getItem("access_token");
  const tokenType = sessionStorage.getItem("token_type") || localStorage.getItem("token_type") || "bearer";
  return { token, tokenType };
}

export function clearSession() {
  ["access_token", "token_type", "user_role", "dashboard_url"].forEach((key) => {
    sessionStorage.removeItem(key);
    localStorage.removeItem(key);
  });
}

export function redirectToLogin() {
  window.location.replace("/login");
}

export function logout() {
  clearSession();
  redirectToLogin();
}

export function rememberDashboard(role, dashboardUrl) {
  sessionStorage.setItem("user_role", role);
  sessionStorage.setItem("dashboard_url", dashboardUrl);
}
