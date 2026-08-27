import { useEffect, useRef, useState } from "react";
import { streamChat } from "../../api/chat";
import { createConversation, saveConversation } from "../../api/conversations";
import type { Message, TutorMode } from "../../types/api";
import { rolePlaySetup } from "../../utils/speaking";
import { turnTelemetry } from "../../utils/telemetry";
import { deriveTitle } from "../../utils/title";
import { useI18n } from "../../hooks/useI18n";

const DEFAULT_MODEL = "qwen3.5:9b";
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
    <div className="speaking-roleplay">
      <p className="speaking-roleplay__hint">
        Role-play: {scenario}
      </p>
      <div className="speaking-roleplay__messages" aria-live="polite">
        {messages.map((m) => (
          <div key={m.id} className={`speaking-roleplay__bubble ${m.role}`}>
            {m.content}
          </div>
        ))}
        {loading && (
          <div className="speaking-roleplay__bubble assistant">…</div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="speaking-roleplay__composer">
        <input
          className="speaking-roleplay__input min-w-0"
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
        <button
          type="button"
          className="speaking-roleplay__send"
          onClick={() => void send()}
          disabled={!input.trim() || loading || !conversationId}
        >
          {t("roleplay.send")}
        </button>
      </div>
      <button
        type="button"
        className="speaking-roleplay__finish"
        onClick={finish}
        disabled={!canFinish}
      >
        {t("roleplay.finish")}
      </button>
    </div>
  );
}
