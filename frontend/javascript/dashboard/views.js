import { listItems, loadList } from "./api.js";
import { escapeHtml, formatDateInputValue, formatDateTime, formatLabel, normalizeRole } from "./format.js";

const SHIPMENT_STATUSES = ["pending", "in_transit", "out_for_delivery", "delivered", "cancelled"];
const SHIPMENT_ROUTES = [
  "Chennai - Hyderabad via NH16",
  "Chennai - Bangalore via NH48",
  "Bangalore - Mumbai via NH48",
  "Hyderabad - Pune via NH65",
  "Mumbai - Delhi via NH48",
];
const GOODS_TYPES = ["Electronics", "Medicines", "Food products", "Textiles", "Automotive parts", "General cargo"];
const FALLBACK_DEVICE_OPTIONS = ["GPS tracker", "Thermal tracker", "Humidity sensor", "Shock sensor"];
const USER_SHIPMENTS_PATH = "/api/shipments?mine=true";
const DASHBOARD_TABLE_PAGE_SIZE = 5;
const USER_MANAGEMENT_TABLE_PAGE_SIZE = 5;
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

  function countBy(items, key, fallback = "unknown") {
    return items.reduce((counts, item) => {
      const value = String(item?.[key] || fallback).toLowerCase();
      counts[value] = (counts[value] || 0) + 1;
      return counts;
    }, {});
  }

  function chartDatasetFromCounts(counts, order = []) {
    const keys = [...new Set([...order, ...Object.keys(counts)])];
    return keys
      .map((key) => ({
        label: formatLabel(key),
        value: Number(counts[key] || 0),
      }))
      .filter((item) => item.value > 0);
  }

  function chartPanel(title, charts, sectionName = "overview") {
    const layout = document.createElement("div");
    layout.className = "chart-layout";
    charts.forEach((chart) => layout.appendChild(chart));
    return ui.panel(title, [layout], sectionName);
  }

  function pieChart(title, data) {
    const total = data.reduce((sum, item) => sum + item.value, 0);
    const chart = document.createElement("article");
    chart.className = "chart-box pie-chart-box";

    const heading = document.createElement("h4");
    heading.textContent = title;

    const body = document.createElement("div");
    body.className = "pie-chart-body";

    const pie = document.createElement("div");
    pie.className = "pie-chart";
    pie.setAttribute("role", "img");
    pie.setAttribute("aria-label", `${title}: ${total || 0} total`);

    if (total > 0) {
      let cursor = 0;
      const colors = ["#0f766e", "#ca8a04", "#15803d", "#dc2626", "#64748b", "#2563eb"];
      const segments = data.map((item, index) => {
        const start = cursor;
        const end = cursor + (item.value / total) * 100;
        cursor = end;
        return `${colors[index % colors.length]} ${start}% ${end}%`;
      });
      pie.style.background = `conic-gradient(${segments.join(", ")})`;
    }

    const totalLabel = document.createElement("span");
    totalLabel.className = "pie-total";
    totalLabel.innerHTML = `<strong>${total}</strong><span>Total</span>`;
    pie.appendChild(totalLabel);

    const legend = chartLegend(data);
    body.append(pie, legend);
    chart.append(heading, body);
    return chart;
  }

  function barChart(title, data) {
    const max = Math.max(1, ...data.map((item) => item.value));
    const chart = document.createElement("article");
    chart.className = "chart-box bar-chart-box";

    const heading = document.createElement("h4");
    heading.textContent = title;
    const bars = document.createElement("div");
    bars.className = "bar-chart";

    data.forEach((item) => {
      const row = document.createElement("div");
      row.className = "bar-row";
      const label = document.createElement("span");
      label.className = "bar-label";
      label.textContent = item.label;
      const track = document.createElement("span");
      track.className = "bar-track";
      const fill = document.createElement("span");
      fill.className = "bar-fill";
      fill.style.width = `${Math.max(8, (item.value / max) * 100)}%`;
      track.appendChild(fill);
      const value = document.createElement("strong");
      value.textContent = item.value;
      row.append(label, track, value);
      bars.appendChild(row);
    });

    if (!data.length) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "No chart data available.";
      bars.appendChild(empty);
    }

    chart.append(heading, bars);
    return chart;
  }

  function chartLegend(data) {
    const legend = document.createElement("div");
    legend.className = "chart-legend";
    data.forEach((item, index) => {
      const row = document.createElement("span");
      row.style.setProperty("--legend-color", ["#0f766e", "#ca8a04", "#15803d", "#dc2626", "#64748b", "#2563eb"][index % 6]);
      row.innerHTML = `<strong>${escapeHtml(item.label)}</strong>${item.value}`;
      legend.appendChild(row);
    });
    if (!data.length) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "No chart data available.";
      legend.appendChild(empty);
    }
    return legend;
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
    ui.grid.appendChild(
      chartPanel("My shipment charts", [
        pieChart(
          "Shipment status",
          chartDatasetFromCounts(countBy(shipments, "status"), SHIPMENT_STATUSES)
        ),
        barChart(
          "Delivery workload",
          [
            { label: "Upcoming", value: upcoming.length },
            { label: "Pending", value: statusCount(shipments, "pending") },
            { label: "In transit", value: statusCount(shipments, "in_transit") },
            { label: "Delivered", value: statusCount(shipments, "delivered") },
          ]
        ),
      ])
    );

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
    const profileHeader = document.createElement("section");
    profileHeader.className = "profile-identity";
    const initial = String(user.name || user.email || "U").trim().charAt(0).toUpperCase() || "U";
    profileHeader.innerHTML = `
      <div class="profile-avatar">${escapeHtml(initial)}</div>
      <div class="profile-summary">
        <span class="profile-kicker">Account console</span>
        <h3>${escapeHtml(user.name || "User")}</h3>
        <div class="profile-badges">
          <span class="badge badge-admin">${escapeHtml(formatLabel(user.role))}</span>
          <span class="badge badge-active">Active</span>
        </div>
      </div>
      <div class="profile-chips">
        <span><i class="fa-solid fa-envelope" aria-hidden="true"></i>${escapeHtml(user.email || "-")}</span>
        <span><i class="fa-solid fa-phone" aria-hidden="true"></i>${escapeHtml(user.phone || "-")}</span>
      </div>
    `;

    const form = document.createElement("form");
    form.className = "stack-form";
    form.innerHTML = `
      <p class="profile-helper">Keep your SCMXpertLite account details up to date.</p>
      <label><span><i class="fa-solid fa-user" aria-hidden="true"></i>Name</span><input name="name" value="${escapeHtml(user.name)}" required></label>
      <label><span><i class="fa-solid fa-envelope" aria-hidden="true"></i>Email</span><input name="email" value="${escapeHtml(user.email)}" readonly></label>
      <label><span><i class="fa-solid fa-phone" aria-hidden="true"></i>Phone</span><input name="phone" value="${escapeHtml(user.phone)}" required></label>
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

    const profileDetails = document.createElement("section");
    profileDetails.className = "profile-details";
    profileDetails.append(form);

    const layout = document.createElement("div");
    layout.className = "profile-layout";
    layout.append(profileDetails, buildPasswordForm());

    ui.grid.appendChild(ui.panel("Profile", [profileHeader, layout], "profile"));
  }

  function buildPasswordForm() {
    const section = document.createElement("section");
    section.className = "profile-security";
    const heading = document.createElement("h4");
    heading.textContent = "Password";

    const form = document.createElement("form");
    form.className = "stack-form";
    form.innerHTML = `
      <p class="profile-helper">Update your password regularly to protect shipment access.</p>
      <label><span><i class="fa-solid fa-lock" aria-hidden="true"></i>Current password</span><input name="old_password" type="password" required></label>
      <label><span><i class="fa-solid fa-key" aria-hidden="true"></i>New password</span><input name="new_password" type="password" required></label>
      <label><span><i class="fa-solid fa-shield-halved" aria-hidden="true"></i>Confirm password</span><input name="confirm_new_password" type="password" required></label>
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
    const expected = url.searchParams.get("expected_delivery_date");

    if (container) labels.push(`container ${container}`);
    if (expected) labels.push(`expected date ${expected}`);

    return labels.length ? `No shipments match ${labels.join(", ")}.` : "No shipment requests found.";
  }

  function selectOptions(options, selectedValue = "", placeholder = "Select option") {
    const normalizedSelected = String(selectedValue || "");
    const uniqueOptions = [...new Set([normalizedSelected, ...options].filter(Boolean))];
    return [
      `<option value="">${escapeHtml(placeholder)}</option>`,
      ...uniqueOptions.map((option) => {
        const selected = option === normalizedSelected ? " selected" : "";
        return `<option value="${escapeHtml(option)}"${selected}>${escapeHtml(option)}</option>`;
      }),
    ].join("");
  }

  async function deviceOptions(selectedValue = "") {
    const devicesResult = await loadList(api, "/api/devices");
    const devices = listItems(devicesResult);
    const availableDevices = devices.filter((device) => device.status === "available");
    const source = availableDevices.length ? availableDevices : devices;
    const options = source.length
      ? source.map((device) => device.device_id || device.device || device.name).filter(Boolean)
      : FALLBACK_DEVICE_OPTIONS;
    return selectOptions(options, selectedValue, "Select requested device");
  }

  async function renderShipmentForm(successSection = "shipments", onCreated = null, formSection = "new-shipment") {
    const requestedDeviceOptions = await deviceOptions();
    const form = document.createElement("form");
    form.className = "shipment-form";
    form.innerHTML = `
      <label>Shipment number<input name="shipment_number" placeholder="Example: SHP-2026-0001" required></label>
      <label>Container number<input name="container_number" placeholder="Example: CONT-45821" required></label>
      <label class="full-span">Route details<select name="route_details" required>${selectOptions(SHIPMENT_ROUTES, "", "Select route")}</select></label>
      <label>Goods type<select name="goods_type" required>${selectOptions(GOODS_TYPES, "", "Select goods type")}</select></label>
      <label>Requested device<select name="device" required>${requestedDeviceOptions}</select></label>
      <label>Expected delivery<input name="expected_delivery_date" type="datetime-local" required></label>
      <label>Phone number<input name="ph_number" placeholder="Example: 9876543210" required></label>
      <label>Delivery number<input name="delivery_number" placeholder="Example: DEL-2026-0008" required></label>
      <label>NDC number<input name="ndc_number" placeholder="Example: NDC-8891" required></label>
      <label>Batch ID<input name="batch_id" placeholder="Example: BATCH-A17" required></label>
      <label>Serial number<input name="serial_number_of_goods" placeholder="Example: SER-CC-2026-0002" required></label>
      <label class="full-span">Description<textarea name="shipment_description" rows="3" placeholder="Example: Temperature-sensitive medicines packed in sealed cartons." required></textarea></label>
    `;
    const message = document.createElement("p");
    const submit = ui.makeButton("Create shipment", async () => {
      if (!form.reportValidity()) return;
      const payload = Object.fromEntries(new FormData(form).entries());
      message.textContent = "";
      submit.disabled = true;
      try {
        const created = await api("/api/shipments", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        form.reset();
        message.textContent = "";
        showShipmentSuccessDialog(created, successSection, onCreated);
      } catch (error) {
        message.textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
    const actions = document.createElement("div");
    actions.className = "form-actions full-span";
    actions.append(submit, message);
    form.append(actions);
    ui.grid.appendChild(ui.panel("New shipment", [form], formSection));
  }

  function showShipmentSuccessDialog(created, successSection, onCreated) {
    const overlay = document.createElement("div");
    overlay.className = "dialog-overlay active";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-labelledby", "shipment-success-title");

    const dialog = document.createElement("div");
    dialog.className = "dialog-box success";

    const title = document.createElement("div");
    title.id = "shipment-success-title";
    title.className = "dialog-title";
    title.textContent = "Success";

    const message = document.createElement("div");
    message.className = "dialog-message";
    message.textContent = `Shipment ${created.tracking_id} created successfully.`;

    const ok = document.createElement("button");
    ok.type = "button";
    ok.className = "dialog-button";
    ok.textContent = "OK";
    ok.addEventListener("click", async () => {
      ok.disabled = true;
      if (onCreated) await onCreated(created);
      overlay.remove();
      ui.setActiveSection(successSection);
    });

    dialog.append(title, message, ok);
    overlay.append(dialog);
    document.body.appendChild(overlay);
    ok.focus();
  }

  function editShipmentAction(shipment) {
    if (shipment.status !== "pending") return "Locked";

    const button = ui.makeButton("Edit", async () => {
      button.disabled = true;
      const requestedDeviceOptions = await deviceOptions(shipment.device);
      const form = document.createElement("form");
      form.className = "shipment-form";
      form.innerHTML = `
        <label>Shipment number<input name="shipment_number" value="${escapeHtml(shipment.shipment_number)}" required></label>
        <label>Container number<input name="container_number" value="${escapeHtml(shipment.container_number)}" required></label>
        <label>Route details<select name="route_details" required>${selectOptions(SHIPMENT_ROUTES, shipment.route_details, "Select route")}</select></label>
        <label>Goods type<select name="goods_type" required>${selectOptions(GOODS_TYPES, shipment.goods_type, "Select goods type")}</select></label>
        <label>Requested device<select name="device" required>${requestedDeviceOptions}</select></label>
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

      children.push(ui.card("metric metric-third", "My shipments", shipments.length, "shipments"));
      children.push(ui.card("metric metric-third", "Pending", shipments.filter((shipment) => shipment.status === "pending").length, "shipments"));
      children.push(ui.card("metric metric-third", "Delivered", shipments.filter((shipment) => shipment.status === "delivered").length, "shipments"));
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
    await renderShipmentForm();
    renderProfile(dashboard.user);
  }

  async function renderAdmin(dashboard) {
    ui.setWelcome("admin", dashboard.user);
    const metrics = dashboard.metrics || {};
    const usersResult = await loadList(api, "/api/admin/users");
    const devicesResult = await loadList(api, "/api/devices");
    const shipmentsResult = await loadList(api, "/api/shipments");
    const users = listItems(usersResult);
    const devices = listItems(devicesResult);
    const shipments = listItems(shipmentsResult);

    const usersError = ui.errorPanel("User roster status", usersResult, "overview users");
    const devicesError = ui.errorPanel("Device inventory status", devicesResult, "devices");
    const shipmentsError = ui.errorPanel("Shipment chart status", shipmentsResult, "overview operations");
    if (usersError) ui.grid.appendChild(usersError);
    if (devicesError) ui.grid.appendChild(devicesError);
    if (shipmentsError) ui.grid.appendChild(shipmentsError);

    ui.grid.appendChild(
      chartPanel("Operations charts", [
        pieChart(
          "Shipment status",
          chartDatasetFromCounts(countBy(shipments, "status"), SHIPMENT_STATUSES)
        ),
        barChart(
          "Device status",
          chartDatasetFromCounts(countBy(devices, "status"), ["available", "assigned", "active", "inactive", "maintenance"])
        ),
        barChart(
          "User access",
          chartDatasetFromCounts(countBy(users, "role"), ["user", "admin", "super_admin"])
        ),
      ], "overview")
    );

    ui.grid.appendChild(
      ui.panel("User roster", [
        ui.paginatedTable(
          ["Name", "Email", "Role", "Status"],
          users.map((user) => [user.name, user.email, user.role, user.is_active ? "active" : "inactive"]),
          "No users are currently registered.",
          DASHBOARD_TABLE_PAGE_SIZE
        ),
      ], "overview")
    );
    ui.grid.appendChild(userManagementPanel(users, dashboard.user, false));
    ui.grid.appendChild(deviceDataStreamPanel(devices));
    const shipmentHost = document.createElement("div");
    shipmentHost.className = "section-stack";
    shipmentHost.setAttribute("data-view-section", "operations");
    await renderShipmentForm("operations", refreshAdminShipments, "operations");
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

  function roleAction(user, currentUserId, roles = ["user", "admin", "super_admin"]) {
    if (user.id === currentUserId) {
      return "Locked";
    }
    if (user.role === "super_admin" && !roles.includes("super_admin")) {
      return "Locked";
    }

    const wrapper = document.createElement("div");
    wrapper.className = "inline-actions role-actions";
    const select = document.createElement("select");
    roles.forEach((role) => {
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

  function deleteUserAction(user, currentUserId) {
    if (user.id === currentUserId || user.role === "super_admin") {
      return "Locked";
    }

    const remove = ui.makeButton("Delete", async () => {
      if (!window.confirm(`Delete user ${user.email}?`)) return;
      remove.disabled = true;
      try {
        await api(`/api/admin/users/${user.id}`, { method: "DELETE" });
        remove.textContent = "Deleted";
        window.setTimeout(() => window.location.reload(), 700);
      } catch (error) {
        remove.textContent = "Error";
        window.setTimeout(() => {
          remove.textContent = "Delete";
        }, 1200);
      } finally {
        remove.disabled = false;
      }
    });
    remove.classList.add("danger-action");
    return remove;
  }

  function userManagementAction(user, currentUser, canDelete) {
    const wrapper = document.createElement("div");
    wrapper.className = "inline-actions user-management-actions";
    const allowedRoles = canDelete ? ["user", "admin", "super_admin"] : ["user", "admin"];
    const roleControl = roleAction(user, currentUser.id, allowedRoles);
    const roleWrapper = document.createElement("span");
    roleWrapper.append(roleControl);
    wrapper.append(roleWrapper);
    if (canDelete) {
      const deleteControl = deleteUserAction(user, currentUser.id);
      const deleteWrapper = document.createElement("span");
      deleteWrapper.append(deleteControl);
      wrapper.append(deleteWrapper);
    }
    return wrapper;
  }

  function userManagementRows(users, currentUser, canDelete) {
    return users.map((user) => [
      user.name,
      user.email,
      user.role,
      user.is_active ? "active" : "inactive",
      userManagementAction(user, currentUser, canDelete),
    ]);
  }

  function deviceDataStreamPanel(devices, sectionName = "devices") {
    return ui.panel("Device data stream", [
      ui.paginatedTable(
        ["Device ID", "Battery level", "First sensor temperature", "Route from", "Route to", "Timestamp"],
        devices.map((device) => [
          device.device_id,
          device.battery_level ?? "-",
          device.first_sensor_temperature || "-",
          device.route_from || "-",
          device.route_to || "-",
          formatDateTime(device.timestamp),
        ]),
        "No device data is currently available.",
        DASHBOARD_TABLE_PAGE_SIZE
      ),
    ], sectionName);
  }

  function userMatchesSearch(user, query) {
    if (!query) return true;
    const status = user.is_active ? "active" : "inactive";
    return [user.name, user.email, user.role, status]
      .some((value) => String(value || "").toLowerCase().includes(query));
  }

  function userManagementPanel(users, currentUser, canDelete) {
    const contentHost = document.createElement("div");
    const tabs = document.createElement("div");
    tabs.className = "management-tabs";
    tabs.setAttribute("role", "tablist");

    const usersTab = makeManagementTab("Users", true);
    const createTab = makeManagementTab("Create account", false);
    tabs.append(usersTab, createTab);

    const searchWrap = document.createElement("label");
    searchWrap.className = "table-search-wrap";
    const searchIcon = document.createElement("i");
    searchIcon.className = "fa-solid fa-magnifying-glass";
    searchIcon.setAttribute("aria-hidden", "true");
    const search = document.createElement("input");
    search.type = "search";
    search.className = "table-search";
    search.placeholder = "Search users by name, email, role, or status";
    search.setAttribute("aria-label", "Search users");
    searchWrap.append(searchIcon, search);

    const tableHost = document.createElement("div");
    tableHost.className = "search-results user-management-results";

    function renderTable() {
      const query = search.value.trim().toLowerCase();
      const filteredUsers = users.filter((user) => userMatchesSearch(user, query));
      tableHost.replaceChildren(
        ui.paginatedTable(
          ["Name", "Email", "Current role", "Status", "Action"],
          userManagementRows(filteredUsers, currentUser, canDelete),
          query ? "No users match your search." : "No users are currently available for management.",
          USER_MANAGEMENT_TABLE_PAGE_SIZE
        )
      );
    }

    function setActiveTab(activeTab) {
      [usersTab, createTab].forEach((tab) => {
        const isActive = tab === activeTab;
        tab.classList.toggle("active", isActive);
        tab.setAttribute("aria-selected", String(isActive));
      });
    }

    function showUserList() {
      setActiveTab(usersTab);
      contentHost.replaceChildren(searchWrap, tableHost);
    }

    function showCreateAccount() {
      setActiveTab(createTab);
      const form = buildCreateUserForm(canDelete, (createdUser) => {
        users.unshift(createdUser);
        renderTable();
        showUserList();
      });
      const formPanel = createFormWrapper(form);
      contentHost.replaceChildren(formPanel);
    }

    usersTab.addEventListener("click", showUserList);
    createTab.addEventListener("click", showCreateAccount);
    search.addEventListener("input", renderTable);
    renderTable();
    showUserList();
    return ui.panel("User management", [tabs, contentHost], "users");
  }

  function makeManagementTab(label, active) {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = `management-tab${active ? " active" : ""}`;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(active));
    tab.textContent = label;
    return tab;
  }

  function buildCreateUserForm(canCreateSuperAdmin, onCreated) {
    const form = document.createElement("form");
    form.className = "create-user-form";
    const roleOptions = canCreateSuperAdmin ? ["user", "admin", "super_admin"] : ["user", "admin"];
    form.innerHTML = `
      <label>Name<input name="name" required></label>
      <label>Email<input name="email" type="email" required></label>
      <label>Phone<input name="phone" inputmode="numeric" maxlength="10" pattern="[0-9]{10}" required></label>
      <label>Role<select name="role">${roleOptions.map((role) => `<option value="${role}">${role.replace(/_/g, " ")}</option>`).join("")}</select></label>
      <label class="full-span">Password<span class="password-generate-row"><input name="password" type="text" minlength="8" required><button type="button" class="action-button generate-password">Generate</button></span></label>
    `;
    const message = document.createElement("p");
    message.className = "form-message";
    let generatedPassword = "";
    const passwordInput = form.elements.password;
    const generate = form.querySelector(".generate-password");
    generate.addEventListener("click", () => {
      generatedPassword = generatePassword();
      passwordInput.value = generatedPassword;
      message.textContent = "Generated password filled. It will be shown once after account creation.";
    });

    const submit = ui.makeButton("Create account", async () => {
      if (!form.reportValidity()) return;
      const payload = Object.fromEntries(new FormData(form).entries());
      const role = payload.role || "user";
      const createdPassword = generatedPassword && generatedPassword === payload.password ? generatedPassword : "";
      delete payload.role;
      message.textContent = "";
      submit.disabled = true;
      try {
        const created = await api("/api/users", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        if (role !== "user" && created.id) {
          await api(`/api/admin/users/${created.id}/role`, {
            method: "PATCH",
            body: JSON.stringify({ role }),
          });
        }
        onCreated({
          id: created.id,
          name: payload.name,
          email: created.email || payload.email,
          role,
          is_active: true,
        });
        form.reset();
        generatedPassword = "";
        message.textContent = createdPassword
          ? `Account created for ${created.email}. Temporary password: ${createdPassword}`
          : `Account created for ${created.email}.`;
      } catch (error) {
        message.textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
    const actions = document.createElement("div");
    actions.className = "form-actions full-span";
    actions.append(submit, message);
    form.append(actions);
    return form;
  }

  function generatePassword(length = 14) {
    const groups = [
      "ABCDEFGHJKLMNPQRSTUVWXYZ",
      "abcdefghijkmnopqrstuvwxyz",
      "23456789",
      "!@#$%&*?",
    ];
    const allChars = groups.join("");
    const bytes = new Uint32Array(length);
    window.crypto.getRandomValues(bytes);
    const password = groups.map((group, index) => group[bytes[index] % group.length]);
    for (let index = password.length; index < length; index += 1) {
      password.push(allChars[bytes[index] % allChars.length]);
    }
    return password
      .map((char, index, list) => {
        const swapIndex = bytes[index] % list.length;
        const swapped = list[swapIndex];
        list[swapIndex] = char;
        return swapped;
      })
      .join("");
  }

  function createFormWrapper(form) {
    const wrapper = document.createElement("div");
    wrapper.className = "create-user-panel";
    const heading = document.createElement("h4");
    heading.textContent = "Create account";
    wrapper.append(heading, form);
    return wrapper;
  }

  async function renderSuperAdmin(dashboard) {
    ui.setWelcome("super_admin", dashboard.user);
    const metrics = dashboard.metrics || {};
    ui.setQuickStats([
      { label: "Active users", value: metrics.active_users ?? 0 },
      { label: "Pending shipments", value: metrics.pending_shipments ?? 0 },
      { label: "Available devices", value: metrics.available_devices ?? 0 },
      { label: "Today's deliveries", value: metrics.todays_deliveries ?? 0 },
    ]);
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
    const devicesResult = await loadList(api, "/api/devices");
    const shipmentsResult = await loadList(api, "/api/shipments");
    const users = listItems(usersResult);
    const devices = listItems(devicesResult);
    const shipments = listItems(shipmentsResult);
    const userManagementError = ui.errorPanel("User management status", usersResult, "users");
    const devicesError = ui.errorPanel("Device data stream status", devicesResult, "devices");
    const shipmentsError = ui.errorPanel("Shipment chart status", shipmentsResult, "overview");
    if (userManagementError) ui.grid.appendChild(userManagementError);
    if (devicesError) ui.grid.appendChild(devicesError);
    if (shipmentsError) ui.grid.appendChild(shipmentsError);
    ui.grid.appendChild(
      chartPanel("Governance charts", [
        pieChart(
          "User roles",
          chartDatasetFromCounts(countBy(users, "role"), ["user", "admin", "super_admin"])
        ),
        pieChart(
          "User status",
          [
            { label: "Active", value: metrics.active_users ?? users.filter((user) => user.is_active).length },
            { label: "Inactive", value: metrics.inactive_users ?? users.filter((user) => !user.is_active).length },
          ].filter((item) => item.value > 0)
        ),
        barChart(
          "Shipment status",
          chartDatasetFromCounts(countBy(shipments, "status"), SHIPMENT_STATUSES)
        ),
        barChart(
          "Device status",
          chartDatasetFromCounts(countBy(devices, "status"), ["available", "assigned", "active", "inactive", "maintenance"])
        ),
      ], "overview")
    );
    ui.grid.appendChild(userManagementPanel(users, dashboard.user, true));
    ui.grid.appendChild(deviceDataStreamPanel(devices));
    const shipmentHost = document.createElement("div");
    shipmentHost.className = "section-stack";
    shipmentHost.setAttribute("data-view-section", "operations");
    await renderShipmentForm("operations", refreshSuperAdminShipments, "operations");
    ui.grid.appendChild(buildShipmentFilterForm("operations", refreshSuperAdminShipments));
    ui.grid.appendChild(shipmentHost);

    async function refreshSuperAdminShipments(path = "/api/shipments") {
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
              adminShipmentActions(shipment, refreshSuperAdminShipments),
            ]),
            "No shipments are currently tracked.",
            DASHBOARD_TABLE_PAGE_SIZE
          ),
        ], "operations")
      );
      shipmentHost.replaceChildren(...children);
    }

    await refreshSuperAdminShipments();

    ui.grid.appendChild(ui.panel("System health", [systemHealthPanel()], "health"));
    renderProfile(dashboard.user);
  }

  return { renderAdmin, renderSuperAdmin, renderUser };
}
