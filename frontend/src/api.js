const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

async function request(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  let response;
  try {
    response = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
  } catch (error) {
    console.error("API network error", { url, error });
    throw new Error(`Unable to reach the backend at ${API_BASE_URL}. Check that the API is running and CORS allows this frontend origin.`);
  }

  if (!response.ok) {
    let detail = `Request failed for ${path} (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail || body.message || detail;
    } catch {
      console.error("API returned a non-JSON error response", { url, status: response.status });
    }
    console.error("API request failed", { url, status: response.status, detail });
    throw new Error(`${detail}${response.status >= 500 ? ". Check the backend database connection." : ""}`);
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