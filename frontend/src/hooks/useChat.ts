import { useCallback, useEffect, useRef, useState } from "react";
import { getModels, streamChat } from "../api/chat";
import { completeLesson as completeLessonRequest } from "../api/academy";
import {
  changeEmail as changeEmailApi,
  changePassword as changePasswordApi,
  closeSession,
  getSession,
  openSession,
  resendVerification as resendVerificationApi,
  SessionLoginError,
  unenrollAccount,
} from "../api/session";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  saveConversation,
} from "../api/conversations";
import { updateUser as updateUserApi, type UserPatch } from "../api/users";
import {
  requestProfile,
  requestProfileDelete,
  type ProfileRequestOutcome,
  type RequestedAvatar,
} from "../api/profileRequests";
import { getProgressHistory } from "../api/progress";
import { getSettings, saveSettings } from "../api/settings";
import { analyzeText, getEvents, getProfile } from "../api/learning";
import { deriveTitle } from "../utils/title";
import { ApiError } from "../api/client";
import { turnTelemetry } from "../utils/telemetry";
import { nextDefaultUserName } from "../utils/users";
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
 * Cómo terminó un intento de entrada (V3.82).
 *
 * Sustituye al estado `passwordPromptUserId` de V3.81: ya no hay un «paso de
 * contraseña» separado del selector, porque **entrar es** escribir email y
 * contraseña. La puerta recibe el desenlace y decide qué texto pintar.
 */
export type LoginOutcome =
  | { ok: true; user: User }
  | {
      ok: false;
      reason:
        | "invalid-credentials"
        | "not-activated"
        | "disabled"
        | "unenrolled"
        | "throttled"
        | "error";
      retryAfterSeconds?: number;
    };

/** Cómo terminó una acción del diálogo de cuenta. */
export type AccountActionOutcome =
  | { ok: true; user: User }
  | {
      ok: false;
      reason:
        | "password-invalid"
        | "password-required"
        | "password-format"
        | "email-format"
        | "email-taken"
        | "error";
    };

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
  // V3.80.2: ¿falló la sonda de la sesión? La puerta lo usa para ofrecer
  // «Reintentar» en vez de decir «no hay sesión»: confundir las dos cosas es
  // exactamente lo que dejaba al alumno sin salida.
  const [usersLoadFailed, setUsersLoadFailed] = useState(false);
  // V3.81: la contraseña vigente es temporal (la puso el webmaster) y hay que
  // cambiarla antes de usar nada. Se aprende de la respuesta del servidor, nunca
  // se adivina; el servidor lo hace cumplir igual con `403
  // PASSWORD_CHANGE_REQUIRED`, esto solo es para no llegar a ese 403.
  const [mustChangePassword, setMustChangePassword] = useState(false);
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
   * Abre sesión con **email + contraseña** (V3.82).
   *
   * Es el único camino que abre sesión. Lo que devuelve es un desenlace tipado
   * para que la puerta pueda decir qué pasa: credenciales que no cuadran, cuenta
   * sin activar (su invitación está en el correo), cuenta fuera de servicio o el
   * freno de intentos. Ninguno de esos casos es una avería, y tratarlos como
   * «algo falló» era exactamente lo que hacía indescifrable la puerta.
   */
  const login = useCallback(
    async (email: string, password: string): Promise<LoginOutcome> => {
      try {
        const user = await openSession(email, password);
        setMustChangePassword(user.must_change_password === true);
        setCurrentUserId(user.id);
        setUsers([user]);
        return { ok: true, user };
      } catch (err) {
        if (err instanceof SessionLoginError) {
          return err.reason === "throttled"
            ? {
                ok: false,
                reason: "throttled",
                retryAfterSeconds: err.retryAfterSeconds,
              }
            : { ok: false, reason: err.reason };
        }
        // Backend caído o sin red: no se cambia de estado ni se finge que la
        // contraseña era mala.
        return { ok: false, reason: "error" };
      }
    },
    [],
  );

  /**
   * Carga la sesión del servidor al arrancar (V3.82).
   *
   * Antes esto pedía también la lista de cuentas y resolvía «con quién entro»
   * (`planSession`). Con el login por email no hay lista que resolver: o hay
   * sesión y se adopta, o no la hay y se pinta la puerta. Menos estados, y sobre
   * todo: deja de existir el arranque automático que abría sesión «nombrando» a
   * una cuenta heredada — que era justo el agujero que G0 vigilaba.
   */
  const loadSession = useCallback(async () => {
    setUsersLoaded(false);
    try {
      const session = await getSession();
      if (session) {
        setCurrentUserId(session.id);
        setUsers([session]);
        setMustChangePassword(session.must_change_password === true);
      } else {
        setCurrentUserId(null);
        setUsers([]);
      }
      setUsersLoadFailed(false);
    } catch {
      // Un fallo de red no es «no hay sesión»: se declara para que la puerta
      // ofrezca reintentar en vez de mentir.
      setUsersLoadFailed(true);
    } finally {
      setUsersLoaded(true);
    }
  }, []);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

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
   * Salir: cierra la sesión en el servidor (caduca la cookie) y vacía el estado
   * local para que la puerta vuelva a pedir credencial.
   *
   * V3.81 lo usa por primera vez: `closeSession()` existía desde V3.75 sin que
   * nadie la llamara, así que en un producto con selector de cuentas compartido en
   * casa **no había forma de salir** salvo borrar las cookies a mano.
   */
  const signOut = useCallback(async () => {
    await closeSession().catch(() => {
      /* sin backend la cookie también caduca sola: la UI sale igual */
    });
    setCurrentUserId(null);
    setUsers([]);
    setMustChangePassword(false);
    await loadSession();
  }, [loadSession]);

  /**
   * Cambia la contraseña de la cuenta de la sesión. Al terminar, la app relee la
   * cuenta: si la contraseña era temporal, el aviso de cambio forzado desaparece
   * con la misma respuesta que lo levantó.
   */
  const changePasswordNow = useCallback(
    async (
      currentPassword: string | null,
      newPassword: string,
    ): Promise<AccountActionOutcome> => {
      try {
        const updated = await changePasswordApi(currentPassword, newPassword);
        setMustChangePassword(updated.must_change_password === true);
        setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
        return { ok: true, user: updated };
      } catch (err) {
        return { ok: false, reason: accountFailure(err) };
      }
    },
    [],
  );

  /** Cambia el email de la cuenta de la sesión (exige la contraseña). */
  const changeEmailNow = useCallback(
    async (password: string, email: string): Promise<AccountActionOutcome> => {
      try {
        const updated = await changeEmailApi(password, email.trim());
        setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
        return { ok: true, user: updated };
      } catch (err) {
        return { ok: false, reason: accountFailure(err) };
      }
    },
    [],
  );

  /** Reenvía el enlace de verificación. `sent: false` = no hay SMTP (híbrido). */
  const resendVerificationNow = useCallback(async (): Promise<boolean> => {
    const res = await resendVerificationApi();
    return res.sent;
  }, []);

  /**
   * Baja autoservicio: cierra la cuenta (sin borrar nada) y deja la app en la
   * puerta. Se limpia el estado local igual que en `signOut` porque el servidor ya
   * retiró la cookie: seguir pintando la app con una sesión que no existe sería
   * mentir hasta el siguiente 403.
   */
  const unenrollNow = useCallback(
    async (password: string): Promise<AccountActionOutcome> => {
      try {
        const res = await unenrollAccount(password);
        setCurrentUserId(null);
        setUsers([]);
        setMustChangePassword(false);
        await loadSession();
        return { ok: true, user: res.user };
      } catch (err) {
        return { ok: false, reason: accountFailure(err) };
      }
    },
    [loadSession],
  );

  /**
   * Pide un acceso: nombre/nick, email y avatar (V3.77; email y avatar en V3.82).
   *
   * Sigue sin crear nada —la solicitud va a la cola del webmaster— pero ahora
   * lleva **todo lo que hace falta para autorizarla**: sin el email no habría
   * forma de mandar la invitación, y sin la contraseña nadie entra nunca sin
   * demostrar quién es. Por eso el formulario ya no es «un nombre y a esperar».
   *
   * El nombre sí se puede dejar en blanco y se resuelve con el siguiente libre
   * («Alumno 2» en la cola del webmaster es más útil que una fila vacía).
   */
  const requestProfileForGate = useCallback(
    async (
      name: string,
      email: string,
      avatar: RequestedAvatar = {},
      note = "",
    ): Promise<ProfileRequestOutcome> => {
      const trimmed = name.trim();
      const finalName = trimmed || nextDefaultUserName(users.map((u) => u.name));
      return requestProfile(finalName, email, avatar, note);
    },
    [users],
  );

  /**
   * El perfil de la sesión pide su baja. **No** desactiva ni borra nada: deja la
   * solicitud en la cola del webmaster, que es quien decide (y quien, si
   * aprueba, desactiva el perfil — la evidencia sigue intacta y reversible).
   */
  const requestProfileRemoval = useCallback(
    (note = ""): Promise<ProfileRequestOutcome> => requestProfileDelete(note),
    [],
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
    // V3.80.2: la puerta distingue «no hay sesión» de «no se pudo comprobar» y
    // puede volver a intentarlo sin recargar la página.
    usersLoadFailed,
    reloadSession: loadSession,
    // V3.82: entrar es un acto explícito (email + contraseña). `login` devuelve el
    // desenlace del intento y la puerta lo pinta; el resto del ciclo de vida de la
    // cuenta vive en las acciones de abajo.
    login,
    mustChangePassword,
    changePasswordNow,
    changeEmailNow,
    resendVerificationNow,
    unenrollNow,
    signOut,
    bottomRef,
    send,
    sendText,
    newConversation,
    loadConversation,
    removeConversation,
    requestProfileForGate,
    requestProfileRemoval,
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

/**
 * Traduce un fallo de la API al desenlace que el diálogo de cuenta sabe pintar.
 *
 * Se decide aquí, una sola vez, en vez de en cada componente: `PASSWORD_INVALID`
 * (la contraseña actual no cuadra) y `PASSWORD_REQUIRED` (hace falta y no llegó)
 * son desenlaces **de producto** y merecen su propio texto; el resto es avería.
 * Un `PASSWORD_THROTTLED` cae en `password-invalid` a propósito: el mensaje que
 * la UI tiene para él habla del freno, y decir «espera un momento» es más útil
 * que «algo falló».
 */
/**
 * Traduce un fallo de la API al desenlace que el diálogo de cuenta sabe pintar.
 *
 * Se decide aquí, una sola vez, en vez de en cada componente: cada desenlace
 * **de producto** tiene su frase, y decir la frase equivocada manda a arreglar lo
 * que no era.
 *
 * V3.82 separa lo que antes era un único `invalid`: `PASSWORD_FORMAT` (la
 * contraseña nueva no cumple la política) y `EMAIL_TAKEN` (ese correo ya tiene
 * cuenta) son ahora alcanzables —la cuenta tiene email único— y los dos caían en
 * el texto de «el email no tiene forma», que era falso en los dos casos: en el
 * primero hablaba del campo que no era, y en el segundo mandaba a corregir un
 * email perfectamente válido.
 *
 * Un `PASSWORD_THROTTLED` cae en `password-invalid` a propósito: el mensaje que
 * la UI tiene para él habla del freno, y decir «espera un momento» es más útil
 * que «algo falló».
 */
function accountFailure(err: unknown): Exclude<AccountActionOutcome, { ok: true }>["reason"] {
  if (err instanceof ApiError) {
    if (err.detail === "PASSWORD_INVALID" || err.detail === "PASSWORD_THROTTLED") {
      return "password-invalid";
    }
    if (err.detail === "PASSWORD_REQUIRED") return "password-required";
    if (err.detail === "PASSWORD_FORMAT") return "password-format";
    if (err.detail === "EMAIL_FORMAT") return "email-format";
    if (err.detail === "EMAIL_TAKEN") return "email-taken";
  }
  return "error";
}
