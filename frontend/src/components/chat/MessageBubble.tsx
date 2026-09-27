import { cn } from "@/lib/utils";
import { SourceCitation } from "./SourceCitation";
import type { Message } from "@/lib/types";

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[75%] rounded-lg px-4 py-2 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted",
        )}
      >
        {message.insufficientEvidence ? (
          <p className="italic text-muted-foreground">
            I dont have enough approved information to answer that confidently.
          </p>
        ) : (
          <p>{message.content}</p>
        )}
        {!isUser && message.sources && (
          <SourceCitation sources={message.sources} />
        )}
      </div>
    </div>
  );
}
