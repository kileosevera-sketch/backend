const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    let detail = `Request failed for ${path} (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // Keep the HTTP status when the server did not return JSON.
    }
    if (response.status >= 500) {
      throw new Error(`${detail}. Check the backend database connection.`);
    }
    throw new Error(detail);
  }
  return response.json();
}

export const api = {
  health: () => request("/health"),
  overview: () => request("/dashboard/overview"),
  weeklyTrend: (weeks = 12) => request(`/dashboard/trends/weekly?weeks=${weeks}`),
  monthlyTrend: (months = 6) => request(`/dashboard/trends/monthly?months=${months}`),
  recommendations: () => request("/dashboard/recommendations"),
  sync: () => request("/dashboard/sync", { method: "POST" }),
};

export { API_BASE_URL };