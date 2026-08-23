import { useCallback, useEffect, useRef, useState } from "react";
import { getModels, streamChat } from "../api/chat";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  saveConversation,
} from "../api/conversations";
import { deriveTitle } from "../utils/title";
import type { ConversationMeta, Message, TutorMode } from "../types/api";

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
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await listConversations());
    } catch {
      /* backend no disponible */
    }
  }, []);

  useEffect(() => {
    getModels()
      .then((d) => {
        if (d.models && d.models.length) {
          setModels(d.models);
          if (!d.models.includes(model)) setModel(d.models[0]);
        }
      })
      .catch(() => {});
    void refreshConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const newConversation = useCallback(async () => {
    try {
      const conv = await createConversation();
      setConversationId(conv.id);
      setMessages([]);
      await refreshConversations();
    } catch {
      /* backend no disponible */
    }
  }, [refreshConversations]);

  const loadConversation = useCallback(async (id: string) => {
    try {
      const conv = await getConversation(id);
      setConversationId(id);
      setMessages(conv.messages);
    } catch {
      /* backend no disponible */
    }
  }, []);

  const removeConversation = useCallback(
    async (id: string) => {
      try {
        await deleteConversation(id);
        await refreshConversations();
        if (conversationId === id) {
          setConversationId(null);
          setMessages([]);
        }
      } catch {
        /* backend no disponible */
      }
    },
    [conversationId, refreshConversations],
  );

  const persist = useCallback(
    async (id: string, history: Message[]) => {
      try {
        await saveConversation(id, deriveTitle(history), history);
        await refreshConversations();
      } catch {
        /* backend no disponible */
      }
    },
    [refreshConversations],
  );

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    let cid = conversationId;
    if (!cid) {
      try {
        cid = (await createConversation()).id;
        setConversationId(cid);
      } catch {
        return;
      }
    }

    const history: Message[] = [...messages, { role: "user", content: text }];
    setMessages(history);
    setInput("");
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
              };
            } else {
              next.push({ role: "assistant", content });
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
            { role: "assistant", content: assistantReply },
          ]);
        },
      });
    } catch (e) {
      errored = true;
      assistantReply = `Error al hablar con el modelo: ${(e as Error).message}`;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: assistantReply },
      ]);
    } finally {
      setLoading(false);
    }

    if (assistantReply && !errored) {
      void persist(cid, [
        ...history,
        { role: "assistant", content: assistantReply },
      ]);
    }
  }, [input, loading, messages, model, mode, conversationId, persist]);

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
    bottomRef,
    send,
    newConversation,
    loadConversation,
    removeConversation,
  };
}
