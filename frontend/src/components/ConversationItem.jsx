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
}) {
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
      <button
        className={`conversation-item ${isActive ? "active" : ""}`}
        onClick={onSelect}
        onDoubleClick={onStartRename}
        title="Double-click to rename"
      >
        <span className="conversation-title">{conversation.title || "Untitled"}</span>
      </button>
    </li>
  );
}
