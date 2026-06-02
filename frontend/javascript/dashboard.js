(() => {
  const token = localStorage.getItem("access_token");
  const tokenType = localStorage.getItem("token_type") || "bearer";
  const grid = document.querySelector(".grid");
  const welcomeCard = document.querySelector(".welcome");
  const contentWrapper = document.getElementById("content-wrapper");
  const navToggle = document.getElementById("nav-toggle");
  const sideNav = document.getElementById("side-nav");
  const brandHome = document.getElementById("brand-home");

  if (!token) {
    window.location.href = "/login";
    return;
  }

  const headers = {
    Authorization: `${tokenType} ${token}`,
    "Content-Type": "application/json",
  };

  function clearSession() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("user_role");
    localStorage.removeItem("dashboard_url");
  }

  function logout() {
    clearSession();
    window.location.href = "/login";
  }

  function normalizeRole(role) {
    return String(role || "user").trim().toLowerCase();
  }

  function titleForRole(role) {
    if (role === "super_admin") return "Super Admin Dashboard";
    if (role === "admin") return "Admin Dashboard";
    return "User Dashboard";
  }

  function roleLabel(role) {
    if (role === "super_admin") return "super admin";
    return role || "user";
  }

  function setVerifiedRole(role) {
    document.body.classList.remove("role-user", "role-admin", "role-super-admin");
    document.body.classList.add(`role-${role.replace("_", "-")}`);
  }

  function roleHomePath(role) {
    if (role === "super_admin") return "/dashboard/super-admin";
    if (role === "admin") return "/dashboard/admin";
    return "/dashboard/user";
  }

  function setBrandHome(role, dashboardUrl) {
    if (!brandHome) return;
    const target = dashboardUrl || roleHomePath(role);
    brandHome.addEventListener("click", () => {
      window.location.href = target;
    }, { once: true });
  }

  function revealDashboard() {
    if (!contentWrapper) return;
    contentWrapper.classList.remove("loading");
    contentWrapper.classList.add("ready");
  }

  function setWelcome(role, user) {
    const name = user?.name || "there";
    welcomeCard.querySelector("h1").textContent = titleForRole(role);
    welcomeCard.querySelector("p").textContent = `Welcome back, ${name}. Access level: ${roleLabel(role)}.`;
  }

  function setActiveSection(section) {
    const normalizedSection = section || "all";
    document.querySelectorAll("[data-view-section]").forEach((element) => {
      const sectionName = element.getAttribute("data-view-section");
      element.classList.toggle("view-hidden", normalizedSection !== "all" && sectionName !== normalizedSection);
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
    const heading = document.createElement("h3");
    heading.textContent = title;
    const body = document.createElement("div");
    body.className = "value";
    body.textContent = value;
    section.append(heading, body);
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
    section.appendChild(heading);
    section.appendChild(body);
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

  function formatDateTime(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString();
  }

  function formatDateInputValue(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toISOString().slice(0, 16);
  }

  function formatLabel(value) {
    if (value == null || value === "") return "-";
    return String(value)
      .replace(/_/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
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

  function makeButton(label, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "theme-toggle";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        ...headers,
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => null);
    if (response.status === 401) {
      logout();
      return null;
    }
    if (!response.ok) {
      throw new Error(data?.detail || `Request failed: ${path}`);
    }
    return data;
  }

  async function loadList(path) {
    try {
      return await api(path);
    } catch (error) {
      return { error: error.message, items: [] };
    }
  }

  function listItems(result) {
    return Array.isArray(result) ? result : result.items || [];
  }

  function errorPanel(title, result, sectionName) {
    if (Array.isArray(result) || !result?.error) return null;
    return panel(title, [textBlock([result.error])], sectionName);
  }

  function renderPermissions(dashboard) {
    const allowed = dashboard.permissions || [];
    const restricted = dashboard.restricted || [];
    grid.appendChild(card("metric", "Allowed actions", allowed.length));
    grid.appendChild(card("metric", "Restricted actions", restricted.length));
    grid.appendChild(card("metric", "Backend status", "Online"));
  }

  function renderProfile(user) {
    const form = document.createElement("form");
    form.className = "stack-form";
    form.innerHTML = `
      <label>Name<input name="name" value="${escapeHtml(user.name)}" required></label>
      <label>Email<input name="email" value="${escapeHtml(user.email)}" readonly></label>
      <label>Phone<input name="phone" value="${escapeHtml(user.phone)}" required></label>
    `;
    const message = document.createElement("p");
    const save = makeButton("Save profile", async () => {
      const payload = Object.fromEntries(new FormData(form).entries());
      message.textContent = "";
      save.disabled = true;
      try {
        const updated = await api("/api/users/me", {
          method: "PUT",
          body: JSON.stringify({ name: payload.name, phone: payload.phone }),
        });
        user.name = updated.name || payload.name;
        user.phone = updated.phone || payload.phone;
        setWelcome(normalizeRole(user.role), user);
        message.textContent = "Profile updated.";
      } catch (error) {
        message.textContent = error.message;
      } finally {
        save.disabled = false;
      }
    });
    form.append(save, message);

    grid.appendChild(
      panel("Profile", [
        form,
        textBlock([
          `User ID: ${user.id || "-"}`,
          `Status: ${user.is_active ? "active" : "inactive"}`,
        ]),
      ], "profile")
    );
  }

  function renderPasswordPanel(sectionName = "profile") {
    const form = document.createElement("form");
    form.className = "stack-form";
    form.innerHTML = `
      <label>Current password<input name="old_password" type="password" required></label>
      <label>New password<input name="new_password" type="password" required></label>
      <label>Confirm password<input name="confirm_new_password" type="password" required></label>
    `;
    const message = document.createElement("p");
    const submit = makeButton("Update password", async () => {
      const payload = Object.fromEntries(new FormData(form).entries());
      message.textContent = "";
      try {
        await api("/api/auth/change-password", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        form.reset();
        message.textContent = "Password updated.";
      } catch (error) {
        message.textContent = error.message;
      }
    });
    form.append(submit, message);
    grid.appendChild(panel("Security", [form], sectionName));
  }

  function shipmentRows(shipments) {
    return shipments.map((shipment) => [
      shipment.tracking_id,
      shipment.shipment_number,
      shipment.container_number,
      shipment.route_details,
      shipment.status,
      formatDateTime(shipment.expected_delivery_date),
      shipment.device_id || shipment.device || "-",
    ]);
  }

  function renderShipmentForm() {
    const form = document.createElement("form");
    form.className = "shipment-form";
    form.innerHTML = `
      <label>Shipment number<input name="shipment_number" required></label>
      <label>Container number<input name="container_number" required></label>
      <label>Route details<input name="route_details" required></label>
      <label>Goods type<input name="goods_type" required></label>
      <label>Requested device<input name="device" required></label>
      <label>Expected delivery<input name="expected_delivery_date" type="datetime-local" required></label>
      <label>PH number<input name="ph_number" required></label>
      <label>Delivery number<input name="delivery_number" required></label>
      <label>NDC number<input name="ndc_number" required></label>
      <label>Batch ID<input name="batch_id" required></label>
      <label>Serial number<input name="serial_number_of_goods" required></label>
      <label class="full-span">Description<textarea name="shipment_description" rows="3" required></textarea></label>
    `;
    const message = document.createElement("p");
    const submit = makeButton("Create shipment", async () => {
      const payload = Object.fromEntries(new FormData(form).entries());
      message.textContent = "";
      submit.disabled = true;
      try {
        const created = await api("/api/shipments", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        form.reset();
        message.textContent = `Shipment ${created.tracking_id} created.`;
      } catch (error) {
        message.textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
    form.append(submit, message);
    grid.appendChild(panel("New shipment", [form], "new-shipment"));
  }

  function editShipmentAction(shipment) {
    if (shipment.status !== "pending") return "Locked";

    const button = makeButton("Edit", () => {
      const form = document.createElement("form");
      form.className = "shipment-form";
      form.innerHTML = `
        <label>Shipment number<input name="shipment_number" value="${escapeHtml(shipment.shipment_number)}" required></label>
        <label>Container number<input name="container_number" value="${escapeHtml(shipment.container_number)}" required></label>
        <label>Route details<input name="route_details" value="${escapeHtml(shipment.route_details)}" required></label>
        <label>Goods type<input name="goods_type" value="${escapeHtml(shipment.goods_type)}" required></label>
        <label>Requested device<input name="device" value="${escapeHtml(shipment.device)}" required></label>
        <label>Expected delivery<input name="expected_delivery_date" type="datetime-local" value="${formatDateInputValue(shipment.expected_delivery_date)}" required></label>
        <label class="full-span">Description<textarea name="shipment_description" rows="3" required>${escapeHtml(shipment.shipment_description)}</textarea></label>
      `;
      const message = document.createElement("p");
      const save = makeButton("Save shipment", async () => {
        const payload = Object.fromEntries(new FormData(form).entries());
        save.disabled = true;
        message.textContent = "";
        try {
          await api(`/api/shipments/${shipment.tracking_id}`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          });
          message.textContent = "Shipment updated. Refreshing...";
          window.setTimeout(() => window.location.reload(), 700);
        } catch (error) {
          message.textContent = error.message;
          save.disabled = false;
        }
      });
      form.append(save, message);
      grid.appendChild(panel(`Edit ${shipment.tracking_id}`, [form], "shipments"));
      button.disabled = true;
    });
    return button;
  }

  async function renderMyShipments() {
    const result = await loadList("/api/shipments");
    const shipments = listItems(result);
    const error = errorPanel("My shipments status", result, "shipments");
    if (error) grid.appendChild(error);

    grid.appendChild(card("metric", "My shipments", shipments.length));
    grid.appendChild(card("metric", "Pending", shipments.filter((shipment) => shipment.status === "pending").length));
    grid.appendChild(card("metric", "Delivered", shipments.filter((shipment) => shipment.status === "delivered").length));
    grid.appendChild(
      panel("My shipments", [
        paginatedTable(
          ["Tracking ID", "Shipment", "Container", "Route", "Status", "Expected delivery", "Device"],
          shipmentRows(shipments),
          "No shipment requests found.",
          8
        ),
      ], "shipments")
    );
    grid.appendChild(
      panel("Editable pending shipments", [
        paginatedTable(
          ["Tracking ID", "Route", "Status", "Action"],
          shipments.map((shipment) => [shipment.tracking_id, shipment.route_details, shipment.status, editShipmentAction(shipment)]),
          "No shipment requests found.",
          8
        ),
      ], "shipments")
    );
  }

  async function renderUser(dashboard) {
    setWelcome("user", dashboard.user);
    renderPermissions(dashboard);
    await renderMyShipments();
    renderShipmentForm();
    renderProfile(dashboard.user);
    renderPasswordPanel("security");
  }

  async function renderAdmin(dashboard) {
    setWelcome("admin", dashboard.user);
    const metrics = dashboard.metrics || {};
    grid.appendChild(card("metric", "Users managed", metrics.users_managed ?? 0));
    grid.appendChild(card("metric", "Devices monitored", metrics.devices_monitored ?? 0));
    grid.appendChild(card("metric", "Shipments tracked", metrics.shipments_tracked ?? 0));

    const usersResult = await loadList("/api/admin/users");
    const devicesResult = await loadList("/api/devices");
    const shipmentsResult = await loadList("/api/shipments");
    const users = listItems(usersResult);
    const devices = listItems(devicesResult);
    const shipments = listItems(shipmentsResult);

    const usersError = errorPanel("User roster status", usersResult, "overview");
    const devicesError = errorPanel("Device inventory status", devicesResult, "devices");
    const shipmentsError = errorPanel("Shipment queue status", shipmentsResult, "operations");
    if (usersError) grid.appendChild(usersError);
    if (devicesError) grid.appendChild(devicesError);
    if (shipmentsError) grid.appendChild(shipmentsError);

    grid.appendChild(
      panel("User roster", [
        paginatedTable(
          ["Name", "Email", "Role", "Status"],
          users.map((user) => [user.name, user.email, user.role, user.is_active ? "active" : "inactive"]),
          "No users are currently registered.",
          8
        ),
      ])
    );
    grid.appendChild(
      panel("Device inventory", [
        table(
          ["Device ID", "Status", "Route"],
          devices.map((device) => [device.device_id, device.status, `${device.route_from || "-"} to ${device.route_to || "-"}`]),
          "No devices are currently registered."
        ),
      ], "devices")
    );
    grid.appendChild(
      panel("Shipment queue", [
        table(
          ["Tracking ID", "Device", "Status"],
          shipments.map((shipment) => [shipment.tracking_id, shipment.device_id || shipment.device, shipment.status]),
          "No shipments are currently tracked."
        ),
      ], "operations")
    );
    renderPasswordPanel();
  }

  function roleAction(user, currentUserId) {
    if (user.role === "super_admin" || user.id === currentUserId) {
      return "Locked";
    }

    const wrapper = document.createElement("div");
    const select = document.createElement("select");
    ["user", "admin"].forEach((role) => {
      const option = document.createElement("option");
      option.value = role;
      option.textContent = role;
      option.selected = user.role === role;
      select.appendChild(option);
    });

    const save = makeButton("Save", async () => {
      save.disabled = true;
      try {
        const updated = await api(`/api/admin/users/${user.id}/role`, {
          method: "PATCH",
          body: JSON.stringify({ role: select.value }),
        });
        user.role = updated.role;
        save.textContent = "Saved";
        setTimeout(() => {
          save.textContent = "Save";
        }, 1200);
      } catch (error) {
        save.textContent = "Error";
        setTimeout(() => {
          save.textContent = "Save";
        }, 1200);
      } finally {
        save.disabled = false;
      }
    });

    wrapper.append(select, save);
    return wrapper;
  }

  async function renderSuperAdmin(dashboard) {
    setWelcome("super_admin", dashboard.user);
    const metrics = dashboard.metrics || {};
    grid.appendChild(card("metric", "Total users", metrics.total_users ?? 0));
    grid.appendChild(card("metric", "Admin count", metrics.admin_count ?? 0));
    grid.appendChild(card("metric", "Active users", metrics.active_users ?? 0));
    grid.appendChild(card("metric", "Platform health", metrics.platform_health || "online"));
    grid.appendChild(card("metric", "Devices monitored", metrics.devices_monitored ?? 0));
    grid.appendChild(card("metric", "Shipments tracked", metrics.shipments_tracked ?? 0));
    grid.appendChild(card("metric", "Pending shipments", metrics.pending_shipments ?? 0));
    grid.appendChild(card("metric", "Assigned devices", metrics.assigned_devices ?? 0));

    grid.appendChild(
      panel("Recent logins", [
        table(
          ["Name", "Email", "Role", "Login time"],
          (dashboard.recent_logins || []).map((login) => [
            login.name,
            login.email,
            login.role,
            formatDateTime(login.logged_in_at),
          ]),
          "No login records found."
        ),
      ])
    );

    grid.appendChild(
      panel("Governance rules", [
        textBlock([
          "Super admin accounts are locked from role edits.",
          "Only user and admin roles can be changed from role governance.",
          "Self downgrade and self delete actions are blocked.",
        ]),
      ])
    );

    const usersResult = await loadList("/api/admin/users");
    const users = listItems(usersResult);
    const usersError = errorPanel("Role governance status", usersResult, "governance");
    if (usersError) grid.appendChild(usersError);
    grid.appendChild(
      panel("Role governance", [
        paginatedTable(
          ["Name", "Email", "Current role", "Action"],
          users.map((user) => [user.name, user.email, user.role, roleAction(user, dashboard.user.id)]),
          "No users are currently available for role governance.",
          8
        ),
      ], "governance")
    );

    const admins = users.filter((user) => user.role === "admin" || user.role === "super_admin");
    grid.appendChild(
      panel("Admin roster", [
        paginatedTable(
          ["Name", "Email", "Role", "Status"],
          admins.map((user) => [user.name, user.email, user.role, user.is_active ? "active" : "inactive"]),
          "No admin accounts are currently listed.",
          8
        ),
      ], "governance")
    );
    grid.appendChild(panel("System health", [textBlock(["Backend: online", "Database: reachable through protected API access"])], "health"));
    renderPasswordPanel();
  }

  async function init() {
    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) logoutBtn.addEventListener("click", logout);
    const sidebarLogoutBtn = document.getElementById("sidebar-logout-btn");
    if (sidebarLogoutBtn) sidebarLogoutBtn.addEventListener("click", logout);
    if (navToggle && sideNav) {
      navToggle.addEventListener("click", () => {
        document.body.classList.toggle("nav-open");
      });
    }
    setupSectionNavigation();

    try {
      const session = await api("/api/dashboard/me");
      if (!session) return;

      const role = normalizeRole(session.role);
      setVerifiedRole(role);
      localStorage.setItem("user_role", role);
      localStorage.setItem("dashboard_url", session.dashboard_url);
      setBrandHome(role, session.dashboard_url);

      if (window.location.pathname === "/dashboard" && session.dashboard_url) {
        window.history.replaceState(null, "", session.dashboard_url);
      }

      const dashboard = await api(`/api/dashboard/${role === "super_admin" ? "super-admin" : role}`);
      if (role === "super_admin") await renderSuperAdmin(dashboard);
      else if (role === "admin") await renderAdmin(dashboard);
      else await renderUser(dashboard);
      setActiveSection("overview");
      revealDashboard();
    } catch (error) {
      setVerifiedRole("user");
      setWelcome("user", { name: "there" });
      grid.appendChild(panel("Dashboard status", [textBlock([error.message])]));
      revealDashboard();
    }
  }

  init();
})();
