const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error("Failed to connect to backend API");
  return res.json();
}

export async function fetchSamples() {
  const res = await fetch(`${API_BASE}/api/samples`);
  if (!res.ok) throw new Error("Failed to load sample repositories");
  return res.json();
}

export async function fetchRuns() {
  const res = await fetch(`${API_BASE}/api/runs`);
  if (!res.ok) throw new Error("Failed to load past runs");
  return res.json();
}

export async function triggerAgentRun(payload) {
  const res = await fetch(`${API_BASE}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Agent run failed");
  }
  return res.json();
}

export async function searchCodeVectors(payload) {
  const res = await fetch(`${API_BASE}/api/vector-search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Vector search failed");
  return res.json();
}

