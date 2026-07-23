// Thin API client. Tenant is sent via the X-Tenant header (click-to-login).

function tenantId() {
  return localStorage.getItem("tenantId") || "";
}

async function req(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const t = tenantId();
  if (t) headers["X-Tenant"] = t;
  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch (e) {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  tenants: () => req("/api/tenants"),
  login: (id) => req("/api/login", { method: "POST", body: { tenantId: id } }),
  me: () => req("/api/me"),
  ingestStatus: () => req("/api/ingest/status"),
  loadBatch: (size = 10) => req("/api/ingest/load-batch", { method: "POST", body: { size } }),
  embedPending: () => req("/api/ingest/embed-pending", { method: "POST" }),
  searchPatients: (q, limit = 20) =>
    req(`/api/patients?limit=${limit}${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  getPatient: (id) => req(`/api/patients/${id}`),
  chat: (message) => req("/api/chat", { method: "POST", body: { message } }),
  // Specialized endpoints: path templates come from /me; {id} is substituted.
  callFeature: (path, patientId, query) => {
    let url = path.replace("{id}", patientId);
    if (query) url += (url.includes("?") ? "&" : "?") + query;
    return req(url);
  },
};
