"use client";

import { useEffect, useState } from "react";

import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { apiFetch } from "@/lib/apiClient";

import type { Message, Source } from "@/lib/types";

type ConversationMessage = {
  id: string;
  role: string;
  content: string;
  sources: {
    document_id: string;
    title: string;
    chunk_id: string;
    snippet: string;
  }[];
  insufficient_evidence: boolean;
  created_at: string;
};

type ConversationResponse = {
  id: string;
  title: string;
  created_at: string;
  messages: ConversationMessage[];
};

export default function ConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const [conversationId, setConversationId] = useState<string | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadConversation() {
      const { conversationId: id } = await params;

      setConversationId(id);

      try {
        const res = await apiFetch(`/conversations/${id}`);

        if (!res.ok) {
          throw new Error("Failed to load conversation");
        }

        const data: ConversationResponse = await res.json();

        const loadedMessages: Message[] = data.messages.map((message) => {
          const sources: Source[] = message.sources.map((source) => ({
            documentId: source.document_id,
            title: source.title,
            snippet: source.snippet,
          }));

          return {
            id: message.id,
            role: message.role === "user" ? "user" : "assistant",
            content: message.content,
            sources,
            insufficientEvidence: message.insufficient_evidence,
          };
        });

        setMessages(loadedMessages);
      } catch (error) {
        console.error("Failed to load conversation:", error);
      } finally {
        setLoading(false);
      }
    }

    loadConversation();
  }, [params]);

  if (loading || !conversationId) {
    return (
      <div className="flex h-[calc(100dvh-57px)] min-h-0 overflow-hidden">
        <ChatSidebar />
        <main className="flex min-h-0 min-w-0 flex-1 items-center justify-center overflow-hidden">
          <p className="text-sm text-muted-foreground">
            Loading conversation...
          </p>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100dvh-57px)] min-h-0 overflow-hidden">
      <ChatSidebar />

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <ChatWindow
          initialMessages={messages}
          initialConversationId={conversationId}
        />
      </main>
    </div>
  );
}
