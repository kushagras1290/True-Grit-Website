/** Staff messaging: groups and direct messages. Membership (create, rename,
 * add/remove participants) is owner-only at the API (require_owner) — this
 * page only offers those actions when `useMe().isSuperAdmin`, matching how
 * `layout.tsx` gates Admin Logs. Anyone with `messages.use` (route-level,
 * see main.tsx) can read and send in a conversation they were added to.
 * Sending goes over `useChatSocket`'s WebSocket, not a REST call. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, Send, UserMinus, UserPlus, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button, EmptyState, Field, Input, Modal, Select, Textarea } from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api, type ChatMessage, type ConversationSummary } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { useMe } from "../lib/permissions";
import { conversationHistoryKey, useChatSocket } from "../lib/useChatSocket";
import { T } from "../lib/i18n";

function conversationLabel(
  conversation: ConversationSummary,
  myUserId: string | undefined,
): string {
  if (conversation.type === "group") return conversation.name ?? "Untitled group";
  const other = conversation.participants.find((p) => p.userId !== myUserId);
  return other?.displayName ?? "Direct message";
}

/** The other person's role(s) in a direct message, e.g. "Farm Owner" -- so
 *  an admin can see who they are actually talking to, not just a name.
 *  Group conversations already show every member's role in "Manage". */
function directMessageRole(
  conversation: ConversationSummary,
  myUserId: string | undefined,
): string | null {
  if (conversation.type !== "direct") return null;
  const other = conversation.participants.find((p) => p.userId !== myUserId);
  return other && other.roles.length > 0 ? other.roles.join(", ") : null;
}

function ConversationList({
  conversations,
  isLoading,
  selectedId,
  onSelect,
  myUserId,
}: {
  conversations: ConversationSummary[];
  isLoading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  myUserId: string | undefined;
}) {
  if (isLoading) {
    return (
      <p className="p-4 text-sm text-ink-muted">
        <T>Loading conversations…</T>
      </p>
    );
  }
  if (conversations.length === 0) {
    return (
      <div className="p-4">
        <EmptyState
          title="No conversations yet"
          hint="A super admin can start a group or direct message from the + button above."
        />
      </div>
    );
  }
  return (
    <ul className="divide-y divide-line overflow-y-auto">
      {conversations.map((conversation) => (
        <li key={conversation.id}>
          <button
            type="button"
            onClick={() => onSelect(conversation.id)}
            className={`flex w-full flex-col gap-0.5 px-4 py-3 text-left hover:bg-canvas ${
              selectedId === conversation.id ? "bg-subtle" : ""
            }`}
          >
            <span className="flex items-center justify-between gap-2">
              <span className="truncate text-sm font-medium text-ink">
                {conversationLabel(conversation, myUserId)}
              </span>
              {conversation.unreadCount > 0 ? (
                <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-brand px-1.5 py-0.5 text-[11px] font-semibold leading-none text-ink-inverse">
                  {conversation.unreadCount}
                </span>
              ) : null}
            </span>
            <span className="flex items-center justify-between gap-2">
              <span className="truncate text-xs text-ink-muted">
                {conversation.lastMessageBody ?? <T>{"No messages yet"}</T>}
              </span>
              {conversation.lastMessageAt ? (
                <span className="shrink-0 text-[11px] text-ink-muted">
                  {formatDateTime(conversation.lastMessageAt)}
                </span>
              ) : null}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function MessageBubble({ message, isMine }: { message: ChatMessage; isMine: boolean }) {
  return (
    <div className={`flex flex-col ${isMine ? "items-end" : "items-start"}`}>
      <div
        className={`max-w-[75%] rounded-md px-3 py-2 text-sm ${
          isMine ? "bg-brand text-ink-inverse" : "border border-line bg-surface text-ink"
        }`}
      >
        {!isMine ? (
          <p className="mb-0.5 text-xs font-semibold opacity-80">{message.senderName}</p>
        ) : null}
        <p className="whitespace-pre-wrap break-words">{message.body}</p>
      </div>
      <span className="mt-1 text-[11px] text-ink-muted">{formatDateTime(message.createdAt)}</span>
    </div>
  );
}

function MessageThread({
  conversation,
  myUserId,
  isSuperAdmin,
  onBack,
}: {
  conversation: ConversationSummary;
  myUserId: string | undefined;
  isSuperAdmin: boolean;
  onBack: () => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [manageOpen, setManageOpen] = useState(false);
  const { status, send } = useChatSocket(conversation.id);

  const { data: history, isLoading } = useQuery({
    queryKey: conversationHistoryKey(conversation.id),
    queryFn: () => api.conversationHistory(conversation.id),
  });

  const messages = history?.messages ?? [];
  const lastMessageId = messages.at(-1)?.id ?? null;

  const markRead = useMutation({
    mutationFn: (lastReadMessageId: string | null) =>
      api.markConversationRead(conversation.id, lastReadMessageId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["conversations"] }),
  });

  useEffect(() => {
    if (lastMessageId) markRead.mutate(lastMessageId);
    // Only re-run when the conversation or its latest message changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversation.id, lastMessageId]);

  function handleSend() {
    const body = draft.trim();
    if (!body) return;
    const sent = send(body);
    if (!sent) {
      toast.error("Not connected yet — try again in a moment.");
      return;
    }
    setDraft("");
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onBack}
            aria-label="Back to conversations"
            className="flex h-8 w-8 items-center justify-center rounded-sm text-ink-muted hover:bg-canvas md:hidden"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <p className="flex items-center gap-2 font-medium text-ink">
              {conversationLabel(conversation, myUserId)}
              {directMessageRole(conversation, myUserId) ? (
                <span className="rounded-full bg-subtle px-2 py-0.5 text-[11px] font-medium text-ink-muted">
                  {directMessageRole(conversation, myUserId)}
                </span>
              ) : null}
            </p>
            <p className="text-xs text-ink-muted">
              {status === "open" ? (
                <T>{"Live"}</T>
              ) : status === "connecting" ? (
                <T>{"Connecting…"}</T>
              ) : (
                <T>{"Reconnecting…"}</T>
              )}
            </p>
          </div>
        </div>
        {isSuperAdmin && conversation.type === "group" ? (
          <Button variant="secondary" onClick={() => setManageOpen(true)}>
            <Users size={15} />
            <T>Manage</T>
          </Button>
        ) : null}
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {isLoading ? (
          <p className="text-sm text-ink-muted">
            <T>Loading messages…</T>
          </p>
        ) : messages.length === 0 ? (
          <p className="text-sm text-ink-muted">
            <T>No messages yet. Say hello.</T>
          </p>
        ) : (
          messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              isMine={message.senderId === myUserId}
            />
          ))
        )}
      </div>

      <div className="flex items-end gap-2 border-t border-line px-4 py-3">
        <Textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              handleSend();
            }
          }}
          placeholder="Write a message…"
          className="min-h-11 flex-1"
          maxLength={4000}
        />
        <Button variant="primary" onClick={handleSend} disabled={!draft.trim()}>
          <Send size={15} />
        </Button>
      </div>

      {manageOpen ? (
        <ManageParticipantsModal conversation={conversation} onClose={() => setManageOpen(false)} />
      ) : null}
    </div>
  );
}

function StaffPicker({
  excludeUserIds,
  selected,
  onToggle,
}: {
  excludeUserIds: string[];
  selected: string[];
  onToggle: (userId: string) => void;
}) {
  const { data: staff, isLoading } = useQuery({
    queryKey: ["messages-staff-picker"],
    queryFn: () => api.users({ limit: 200 }),
  });
  const candidates = (staff ?? []).filter(
    (user) => user.status === "active" && !excludeUserIds.includes(user.id),
  );

  if (isLoading)
    return (
      <p className="text-sm text-ink-muted">
        <T>Loading staff…</T>
      </p>
    );
  if (candidates.length === 0)
    return (
      <p className="text-sm text-ink-muted">
        <T>No one else to add.</T>
      </p>
    );

  return (
    <div className="max-h-56 space-y-1 overflow-y-auto rounded-sm border border-line-strong p-2">
      {candidates.map((user) => (
        <label
          key={user.id}
          className="flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-canvas"
        >
          <input
            type="checkbox"
            checked={selected.includes(user.id)}
            onChange={() => onToggle(user.id)}
          />
          <span className="text-ink">{user.displayName}</span>
          <span className="text-xs text-ink-muted">
            {user.roles.length > 0 ? user.roles.join(", ") : <T>{"No role"}</T>}
          </span>
        </label>
      ))}
    </div>
  );
}

function ManageParticipantsModal({
  conversation,
  onClose,
}: {
  conversation: ConversationSummary;
  onClose: () => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [name, setName] = useState(conversation.name ?? "");
  const [toAdd, setToAdd] = useState<string[]>([]);
  const currentIds = conversation.participants.map((p) => p.userId);

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["conversations"] });
  }

  const rename = useMutation({
    mutationFn: () => api.renameConversation(conversation.id, name.trim()),
    onSuccess: async () => {
      await invalidate();
      toast.success("Renamed.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not rename."),
  });

  const addParticipants = useMutation({
    mutationFn: () => api.addConversationParticipants(conversation.id, toAdd),
    onSuccess: async () => {
      await invalidate();
      setToAdd([]);
      toast.success("Added.");
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not add."),
  });

  const removeParticipant = useMutation({
    mutationFn: (userId: string) => api.removeConversationParticipant(conversation.id, userId),
    onSuccess: async () => {
      await invalidate();
      toast.success("Removed.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not remove."),
  });

  return (
    <Modal title="Manage conversation" onClose={onClose}>
      <div className="space-y-5">
        <Field label="Group name" htmlFor="conversation-name">
          <div className="flex gap-2">
            <Input id="conversation-name" value={name} onChange={(e) => setName(e.target.value)} />
            <Button
              variant="secondary"
              disabled={rename.isPending || !name.trim() || name.trim() === conversation.name}
              onClick={() => rename.mutate()}
            >
              <T>Save</T>
            </Button>
          </div>
        </Field>

        <div>
          <p className="mb-1.5 text-sm font-medium text-ink">
            <T>Participants</T>
          </p>
          <ul className="space-y-1">
            {conversation.participants.map((participant) => (
              <li
                key={participant.userId}
                className="flex items-center justify-between rounded-sm border border-line px-2.5 py-1.5 text-sm"
              >
                <span>
                  {participant.displayName}
                  {participant.roles.length > 0 ? (
                    <span className="ml-1.5 text-xs text-ink-muted">
                      ({participant.roles.join(", ")})
                    </span>
                  ) : null}
                </span>
                <button
                  type="button"
                  aria-label={`Remove ${participant.displayName}`}
                  className="text-ink-muted hover:text-danger"
                  disabled={removeParticipant.isPending}
                  onClick={() => removeParticipant.mutate(participant.userId)}
                >
                  <UserMinus size={15} />
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="mb-1.5 text-sm font-medium text-ink">
            <T>Add participants</T>
          </p>
          <StaffPicker
            excludeUserIds={currentIds}
            selected={toAdd}
            onToggle={(userId) =>
              setToAdd((current) =>
                current.includes(userId)
                  ? current.filter((id) => id !== userId)
                  : [...current, userId],
              )
            }
          />
          <Button
            variant="secondary"
            className="mt-2"
            disabled={toAdd.length === 0 || addParticipants.isPending}
            onClick={() => addParticipants.mutate()}
          >
            <UserPlus size={15} />
            <T>Add selected</T>
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function NewConversationModal({
  myUserId,
  onClose,
  onCreated,
}: {
  myUserId: string | undefined;
  onClose: () => void;
  onCreated: (conversationId: string) => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [type, setType] = useState<"group" | "direct">("group");
  const [name, setName] = useState("");
  const [participantIds, setParticipantIds] = useState<string[]>([]);

  const create = useMutation({
    mutationFn: () =>
      api.createConversation({
        type,
        name: type === "group" ? name.trim() : null,
        // The creator is always a participant of what they create -- without
        // this, a conversation made from this modal never appears in the
        // creator's own list (list_my_conversations only returns
        // conversations you belong to), so they could never open, message
        // in, or manage it again after closing this modal.
        participantUserIds: myUserId ? [...participantIds, myUserId] : participantIds,
      }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      toast.success(
        type === "group"
          ? "Group created."
          : result.reused
            ? "Conversation found."
            : "Conversation started.",
      );
      onCreated(result.id);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not create."),
  });

  // The current user is added automatically above, so the picker only ever
  // needs to name the *other* people -- one more for a direct message, at
  // least one more for a group.
  const canSubmit =
    type === "group"
      ? name.trim().length > 0 && participantIds.length >= 1
      : participantIds.length === 1;

  return (
    <Modal title="New conversation" onClose={onClose}>
      <div className="space-y-5">
        <Field label="Type" htmlFor="conversation-type">
          <Select
            id="conversation-type"
            value={type}
            onChange={(event) => {
              setType(event.target.value as "group" | "direct");
              setParticipantIds([]);
            }}
          >
            <option value="group">
              <T>Group</T>
            </option>
            <option value="direct">
              <T>Direct message</T>
            </option>
          </Select>
        </Field>

        {type === "group" ? (
          <Field label="Group name" htmlFor="new-conversation-name">
            <Input
              id="new-conversation-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Ops Room"
            />
          </Field>
        ) : (
          <p className="text-xs text-ink-muted">
            <T>Pick the other person for this direct message.</T>
          </p>
        )}

        <div>
          <p className="mb-1.5 text-sm font-medium text-ink">
            <T>Participants</T>
          </p>
          <StaffPicker
            excludeUserIds={myUserId ? [myUserId] : []}
            selected={participantIds}
            onToggle={(userId) =>
              setParticipantIds((current) => {
                if (current.includes(userId)) return current.filter((id) => id !== userId);
                if (type === "direct" && current.length >= 1) return current;
                return [...current, userId];
              })
            }
          />
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            <T>Cancel</T>
          </Button>
          <Button
            variant="primary"
            disabled={!canSubmit || create.isPending}
            onClick={() => create.mutate()}
          >
            {create.isPending ? <T>{"Creating..."}</T> : <T>Create</T>}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export function MessagesPage() {
  const { data: me } = useMe();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [newConversationOpen, setNewConversationOpen] = useState(false);

  const { data: conversations, isLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: api.listConversations,
    refetchInterval: 30_000,
  });

  const selected = useMemo(
    () => (conversations ?? []).find((c) => c.id === selectedId) ?? null,
    [conversations, selectedId],
  );

  return (
    <div className="flex h-[calc(100vh-8.5rem)] flex-col">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="font-display text-2xl text-ink">
          <T>Messages</T>
        </h1>
        {me?.isSuperAdmin ? (
          <Button variant="primary" onClick={() => setNewConversationOpen(true)}>
            <Plus size={15} />
            <T>New conversation</T>
          </Button>
        ) : null}
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden rounded-md border border-line bg-surface shadow-card md:grid-cols-[20rem_minmax(0,1fr)]">
        <div
          className={`min-h-0 flex-col border-line md:flex md:border-r ${
            selected ? "hidden md:flex" : "flex"
          }`}
        >
          <ConversationList
            conversations={conversations ?? []}
            isLoading={isLoading}
            selectedId={selectedId}
            onSelect={setSelectedId}
            myUserId={me?.id}
          />
        </div>
        <div className={`min-h-0 md:block ${selected ? "block" : "hidden md:block"}`}>
          {selected ? (
            <MessageThread
              conversation={selected}
              myUserId={me?.id}
              isSuperAdmin={me?.isSuperAdmin ?? false}
              onBack={() => setSelectedId(null)}
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <EmptyState
                title="Select a conversation"
                hint="Pick one from the list to start reading."
              />
            </div>
          )}
        </div>
      </div>

      {newConversationOpen ? (
        <NewConversationModal
          myUserId={me?.id}
          onClose={() => setNewConversationOpen(false)}
          onCreated={(conversationId) => {
            setSelectedId(conversationId);
            setNewConversationOpen(false);
          }}
        />
      ) : null}
    </div>
  );
}
