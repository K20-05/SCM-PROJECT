import { formatLabel, roleHomePath, roleLabel, titleForRole } from "./format.js";

export function createUi({ grid, welcomeCard, contentWrapper, brandHome, sideNav }) {
  function setVerifiedRole(role) {
    document.body.classList.remove("role-user", "role-admin", "role-super-admin");
    document.body.classList.add(`role-${role.replace("_", "-")}`);
  }

  function setBrandHome(role, dashboardUrl) {
    if (!brandHome) return;
    const target = dashboardUrl || roleHomePath(role);
    brandHome.onclick = () => {
      window.location.href = target;
    };
  }

  function revealDashboard() {
    if (!contentWrapper) return;
    contentWrapper.classList.remove("loading");
    contentWrapper.classList.add("ready");
  }

  function setWelcome(role, user) {
    const name = user?.name || "there";
    welcomeCard.querySelector("h1").textContent = titleForRole(role);
    welcomeCard.querySelector("p").textContent = `Signed in as ${name} with ${roleLabel(role)} access.`;
  }

  function setSidebarUser(role, user) {
    if (!sideNav) return;
    sideNav.querySelector(".sidebar-account")?.remove();

    const account = document.createElement("section");
    account.className = "sidebar-account";

    const icon = document.createElement("i");
    icon.className = "fa-solid fa-circle-user";
    icon.setAttribute("aria-hidden", "true");

    const details = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = user?.name || "User";
    const meta = document.createElement("span");
    meta.textContent = roleLabel(role);

    const status = document.createElement("span");
    status.className = `account-status ${user?.is_active ? "is-active" : "is-inactive"}`;
    status.textContent = user?.is_active ? "Active" : "Inactive";

    details.append(name, meta, status);
    account.append(icon, details);

    const logoutLink = sideNav.querySelector(".logout-link");
    if (logoutLink) {
      sideNav.insertBefore(account, logoutLink);
    } else {
      sideNav.appendChild(account);
    }
  }

  function setActiveSection(section) {
    const normalizedSection = section || "all";
    document.querySelectorAll("[data-view-section]").forEach((element) => {
      const sectionNames = (element.getAttribute("data-view-section") || "")
        .split(/[\s,]+/)
        .filter(Boolean);
      element.classList.toggle(
        "view-hidden",
        normalizedSection !== "all" && !sectionNames.includes(normalizedSection)
      );
    });

    document.querySelectorAll(".nav-link[data-section]").forEach((link) => {
      const isActive = link.getAttribute("data-section") === normalizedSection;
      link.classList.toggle("active", isActive);
      link.setAttribute("aria-current", isActive ? "page" : "false");
    });

    document.body.classList.remove("nav-open");
  }

  function setupSectionNavigation() {
    document.querySelectorAll(".nav-link[data-section]").forEach((link) => {
      link.addEventListener("click", () => {
        setActiveSection(link.getAttribute("data-section") || "all");
      });
    });
  }

  function markSection(element, sectionName) {
    element.setAttribute("data-view-section", sectionName);
    return element;
  }

  function card(className, title, value, sectionName = "overview") {
    const section = document.createElement("section");
    section.className = `card ${className}`;
    markSection(section, sectionName);
    const header = document.createElement("div");
    header.className = "metric-header";
    const icon = document.createElement("i");
    icon.className = `fa-solid ${metricIcon(title)}`;
    icon.setAttribute("aria-hidden", "true");
    const heading = document.createElement("h3");
    heading.textContent = title;
    header.append(icon, heading);
    const body = document.createElement("div");
    body.className = "value";
    body.textContent = value;
    section.append(header, body);
    return section;
  }

  function panel(title, children, sectionName = "overview") {
    const section = document.createElement("section");
    section.className = "card table-card";
    markSection(section, sectionName);
    const heading = document.createElement("h3");
    heading.textContent = title;
    const body = document.createElement("div");
    body.className = "table-scroll";
    children.forEach((child) => body.appendChild(child));
    section.append(heading, body);
    return section;
  }

  function textBlock(lines) {
    const box = document.createElement("div");
    lines.forEach((line) => {
      const p = document.createElement("p");
      p.textContent = line;
      box.appendChild(p);
    });
    return box;
  }

  function makeButton(label, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "theme-toggle";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }

  function table(headers, rows, emptyText) {
    if (!rows.length) {
      const p = document.createElement("p");
      p.className = "empty-state";
      p.textContent = emptyText || "No records found.";
      return p;
    }

    const tableEl = document.createElement("table");
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    headers.forEach((header) => {
      const th = document.createElement("th");
      th.textContent = header;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      row.forEach((cell, index) => {
        const td = document.createElement("td");
        if (isIdentifierColumn(headers[index])) {
          td.classList.add("identifier-cell");
        }
        if (cell instanceof Node) {
          td.appendChild(cell);
        } else if (isBadgeColumn(headers[index], cell)) {
          td.appendChild(statusBadge(cell));
        } else {
          td.textContent = cell == null || cell === "" ? "-" : String(cell);
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    tableEl.append(thead, tbody);
    return tableEl;
  }

  function paginatedTable(headers, rows, emptyText, pageSize = 8) {
    if (!rows.length) return table(headers, rows, emptyText);

    let page = 1;
    const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
    const wrapper = document.createElement("div");
    const tableHost = document.createElement("div");
    const controls = document.createElement("div");
    const status = document.createElement("span");
    const prev = makeButton("Previous", () => {
      page = Math.max(1, page - 1);
      renderPage();
    });
    const next = makeButton("Next", () => {
      page = Math.min(pageCount, page + 1);
      renderPage();
    });

    controls.className = "pager";
    status.className = "pager-status";
    controls.append(prev, status, next);
    wrapper.append(tableHost, controls);

    function renderPage() {
      const start = (page - 1) * pageSize;
      tableHost.replaceChildren(table(headers, rows.slice(start, start + pageSize), emptyText));
      status.textContent = `Page ${page} of ${pageCount}`;
      prev.disabled = page === 1;
      next.disabled = page === pageCount;
    }

    renderPage();
    return wrapper;
  }

  function errorPanel(title, result, sectionName) {
    if (Array.isArray(result) || !result?.error) return null;
    return panel(title, [textBlock([result.error])], sectionName);
  }

  return {
    grid,
    setActiveSection,
    setBrandHome,
    setVerifiedRole,
    revealDashboard,
    setWelcome,
    setSidebarUser,
    setupSectionNavigation,
    card,
    panel,
    textBlock,
    makeButton,
    table,
    paginatedTable,
    errorPanel,
  };
}

function isBadgeColumn(header, value) {
  const normalizedHeader = String(header || "").toLowerCase();
  const normalizedValue = String(value || "").toLowerCase();
  return (
    ["role", "status", "current role"].includes(normalizedHeader) &&
    [
      "user",
      "admin",
      "super_admin",
      "active",
      "inactive",
      "available",
      "assigned",
      "pending",
      "in_transit",
      "out_for_delivery",
      "delivered",
      "cancelled",
    ].includes(normalizedValue)
  );
}

function isIdentifierColumn(header) {
  const normalizedHeader = String(header || "").toLowerCase();
  return (
    normalizedHeader.includes("id") ||
    normalizedHeader.includes("number") ||
    normalizedHeader.includes("container") ||
    normalizedHeader.includes("device") ||
    normalizedHeader.includes("tracking")
  );
}

function statusBadge(value) {
  const span = document.createElement("span");
  const normalized = String(value || "").toLowerCase();
  span.className = `badge badge-${normalized.replace(/_/g, "-")}`;
  span.textContent = formatLabel(value);
  return span;
}

function metricIcon(title) {
  const normalized = String(title || "").toLowerCase();
  if (normalized.includes("pending")) return "fa-clock";
  if (normalized.includes("transit")) return "fa-truck-fast";
  if (normalized.includes("delivered")) return "fa-circle-check";
  if (normalized.includes("delivery")) return "fa-calendar-day";
  if (normalized.includes("shipment")) return "fa-box";
  if (normalized.includes("backend") || normalized.includes("health") || normalized.includes("platform")) return "fa-signal";
  if (normalized.includes("user")) return "fa-users";
  if (normalized.includes("admin")) return "fa-user-shield";
  if (normalized.includes("device")) return "fa-microchip";
  return "fa-chart-simple";
}
