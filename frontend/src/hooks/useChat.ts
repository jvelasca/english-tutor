import { useCallback, useEffect, useRef, useState } from "react";
import { getModels, streamChat } from "../api/chat";
import { completeLesson as completeLessonRequest } from "../api/academy";
import {
  changeEmail as changeEmailApi,
  changePassword as changePasswordApi,
  closeSession,
  createAccount as createAccountApi,
  getSession,
  openSession,
  resendVerification as resendVerificationApi,
  SessionPasswordError,
  unenrollAccount,
} from "../api/session";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  saveConversation,
} from "../api/conversations";
import { listUsers, updateUser as updateUserApi, type UserPatch } from "../api/users";
import {
  requestProfile,
  requestProfileDelete,
  type ProfileRequestOutcome,
} from "../api/profileRequests";
import { getProgressHistory } from "../api/progress";
import { getSettings, saveSettings } from "../api/settings";
import { analyzeText, getEvents, getProfile } from "../api/learning";
import { deriveTitle } from "../utils/title";
import { ApiError } from "../api/client";
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
 * Por qué la puerta está pidiendo la contraseña (V3.81; sustituye al PIN de
 * V3.76). `null` = pidiéndola por primera vez (o tras un arranque, que es el caso
 * normal de una cuenta con credencial).
 */
export type PasswordFeedback = "password-invalid" | "password-throttled" | null;

/** Cómo terminó el alta de una cuenta desde la puerta. */
export type CreateAccountOutcome =
  | { ok: true; user: User }
  | {
      ok: false;
      reason:
        | "name-taken"
        | "email-taken"
        | "email-format"
        | "password-format"
        | "not-local"
        | "error";
    };

/** Cómo terminó una acción del diálogo de cuenta. */
export type AccountActionOutcome =
  | { ok: true; user: User }
  | {
      ok: false;
      reason: "password-invalid" | "password-required" | "invalid" | "error";
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
  // V3.80.2: ¿falló la sonda de usuarios? La puerta lo usa para ofrecer
  // «Reintentar» en vez de decir «no hay perfiles»: confundir las dos cosas es
  // exactamente lo que dejaba al alumno sin salida.
  const [usersLoadFailed, setUsersLoadFailed] = useState(false);
  // V3.81 (Fase 3 del P0): cuenta que está esperando su contraseña y por qué.
  // Que la contraseña se pida es un estado de la **app**, no de un componente:
  // así los tres caminos que abren sesión (arranque, selector y alta) piden lo
  // mismo y la puerta solo tiene que pintarlo.
  const [passwordPromptUserId, setPasswordPromptUserId] = useState<string | null>(
    null,
  );
  const [passwordFeedback, setPasswordFeedback] =
    useState<PasswordFeedback>(null);
  const [passwordRetryAfter, setPasswordRetryAfter] = useState(0);
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
   * Abre sesión para una cuenta y, si el servidor pide contraseña, deja la app en
   * el paso de contraseña en vez de fallar en silencio (V3.81; misma pieza que en
   * V3.76 pedía el PIN).
   *
   * Es el **único** camino que abre sesión: el arranque, el selector de cuenta y
   * el alta comparten esta función, así que la política de credencial no puede
   * quedar despareja entre ellos. Devuelve si la cuenta quedó activa.
   */
  const openProfile = useCallback(
    async (userId: string, password?: string): Promise<boolean> => {
      try {
        const user = await openSession(userId, password);
        setPasswordPromptUserId(null);
        setPasswordFeedback(null);
        setPasswordRetryAfter(0);
        setMustChangePassword(user.must_change_password === true);
        setCurrentUserId(user.id);
        return true;
      } catch (err) {
        if (err instanceof SessionPasswordError) {
          // «Falta la contraseña» no es un error que pintar: es el paso siguiente.
          setPasswordPromptUserId(userId);
          setPasswordFeedback(
            err.reason === "password-required"
              ? null
              : err.reason === "password-throttled"
                ? "password-throttled"
                : "password-invalid",
          );
          setPasswordRetryAfter(err.retryAfterSeconds);
          return false;
        }
        /* backend no disponible: no se cambia de cuenta ni se pide contraseña */
        return false;
      }
    },
    [],
  );

  const cancelPassword = useCallback(() => {
    setPasswordPromptUserId(null);
    setPasswordFeedback(null);
    setPasswordRetryAfter(0);
  }, []);

  /**
   * Carga los usuarios y resuelve el perfil inicial.
   *
   * V3.80.2: las dos sondas viajan juntas en el tiempo pero **no** comparten
   * destino. Antes un `Promise.all` las ataba: un 404 de `GET /api/session`
   * (sesión abierta para un usuario que el webmaster acaba de purgar desde el
   * lanzador) rechazaba la promesa conjunta y `setUsers` no llegaba a
   * ejecutarse, así que la app caía en «Elige tu perfil» con la lista **vacía**
   * y sin forma de salir. Con `allSettled` la lista se puebla igual, y el fallo
   * de la sonda se declara en `usersLoadFailed` para que la puerta pueda ofrecer
   * reintentar en vez de mentir con un «no hay perfiles».
   *
   * Se expone como `reloadUsers` porque ese reintento es del alumno: sin él, un
   * backend que tardó en arrancar dejaría la puerta otra vez sin salida.
   */
  const loadUsers = useCallback(async () => {
    setUsersLoaded(false);
    try {
      // V3.75 (Fase 2 del P0): quién es el perfil activo lo dice **el
      // servidor**, no el navegador. La sesión viaja en una cookie
      // `et_session` HttpOnly que JavaScript no puede leer (ese es el punto:
      // antes bastaba con reescribir `et_user_id` para suplantar un perfil),
      // así que se **pregunta** con `GET /api/session`.
      const [usersResult, sessionResult] = await Promise.allSettled([
        listUsers(),
        getSession(),
      ]);
      const existing = usersResult.status === "fulfilled" ? usersResult.value : [];
      const session =
        sessionResult.status === "fulfilled" ? sessionResult.value : null;
      setUsers(existing);
      setUsersLoadFailed(usersResult.status === "rejected");
      // Resolución del perfil inicial (sesión del servidor → perfil único → null)
      // y, con ella, si hay que **abrir** sesión o basta con adoptarla. La
      // decisión es pura y tiene test propio (`utils/session.ts`): es el punto
      // donde un fallo se ve como «todo normal» mientras cada petición da 401.
      const plan = planSession(existing, session?.id ?? null);
      if (plan.action === "adopt") {
        setCurrentUserId(plan.userId);
        setMustChangePassword(session?.must_change_password === true);
      } else if (plan.action === "password") {
        // V3.81: la cuenta tiene contraseña. No se lanza un `POST` condenado a
        // 401 —su error lo tragaría el `catch` de abajo y el arranque se vería
        // como «no ha pasado nada»—: se pide la contraseña y se espera.
        setPasswordPromptUserId(plan.userId);
      } else if (plan.action === "open") {
        // Cuenta resuelta **sin** sesión abierta y **sin** credencial (el caso
        // heredado): se abre aquí antes de pintar nada.
        await openProfile(plan.userId);
      }
    } finally {
      setUsersLoaded(true);
    }
  }, [openProfile]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

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
      // V3.75: elegir usuario es **abrir sesión** en el servidor. Antes esto
      // escribía la cookie `et_user_id`, que el propio cliente podía reescribir
      // para suplantar a otra cuenta; ahora la firma el servidor y el estado local
      // se fija con la cuenta que **él** devuelve, no con lo que pide el cliente.
      // V3.81: si la cuenta tiene contraseña, el servidor responde 401
      // `PASSWORD_REQUIRED` y `openProfile` deja la app en el paso de contraseña.
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
   * Alta de una cuenta nueva desde la propia puerta (V3.81).
   *
   * Sustituye al «pide un perfil» de V3.77 como camino principal: cualquiera que
   * esté delante de este equipo puede crearse una cuenta con contraseña y email.
   * Si el backend responde 403 es que la petición no viene del propio equipo (modo
   * LAN): entonces lo que toca es **pedir**, y el componente ya ofrece esa vía.
   *
   * Al terminar bien, la cuenta queda con sesión abierta: quien acaba de
   * registrarse no tiene que volver a escribir lo que ya escribió.
   */
  const createAccountForGate = useCallback(
    async (
      name: string,
      email: string,
      password: string,
    ): Promise<CreateAccountOutcome> => {
      try {
        const user = await createAccountApi(name.trim(), email.trim(), password);
        await openProfile(user.id, password);
        return { ok: true, user };
      } catch (err) {
        if (err instanceof ApiError) {
          const mapped: Record<string, CreateAccountOutcome & { ok: false }> = {
            USER_NAME_TAKEN: { ok: false, reason: "name-taken" },
            EMAIL_TAKEN: { ok: false, reason: "email-taken" },
            EMAIL_FORMAT: { ok: false, reason: "email-format" },
            PASSWORD_FORMAT: { ok: false, reason: "password-format" },
          };
          if (err.status === 403) return { ok: false, reason: "not-local" };
          const hit = mapped[err.detail];
          if (hit) return hit;
        }
        return { ok: false, reason: "error" };
      }
    },
    [openProfile],
  );

  /**
   * Salir: cierra la sesión en el servidor (caduca la cookie) y vacía el estado
   * local para que la puerta vuelva a pedir cuenta.
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
    setPasswordPromptUserId(null);
    setPasswordFeedback(null);
    setPasswordRetryAfter(0);
    setMustChangePassword(false);
    await loadUsers();
  }, [loadUsers]);

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
        setMustChangePassword(false);
        await loadUsers();
        return { ok: true, user: res.user };
      } catch (err) {
        return { ok: false, reason: accountFailure(err) };
      }
    },
    [loadUsers],
  );

  // V3.77: la app ya no crea perfiles. Lo que hace es **pedirlos**, y el
  // desenlace se devuelve tal cual para que la puerta pueda contarlo (una
  // solicitud no abre sesión: no hay perfil al que abrirla). El nombre por
  // defecto sigue teniendo sentido aquí —«Alumno 2» es más útil en la cola del
  // webmaster que una fila vacía—, pero se resuelve solo si no escribieron nada.
  const requestProfileForGate = useCallback(
    async (name: string): Promise<ProfileRequestOutcome> => {
      const trimmed = name.trim();
      const finalName = trimmed || nextDefaultUserName(users.map((u) => u.name));
      return requestProfile(finalName);
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
    // V3.80.2: la puerta distingue «no hay usuarios» de «no se pudo cargar» y
    // puede volver a intentarlo sin recargar la página.
    usersLoadFailed,
    reloadUsers: loadUsers,
    // V3.81 (Fase 3 del P0): estado del paso de contraseña y las acciones que lo
    // cierran, más el ciclo de vida de la cuenta. La puerta de entrada y el menú
    // de cuenta los pintan; el resto de la app no los toca.
    passwordPromptUserId,
    passwordFeedback,
    passwordRetryAfter,
    submitPassword: openProfile,
    cancelPassword,
    createAccountForGate,
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
    selectUser,
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
function accountFailure(err: unknown): "password-invalid" | "password-required" | "invalid" | "error" {
  if (err instanceof ApiError) {
    if (err.detail === "PASSWORD_INVALID" || err.detail === "PASSWORD_THROTTLED") {
      return "password-invalid";
    }
    if (err.detail === "PASSWORD_REQUIRED") return "password-required";
    if (
      err.detail === "EMAIL_FORMAT" ||
      err.detail === "EMAIL_TAKEN" ||
      err.detail === "PASSWORD_FORMAT"
    ) {
      return "invalid";
    }
  }
  return "error";
}
