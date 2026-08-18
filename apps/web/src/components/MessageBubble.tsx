import { Markdown } from "@/components/Markdown";
import type { Message } from "@/api/types";

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const isStreaming = message.id === "streaming";
  return (
    <div className={`message ${isUser ? "user" : "assistant"}`}>
      <div className="bubble">
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <>
            {isStreaming && !message.content ? (
              <p className="muted">…</p>
            ) : (
              <Markdown content={message.content} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
