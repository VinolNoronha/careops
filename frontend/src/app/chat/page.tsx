"use client";

import { useRouter } from "next/navigation";

import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatWindow } from "@/components/chat/ChatWindow";

export default function ChatPage() {
  const router = useRouter();

  return (
    <div className="flex h-[calc(100vh-57px)]">
      <ChatSidebar />

      <main className="flex-1">
        <ChatWindow
          onConversationCreated={(conversationId) => {
            router.replace(`/chat/${conversationId}`);
          }}
        />
      </main>
    </div>
  );
}
