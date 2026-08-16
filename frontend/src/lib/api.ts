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

export async function getOpenAIAuthUrl() {
  const res = await fetch(`${API_BASE}/api/v1/auth/openai/login`, opts);
  if (!res.ok) throw new Error("Failed to get OpenAI auth URL");
  return res.json();
}

export async function disconnectOpenAI() {
  const res = await fetch(`${API_BASE}/api/v1/auth/openai/disconnect`, {
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

export type StreamHandlers = {
  onStatus?: (message: string) => void;
  onDelta?: (text: string) => void;
  onDone?: (data: {
    reply: string;
    pending_action_id?: string | null;
    conversation_id?: string;
  }) => void;
  onError?: (message: string) => void;
};

/** SSE chat stream against POST /api/v1/chat/stream */
export async function streamChat(
  message: string,
  history: { role: string; content: string }[] = [],
  conversationId: string | null | undefined,
  handlers: StreamHandlers
) {
  const res = await fetch(`${API_BASE}/api/v1/chat/stream`, {
    ...opts,
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      message,
      history,
      conversation_id: conversationId || undefined,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Stream request failed");
  }
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part
        .split("\n")
        .find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        const data = JSON.parse(line.slice(6));
        if (data.type === "status") handlers.onStatus?.(data.message);
        else if (data.type === "delta") handlers.onDelta?.(data.text || "");
        else if (data.type === "done") handlers.onDone?.(data);
        else if (data.type === "error")
          handlers.onError?.(data.message || "Error");
      } catch {
        /* ignore partial JSON */
      }
    }
  }
}
