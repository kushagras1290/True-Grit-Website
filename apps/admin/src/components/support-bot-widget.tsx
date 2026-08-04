/** Floating "Help Assistant" launcher, mounted once in `Shell` so it is
 * available on every admin page. Open to any signed-in staff member — the
 * chat endpoint itself has no permission gate (services/support_bot.py),
 * every live-data tool it can call re-checks the caller's own permissions
 * independently server-side, so there is nothing extra to hide here.
 *
 * Conversation state lives in this component, which stays mounted across
 * route changes (Shell wraps <Outlet />), so the thread survives page
 * navigation within a session but resets on reload — no server-side
 * conversation history exists for this bot, unlike staff messaging. */

import { useMutation } from "@tanstack/react-query";
import { HelpCircle, Loader2, Send, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button, Textarea } from "./ui";
import { ApiError, api, type SupportBotChatTurn } from "../lib/api";
import { T } from "../lib/i18n";

const MAX_HISTORY_TURNS = 10;

interface DisplayTurn extends SupportBotChatTurn {
  isError?: boolean;
}

function BotBubble({ turn }: { turn: DisplayTurn }) {
  const isMine = turn.role === "user";
  return (
    <div className={`flex flex-col ${isMine ? "items-end" : "items-start"}`}>
      <div
        className={`max-w-[85%] rounded-md px-3 py-2 text-sm whitespace-pre-wrap ${
          isMine
            ? "bg-brand text-ink-inverse"
            : turn.isError
              ? "border border-danger/30 bg-danger/5 text-danger"
              : "border border-line bg-canvas text-ink"
        }`}
      >
        {turn.content}
      </div>
    </div>
  );
}

export function SupportBotWidget() {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<DisplayTurn[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [turns, open]);

  const ask = useMutation({
    mutationFn: (history: SupportBotChatTurn[]) =>
      api.supportBotChat(history.at(-1)!.content, history.slice(0, -1)),
    onSuccess: (result) => {
      setTurns((prev) => [...prev, { role: "assistant", content: result.reply }]);
    },
    onError: (error: unknown) => {
      const message =
        error instanceof ApiError ? error.message : "Something went wrong. Try again.";
      setTurns((prev) => [...prev, { role: "assistant", content: message, isError: true }]);
    },
  });

  function send() {
    const message = draft.trim();
    if (!message || ask.isPending) return;
    const nextTurns = [...turns, { role: "user" as const, content: message }];
    setTurns(nextTurns);
    setDraft("");
    ask.mutate(nextTurns.slice(-MAX_HISTORY_TURNS).map(({ role, content }) => ({ role, content })));
  }

  return (
    <div className="fixed right-5 bottom-5 z-40">
      {open ? (
        <div
          role="dialog"
          aria-modal="false"
          aria-label="Help assistant"
          className="mb-3 flex h-[32rem] w-[22rem] max-w-[calc(100vw-2.5rem)] flex-col rounded-md border border-line bg-surface shadow-overlay"
        >
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <p className="font-display text-base text-ink">
              <T>Help Assistant</T>
            </p>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close help assistant"
              className="flex h-7 w-7 items-center justify-center text-ink-muted hover:text-ink"
            >
              <X size={16} />
            </button>
          </div>
          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {turns.length === 0 ? (
              <p className="text-sm text-ink-muted">
                <T>
                  Ask how to do something in the admin panel, or ask about pending orders, low-stock
                  items, or an order's status.
                </T>
              </p>
            ) : (
              turns.map((turn, index) => <BotBubble key={index} turn={turn} />)
            )}
            {ask.isPending ? (
              <div className="flex items-center gap-2 text-sm text-ink-muted">
                <Loader2 size={14} className="animate-spin" />
                <T>Thinking…</T>
              </div>
            ) : null}
          </div>
          <div className="border-t border-line p-3">
            <div className="flex items-end gap-2">
              <Textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    send();
                  }
                }}
                placeholder="Ask a question…"
                rows={2}
                className="min-h-0 flex-1 resize-none"
              />
              <Button
                type="button"
                variant="primary"
                className="min-h-9 px-2.5"
                onClick={send}
                disabled={ask.isPending || !draft.trim()}
                aria-label="Send"
              >
                <Send size={15} />
              </Button>
            </div>
          </div>
        </div>
      ) : null}
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label={open ? "Close help assistant" : "Open help assistant"}
        aria-expanded={open}
        className="ml-auto flex h-12 w-12 items-center justify-center rounded-full bg-brand text-ink-inverse shadow-overlay transition-opacity hover:opacity-90"
      >
        {open ? <X size={20} /> : <HelpCircle size={20} />}
      </button>
    </div>
  );
}
