/**
 * Floating "Ask us" chat widget, mounted once in `root.tsx` alongside
 * `LanguageSuggestionPrompt` (same reasoning: it needs provider access and is
 * excluded from the payment popup window branch) so it is available on every
 * storefront page. Open to anyone, signed in or not — the API itself
 * (`api/support_bot_public.py`) is what decides whether order-lookup tools
 * are offered, based on the same session cookie `supportBotChat`'s
 * `credentials: "include"` already carries; there is nothing to gate here.
 *
 * Conversation state lives in this component only, so it resets on reload —
 * there is no server-side thread for this bot, unlike staff messaging.
 */

import { MessageCircle, Send, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { supportBotChat, type SupportBotChatTurn } from "../lib/commerce";
import { AuthError, useCustomer } from "../lib/customer-auth";
import { useLocalizeText } from "../lib/i18n/localized-text";
import { useLocaleContext } from "../lib/i18n/context";

const MAX_HISTORY_TURNS = 10;

interface DisplayTurn extends SupportBotChatTurn {
  isError?: boolean;
}

export function SupportBotWidget({ country }: { country?: string | null }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<DisplayTurn[]>([]);
  const [isPending, setIsPending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const localize = useLocalizeText();
  const { locale } = useLocaleContext();
  const { status } = useCustomer();

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [turns, open]);

  async function send() {
    const message = draft.trim();
    if (!message || isPending) return;
    const nextTurns = [...turns, { role: "user" as const, content: message }];
    setTurns(nextTurns);
    setDraft("");
    setIsPending(true);
    const history = nextTurns.slice(-MAX_HISTORY_TURNS).map(({ role, content }) => ({
      role,
      content,
    }));
    try {
      const result = await supportBotChat({
        message: history.at(-1)!.content,
        history: history.slice(0, -1),
        country,
        locale,
      });
      setTurns((prev) => [...prev, { role: "assistant", content: result.reply }]);
    } catch (error) {
      const message =
        error instanceof AuthError ? error.message : localize("Something went wrong. Try again.");
      setTurns((prev) => [...prev, { role: "assistant", content: message, isError: true }]);
    } finally {
      setIsPending(false);
    }
  }

  return (
    <div className="fixed right-4 bottom-4 z-40 md:right-6 md:bottom-6">
      {open ? (
        <div
          role="dialog"
          aria-modal="false"
          aria-label={localize("Help")}
          className="mb-3 flex h-[30rem] w-[21rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-lg border border-line bg-surface shadow-overlay"
        >
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <p className="text-sm font-medium text-ink">{localize("Ask us anything")}</p>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label={localize("Close")}
              className="-mr-1 rounded-sm p-1.5 text-ink-muted hover:text-ink"
            >
              <X size={16} />
            </button>
          </div>
          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {turns.length === 0 ? (
              <p className="text-sm text-ink-muted">
                {status === "authenticated"
                  ? localize("Ask about products, shipping, returns, or the status of your order.")
                  : localize("Ask about products, shipping, returns, or how True Grit works.")}
              </p>
            ) : (
              turns.map((turn, index) => {
                const isMine = turn.role === "user";
                return (
                  <div
                    key={index}
                    className={`flex flex-col ${isMine ? "items-end" : "items-start"}`}
                  >
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
              })
            )}
            {isPending ? <p className="text-sm text-ink-muted">{localize("Thinking…")}</p> : null}
          </div>
          <div className="border-t border-line p-3">
            <div className="flex items-end gap-2">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    send();
                  }
                }}
                placeholder={localize("Ask a question…")}
                rows={2}
                aria-label={localize("Ask a question…")}
                className="min-h-0 flex-1 resize-none rounded-sm border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-muted"
              />
              <button
                type="button"
                onClick={send}
                disabled={isPending || !draft.trim()}
                aria-label={localize("Send")}
                className="flex min-h-9 items-center justify-center rounded-sm bg-brand px-2.5 text-ink-inverse transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send size={15} />
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label={open ? localize("Close") : localize("Help")}
        aria-expanded={open}
        className="ml-auto flex h-12 w-12 items-center justify-center rounded-full bg-brand text-ink-inverse shadow-overlay transition-opacity hover:opacity-90"
      >
        {open ? <X size={20} /> : <MessageCircle size={20} />}
      </button>
    </div>
  );
}
