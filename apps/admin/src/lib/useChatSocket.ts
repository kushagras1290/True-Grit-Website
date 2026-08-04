/**
 * Live delivery for one conversation's thread.
 *
 * Connects to the per-conversation Durable Object (`conversationSocketUrl`,
 * see `truegrit_api/realtime/chat_room.py`) and pushes incoming messages
 * straight into the react-query cache for `["conversation-history",
 * conversationId]` — the same cache key `MessageThread` reads with
 * `useQuery`, so a live-delivered message and the initial REST-fetched
 * history are always one list, never two sources fighting each other.
 *
 * Reconnects with exponential backoff (capped at 15s) on any drop; the
 * session cookie rides along on the WebSocket handshake automatically, the
 * same as every other admin request, so there is nothing to re-authenticate
 * on reconnect.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { conversationSocketUrl, demoMode, type ChatMessage, type ConversationHistory } from "./api";

const MAX_BACKOFF_MS = 15_000;

type SocketStatus = "connecting" | "open" | "closed";

interface IncomingMessage extends ChatMessage {
  type: "message";
  conversationId: string;
}

export function conversationHistoryKey(conversationId: string) {
  return ["conversation-history", conversationId] as const;
}

export function useChatSocket(conversationId: string | null) {
  const queryClient = useQueryClient();
  const socketRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<SocketStatus>("connecting");

  useEffect(() => {
    if (!conversationId || demoMode) {
      setStatus("closed");
      return;
    }

    let cancelled = false;
    let attempt = 0;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    function connect() {
      if (cancelled) return;
      setStatus("connecting");
      const socket = new WebSocket(conversationSocketUrl(conversationId!));
      socketRef.current = socket;

      socket.onopen = () => {
        attempt = 0;
        setStatus("open");
      };

      socket.onmessage = (event) => {
        let parsed: IncomingMessage;
        try {
          parsed = JSON.parse(String(event.data)) as IncomingMessage;
        } catch {
          return;
        }
        if (parsed.type !== "message") return;
        queryClient.setQueryData<ConversationHistory | undefined>(
          conversationHistoryKey(parsed.conversationId),
          (current) => {
            if (!current) return current;
            if (current.messages.some((existing) => existing.id === parsed.id)) return current;
            return { ...current, messages: [...current.messages, parsed] };
          },
        );
        void queryClient.invalidateQueries({ queryKey: ["conversations"] });
      };

      socket.onclose = () => {
        socketRef.current = null;
        if (cancelled) return;
        setStatus("closed");
        const wait = Math.min(1000 * 2 ** attempt, MAX_BACKOFF_MS);
        attempt += 1;
        retryTimer = setTimeout(connect, wait);
      };

      socket.onerror = () => socket.close();
    }

    connect();
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [conversationId, queryClient]);

  function send(body: string): boolean {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify({ body }));
    return true;
  }

  return { status, send };
}
