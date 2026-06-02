export function normalizeRole(role) {
  return String(role || "user").trim().toLowerCase();
}

export function titleForRole(role) {
  if (role === "super_admin") return "Super Admin Dashboard";
  if (role === "admin") return "Admin Dashboard";
  return "User Dashboard";
}

export function roleLabel(role) {
  if (role === "super_admin") return "super admin";
  return role || "user";
}

export function roleHomePath(role) {
  if (role === "super_admin") return "/dashboard/super-admin";
  if (role === "admin") return "/dashboard/admin";
  return "/dashboard/user";
}

export function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

export function formatDateInputValue(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 16);
}

export function formatLabel(value) {
  if (value == null || value === "") return "-";
  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

