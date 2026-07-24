export default function ConversationItem({
  conversation,
  isActive,
  isRenaming,
  renameValue,
  onRenameChange,
  onCommitRename,
  onCancelRename,
  onSelect,
  onStartRename,
  draggable,
  onDragStart,
}) {
  const isCancelled = conversation.status === "cancelled";

  if (isRenaming) {
    return (
      <li>
        <input
          autoFocus
          className="rename-input"
          value={renameValue}
          onChange={(e) => onRenameChange(e.target.value)}
          onBlur={onCommitRename}
          onKeyDown={(e) => {
            if (e.key === "Enter") onCommitRename();
            if (e.key === "Escape") onCancelRename();
          }}
        />
      </li>
    );
  }

  return (
    <li>
      <div
        className={`conversation-item ${isActive ? "active" : ""} ${isCancelled ? "cancelled" : ""}`}
        draggable={draggable}
        onDragStart={onDragStart}
      >
        <button
          className="conversation-item-btn"
          onClick={onSelect}
          onDoubleClick={onStartRename}
          title="Double-click to rename"
        >
          <span className="conversation-title">{conversation.title || "Untitled"}</span>
        </button>
      </div>
    </li>
  );
}
