import type { ConversationMeta } from "../types/api";
import { useI18n } from "../hooks/useI18n";

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
  const { t } = useI18n();
  return (
    <aside className="sidebar">
      <button className="new-chat" onClick={onNew}>
        + {t("chat.new")}
      </button>
      <div className="conversation-list">
        {conversations.length === 0 && (
          <p className="conversation-empty">
            {t("chat.empty")}
            <br />
            {t("chat.emptyHint")}
          </p>
        )}
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
              title={t("common.delete")}
              aria-label={`${t("common.delete")} ${c.title}`}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}
