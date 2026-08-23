import type { ConversationMeta } from "../types/api";

interface SidebarProps {
  conversations: ConversationMeta[];
  activeId: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

export function Sidebar({
  conversations,
  activeId,
  onNew,
  onSelect,
  onDelete,
}: SidebarProps) {
  return (
    <aside className="sidebar">
      <button className="new-chat" onClick={onNew}>
        + Nuevo chat
      </button>
      <div className="conversation-list">
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`conversation-item${c.id === activeId ? " active" : ""}`}
          >
            <button
              className="conversation-title"
              onClick={() => onSelect(c.id)}
              title={c.title}
            >
              {c.title}
            </button>
            <button
              className="conversation-delete"
              onClick={() => onDelete(c.id)}
              title="Eliminar"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}
