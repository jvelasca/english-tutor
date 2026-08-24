import { useCallback, useEffect, useRef, useState } from "react";
import { getModels, streamChat } from "../api/chat";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  saveConversation,
} from "../api/conversations";
import { createUser, listUsers } from "../api/users";
import { getProgress } from "../api/progress";
import { deriveTitle } from "../utils/title";
import { nextDefaultUserName } from "../utils/users";
import type {
  ConversationMeta,
  Message,
  ProgressSummary,
  TutorMode,
  User,
} from "../types/api";

const DEFAULT_MODEL = "qwen3.5:9b";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [models, setModels] = useState<string[]>([]);
  const [mode, setMode] = useState<TutorMode>("conversation");
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressSummary | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshConversations = useCallback(async () => {
    if (!currentUserId) return;
    try {
      setConversations(await listConversations(currentUserId));
    } catch {
      /* backend no disponible */
    }
  }, [currentUserId]);

  const refreshProgress = useCallback(async () => {
    if (!currentUserId) return;
    try {
      setProgress(await getProgress(currentUserId));
    } catch {
      /* backend no disponible */
    }
  }, [currentUserId]);

  useEffect(() => {
    getModels()
      .then((d) => {
        if (d.models && d.models.length) {
          setModels(d.models);
          if (!d.models.includes(model)) setModel(d.models[0]);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const existing = await listUsers();
        if (cancelled) return;
        if (existing.length > 0) {
          setUsers(existing);
          setCurrentUserId(existing[0].id);
        } else {
          const created = await createUser(nextDefaultUserName([]));
          if (cancelled) return;
          setUsers([created]);
          setCurrentUserId(created.id);
        }
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!currentUserId) return;
    setConversations([]);
    setConversationId(null);
    setMessages([]);
    void refreshConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUserId]);

  useEffect(() => {
    setProgress(null);
    void refreshProgress();
  }, [refreshProgress]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const newConversation = useCallback(async () => {
    if (!currentUserId) return;
    try {
      const conv = await createConversation(currentUserId);
      setConversationId(conv.id);
      setMessages([]);
      await refreshConversations();
    } catch {
      /* backend no disponible */
    }
  }, [currentUserId, refreshConversations]);

  const loadConversation = useCallback(
    async (id: string) => {
      if (!currentUserId) return;
      try {
        const conv = await getConversation(id, currentUserId);
        setConversationId(id);
        setMessages(conv.messages);
      } catch {
        /* backend no disponible */
      }
    },
    [currentUserId],
  );

  const removeConversation = useCallback(
    async (id: string) => {
      if (!currentUserId) return;
      try {
        await deleteConversation(id, currentUserId);
        await refreshConversations();
        if (conversationId === id) {
          setConversationId(null);
          setMessages([]);
        }
      } catch {
        /* backend no disponible */
      }
    },
    [conversationId, currentUserId, refreshConversations],
  );

  const persist = useCallback(
    async (id: string, history: Message[]) => {
      if (!currentUserId) return;
      try {
        await saveConversation(id, currentUserId, deriveTitle(history), history);
        await refreshConversations();
      } catch {
        /* backend no disponible */
      }
    },
    [currentUserId, refreshConversations],
  );

  const selectUser = useCallback((userId: string) => {
    setCurrentUserId(userId);
  }, []);

  const addUser = useCallback(
    async (name: string) => {
      const trimmed = name.trim();
      const finalName = trimmed || nextDefaultUserName(users.map((u) => u.name));
      try {
        const created = await createUser(finalName);
        setUsers((prev) => [...prev, created]);
        setCurrentUserId(created.id);
      } catch {
        /* backend no disponible */
      }
    },
    [users],
  );

  const sendText = useCallback(
    async (text: string): Promise<string> => {
      const trimmed = text.trim();
      if (!trimmed || loading || !currentUserId) return "";

      let cid = conversationId;
      if (!cid) {
        try {
          cid = (await createConversation(currentUserId)).id;
          setConversationId(cid);
        } catch {
          return "";
        }
      }

      const history: Message[] = [
        ...messages,
        { role: "user", content: trimmed, mode },
      ];
      setMessages(history);
      setLoading(true);

      let assistantReply = "";
      let errored = false;

      try {
        await streamChat(history, model, mode, {
          onDelta: (content) => {
            assistantReply += content;
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last && last.role === "assistant") {
                next[next.length - 1] = {
                  role: "assistant",
                  content: last.content + content,
                  mode,
                };
              } else {
                next.push({ role: "assistant", content, mode });
              }
              return next;
            });
          },
          onDone: () => {},
          onError: (message) => {
            errored = true;
            assistantReply = `Error al hablar con el modelo: ${message}`;
            setMessages((prev) => [
              ...prev,
              { role: "assistant", content: assistantReply, mode },
            ]);
          },
        });
      } catch (e) {
        errored = true;
        assistantReply = `Error al hablar con el modelo: ${(e as Error).message}`;
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: assistantReply, mode },
        ]);
      } finally {
        setLoading(false);
      }

      if (assistantReply && !errored) {
        void persist(cid, [
          ...history,
          { role: "assistant", content: assistantReply, mode },
        ]);
      }

      return errored ? "" : assistantReply;
    },
    [loading, messages, model, mode, conversationId, currentUserId, persist],
  );

  const send = useCallback(() => {
    const text = input.trim();
    if (!text) return;
    setInput("");
    void sendText(text);
  }, [input, sendText]);

  return {
    messages,
    input,
    setInput,
    loading,
    model,
    setModel,
    models,
    mode,
    setMode,
    conversations,
    conversationId,
    users,
    currentUserId,
    bottomRef,
    send,
    sendText,
    newConversation,
    loadConversation,
    removeConversation,
    selectUser,
    addUser,
    progress,
    refreshProgress,
  };
}
