import type { Message } from "../types/api";
import { SpeakButton } from "./SpeakButton";

export function ChatMessage({ message }: { message: Message }) {
  return (
    <div className={`row ${message.role}`}>
      <div className="bubble">
        <span className="bubble-text">{message.content}</span>
        {message.role === "assistant" && <SpeakButton text={message.content} />}
      </div>
    </div>
  );
}
