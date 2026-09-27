"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { apiFetch } from "@/lib/apiClient";

type Conversation = {
  id: string;
  title: string;
  created_at: string;
};

export function ChatSidebar() {
  const router = useRouter();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const loadConversations = async () => {
      try {
        const res = await apiFetch("/conversations");

        if (!res.ok) {
          throw new Error("Failed to load conversations");
        }

        const data: Conversation[] = await res.json();

        if (!cancelled) {
          setConversations(data);
        }
      } catch (error) {
        if (!cancelled) {
          console.error("Failed to load conversations:", error);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadConversations();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <aside className="flex h-full w-64 flex-col border-r bg-muted/20">
      <div className="border-b p-4">
        <Button className="w-full" onClick={() => router.push("/chat")}>
          + New Chat
        </Button>
      </div>

      <ScrollArea className="flex-1 p-2">
        {loading ? (
          <p className="p-2 text-sm text-muted-foreground">Loading chats...</p>
        ) : conversations.length === 0 ? (
          <p className="p-2 text-sm text-muted-foreground">
            No conversations yet.
          </p>
        ) : (
          <div className="space-y-1">
            {conversations.map((conversation) => (
              <button
                key={conversation.id}
                onClick={() => router.push(`/chat/${conversation.id}`)}
                className="w-full rounded-md px-3 py-2 text-left text-sm hover:bg-muted"
              >
                <p className="truncate font-medium">{conversation.title}</p>

                <p className="mt-1 text-xs text-muted-foreground">
                  {new Date(conversation.created_at).toLocaleDateString()}
                </p>
              </button>
            ))}
          </div>
        )}
      </ScrollArea>
    </aside>
  );
}
