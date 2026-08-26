import type { Message } from "../types/api";
import { SpeakButton } from "./SpeakButton";

export function ChatMessage({ message }: { message: Message }) {
  const isError =
    message.role === "assistant" &&
    message.content.startsWith("Error al hablar con el modelo");

  return (
    <div className={`row ${message.role}`}>
      {message.role === "assistant" && (
        <span className="tutor-avatar" aria-hidden="true">
          EN
        </span>
      )}
      <div className={`bubble${isError ? " is-error" : ""}`}>
        <span className="bubble-text">{message.content}</span>
        {message.role === "assistant" && <SpeakButton text={message.content} />}
      </div>
    </div>
  );
}
