"use client";

import { useState } from "react";

import { ScrollArea } from "@/components/ui/scroll-area";

import { MessageBubble } from "@/components/chat/MessageBubble";
import { ChatInput } from "@/components/chat/ChatInput";
import { LoadingState } from "@/components/chat/LoadingState";

import type { Message, Source } from "@/lib/types";
import { apiFetch } from "@/lib/apiClient";

type AskResponseSource = {
  document_id: string;
  title: string;
  chunk_id: string;
  snippet: string;
};

type AskResponse = {
  answer: string;
  sources: AskResponseSource[];
  insufficient_evidence: boolean;
  conversation_id: string;
};

type ChatWindowProps = {
  initialMessages?: Message[];
  initialConversationId?: string | null;
  onConversationCreated?: (conversationId: string) => void;
};

export function ChatWindow({
  initialMessages = [],
  initialConversationId = null,
  onConversationCreated,
}: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>(initialMessages);

  const [loading, setLoading] = useState(false);

  const [conversationId, setConversationId] = useState<string | null>(
    initialConversationId,
  );

  const handleSend = async (text: string) => {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };

    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await apiFetch("/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: text,
          conversation_id: conversationId,
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to ask question");
      }

      const data: AskResponse = await res.json();

      setConversationId(data.conversation_id);

      onConversationCreated?.(data.conversation_id);

      const sources: Source[] = data.sources.map((s) => ({
        documentId: s.document_id,
        title: s.title,
        snippet: s.snippet,
      }));

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.answer,
          sources,
          insufficientEvidence: data.insufficient_evidence,
        },
      ]);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      {/* Scrollable messages */}
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto max-w-2xl space-y-4 p-4">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {loading && <LoadingState />}
        </div>
      </ScrollArea>

      {/* Fixed input area */}
      <div className="mx-auto w-full max-w-2xl shrink-0 px-4 pb-4">
        <ChatInput onSend={handleSend} disabled={loading} />
      </div>
    </div>
  );
}
