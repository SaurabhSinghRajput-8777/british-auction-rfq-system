const API_BASE = "http://localhost:8000/api/v1";

let storedUserId = localStorage.getItem("demo_user_id") || "1";

export function getCurrentUserId() {
  return storedUserId;
}

export function setCurrentUserId(id) {
  storedUserId = String(id);
  localStorage.setItem("demo_user_id", storedUserId);
  return storedUserId;
}

export async function fetchUsers() {
  const res = await fetch(`${API_BASE}/users`);
  if (!res.ok) throw new Error("Failed to fetch demo users");
  return res.json();
}

export async function fetchCurrentUser() {
  const users = await fetchUsers();
  const current = users.find((u) => String(u.id) === String(storedUserId)) || users[0];
  if (current) {
    setCurrentUserId(current.id);
  }
  return current;
}

export async function switchCurrentUser(userId) {
  setCurrentUserId(userId);
  return fetchCurrentUser();
}

export async function fetchRfqs(statusFilter = null) {
  const url = statusFilter ? `${API_BASE}/rfqs?status=${statusFilter}` : `${API_BASE}/rfqs`;
  const res = await fetch(url, {
    headers: { "X-User-Id": getCurrentUserId() },
  });
  if (!res.ok) throw new Error("Failed to fetch RFQs");
  return res.json();
}

export async function fetchRfqDetails(rfqId) {
  const res = await fetch(`${API_BASE}/rfqs/${rfqId}`, {
    headers: { "X-User-Id": getCurrentUserId() },
  });
  if (!res.ok) throw new Error("Failed to fetch RFQ details");
  return res.json();
}

export async function createRfq(payload, userId = getCurrentUserId()) {
  const res = await fetch(`${API_BASE}/rfqs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": String(userId),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to create RFQ");
  }
  return res.json();
}

export async function submitBid(rfqId, payload, userId = getCurrentUserId()) {
  const res = await fetch(`${API_BASE}/rfqs/${rfqId}/bids`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": String(userId),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to submit quote");
  }
  return res.json();
}
