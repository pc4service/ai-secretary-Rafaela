const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const opts: RequestInit = { credentials: "include" };

export async function chat(
  message: string,
  history: { role: string; content: string }[] = [],
  conversationId?: string | null
) {
  const res = await fetch(`${API_BASE}/api/v1/chat`, {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      history,
      conversation_id: conversationId || undefined,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Chat request failed");
  }
  return res.json();
}

export async function getSettings() {
  const res = await fetch(`${API_BASE}/api/v1/settings`, opts);
  if (!res.ok) throw new Error("Failed to load settings");
  return res.json();
}

export async function getMicrosoftAuthUrl() {
  const res = await fetch(`${API_BASE}/api/v1/auth/microsoft/login`, opts);
  if (!res.ok) throw new Error("Failed to get Microsoft auth URL");
  return res.json();
}

export async function getGoogleAuthUrl() {
  const res = await fetch(`${API_BASE}/api/v1/auth/google/login`, opts);
  if (!res.ok) throw new Error("Failed to get Google auth URL");
  return res.json();
}

export async function disconnectMicrosoft() {
  const res = await fetch(`${API_BASE}/api/v1/auth/microsoft/disconnect`, {
    ...opts,
    method: "POST",
  });
  return res.json();
}

export async function disconnectGoogle() {
  const res = await fetch(`${API_BASE}/api/v1/auth/google/disconnect`, {
    ...opts,
    method: "POST",
  });
  return res.json();
}

export async function resolveAction(actionId: string, approve: boolean) {
  const res = await fetch(`${API_BASE}/api/v1/actions/${actionId}/resolve`, {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approve }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to resolve action");
  }
  return res.json();
}

export async function getPendingActions(status = "pending") {
  const res = await fetch(
    `${API_BASE}/api/v1/actions/pending?status=${status}`,
    opts
  );
  if (!res.ok) throw new Error("Failed to load pending actions");
  return res.json();
}

export async function getActionHistory() {
  const res = await fetch(`${API_BASE}/api/v1/actions/history`, opts);
  if (!res.ok) throw new Error("Failed to load action history");
  return res.json();
}

export async function listConversations() {
  const res = await fetch(`${API_BASE}/api/v1/conversations`, opts);
  if (!res.ok) throw new Error("Failed to load conversations");
  return res.json();
}

export async function getConversationMessages(conversationId: string) {
  const res = await fetch(
    `${API_BASE}/api/v1/conversations/${conversationId}/messages`,
    opts
  );
  if (!res.ok) throw new Error("Failed to load messages");
  return res.json();
}

export async function deleteConversation(conversationId: string) {
  const res = await fetch(
    `${API_BASE}/api/v1/conversations/${conversationId}`,
    { ...opts, method: "DELETE" }
  );
  if (!res.ok) throw new Error("Failed to delete conversation");
  return res.json();
}
