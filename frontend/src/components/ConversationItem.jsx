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
  groups,
  onMoveToGroup,
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
      <div className={`conversation-item ${isActive ? "active" : ""} ${isCancelled ? "cancelled" : ""}`}>
        <button
          className="conversation-item-btn"
          onClick={onSelect}
          onDoubleClick={onStartRename}
          title="Double-click to rename"
        >
          <span className="conversation-title">{conversation.title || "Untitled"}</span>
        </button>

        {!isCancelled && groups && onMoveToGroup && (
          <select
            className="group-select"
            value={conversation.group_id || ""}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => onMoveToGroup(e.target.value || null)}
            title="Move to group"
          >
            <option value="">No group</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        )}
      </div>
    </li>
  );
}
