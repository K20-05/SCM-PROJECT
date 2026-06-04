import { listItems, loadList } from "./api.js";
import { escapeHtml, formatDateInputValue, formatDateTime, normalizeRole } from "./format.js";

const SHIPMENT_STATUSES = ["pending", "in_transit", "out_for_delivery", "delivered", "cancelled"];
const USER_SHIPMENTS_PATH = "/api/shipments?mine=true";
const DASHBOARD_TABLE_PAGE_SIZE = 5;
const GOVERNANCE_TABLE_PAGE_SIZE = 7;
const RECENT_LOGINS_PAGE_SIZE = 3;

export function createDashboardViews({ api, ui }) {
  function deliveryDate(value) {
    if (!value) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return date;
  }

  function dateOnlyParam(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function todayRange() {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setDate(start.getDate() + 1);
    return { start, end };
  }

  function statusCount(shipments, status) {
    return shipments.filter((shipment) => shipment.status === status).length;
  }

  function ownedShipments(result, user) {
    const userId = String(user?.id || "");
    return listItems(result).filter((shipment) => String(shipment.owner_id || "") === userId);
  }

  function upcomingDeliveries(shipments, days = 7) {
    const now = new Date();
    const limit = new Date(now);
    limit.setDate(now.getDate() + days);
    return shipments
      .filter((shipment) => {
        const expected = deliveryDate(shipment.expected_delivery_date);
        return expected && expected >= now && expected <= limit && shipment.status !== "delivered";
      })
      .sort((left, right) => deliveryDate(left.expected_delivery_date) - deliveryDate(right.expected_delivery_date));
  }

  function userNotifications(shipments, upcoming) {
    const pending = statusCount(shipments, "pending");
    const inTransit = statusCount(shipments, "in_transit");
    const missingDevice = shipments.filter((shipment) => !(shipment.device_id || shipment.device)).length;
    const alerts = [];

    if (!shipments.length) {
      alerts.push({
        icon: "fa-box-open",
        title: "No shipment requests",
        detail: "Create a shipment to start tracking activity.",
        tone: "neutral",
      });
    }
    if (pending) {
      alerts.push({
        icon: "fa-pen-to-square",
        title: `${pending} pending shipment${pending === 1 ? "" : "s"}`,
        detail: "Still editable before transit begins.",
        tone: "warning",
      });
    }
    if (inTransit) {
      alerts.push({
        icon: "fa-truck-fast",
        title: `${inTransit} in transit`,
        detail: "Locked while delivery is underway.",
        tone: "info",
      });
    }
    if (upcoming.length) {
      alerts.push({
        icon: "fa-calendar-day",
        title: `${upcoming.length} upcoming deliver${upcoming.length === 1 ? "y" : "ies"}`,
        detail: "Expected within the next 7 days.",
        tone: "success",
      });
    }
    if (missingDevice) {
      alerts.push({
        icon: "fa-microchip",
        title: `${missingDevice} device assignment${missingDevice === 1 ? "" : "s"} needed`,
        detail: "A device is required for live monitoring.",
        tone: "danger",
      });
    }

    return alerts.length
      ? alerts
      : [{
          icon: "fa-circle-check",
          title: "No new alerts",
          detail: "Your shipments are up to date.",
          tone: "success",
        }];
  }

  function notificationList(alerts) {
    const list = document.createElement("div");
    list.className = "notification-list";

    alerts.forEach((alert) => {
      const item = document.createElement("article");
      item.className = `notification-item notification-${alert.tone}`;

      const icon = document.createElement("i");
      icon.className = `fa-solid ${alert.icon}`;
      icon.setAttribute("aria-hidden", "true");

      const copy = document.createElement("div");
      const title = document.createElement("strong");
      const detail = document.createElement("span");
      title.textContent = alert.title;
      detail.textContent = alert.detail;
      copy.append(title, detail);

      item.append(icon, copy);
      list.appendChild(item);
    });

    return list;
  }

  function systemHealthPanel() {
    const list = document.createElement("div");
    list.className = "health-list";

    [
      {
        icon: "fa-server",
        label: "Backend",
        status: "Online",
        detail: "Protected API is responding.",
      },
      {
        icon: "fa-database",
        label: "Database",
        status: "Reachable",
        detail: "MongoDB access is available through authenticated routes.",
      },
    ].forEach((item) => {
      const row = document.createElement("article");
      row.className = "health-item";

      const icon = document.createElement("i");
      icon.className = `fa-solid ${item.icon}`;
      icon.setAttribute("aria-hidden", "true");

      const copy = document.createElement("div");
      const title = document.createElement("strong");
      const detail = document.createElement("span");
      title.textContent = item.label;
      detail.textContent = item.detail;
      copy.append(title, detail);

      const badge = document.createElement("span");
      badge.className = "badge badge-active health-badge";
      badge.textContent = item.status;

      row.append(icon, copy, badge);
      list.appendChild(row);
    });

    return list;
  }

  function shortcutButton(label, path) {
    return ui.makeButton(label, () => {
      ui.setActiveSection("shipments");
      window.dispatchEvent(new CustomEvent("dashboard:shipment-filter", { detail: { path } }));
    });
  }

  function ownShipmentsPath(path = "/api/shipments") {
    const url = new URL(path, window.location.origin);
    url.searchParams.set("mine", "true");
    return `${url.pathname}?${url.searchParams.toString()}`;
  }

  async function renderUserOverview(user) {
    const result = await loadList(api, USER_SHIPMENTS_PATH);
    const shipments = ownedShipments(result, user);
    const error = ui.errorPanel("Dashboard shipment status", result, "overview");
    const upcoming = upcomingDeliveries(shipments);
    const { start } = todayRange();

    if (error) ui.grid.appendChild(error);
    ui.grid.appendChild(ui.card("metric", "Total shipments", shipments.length));
    ui.grid.appendChild(ui.card("metric", "Pending", statusCount(shipments, "pending")));
    ui.grid.appendChild(ui.card("metric", "In transit", statusCount(shipments, "in_transit")));
    ui.grid.appendChild(ui.card("metric", "Delivered", statusCount(shipments, "delivered")));
    ui.grid.appendChild(ui.card("metric", "Upcoming deliveries", upcoming.length));

    ui.grid.appendChild(
      ui.panel("Upcoming deliveries", [
        ui.table(
          ["Tracking ID", "Route", "Status", "Expected delivery"],
          upcoming.slice(0, 5).map((shipment) => [
            shipment.tracking_id,
            shipment.route_details,
            shipment.status,
            formatDateTime(shipment.expected_delivery_date),
          ]),
          "No deliveries are expected in the next 7 days."
        ),
      ])
    );

    const shortcutList = document.createElement("div");
    shortcutList.className = "shortcut-list";
    shortcutList.append(
      shortcutButton("Pending", "/api/shipments?status=pending"),
      shortcutButton("In transit", "/api/shipments?status=in_transit"),
      shortcutButton("Delivered", "/api/shipments?status=delivered"),
      shortcutButton("Expected today", `/api/shipments?expected_delivery_date=${dateOnlyParam(start)}`),
      shortcutButton("All shipments", USER_SHIPMENTS_PATH)
    );
    ui.grid.appendChild(ui.panel("Shipment shortcuts", [shortcutList]));

    ui.grid.appendChild(
      ui.panel("Shipment Alerts", [
        notificationList(userNotifications(shipments, upcoming)),
      ], "notifications")
    );
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
    const save = ui.makeButton("Save profile", async () => {
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
        ui.setWelcome(normalizeRole(user.role), user);
        message.textContent = "Profile updated.";
      } catch (error) {
        message.textContent = error.message;
      } finally {
        save.disabled = false;
      }
    });
    form.append(save, message);

    ui.grid.appendChild(
      ui.panel("Profile", [
        form,
        ui.textBlock([
          `User ID: ${user.id || "-"}`,
          `Status: ${user.is_active ? "active" : "inactive"}`,
        ]),
        buildPasswordForm(),
      ], "profile")
    );
  }

  function buildPasswordForm() {
    const section = document.createElement("section");
    section.className = "profile-security";
    const heading = document.createElement("h4");
    heading.textContent = "Security";

    const form = document.createElement("form");
    form.className = "stack-form";
    form.innerHTML = `
      <label>Current password<input name="old_password" type="password" required></label>
      <label>New password<input name="new_password" type="password" required></label>
      <label>Confirm password<input name="confirm_new_password" type="password" required></label>
    `;
    const message = document.createElement("p");
    const submit = ui.makeButton("Update password", async () => {
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
    section.append(heading, form);
    return section;
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

  function shipmentDetailBlock(shipment) {
    return ui.textBlock([
      `Tracking ID: ${shipment.tracking_id}`,
      `Shipment number: ${shipment.shipment_number}`,
      `Container number: ${shipment.container_number}`,
      `Route: ${shipment.route_details}`,
      `Goods type: ${shipment.goods_type}`,
      `Device: ${shipment.device_id || shipment.device || "-"}`,
      `Status: ${shipment.status}`,
      `Expected delivery: ${formatDateTime(shipment.expected_delivery_date)}`,
      `Phone number: ${shipment.ph_number}`,
      `Delivery number: ${shipment.delivery_number}`,
      `NDC number: ${shipment.ndc_number}`,
      `Batch ID: ${shipment.batch_id}`,
      `Serial number: ${shipment.serial_number_of_goods}`,
      `Description: ${shipment.shipment_description}`,
    ]);
  }

  function detailAction(shipment, sectionName) {
    const button = ui.makeButton("Details", () => {
      ui.grid.appendChild(ui.panel(`Shipment ${shipment.tracking_id}`, [shipmentDetailBlock(shipment)], sectionName));
      button.disabled = true;
    });
    return button;
  }

  function buildShipmentFilterForm(sectionName, onApply) {
    const form = document.createElement("form");
    form.className = "shipment-filter-form";
    form.innerHTML = `
      <label>Container<input name="container_number" placeholder="Container number"></label>
      <label>Status<select name="status">
        <option value="">All statuses</option>
        ${SHIPMENT_STATUSES.map((status) => `<option value="${status}">${status.replace(/_/g, " ")}</option>`).join("")}
      </select></label>
      <label>Expected date<input name="expected_delivery_date" type="date"></label>
    `;
    const message = document.createElement("p");
    const apply = ui.makeButton("Apply filters", async () => {
      const params = new URLSearchParams();
      Object.entries(Object.fromEntries(new FormData(form).entries())).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      message.textContent = "";
      apply.disabled = true;
      try {
        await onApply(params.toString() ? `/api/shipments?${params.toString()}` : "/api/shipments");
      } catch (error) {
        message.textContent = error.message;
      } finally {
        apply.disabled = false;
      }
    });
    const reset = ui.makeButton("Reset", async () => {
      form.reset();
      message.textContent = "";
      await onApply("/api/shipments");
    });
    form.append(apply, reset, message);
    return ui.panel("Shipment filters", [form], sectionName);
  }

  function shipmentFilterSummary(path) {
    const url = new URL(path, window.location.origin);
    const labels = [];
    const container = url.searchParams.get("container_number");
    const status = url.searchParams.get("status");
    const expected = url.searchParams.get("expected_delivery_date");

    if (container) labels.push(`container ${container}`);
    if (status) labels.push(`status ${status.replace(/_/g, " ")}`);
    if (expected) labels.push(`expected date ${expected}`);

    return labels.length ? `No shipments match ${labels.join(", ")}.` : "No shipment requests found.";
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
      <label>Phone number<input name="ph_number" required></label>
      <label>Delivery number<input name="delivery_number" required></label>
      <label>NDC number<input name="ndc_number" required></label>
      <label>Batch ID<input name="batch_id" required></label>
      <label>Serial number<input name="serial_number_of_goods" required></label>
      <label class="full-span">Description<textarea name="shipment_description" rows="3" required></textarea></label>
    `;
    const message = document.createElement("p");
    const submit = ui.makeButton("Create shipment", async () => {
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
    ui.grid.appendChild(ui.panel("New shipment", [form], "new-shipment"));
  }

  function editShipmentAction(shipment) {
    if (shipment.status !== "pending") return "Locked";

    const button = ui.makeButton("Edit", () => {
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
      const save = ui.makeButton("Save shipment", async () => {
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
      ui.grid.appendChild(ui.panel(`Edit ${shipment.tracking_id}`, [form], "shipments"));
      button.disabled = true;
    });
    return button;
  }

  function userShipmentActions(shipment) {
    const wrapper = document.createElement("div");
    wrapper.className = "inline-actions";
    wrapper.appendChild(detailAction(shipment, "shipments"));
    if (shipment.status === "pending") {
      wrapper.appendChild(editShipmentAction(shipment));
    }
    return wrapper;
  }

  function adminStatusAction(shipment) {
    const wrapper = document.createElement("div");
    wrapper.className = "inline-actions";
    const select = document.createElement("select");
    SHIPMENT_STATUSES.forEach((status) => {
      const option = document.createElement("option");
      option.value = status;
      option.textContent = status.replace(/_/g, " ");
      option.selected = shipment.status === status;
      select.appendChild(option);
    });
    const save = ui.makeButton("Save", async () => {
      save.disabled = true;
      try {
        const updated = await api(`/api/shipments/${shipment.tracking_id}`, {
          method: "PATCH",
          body: JSON.stringify({ status: select.value }),
        });
        shipment.status = updated.status;
        save.textContent = "Saved";
        window.setTimeout(() => {
          save.textContent = "Save";
        }, 1200);
      } catch (error) {
        save.textContent = "Error";
        window.setTimeout(() => {
          save.textContent = "Save";
        }, 1200);
      } finally {
        save.disabled = false;
      }
    });
    wrapper.append(select, save);
    return wrapper;
  }

  function adminShipmentActions(shipment, refresh) {
    const wrapper = document.createElement("div");
    wrapper.className = "inline-actions";
    const details = detailAction(shipment, "operations");
    const remove = ui.makeButton("Delete", async () => {
      if (!window.confirm(`Delete shipment ${shipment.tracking_id}?`)) return;
      remove.disabled = true;
      try {
        await api(`/api/shipments/${shipment.tracking_id}`, { method: "DELETE" });
        await refresh();
      } catch (error) {
        remove.textContent = "Error";
        window.setTimeout(() => {
          remove.textContent = "Delete";
        }, 1200);
      } finally {
        remove.disabled = false;
      }
    });
    wrapper.append(details, remove);
    return wrapper;
  }

  async function renderMyShipments(user) {
    const host = document.createElement("div");
    host.className = "section-stack";
    host.setAttribute("data-view-section", "shipments");
    const filterPanel = buildShipmentFilterForm("shipments", applyFilterPath);
    ui.grid.append(filterPanel, host);

    function syncFilterForm(path) {
      const form = filterPanel.querySelector("form");
      if (!form) return;
      const url = new URL(path, window.location.origin);
      const fields = ["container_number", "status", "expected_delivery_date"];
      fields.forEach((field) => {
        if (form.elements[field]) {
          form.elements[field].value = url.searchParams.get(field) || "";
        }
      });
    }

    async function applyFilterPath(path = USER_SHIPMENTS_PATH) {
      const ownedPath = ownShipmentsPath(path);
      syncFilterForm(ownedPath);
      await refresh(ownedPath);
      window.requestAnimationFrame(() => {
        filterPanel.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }

    async function refresh(path = USER_SHIPMENTS_PATH) {
      const result = await loadList(api, path);
      const shipments = ownedShipments(result, user);
      const children = [];
      const error = ui.errorPanel("My shipments status", result, "shipments");
      if (error) children.push(error);

      children.push(ui.card("metric", "My shipments", shipments.length, "shipments"));
      children.push(ui.card("metric", "Pending", shipments.filter((shipment) => shipment.status === "pending").length, "shipments"));
      children.push(ui.card("metric", "Delivered", shipments.filter((shipment) => shipment.status === "delivered").length, "shipments"));
      children.push(
        ui.panel("My shipments", [
          ui.paginatedTable(
            ["Tracking ID", "Shipment", "Container", "Route", "Status", "Expected delivery", "Device", "Action"],
            shipments.map((shipment) => [...shipmentRows([shipment])[0], userShipmentActions(shipment)]),
            shipmentFilterSummary(path),
            DASHBOARD_TABLE_PAGE_SIZE
          ),
        ], "shipments")
      );
      host.replaceChildren(...children);
    }

    window.addEventListener("dashboard:shipment-filter", (event) => {
      applyFilterPath(event.detail?.path || USER_SHIPMENTS_PATH);
    });
    await refresh();
  }

  async function renderUser(dashboard) {
    ui.setWelcome("user", dashboard.user);
    await renderUserOverview(dashboard.user);
    await renderMyShipments(dashboard.user);
    renderShipmentForm();
    renderProfile(dashboard.user);
  }

  async function renderAdmin(dashboard) {
    ui.setWelcome("admin", dashboard.user);
    const metrics = dashboard.metrics || {};
    ui.grid.appendChild(ui.card("metric", "Users managed", metrics.users_managed ?? 0));
    ui.grid.appendChild(ui.card("metric", "Devices monitored", metrics.devices_monitored ?? 0));
    ui.grid.appendChild(ui.card("metric", "Shipments tracked", metrics.shipments_tracked ?? 0));

    const usersResult = await loadList(api, "/api/admin/users");
    const devicesResult = await loadList(api, "/api/devices");
    const users = listItems(usersResult);
    const devices = listItems(devicesResult);

    const usersError = ui.errorPanel("User roster status", usersResult, "overview");
    const devicesError = ui.errorPanel("Device inventory status", devicesResult, "devices");
    if (usersError) ui.grid.appendChild(usersError);
    if (devicesError) ui.grid.appendChild(devicesError);

    ui.grid.appendChild(
      ui.panel("User roster", [
        ui.paginatedTable(
          ["Name", "Email", "Role", "Status"],
          users.map((user) => [user.name, user.email, user.role, user.is_active ? "active" : "inactive"]),
          "No users are currently registered.",
          DASHBOARD_TABLE_PAGE_SIZE
        ),
      ])
    );
    ui.grid.appendChild(
      ui.panel("Device inventory", [
        ui.paginatedTable(
          ["Device ID", "Status", "Route"],
          devices.map((device) => [device.device_id, device.status, `${device.route_from || "-"} to ${device.route_to || "-"}`]),
          "No devices are currently registered.",
          DASHBOARD_TABLE_PAGE_SIZE
        ),
      ], "devices")
    );
    const shipmentHost = document.createElement("div");
    shipmentHost.className = "section-stack";
    shipmentHost.setAttribute("data-view-section", "operations");
    ui.grid.appendChild(buildShipmentFilterForm("operations", refreshAdminShipments));
    ui.grid.appendChild(shipmentHost);

    async function refreshAdminShipments(path = "/api/shipments") {
      const shipmentsResult = await loadList(api, path);
      const shipments = listItems(shipmentsResult);
      const children = [];
      const shipmentsError = ui.errorPanel("Shipment queue status", shipmentsResult, "operations");
      if (shipmentsError) children.push(shipmentsError);
      children.push(
        ui.panel("Shipment queue", [
          ui.paginatedTable(
            ["Tracking ID", "Container", "Route", "Device", "Status", "Status update", "Actions"],
            shipments.map((shipment) => [
              shipment.tracking_id,
              shipment.container_number,
              shipment.route_details,
              shipment.device_id || shipment.device,
              shipment.status,
              adminStatusAction(shipment),
              adminShipmentActions(shipment, refreshAdminShipments),
            ]),
            "No shipments are currently tracked.",
            DASHBOARD_TABLE_PAGE_SIZE
          ),
        ], "operations")
      );
      shipmentHost.replaceChildren(...children);
    }

    await refreshAdminShipments();
    renderProfile(dashboard.user);
  }

  function roleAction(user, currentUserId) {
    if (user.id === currentUserId) {
      return "Locked";
    }

    const wrapper = document.createElement("div");
    wrapper.className = "inline-actions role-actions";
    const select = document.createElement("select");
    ["user", "admin", "super_admin"].forEach((role) => {
      const option = document.createElement("option");
      option.value = role;
      option.textContent = role.replace(/_/g, " ");
      option.selected = user.role === role;
      select.appendChild(option);
    });

    const save = ui.makeButton("Save", async () => {
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
    ui.setWelcome("super_admin", dashboard.user);
    const metrics = dashboard.metrics || {};
    ui.grid.appendChild(ui.card("metric", "Total users", metrics.total_users ?? 0));
    ui.grid.appendChild(ui.card("metric", "Admin count", metrics.admin_count ?? 0));
    ui.grid.appendChild(ui.card("metric", "Active users", metrics.active_users ?? 0));
    ui.grid.appendChild(ui.card("metric", "Platform health", metrics.platform_health || "online"));
    ui.grid.appendChild(ui.card("metric", "Devices monitored", metrics.devices_monitored ?? 0));
    ui.grid.appendChild(ui.card("metric", "Shipments tracked", metrics.shipments_tracked ?? 0));
    ui.grid.appendChild(ui.card("metric", "Pending shipments", metrics.pending_shipments ?? 0));
    ui.grid.appendChild(ui.card("metric", "Assigned devices", metrics.assigned_devices ?? 0));

    ui.grid.appendChild(
      ui.panel("Recent logins", [
        ui.paginatedTable(
          ["Name", "Email", "Role", "Login time"],
          (dashboard.recent_logins || []).map((login) => [
            login.name,
            login.email,
            login.role,
            formatDateTime(login.logged_in_at),
          ]),
          "No login records found.",
          RECENT_LOGINS_PAGE_SIZE
        ),
      ])
    );

    const usersResult = await loadList(api, "/api/admin/users");
    const users = listItems(usersResult);
    const usersError = ui.errorPanel("Role governance status", usersResult, "governance");
    if (usersError) ui.grid.appendChild(usersError);
    ui.grid.appendChild(
      ui.panel("Role governance", [
        ui.paginatedTable(
          ["Name", "Email", "Current role", "Action"],
          users.map((user) => [user.name, user.email, user.role, roleAction(user, dashboard.user.id)]),
          "No users are currently available for role governance.",
          GOVERNANCE_TABLE_PAGE_SIZE
        ),
      ], "governance")
    );

    ui.grid.appendChild(ui.panel("System health", [systemHealthPanel()], "health"));
    renderProfile(dashboard.user);
  }

  return { renderAdmin, renderSuperAdmin, renderUser };
}
