import { logout } from "./session.js";

export function createApiClient({ token, tokenType }) {
  const baseHeaders = {
    Authorization: `${tokenType} ${token}`,
    "Content-Type": "application/json",
  };

  return async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        ...baseHeaders,
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => null);
    if (response.status === 401 || (response.status === 403 && data?.detail === "Account is inactive")) {
      logout();
      return null;
    }
    if (!response.ok) {
      throw new Error(data?.detail || data?.message || `Request failed: ${path}`);
    }
    return data;
  };
}

export async function loadList(api, path) {
  try {
    return await api(path);
  } catch (error) {
    return { error: error.message, items: [] };
  }
}

export function listItems(result) {
  return Array.isArray(result) ? result : result.items || [];
}
