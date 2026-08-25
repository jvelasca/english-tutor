import { useCallback, useEffect, useRef, useState } from "react";
import { getModels, streamChat } from "../api/chat";
import { completeLesson as completeLessonRequest } from "../api/academy";
import { readUserIdCookie, writeUserIdCookie } from "../utils/cookie";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  saveConversation,
} from "../api/conversations";
import { createUser, listUsers, updateUser as updateUserApi, type UserPatch } from "../api/users";
import { getProgressHistory } from "../api/progress";
import { getSettings, saveSettings } from "../api/settings";
import { analyzeText, getEvents, getProfile } from "../api/learning";
import { deriveTitle } from "../utils/title";
import { nextDefaultUserName, resolveInitialUserId } from "../utils/users";import {
  LAYOUT_DEFAULTS,
  parseLayout,
  serializeLayout,
  type LayoutState,
} from "../utils/layout";
import type {
  Bucket,
  ConversationMeta,
  LearningEvent,
  LearningProfile,
  Message,
  ProgressHistory,
  TutorMode,
  User,
} from "../types/api";

const DEFAULT_MODEL = "qwen3.5:9b";

const TUTOR_MODES: TutorMode[] = [
  "conversation",
  "grammar",
  "exercises",
  "pronunciation",
];

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [models, setModels] = useState<string[]>([]);
  const [mode, setMode] = useState<TutorMode>("conversation");
  const [layout, setLayoutState] = useState<LayoutState>(LAYOUT_DEFAULTS);
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [history, setHistory] = useState<ProgressHistory | null>(null);
  const [events, setEvents] = useState<LearningEvent[]>([]);
  const [bucket, setBucket] = useState<Bucket>("week");
  const [profile, setProfile] = useState<LearningProfile | null>(null);
  const [favoriteModel, setFavoriteModel] = useState<string | null>(null);
  const [activeObjective, setActiveObjective] = useState<{
    id: string;
    title: string;
    levelId: string;
    skills: string[];
  } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const modelRef = useRef<string>(DEFAULT_MODEL);

  useEffect(() => {
    modelRef.current = model;
  }, [model]);

  const refreshConversations = useCallback(async () => {
    if (!currentUserId) return;
    try {
      setConversations(await listConversations(currentUserId));
    } catch {
      /* backend no disponible */
    }
  }, [currentUserId]);

  const refreshHistory = useCallback(async () => {
    if (!currentUserId) return;
    try {
      setHistory(await getProgressHistory(currentUserId, bucket));
    } catch {
      /* backend no disponible */
    }
  }, [currentUserId, bucket]);

  const refreshEvents = useCallback(async () => {
    if (!currentUserId) return;
    try {
      setEvents(await getEvents(currentUserId));
    } catch {
      /* backend no disponible */
    }
  }, [currentUserId]);

  const refreshProfile = useCallback(async () => {
    if (!currentUserId) return;
    try {
      setProfile(await getProfile(currentUserId));
    } catch {
      /* backend no disponible */
    }
  }, [currentUserId]);

  useEffect(() => {
    getModels()
      .then((d) => {
        if (d.models && d.models.length) {
          setModels(d.models);
          if (!d.models.includes(modelRef.current)) setModel(d.models[0]);
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
        if (existing.length === 0) {
          const created = await createUser(nextDefaultUserName([]));
          if (cancelled) return;
          setUsers([created]);
          setCurrentUserId(created.id);
        } else {
          setUsers(existing);
          // Se recuerda el último perfil usado (cookie); si no existe, con un
          // único usuario se auto-selecciona y si hay varios el usuario elige.
          setCurrentUserId(resolveInitialUserId(existing, readUserIdCookie()));
        }
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Carga las preferencias persistidas del usuario (modelo, modo, layout).
  useEffect(() => {
    if (!currentUserId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await getSettings(currentUserId);
        if (cancelled) return;
        const s = res.settings ?? {};
        if (typeof s.favorite_model === "string" && s.favorite_model) {
          setFavoriteModel(s.favorite_model);
          setModel(s.favorite_model);
        } else if (typeof s.model === "string" && s.model) {
          setModel(s.model);
        }
        if (typeof s.mode === "string" && (TUTOR_MODES as string[]).includes(s.mode)) {
          setMode(s.mode as TutorMode);
        }
        if (typeof s.layout === "string") setLayoutState(parseLayout(s.layout));
      } catch {
        /* sin preferencias guardadas todavía */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [currentUserId]);

  useEffect(() => {
    if (!currentUserId) return;
    setConversations([]);
    setConversationId(null);
    setMessages([]);
    setActiveObjective(null);
    void refreshConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUserId]);

  useEffect(() => {
    setHistory(null);
    setEvents([]);
  }, [currentUserId]);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  useEffect(() => {
    void refreshEvents();
  }, [refreshEvents]);

  useEffect(() => {
    setProfile(null);
    void refreshProfile();
  }, [refreshProfile]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const newConversation = useCallback(async () => {
    if (!currentUserId) return;
    try {
      const conv = await createConversation(currentUserId);
      setConversationId(conv.id);
      setMessages([]);
      setActiveObjective(null);
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

  const startLesson = useCallback(
    (objectiveId: string, title: string, levelId: string, skills: string[]) => {
      setConversationId(null);
      setMessages([]);
      setActiveObjective({ id: objectiveId, title, levelId, skills });
    },
    [],
  );

  const clearLesson = useCallback(() => setActiveObjective(null), []);

  const completeLesson = useCallback(async () => {
    const objective = activeObjective;
    setActiveObjective(null);
    if (!objective || !currentUserId) return;
    try {
      await completeLessonRequest(currentUserId, objective.levelId, objective.id);
    } catch {
      /* backend no disponible */
    }
  }, [activeObjective, currentUserId]);

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

  const persistSettings = useCallback(
    (patch: Record<string, string>) => {
      if (!currentUserId) return;
      void saveSettings(currentUserId, patch).catch(() => {});
    },
    [currentUserId],
  );

  const selectUser = useCallback((userId: string) => {
    setCurrentUserId(userId);
    writeUserIdCookie(userId);
  }, []);

  const selectModel = useCallback(
    (next: string) => {
      setModel(next);
      persistSettings({ model: next });
    },
    [persistSettings],
  );

  const toggleFavorite = useCallback(() => {
    const next = favoriteModel === model ? null : model;
    setFavoriteModel(next);
    persistSettings({ favorite_model: next ?? "" });
  }, [model, favoriteModel, persistSettings]);

  const selectMode = useCallback(
    (next: TutorMode) => {
      setMode(next);
      persistSettings({ mode: next });
    },
    [persistSettings],
  );

  const setLayout = useCallback(
    (next: LayoutState) => {
      setLayoutState(next);
      persistSettings({ layout: serializeLayout(next) });
    },
    [persistSettings],
  );

  const editUser = useCallback(
    async (id: string, patch: UserPatch): Promise<User | null> => {
      const updated = await updateUserApi(id, patch);
      setUsers((prev) => prev.map((u) => (u.id === id ? updated : u)));
      return updated;
    },
    [],
  );

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
        { id: crypto.randomUUID(), role: "user", content: trimmed, mode },
      ];
      setMessages(history);
      setLoading(true);

      const assistantId = crypto.randomUUID();
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
                  id: assistantId,
                  role: "assistant",
                  content: last.content + content,
                  mode,
                };
              } else {
                next.push({ id: assistantId, role: "assistant", content, mode });
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
              { id: crypto.randomUUID(), role: "assistant", content: assistantReply, mode },
            ]);
          },
        }, currentUserId, activeObjective?.id);
      } catch (e) {
        errored = true;
        assistantReply = `Error al hablar con el modelo: ${(e as Error).message}`;
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: "assistant", content: assistantReply, mode },
        ]);
      } finally {
        setLoading(false);
      }

      if (assistantReply && !errored) {
        void persist(cid, [
          ...history,
          { id: assistantId, role: "assistant", content: assistantReply, mode },
        ]);
      }

      // Alimenta el perfil de aprendizaje (vocabulario + gramática) de forma
      // no bloqueante y refresca el perfil.
      void analyzeText(trimmed, currentUserId)
        .then(() => {
          refreshProfile();
          refreshEvents();
          refreshHistory();
        })
        .catch(() => {});

      return errored ? "" : assistantReply;
    },
    [
      loading,
      messages,
      model,
      mode,
      conversationId,
      currentUserId,
      activeObjective,
      persist,
      refreshProfile,
      refreshEvents,
      refreshHistory,
    ],
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
    selectModel,
    models,
    favoriteModel,
    toggleFavorite,
    mode,
    setMode,
    selectMode,
    layout,
    setLayout,
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
    editUser,
    history,
    events,
    bucket,
    setBucket,
    refreshHistory,
    refreshEvents,
    profile,
    refreshProfile,
    activeObjective,
    startLesson,
    clearLesson,
    completeLesson,
  };
}
