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

export const api = {
  listConversations: () => request("/conversations/"),
  getConversation: (id) => request(`/conversations/${id}/`),
  cancelConversation: (id) => request(`/conversations/${id}/cancel/`, { method: "POST" }),
  sendMessage: (conversationId, message) =>
    request("/chat/", {
      method: "POST",
      body: JSON.stringify(
        conversationId ? { conversation_id: conversationId, message } : { message }
      ),
    }),
};
