import { useCallback, useEffect, useRef, useState } from "react";
import { getModels, streamChat } from "../api/chat";
import { completeLesson as completeLessonRequest } from "../api/academy";
import { getSession, openSession, SessionPinError, setSessionPin } from "../api/session";
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
import { turnTelemetry } from "../utils/telemetry";
import { nextDefaultUserName } from "../utils/users";
import { planSession } from "../utils/session";
import { fallbackChatModel } from "../utils/models";
import {
  LAYOUT_DEFAULTS,
  parseLayout,
  serializeLayout,
  type LayoutState,
} from "../utils/layout";
import { DEFAULT_SECTION, isSection, type Section } from "../utils/sections";
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

// V3.21 (V20-05): el modelo por defecto se resuelve desde el backend
// (`/api/models` → `default_model`, fuente única en `config.py`); la constante
// local es SOLO un fallback de emergencia mientras no responde el backend.
const DEFAULT_MODEL = fallbackChatModel();

const TUTOR_MODES: TutorMode[] = [
  "conversation",
  "grammar",
  "exercises",
  "pronunciation",
];

/**
 * Por qué la puerta está pidiendo el PIN (V3.76). `null` = pidiéndolo por
 * primera vez (o tras un arranque, que es el caso normal de un perfil con PIN).
 */
export type PinFeedback = "pin-invalid" | "pin-throttled" | null;

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [models, setModels] = useState<string[]>([]);
  const [mode, setMode] = useState<TutorMode>("conversation");
  const [section, setSection] = useState<Section>(DEFAULT_SECTION);
  const [layout, setLayoutState] = useState<LayoutState>(LAYOUT_DEFAULTS);
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  // true cuando la lista de perfiles ya se ha cargado del backend (permite al
  // App distinguir "cargando" de "no hay ningún perfil seleccionado").
  const [usersLoaded, setUsersLoaded] = useState(false);
  // V3.76 (Fase 3 del P0): perfil que está esperando su PIN y por qué. Que el
  // PIN se pida es un estado de la **app**, no de un componente: así los tres
  // caminos que abren sesión (arranque, selector y alta) piden lo mismo y la
  // puerta solo tiene que pintarlo.
  const [pinPromptUserId, setPinPromptUserId] = useState<string | null>(null);
  const [pinFeedback, setPinFeedback] = useState<PinFeedback>(null);
  const [pinRetryAfter, setPinRetryAfter] = useState(0);
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
  // Lista de modelos ofertados por el backend (ref para lecturas no reactivas,
  // p. ej. al restaurar preferencias guardadas).
  const modelsRef = useRef<string[]>([]);
  const composeStartedAt = useRef<number | null>(null);
  const lastAssistantAt = useRef<number | null>(null);
  const layoutPersistTimer = useRef<number | null>(null);

  useEffect(() => {
    modelRef.current = model;
  }, [model]);

  useEffect(() => {
    modelsRef.current = models;
  }, [models]);

  // Marca el instante en que el alumno empieza a componer un mensaje (input de
  // vacío a no-vacío) para medir la duración de su turno.
  useEffect(() => {
    if (input === "") {
      composeStartedAt.current = null;
    } else if (composeStartedAt.current === null) {
      composeStartedAt.current = performance.now();
    }
  }, [input]);

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
        const list = d.models ?? [];
        if (list.length === 0) return;
        setModels(list);
        // V3.21 (V20-05): si el modelo activo ya no se oferta (p. ej. quedó
        // excluido como no utilizable), se cae al `default_model` que expone el
        // backend (fuente única) o, si no está utilizable, al primer modelo.
        if (modelRef.current && list.includes(modelRef.current)) return;
        const backendDefault = d.default_model ?? "";
        const next =
          backendDefault && list.includes(backendDefault)
            ? backendDefault
            : list[0];
        setModel(next);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // El backend excluye de la lista los modelos marcados como no utilizables en
  // config.UNUSABLE_MODELS (instalados pero demasiado lentos). Si el modelo
  // activo o el favorito guardado apuntan a uno excluido (p. ej. una
  // preferencia persistida antes de que dejara de ofertarse), se cae al primer
  // modelo disponible para que el chat nunca use un modelo lento.
  useEffect(() => {
    if (models.length === 0) return;
    if (!models.includes(model)) setModel(models[0]);
    if (favoriteModel && !models.includes(favoriteModel)) setFavoriteModel(null);
  }, [models, model, favoriteModel]);

  /**
   * Abre sesión para un perfil y, si el servidor pide PIN, deja la app en el
   * paso de PIN en vez de fallar en silencio (V3.76).
   *
   * Es el **único** camino que abre sesión: el arranque, el selector de perfil y
   * el alta comparten esta función, así que la política del PIN no puede quedar
   * despareja entre ellos. Devuelve si el perfil quedó activo.
   */
  const openProfile = useCallback(
    async (userId: string, pin?: string): Promise<boolean> => {
      try {
        const user = await openSession(userId, pin);
        setPinPromptUserId(null);
        setPinFeedback(null);
        setPinRetryAfter(0);
        setCurrentUserId(user.id);
        return true;
      } catch (err) {
        if (err instanceof SessionPinError) {
          // «Falta el PIN» no es un error que pintar: es el paso siguiente.
          setPinPromptUserId(userId);
          setPinFeedback(
            err.reason === "pin-required"
              ? null
              : err.reason === "pin-throttled"
                ? "pin-throttled"
                : "pin-invalid",
          );
          setPinRetryAfter(err.retryAfterSeconds);
          return false;
        }
        /* backend no disponible: no se cambia de perfil ni se pide PIN */
        return false;
      }
    },
    [],
  );

  const cancelPin = useCallback(() => {
    setPinPromptUserId(null);
    setPinFeedback(null);
    setPinRetryAfter(0);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // V3.75 (Fase 2 del P0): quién es el perfil activo lo dice **el
        // servidor**, no el navegador. La sesión viaja en una cookie
        // `et_session` HttpOnly que JavaScript no puede leer (ese es el punto:
        // antes bastaba con reescribir `et_user_id` para suplantar un perfil),
        // así que se **pregunta** con `GET /api/session`.
        const [existing, session] = await Promise.all([listUsers(), getSession()]);
        if (cancelled) return;
        setUsers(existing);
        // Resolución del perfil inicial (sesión del servidor → perfil único → null)
        // y, con ella, si hay que **abrir** sesión o basta con adoptarla. La
        // decisión es pura y tiene test propio (`utils/session.ts`): es el punto
        // donde un fallo se ve como «todo normal» mientras cada petición da 401.
        const plan = planSession(existing, session?.id ?? null);
        if (plan.action === "none") return;
        if (plan.action === "adopt") {
          setCurrentUserId(plan.userId);
          return;
        }
        if (plan.action === "pin") {
          // V3.76: el perfil tiene PIN. No se lanza un `POST` condenado a 401
          // —su error lo tragaría el `catch` de abajo y el arranque se vería
          // como «no ha pasado nada»—: se pide el PIN y se espera.
          setPinPromptUserId(plan.userId);
          return;
        }
        // Perfil resuelto **sin** sesión abierta (equipo recién instalado, o tras
        // un `DELETE /api/session`): se abre aquí antes de pintar nada.
        await openProfile(plan.userId);
      } catch {
        /* backend no disponible: se queda sin perfiles cargados */
      } finally {
        if (!cancelled) setUsersLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [openProfile]);

  // Carga las preferencias persistidas del usuario (modelo, modo, layout).
  useEffect(() => {
    if (!currentUserId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await getSettings(currentUserId);
        if (cancelled) return;
        const s = res.settings ?? {};
        const fav =
          typeof s.favorite_model === "string" && s.favorite_model
            ? s.favorite_model
            : "";
        const saved = typeof s.model === "string" ? s.model : "";
        const available = modelsRef.current;
        // Solo se restaura un modelo si sigue ofertándose por el backend. Una
        // preferencia que apunte a un modelo excluido (config.UNUSABLE_MODELS:
        // instalado pero no utilizable) se ignora; el efecto de saneo cae al
        // primer modelo disponible.
        if (fav && (available.length === 0 || available.includes(fav))) {
          setFavoriteModel(fav);
          setModel(fav);
        } else if (saved && (available.length === 0 || available.includes(saved))) {
          setModel(saved);
        }
        if (typeof s.mode === "string" && (TUTOR_MODES as string[]).includes(s.mode)) {
          setMode(s.mode as TutorMode);
        }
        if (typeof s.section === "string" && isSection(s.section)) {
          setSection(s.section);
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

  const selectUser = useCallback(
    (userId: string) => {
      // V3.75: elegir perfil es **abrir sesión** en el servidor. Antes esto
      // escribía la cookie `et_user_id`, que el propio cliente podía reescribir
      // para suplantar a otro perfil; ahora la firma el servidor y el estado local
      // se fija con el perfil que **él** devuelve, no con lo que pide el cliente.
      // V3.76: si el perfil tiene PIN, el servidor responde 401 `PIN_REQUIRED` y
      // `openProfile` deja la app en el paso de PIN.
      void openProfile(userId);
    },
    [openProfile],
  );

  const selectModel = useCallback(
    (next: string) => {
      setModel(next);
      persistSettings({ model: next });
    },
    [persistSettings],
  );

  const makeFavorite = useCallback(
    (next: string) => {
      setFavoriteModel(next);
      setModel(next);
      persistSettings({ favorite_model: next, model: next });
    },
    [persistSettings],
  );

  const selectMode = useCallback(
    (next: TutorMode) => {
      setMode(next);
      persistSettings({ mode: next });
    },
    [persistSettings],
  );

  const selectSection = useCallback(
    (next: Section) => {
      setSection(next);
      persistSettings({ section: next });
    },
    [persistSettings],
  );

  const setLayout = useCallback(
    (next: LayoutState) => {
      setLayoutState(next);
      // Persiste una sola vez al terminar de arrastrar (no en cada pointermove).
      if (layoutPersistTimer.current !== null) {
        window.clearTimeout(layoutPersistTimer.current);
      }
      layoutPersistTimer.current = window.setTimeout(() => {
        persistSettings({ layout: serializeLayout(next) });
      }, 400);
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

  /**
   * Pone, cambia o retira el PIN del perfil de la sesión (V3.76).
   *
   * Devuelve el resultado para que Ajustes pueda decir qué pasó sin inventarse
   * los mensajes: `ok`, PIN actual incorrecto, freno activo o avería. El perfil
   * devuelto trae `has_pin` ya actualizado, y con él se refresca la lista local:
   * la puerta tiene que saber si preguntar sin volver a pedir `GET /api/users`.
   */
  const setProfilePin = useCallback(
    async (
      currentPin: string | null,
      newPin: string,
    ): Promise<"ok" | "pin-invalid" | "pin-throttled" | "error"> => {
      try {
        const updated = await setSessionPin(currentPin, newPin);
        setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
        return "ok";
      } catch (err) {
        if (err instanceof SessionPinError) {
          return err.reason === "pin-throttled" ? "pin-throttled" : "pin-invalid";
        }
        return "error";
      }
    },
    [],
  );

  const addUser = useCallback(
    async (name: string): Promise<boolean> => {
      const trimmed = name.trim();
      const finalName = trimmed || nextDefaultUserName(users.map((u) => u.name));
      try {
        const created = await createUser(finalName);
        setUsers((prev) => [...prev, created]);
        // V3.75: crear un perfil **no** abre sesión. Sin este paso la app
        // mostraría el perfil nuevo como activo y todas las peticiones
        // responderían 401.
        // V3.76: se abre por el mismo camino que el resto. Un perfil recién
        // creado no puede tener PIN, pero si algún día lo tuviera, este punto ya
        // sabe pedirlo en vez de tragarse el error.
        return await openProfile(created.id);
      } catch {
        /* backend no disponible */
        return false;
      }
    },
    [users, openProfile],
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

      const sentAt = performance.now();
      const { duration_ms, latency_ms } = turnTelemetry({
        sentAt,
        composeStartedAt: composeStartedAt.current,
        lastAssistantAt: lastAssistantAt.current,
      });

      const history: Message[] = [
        ...messages,
        {
          id: crypto.randomUUID(),
          role: "user",
          content: trimmed,
          mode,
          ...(duration_ms != null ? { duration_ms } : {}),
          ...(latency_ms != null ? { latency_ms } : {}),
        },
      ];
      setMessages(history);
      setLoading(true);
      composeStartedAt.current = null;

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
          onDone: () => {
            lastAssistantAt.current = performance.now();
          },
          onError: (message) => {
            errored = true;
            assistantReply = `Error al hablar con el modelo: ${message}`;
            lastAssistantAt.current = performance.now();
            setMessages((prev) => [
              ...prev,
              { id: crypto.randomUUID(), role: "assistant", content: assistantReply, mode },
            ]);
          },
        }, currentUserId, activeObjective?.id, cid, assistantId);
      } catch (e) {
        errored = true;
        assistantReply = `Error al hablar con el modelo: ${(e as Error).message}`;
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: "assistant", content: assistantReply, mode },
        ]);
      } finally {
        setLoading(false);
        lastAssistantAt.current = performance.now();
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
    makeFavorite,
    mode,
    setMode,
    selectMode,
    section,
    selectSection,
    layout,
    setLayout,
    conversations,
    conversationId,
    users,
    currentUserId,
    usersLoaded,
    // V3.76 (Fase 3 del P0): estado del paso de PIN y las acciones que lo
    // cierran. La puerta de perfil los pinta; el resto de la app no los toca.
    pinPromptUserId,
    pinFeedback,
    pinRetryAfter,
    submitPin: openProfile,
    cancelPin,
    setProfilePin,
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

export type ChatApi = ReturnType<typeof useChat>;
