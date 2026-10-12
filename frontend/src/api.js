async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export const api = {
  health: () => request("/api/health"),
  profile: () => request("/api/profile"),
  saveProfile: (profile) =>
    request("/api/profile", { method: "PUT", body: JSON.stringify({ profile }) }),
  discover: () => request("/api/discovery/run", { method: "POST" }),
  runs: () => request("/api/discovery/runs"),
  opportunities: (params = "") => request(`/api/opportunities${params}`),
  opportunity: (id) => request(`/api/opportunities/${id}`),
  decide: (id, decision) =>
    request(`/api/opportunities/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
  prepare: (id) => request(`/api/opportunities/${id}/prepare-documents`, { method: "POST" }),
  dashboard: () => request("/api/dashboard"),
  notifications: () => request("/api/notifications"),
  approvals: () => request("/api/approvals"),
  approveApp: (id, approved) =>
    request(`/api/approvals/applications/${id}`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    }),
  approveEmail: (id, approved) =>
    request(`/api/approvals/emails/${id}`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    }),
  settings: () => request("/api/settings"),
};
