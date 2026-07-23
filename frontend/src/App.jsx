import { useEffect, useRef, useState } from "react";
import "./App.css";
import { api } from "./api";

export default function App() {
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  const activeConversation = conversations.find((c) => c.id === activeId) || null;
  const isCancelled = activeConversation?.status === "cancelled";

  useEffect(() => {
    refreshConversations();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function refreshConversations() {
    try {
      setConversations(await api.listConversations());
    } catch (err) {
      setError(err.message);
    }
  }

  async function selectConversation(id) {
    setError(null);
    setActiveId(id);
    try {
      const data = await api.getConversation(id);
      setMessages(data.messages);
    } catch (err) {
      setError(err.message);
    }
  }

  function startNewConversation() {
    setActiveId(null);
    setMessages([]);
    setError(null);
  }

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending || isCancelled) return;

    setSending(true);
    setError(null);
    setInput("");
    setMessages((prev) => [
      ...prev,
      { id: `temp-${Date.now()}`, role: "user", content: text, created_at: new Date().toISOString() },
    ]);

    try {
      const data = await api.sendMessage(activeId, text);
      setActiveId(data.conversation_id);
      setMessages((prev) => [...prev, data.message]);
      await refreshConversations();
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  async function handleCancel() {
    if (!activeId) return;
    try {
      await api.cancelConversation(activeId);
      await refreshConversations();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <button className="new-chat-btn" onClick={startNewConversation}>
          + New conversation
        </button>
        <ul className="conversation-list">
          {conversations.map((c) => (
            <li key={c.id}>
              <button
                className={`conversation-item ${c.id === activeId ? "active" : ""}`}
                onClick={() => selectConversation(c.id)}
              >
                <span className="conversation-title">{c.title || "Untitled"}</span>
                {c.status === "cancelled" && <span className="badge">cancelled</span>}
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <main className="chat-panel">
        <header className="chat-header">
          <h1>Ollive Chatbot</h1>
          {activeConversation && !isCancelled && (
            <button className="cancel-btn" onClick={handleCancel}>
              Cancel conversation
            </button>
          )}
        </header>

        <div className="messages">
          {messages.map((m) => (
            <div key={m.id} className={`message ${m.role}`}>
              <div className="bubble">{m.content}</div>
            </div>
          ))}
          {sending && (
            <div className="message assistant">
              <div className="bubble typing">…</div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form className="composer" onSubmit={handleSend}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={isCancelled ? "This conversation is cancelled" : "Type a message..."}
            disabled={sending || isCancelled}
          />
          <button type="submit" disabled={sending || isCancelled}>
            Send
          </button>
        </form>
      </main>
    </div>
  );
}
