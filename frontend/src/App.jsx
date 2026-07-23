import { useEffect, useRef, useState } from "react";
import "./App.css";
import { api } from "./api";
import ConversationItem from "./components/ConversationItem.jsx";
import Dashboard from "./components/Dashboard.jsx";
import MessageBubble from "./components/MessageBubble.jsx";

const STARTER_PROMPTS = [
  { icon: "💡", label: "Explain a concept", prompt: "Explain how " },
  { icon: "✍️", label: "Help me write", prompt: "Help me write " },
  { icon: "🐛", label: "Debug an error", prompt: "Help me debug this error: " },
  { icon: "📝", label: "Summarize text", prompt: "Summarize the following text:\n\n" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("chat");
  const [conversations, setConversations] = useState([]);
  const [groups, setGroups] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [showNewGroupInput, setShowNewGroupInput] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");

  const bottomRef = useRef(null);
  const abortControllerRef = useRef(null);

  const activeConversation = conversations.find((c) => c.id === activeId) || null;
  const isCancelled = activeConversation?.status === "cancelled";
  const isEmptyNewConversation = !activeId && messages.length === 0;
  const filteredConversations = conversations.filter((c) =>
    (c.title || "Untitled").toLowerCase().includes(searchQuery.toLowerCase())
  );
  const activeConversations = filteredConversations.filter((c) => c.status !== "cancelled");
  const cancelledConversations = filteredConversations.filter((c) => c.status === "cancelled");
  const groupedActive = groups.map((g) => ({
    group: g,
    conversations: activeConversations.filter((c) => c.group_id === g.id),
  }));
  const ungroupedActive = activeConversations.filter(
    (c) => !c.group_id || !groups.some((g) => g.id === c.group_id)
  );
  const lastMessage = messages[messages.length - 1];
  const canRegenerate =
    activeId && !isCancelled && !isStreaming && lastMessage?.role === "assistant";

  useEffect(() => {
    refreshConversations();
    refreshGroups();
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

  async function refreshGroups() {
    try {
      setGroups(await api.listGroups());
    } catch (err) {
      setError(err.message);
    }
  }

  async function selectConversation(id) {
    abortControllerRef.current?.abort();
    setIsStreaming(false);
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
    abortControllerRef.current?.abort();
    setIsStreaming(false);
    setActiveId(null);
    setMessages([]);
    setInput("");
    setError(null);
    setActiveTab("chat");
  }

  function appendDeltaTo(tempId, content) {
    setMessages((prev) =>
      prev.map((m) => (m.id === tempId ? { ...m, content: m.content + content } : m))
    );
  }

  function replaceMessage(tempId, message) {
    setMessages((prev) => prev.map((m) => (m.id === tempId ? message : m)));
  }

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || isStreaming || isCancelled) return;

    const tempUserId = `temp-user-${Date.now()}`;
    const tempAssistantId = `temp-assistant-${Date.now()}-a`;

    setError(null);
    setInput("");
    setIsStreaming(true);
    setMessages((prev) => [
      ...prev,
      { id: tempUserId, role: "user", content: text, created_at: new Date().toISOString() },
      { id: tempAssistantId, role: "assistant", content: "", created_at: new Date().toISOString() },
    ]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await api.streamChat(
        activeId,
        text,
        {
          onStart: (payload) => {
            if (!activeId) setActiveId(payload.conversation_id);
            setMessages((prev) =>
              prev.map((m) => (m.id === tempUserId ? { ...m, id: payload.message_id } : m))
            );
          },
          onDelta: (payload) => appendDeltaTo(tempAssistantId, payload.content),
          onDone: (payload) => {
            replaceMessage(tempAssistantId, payload.message);
            refreshConversations();
          },
          onError: (payload) => setError(payload?.error || "inference_failed"),
        },
        controller.signal
      );
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message);
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }

  async function handleRegenerate() {
    if (!activeId || isStreaming) return;
    setError(null);
    setIsStreaming(true);

    const tempAssistantId = `temp-assistant-${Date.now()}-r`;
    setMessages((prev) => {
      const updated = [...prev];
      if (updated.length && updated[updated.length - 1].role === "assistant") {
        updated.pop();
      }
      updated.push({
        id: tempAssistantId,
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
      });
      return updated;
    });

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await api.regenerate(
        activeId,
        {
          onDelta: (payload) => appendDeltaTo(tempAssistantId, payload.content),
          onDone: (payload) => {
            replaceMessage(tempAssistantId, payload.message);
            refreshConversations();
          },
          onError: (payload) => setError(payload?.error || "inference_failed"),
        },
        controller.signal
      );
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message);
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }

  function handleStop() {
    abortControllerRef.current?.abort();
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

  function startRename(conv, e) {
    e.stopPropagation();
    setRenamingId(conv.id);
    setRenameValue(conv.title || "");
  }

  async function commitRename() {
    const title = renameValue.trim();
    const id = renamingId;
    setRenamingId(null);
    if (!title || !id) return;
    try {
      await api.renameConversation(id, title);
      await refreshConversations();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCreateGroup(e) {
    e.preventDefault();
    const name = newGroupName.trim();
    if (!name) {
      setShowNewGroupInput(false);
      return;
    }
    try {
      await api.createGroup(name);
      setNewGroupName("");
      setShowNewGroupInput(false);
      await refreshGroups();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeleteGroup(groupId, e) {
    e.stopPropagation();
    try {
      await api.deleteGroup(groupId);
      await Promise.all([refreshGroups(), refreshConversations()]);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleMoveToGroup(conversationId, groupId) {
    try {
      await api.assignGroup(conversationId, groupId);
      await refreshConversations();
    } catch (err) {
      setError(err.message);
    }
  }

  function renderConversationItem(c) {
    return (
      <ConversationItem
        key={c.id}
        conversation={c}
        isActive={c.id === activeId}
        isRenaming={renamingId === c.id}
        renameValue={renameValue}
        onRenameChange={setRenameValue}
        onCommitRename={commitRename}
        onCancelRename={() => setRenamingId(null)}
        onSelect={() => {
          setActiveTab("chat");
          selectConversation(c.id);
        }}
        onStartRename={(e) => startRename(c, e)}
        groups={groups}
        onMoveToGroup={(groupId) => handleMoveToGroup(c.id, groupId)}
      />
    );
  }

  function renderComposer() {
    return (
      <form className="composer" onSubmit={handleSend}>
        <input
          autoFocus
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isCancelled ? "This conversation is cancelled" : "Type a message..."}
          disabled={isStreaming || isCancelled}
        />
        {isStreaming ? (
          <button type="button" className="stop-btn" onClick={handleStop}>
            Stop
          </button>
        ) : (
          <button type="submit" disabled={isCancelled}>
            Send
          </button>
        )}
      </form>
    );
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="tab-switch">
          <button
            className={`tab-btn ${activeTab === "chat" ? "active" : ""}`}
            onClick={() => setActiveTab("chat")}
          >
            Chat
          </button>
          <button
            className={`tab-btn ${activeTab === "dashboard" ? "active" : ""}`}
            onClick={() => setActiveTab("dashboard")}
          >
            Dashboard
          </button>
        </div>

        <button className="new-chat-btn" onClick={startNewConversation}>
          + New conversation
        </button>

        <input
          className="search-input"
          placeholder="Search conversations…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />

        <div className="groups-header">
          <span>Groups</span>
          <button
            className="add-group-btn"
            onClick={() => setShowNewGroupInput(true)}
            title="New group"
          >
            +
          </button>
        </div>
        {showNewGroupInput && (
          <form onSubmit={handleCreateGroup}>
            <input
              autoFocus
              className="search-input"
              placeholder="Group name…"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              onBlur={handleCreateGroup}
              onKeyDown={(e) => e.key === "Escape" && setShowNewGroupInput(false)}
            />
          </form>
        )}

        <div className="sidebar-lists thin-scroll">
          {groupedActive.map(({ group, conversations: groupConversations }) => (
            <div key={group.id}>
              <div className="sidebar-section-label group-label">
                <span>{group.name}</span>
                <button
                  className="group-delete-btn"
                  onClick={(e) => handleDeleteGroup(group.id, e)}
                  title="Delete group"
                >
                  ×
                </button>
              </div>
              <ul className="conversation-list">
                {groupConversations.map(renderConversationItem)}
              </ul>
            </div>
          ))}

          {groups.length > 0 && ungroupedActive.length > 0 && (
            <div className="sidebar-section-label">Chats</div>
          )}
          <ul className="conversation-list">{ungroupedActive.map(renderConversationItem)}</ul>

          {cancelledConversations.length > 0 && (
            <>
              <div className="sidebar-section-label cancelled-label">Cancelled</div>
              <ul className="conversation-list">
                {cancelledConversations.map(renderConversationItem)}
              </ul>
            </>
          )}
        </div>
      </aside>

      {activeTab === "dashboard" ? (
        <Dashboard />
      ) : (
        <main className="chat-panel">
          <header className="chat-header">
            <h1>Ollive Chatbot</h1>
            {activeConversation && !isCancelled && (
              <button className="cancel-btn" onClick={handleCancel}>
                Cancel conversation
              </button>
            )}
          </header>

          {error && <div className="error-banner">{error}</div>}

          {isEmptyNewConversation ? (
            <div className="empty-state">
              <h2>What would you like to know?</h2>
              <div className="empty-state-composer">{renderComposer()}</div>
              <div className="starter-grid">
                {STARTER_PROMPTS.map((s) => (
                  <button
                    key={s.label}
                    className="starter-chip"
                    onClick={() => setInput(s.prompt)}
                  >
                    <span className="starter-icon">{s.icon}</span>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              <div className="messages thin-scroll">
                {messages.map((m, i) => (
                  <MessageBubble
                    key={m.id}
                    message={m}
                    precedingUserMessageId={
                      m.role === "assistant" &&
                      messages[i - 1]?.role === "user" &&
                      !String(messages[i - 1].id).startsWith("temp-")
                        ? messages[i - 1].id
                        : null
                    }
                    isLastAssistant={i === messages.length - 1 && canRegenerate}
                    onRegenerate={i === messages.length - 1 ? handleRegenerate : null}
                    regenerating={isStreaming && i === messages.length - 1}
                  />
                ))}
                <div ref={bottomRef} />
              </div>

              {renderComposer()}
            </>
          )}
        </main>
      )}
    </div>
  );
}
