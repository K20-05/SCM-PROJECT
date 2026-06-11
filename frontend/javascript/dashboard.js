import { createApiClient } from "./dashboard/api.js";
import { normalizeRole } from "./dashboard/format.js";
import { getStoredSession, logout, redirectToLogin, rememberDashboard } from "./dashboard/session.js";
import { createUi } from "./dashboard/ui.js";
import { createDashboardViews } from "./dashboard/views.js?v=user-list-eight-rows-20260610-1";

window.addEventListener("pagehide", () => {
  document.body.classList.add("auth-suspended");
});

window.addEventListener("pageshow", (event) => {
  const navigation = performance.getEntriesByType("navigation")[0];
  const restoredFromHistory = event.persisted || navigation?.type === "back_forward";
  if (!restoredFromHistory) {
    document.body.classList.remove("auth-suspended");
    return;
  }

  logout();
});

window.addEventListener("popstate", () => {
  logout();
});

const { token, tokenType } = getStoredSession();
const grid = document.querySelector(".grid");
const welcomeCard = document.querySelector(".welcome");
const contentWrapper = document.getElementById("content-wrapper");
const navToggle = document.getElementById("nav-toggle");
const sideNav = document.getElementById("side-nav");
const brandHome = document.getElementById("brand-home");

if (!token) {
  redirectToLogin();
} else {
  init();
}

async function init() {
  const api = createApiClient({ token, tokenType });
  const ui = createUi({ grid, welcomeCard, contentWrapper, brandHome, sideNav });
  const views = createDashboardViews({ api, ui });

  const sidebarLogoutBtn = document.getElementById("sidebar-logout-btn");
  if (sidebarLogoutBtn) sidebarLogoutBtn.addEventListener("click", logout);
  if (navToggle && sideNav) {
    navToggle.addEventListener("click", () => {
      document.body.classList.toggle("nav-open");
    });
  }
  ui.setupSectionNavigation();

  try {
    const session = await api("/api/dashboard/me");
    if (!session) return;

    const role = normalizeRole(session.role);
    ui.setVerifiedRole(role);
    rememberDashboard(role, session.dashboard_url);
    ui.setBrandHome(role, session.dashboard_url);
    ui.setSidebarUser(role, session.user);

    if (window.location.pathname === "/dashboard" && session.dashboard_url) {
      window.history.replaceState(null, "", session.dashboard_url);
    }

    const dashboard = await api(`/api/dashboard/${role === "super_admin" ? "super-admin" : role}`);
    if (role === "super_admin") await views.renderSuperAdmin(dashboard);
    else if (role === "admin") await views.renderAdmin(dashboard);
    else await views.renderUser(dashboard);
    ui.setActiveSection("overview");
    ui.revealDashboard();
  } catch (error) {
    ui.setVerifiedRole("user");
    ui.setWelcome("user", { name: "there" });
    ui.grid.appendChild(ui.panel("Dashboard status", [ui.textBlock([error.message])]));
    ui.revealDashboard();
  }
}
