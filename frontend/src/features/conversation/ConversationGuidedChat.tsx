import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { MessageSquareText, Send } from "lucide-react";
import { streamChat } from "../../api/chat";
import { createConversation, saveConversation } from "../../api/conversations";
import type { ConversationDialogue, Message, TutorMode } from "../../types/api";
import { turnTelemetry } from "../../utils/telemetry";
import { deriveTitle } from "../../utils/title";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { MicButton } from "../../components/MicButton";

// Modelo del tutor guiado: el mismo que usa el role-play conversacional (nunca
// un modelo marcado como no utilizable; ver config.py).
const DEFAULT_MODEL = "llama3.1:8b";
const GUIDED_MODE: TutorMode = "conversation";

// Turnos mínimos del alumno antes de poder terminar la conversación. Es un
// guard de la UI (la evaluación del backend exige además un mínimo de palabras).
const MIN_STUDENT_TURNS = 3;

/**
 * Semilla del tutor para un mini-diálogo guiado. Pide al LLM adoptar el papel
 * del tutor de la situación, mantenerse en personaje y seguir las metas del
 * diálogo; la `opening_line` ya la ha dicho el tutor (se muestra en la UI y se
 * entrega como contexto), así que el tutor responde a lo que diga el alumno.
 */
function guidedSeed(dialogue: ConversationDialogue): string {
  const parts: string[] = [];
  parts.push(
    "Role-play. You are the other speaker in a guided conversation and must " +
      "stay in character and in English.",
  );
  if (dialogue.tutor_role) parts.push(`You play: ${dialogue.tutor_role}`);
  if (dialogue.context) parts.push(`Scenario: ${dialogue.context}`);
  if (dialogue.student_role)
    parts.push(`The student plays: ${dialogue.student_role}`);
  parts.push(
    `You have just opened the conversation saying: "${dialogue.opening_line}".`,
  );
  const goals = dialogue.communicative_goals;
  if (goals.length > 0) {
    parts.push("Help the student achieve these goals naturally:");
    for (const goal of goals) parts.push(`- ${goal}`);
  }
  parts.push(
    "Keep your turns short and natural, ask follow-up questions and never " +
      "speak for the student.",
  );
  return parts.join("\n");
}

interface ConversationGuidedChatProps {
  userId: string;
  /** Mini-diálogo guiado que se está conversando. */
  dialogue: ConversationDialogue;
  /** Se llama la primera vez que el alumno envía un turno propio. */
  onFirstMessage?: () => void;
  /**
   * Se llama al terminar la conversación (ya persistida en el backend) con el
   * transcripto del alumno, los segundos transcurridos y el `conversation_id`
   * real para que el backend evalúe la interacción objetiva.
   */
  onFinish: (
    heard: string,
    durationSeconds: number,
    conversationId: string,
  ) => void;
}

/**
 * Mini-chat guiado multi-turno de las rutas de Conversation (V3.10). Crea una
 * conversación real, muestra la situación y la línea de apertura del tutor, y
 * mantiene el diálogo con el tutor en personaje mientras el alumno cumple las
 * metas comunicativas. Persiste cada turno (con telemetría) para que la
 * evaluación del transcripto pueda inyectar la señal objetiva de interacción.
 */
export function ConversationGuidedChat({
  userId,
  dialogue,
  onFirstMessage,
  onFinish,
}: ConversationGuidedChatProps) {
  const { t } = useI18n();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);

  const startedAt = useRef<number>(performance.now());
  const composeStartedAt = useRef<number | null>(null);
  const lastAssistantAt = useRef<number | null>(null);
  const studentTurns = useRef<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    startedAt.current = performance.now();
    (async () => {
      try {
        const conv = await createConversation(userId);
        if (!cancelled) setConversationId(conv.id);
      } catch {
        setChatError(t("convRoutes.chatCreateError"));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, dialogue.id]);

  useEffect(() => {
    if (input === "") {
      composeStartedAt.current = null;
    } else if (composeStartedAt.current === null) {
      composeStartedAt.current = performance.now();
    }
  }, [input]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendContent(content: string) {
    const trimmed = content.trim();
    if (!trimmed || loading || !conversationId) return;

    setChatError(null);
    const sentAt = performance.now();
    const { duration_ms, latency_ms } = turnTelemetry({
      sentAt,
      composeStartedAt: composeStartedAt.current,
      lastAssistantAt: lastAssistantAt.current,
    });

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
      mode: GUIDED_MODE,
      ...(duration_ms != null ? { duration_ms } : {}),
      ...(latency_ms != null ? { latency_ms } : {}),
    };
    const history = [...messages, userMsg];
    setMessages(history);
    setInput("");
    setLoading(true);
    composeStartedAt.current = null;
    const firstStudentMessage = studentTurns.current.length === 0;
    studentTurns.current.push(trimmed);
    if (firstStudentMessage) onFirstMessage?.();

    const assistantId = crypto.randomUUID();
    let reply = "";
    let errored = false;

    // La semilla del diálogo guiado viaja siempre como primer mensaje (rol
    // "user") para que el tutor mantenga el papel; no se muestra ni persiste.
    const requestMessages: Message[] = [
      { role: "user", content: guidedSeed(dialogue) },
      ...history,
    ];

    try {
      await streamChat(
        requestMessages,
        DEFAULT_MODEL,
        GUIDED_MODE,
        {
          onDelta: (content) => {
            reply += content;
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last && last.role === "assistant") {
                next[next.length - 1] = {
                  id: assistantId,
                  role: "assistant",
                  content: last.content + content,
                  mode: GUIDED_MODE,
                };
              } else {
                next.push({
                  id: assistantId,
                  role: "assistant",
                  content,
                  mode: GUIDED_MODE,
                });
              }
              return next;
            });
          },
          onDone: () => {
            lastAssistantAt.current = performance.now();
          },
          onError: (message) => {
            errored = true;
            reply = `Error: ${message}`;
            setChatError(message);
            lastAssistantAt.current = performance.now();
            setMessages((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "assistant",
                content: reply,
                mode: GUIDED_MODE,
              },
            ]);
          },
        },
        userId,
        undefined,
        conversationId,
        assistantId,
      );
    } catch (e) {
      errored = true;
      reply = `Error: ${(e as Error).message}`;
      setChatError((e as Error).message);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: reply,
          mode: GUIDED_MODE,
        },
      ]);
    } finally {
      setLoading(false);
      lastAssistantAt.current = performance.now();
    }

    if (reply && !errored) {
      const finalHistory: Message[] = [
        ...history,
        { id: assistantId, role: "assistant", content: reply, mode: GUIDED_MODE },
      ];
      setMessages(finalHistory);
      void saveConversation(
        conversationId,
        userId,
        deriveTitle(finalHistory),
        finalHistory,
      ).catch(() => {});
    }
  }

  async function send() {
    await sendContent(input);
  }

  function finish() {
    if (!conversationId || loading) return;
    const durationSeconds = (performance.now() - startedAt.current) / 1000;
    const heard = studentTurns.current.join(" ").trim().slice(0, 2000);
    if (!heard) return;
    onFinish(heard, durationSeconds, conversationId);
  }

  const studentTurnCount = studentTurns.current.length;
  const canFinish =
    messages.length > 0 && !loading && studentTurnCount >= MIN_STUDENT_TURNS;

  return (
    <div className="flex flex-col gap-3">
      {/* Tarjeta de situación del diálogo guiado */}
      <div className="rounded-lg border border-border bg-muted/30 px-3 py-2.5 text-xs leading-relaxed">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">{dialogue.level}</Badge>
          <Badge variant="outline" className="text-[10px] normal-case">
            {dialogue.topic.replace(/_/g, " ")}
          </Badge>
          <span className="font-semibold text-foreground">
            {dialogue.tutor_role}
          </span>
          <span className="text-muted-foreground">·</span>
          <span className="text-muted-foreground">{t("convRoutes.youPlay")}</span>
          <span className="font-semibold text-foreground">
            {dialogue.student_role}
          </span>
        </div>
        <p className="mt-2 text-muted-foreground">{dialogue.context}</p>
        <ul className="mt-2 flex flex-col gap-1 text-muted-foreground">
          {dialogue.communicative_goals.map((goal, i) => (
            <li key={`${dialogue.id}-goal-${goal}`} className="flex gap-1.5">
              <span className="text-foreground">{i + 1}.</span>
              <span>{goal}</span>
            </li>
          ))}
        </ul>
        {chatError && (
          <p role="alert" className="mt-2 text-destructive">
            {chatError}
          </p>
        )}
      </div>

      {/* Línea de apertura del tutor, siempre visible como primer turno */}
      <div className="flex max-w-[86%] self-start flex-col gap-1.5">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          {dialogue.tutor_role}
        </p>
        <div className="rounded-xl rounded-bl-sm border border-border bg-card px-3 py-2 text-sm leading-relaxed text-foreground">
          <p lang="en" className="whitespace-pre-wrap break-words">
            {dialogue.opening_line}
          </p>
        </div>
      </div>

      <div
        className="flex max-h-72 flex-col gap-2 overflow-y-auto py-2"
        aria-live="polite"
      >
        {messages.map((m) => (
          <div
            key={m.id}
            className={
              m.role === "user"
                ? "max-w-[78%] self-end whitespace-pre-wrap break-words rounded-xl rounded-br-sm bg-primary px-3 py-2 text-sm leading-relaxed text-primary-foreground"
                : "max-w-[78%] self-start whitespace-pre-wrap break-words rounded-xl rounded-bl-sm border border-border bg-card px-3 py-2 text-sm leading-relaxed text-foreground"
            }
          >
            <p lang="en">{m.content}</p>
          </div>
        ))}
        {loading && (
          <div className="max-w-[78%] self-start rounded-xl rounded-bl-sm border border-border bg-card px-3 py-2">
            <span className="flex items-center gap-1">
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  className="size-1.5 rounded-full bg-muted-foreground"
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
                />
              ))}
            </span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {studentTurnCount < MIN_STUDENT_TURNS && studentTurnCount > 0 && (
        <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <MessageSquareText className="size-3.5" aria-hidden="true" />
          {t("convRoutes.moreTurns")
            .replace("{done}", String(studentTurnCount))
            .replace("{min}", String(MIN_STUDENT_TURNS))}
        </p>
      )}

      <div className="flex gap-2">
        <MicButton onTranscribed={(text) => void sendContent(text)} disabled={loading} />
        <input
          className="min-w-0 flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/50 disabled:opacity-60"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder={t("convRoutes.chatPlaceholder")}
          disabled={loading || !conversationId}
          aria-label={t("convRoutes.chatAria")}
        />
        <Button
          className="min-h-10 shrink-0"
          onClick={() => void send()}
          disabled={!input.trim() || loading || !conversationId}
        >
          <Send className="size-4" aria-hidden="true" />
          <span className="sr-only">{t("convRoutes.send")}</span>
        </Button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("convRoutes.voiceHint")}
        </p>
        <Button
          variant="outline"
          className="min-h-9"
          onClick={finish}
          disabled={!canFinish}
        >
          {t("convRoutes.finish")}
        </Button>
      </div>
    </div>
  );
}
