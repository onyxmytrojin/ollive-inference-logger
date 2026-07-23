const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Request failed: ${res.status}`);
  }

  if (res.status === 202 || res.status === 204) return null;
  return res.json();
}

async function consumeSSE(res, { onStart, onDelta, onDone, onError }) {
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Request failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop();

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const payload = JSON.parse(line.slice(5).trim());
      if (payload.type === "start") onStart?.(payload);
      else if (payload.type === "delta") onDelta?.(payload);
      else if (payload.type === "done") onDone?.(payload);
      else if (payload.type === "error") onError?.(payload);
    }
  }
}

export const api = {
  listConversations: () => request("/conversations/"),
  getConversation: (id) => request(`/conversations/${id}/`),
  cancelConversation: (id) => request(`/conversations/${id}/cancel/`, { method: "POST" }),
  renameConversation: (id, title) =>
    request(`/conversations/${id}/rename/`, {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  getMessageInference: (messageId) => request(`/messages/${messageId}/inference/`),
  getMetricsSummary: (window) => request(`/metrics/summary/?window=${window}`),
  getMetricsTimeseries: (window) => request(`/metrics/timeseries/?window=${window}`),

  sendMessage: (conversationId, message) =>
    request("/chat/", {
      method: "POST",
      body: JSON.stringify(
        conversationId ? { conversation_id: conversationId, message } : { message }
      ),
    }),

  streamChat: async (conversationId, message, callbacks, signal) => {
    const res = await fetch(`${API_BASE_URL}/chat/stream/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        conversationId ? { conversation_id: conversationId, message } : { message }
      ),
      signal,
    });
    return consumeSSE(res, callbacks);
  },

  regenerate: async (conversationId, callbacks, signal) => {
    const res = await fetch(`${API_BASE_URL}/conversations/${conversationId}/regenerate/`, {
      method: "POST",
      signal,
    });
    return consumeSSE(res, callbacks);
  },
};
