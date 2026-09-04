import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { Send } from "lucide-react";
import { streamChat } from "../../api/chat";
import { createConversation, saveConversation } from "../../api/conversations";
import type { Message, TutorMode } from "../../types/api";
import { rolePlaySetup } from "../../utils/speaking";
import { turnTelemetry } from "../../utils/telemetry";
import { deriveTitle } from "../../utils/title";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";

// Modelo del role-play conversacional. Usa el modelo utilizable por defecto de
// la app (ver config.py / backend): nunca un modelo marcado como no utilizable.
const DEFAULT_MODEL = "llama3.1:8b";
const ROLEPLAY_MODE: TutorMode = "conversation";

interface SpeakingRolePlayProps {
  userId: string;
  scenario: string;
  onFinish: (
    heard: string,
    durationSeconds: number,
    conversationId: string,
  ) => void;
}

/**
 * Chat de role-play en vivo para una parte conversacional del Speaking
 * Assessment. Crea una conversación real, captura la telemetría de turnos del
 * alumno (`duration_ms`/`latency_ms`) y persiste los turnos, de modo que el
 * backend pueda inyectar la señal objetiva de interacción (`interaction_objective`)
 * al enviar la parte con su `conversation_id`.
 */
export function SpeakingRolePlay({
  userId,
  scenario,
  onFinish,
}: SpeakingRolePlayProps) {
  const { t } = useI18n();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const startedAt = useRef<number>(performance.now());
  const composeStartedAt = useRef<number | null>(null);
  const lastAssistantAt = useRef<number | null>(null);
  const studentTurns = useRef<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const conv = await createConversation(userId);
        if (!cancelled) setConversationId(conv.id);
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  // Marca el instante en que el alumno empieza a componer (input vacío→no-vacío).
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

  async function send() {
    const trimmed = input.trim();
    if (!trimmed || loading || !conversationId) return;

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
      mode: ROLEPLAY_MODE,
      ...(duration_ms != null ? { duration_ms } : {}),
      ...(latency_ms != null ? { latency_ms } : {}),
    };
    const history = [...messages, userMsg];
    setMessages(history);
    setInput("");
    setLoading(true);
    composeStartedAt.current = null;
    studentTurns.current.push(trimmed);

    const assistantId = crypto.randomUUID();
    let reply = "";
    let errored = false;

    // La semilla del escenario se envía al LLM como primer mensaje (rol "user")
    // para que el tutor adopte el papel; no se muestra ni se persiste.
    const requestMessages: Message[] = [
      { role: "user", content: rolePlaySetup(scenario) },
      ...history,
    ];

    try {
      await streamChat(
        requestMessages,
        DEFAULT_MODEL,
        ROLEPLAY_MODE,
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
                  mode: ROLEPLAY_MODE,
                };
              } else {
                next.push({
                  id: assistantId,
                  role: "assistant",
                  content,
                  mode: ROLEPLAY_MODE,
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
            lastAssistantAt.current = performance.now();
            setMessages((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "assistant",
                content: reply,
                mode: ROLEPLAY_MODE,
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
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: reply,
          mode: ROLEPLAY_MODE,
        },
      ]);
    } finally {
      setLoading(false);
      lastAssistantAt.current = performance.now();
    }

    if (reply && !errored) {
      const finalHistory: Message[] = [
        ...history,
        { id: assistantId, role: "assistant", content: reply, mode: ROLEPLAY_MODE },
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

  function finish() {
    if (!conversationId || loading) return;
    const durationSeconds = (performance.now() - startedAt.current) / 1000;
    const heard = studentTurns.current.join(" ").trim().slice(0, 2000);
    if (!heard) return;
    onFinish(heard, durationSeconds, conversationId);
  }

  const canFinish = messages.length > 0 && !loading;

  return (
    <div className="flex flex-col gap-3">
      <p className="rounded-md border border-border bg-muted px-3 py-2 text-sm leading-relaxed text-muted-foreground">
        {t("roleplay.hint")}: {scenario}
      </p>
      <div
        className="flex max-h-80 flex-col gap-2 overflow-y-auto py-2"
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
            {m.content}
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
                  transition={{
                    duration: 1,
                    repeat: Infinity,
                    delay: i * 0.2,
                  }}
                />
              ))}
            </span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2">
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
          placeholder={t("roleplay.turnPlaceholder")}
          disabled={loading || !conversationId}
          aria-label={t("roleplay.turnAria")}
        />
        <Button
          className="min-h-10 shrink-0"
          onClick={() => void send()}
          disabled={!input.trim() || loading || !conversationId}
        >
          <Send className="size-4" aria-hidden="true" />
          <span className="sr-only">{t("roleplay.send")}</span>
        </Button>
      </div>
      <Button
        variant="outline"
        className="min-h-10 self-start"
        onClick={finish}
        disabled={!canFinish}
      >
        {t("roleplay.finish")}
      </Button>
    </div>
  );
}
