/** Help Assistant admin screen: on/off switches for both bots, and the
 * shared knowledge base (`support_bot_knowledge`, scoped 'admin' |
 * 'storefront') both bots draw their static how-to/policy reference from —
 * one screen for both scopes rather than two parallel CRUD surfaces (see
 * services/support_bot_knowledge.py's module docstring). Gated on
 * `support_bot.manage` at the route level (main.tsx). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import {
  Button,
  ConfirmDialog,
  DataTableShell,
  EmptyState,
  Field,
  Input,
  LoadingRows,
  Modal,
  PageHeader,
  Select,
  Td,
  Textarea,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import {
  ApiError,
  api,
  type SupportBotEscalation,
  type SupportBotEscalationSeverity,
  type SupportBotEscalationStatus,
  type SupportBotKnowledgeEntry,
  type SupportBotPolicyFact,
  type SupportBotScope,
  type SupportBotTuningKey,
} from "../lib/api";
import { formatDateTime } from "../lib/format";
import { T } from "../lib/i18n";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function AvailabilityRow({
  label,
  description,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  disabled: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <li className="flex items-start justify-between gap-4 border-t border-line py-3 first:border-t-0">
      <div className="min-w-0">
        <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-ink">
          <input
            type="checkbox"
            checked={checked}
            disabled={disabled}
            onChange={(event) => onChange(event.target.checked)}
          />
          {label}
        </label>
        <p className="mt-1 text-sm text-ink-muted">{description}</p>
      </div>
      <span
        className={
          "inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-medium " +
          (checked ? "bg-success/10 text-success" : "border border-line bg-canvas text-ink-muted")
        }
      >
        {checked ? <T>On</T> : <T>Off</T>}
      </span>
    </li>
  );
}

/** Commits on blur/Enter rather than per keystroke, so a half-typed number
 *  ("1" on the way to "12") is never written and immediately clamped. */
function TuningRow({
  label,
  description,
  value,
  min,
  max,
  disabled,
  onCommit,
}: {
  label: string;
  description: string;
  value: number;
  min: number;
  max: number;
  disabled: boolean;
  onCommit: (next: number) => void;
}) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);

  function commit() {
    const parsed = Number.parseInt(draft, 10);
    if (Number.isNaN(parsed)) {
      setDraft(String(value));
      return;
    }
    const bounded = Math.min(max, Math.max(min, parsed));
    setDraft(String(bounded));
    if (bounded !== value) onCommit(bounded);
  }

  return (
    <li className="flex items-start justify-between gap-4 border-t border-line py-3 first:border-t-0">
      <div className="min-w-0">
        <p className="text-sm font-medium text-ink">{label}</p>
        <p className="mt-1 text-sm text-ink-muted">{description}</p>
      </div>
      <div className="w-24 shrink-0">
        <Input
          type="number"
          min={min}
          max={max}
          value={draft}
          disabled={disabled}
          aria-label={label}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.currentTarget.blur();
          }}
        />
      </div>
    </li>
  );
}

/** One standing fact the storefront bot quotes. Blank is a legitimate value,
 *  not an empty form field: it switches the wording that needs this fact back
 *  off and sends those questions to a person, so the row says which state it
 *  is in rather than leaving the operator to infer it. */
function PolicyFactRow({
  fact,
  disabled,
  onCommit,
}: {
  fact: SupportBotPolicyFact;
  disabled: boolean;
  onCommit: (value: string) => void;
}) {
  const [draft, setDraft] = useState(fact.value);
  useEffect(() => setDraft(fact.value), [fact.value]);

  return (
    <li className="border-t border-line py-3 first:border-t-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="text-sm font-medium text-ink" htmlFor={`fact-${fact.key}`}>
          <T>{fact.label}</T>
        </label>
        <span
          className={
            "inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-medium " +
            (fact.isConfigured
              ? "bg-success/10 text-success"
              : "border border-line bg-canvas text-ink-muted")
          }
        >
          {fact.isConfigured ? <T>Answered by the bot</T> : <T>Sent to a person</T>}
        </span>
      </div>
      <p className="mt-1 text-sm text-ink-muted">
        <T>{fact.hint}</T>
      </p>
      <Input
        id={`fact-${fact.key}`}
        className="mt-2"
        value={draft}
        maxLength={200}
        disabled={disabled}
        placeholder="Not set"
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => draft.trim() !== fact.value && onCommit(draft.trim())}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
        }}
      />
    </li>
  );
}

const SEVERITY_STYLES: Record<SupportBotEscalationSeverity, string> = {
  critical: "bg-danger/10 text-danger",
  high: "bg-warning/10 text-warning",
  normal: "border border-line bg-canvas text-ink-muted",
};

/** One handed-over conversation. The runner-up intents matter as much as the
 *  message: they are what tells you which phrasing the phrasebook is missing. */
function EscalationRow({
  escalation,
  disabled,
  onResolve,
}: {
  escalation: SupportBotEscalation;
  disabled: boolean;
  onResolve: (status: SupportBotEscalationStatus) => void;
}) {
  return (
    <li className="border-t border-line py-3 first:border-t-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm break-words text-ink">{escalation.message}</p>
          <p className="mt-1 text-xs text-ink-muted">
            {formatDateTime(escalation.createdAt)} · {escalation.intent} ·{" "}
            {escalation.reason.replace(/_/g, " ")} ·{" "}
            <T>confidence</T> {escalation.confidence.toFixed(2)}
            {escalation.customerUserId ? null : <> · <T>not signed in</T></>}
          </p>
          {escalation.alternatives.length > 0 ? (
            <p className="mt-1 text-xs text-ink-muted">
              <T>Nearly matched</T>:{" "}
              {escalation.alternatives
                .map((item) => `${item.intent} (${item.score.toFixed(2)})`)
                .join(", ")}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={
              "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium " +
              SEVERITY_STYLES[escalation.severity]
            }
          >
            {escalation.severity}
          </span>
          <Button type="button" disabled={disabled} onClick={() => onResolve("resolved")}>
            <T>Resolve</T>
          </Button>
        </div>
      </div>
    </li>
  );
}

/** `<input type="color">` cannot express "no override", so the swatch is paired
 *  with a Clear button rather than trying to encode blank as a colour. */
function WidgetColorRow({
  value,
  disabled,
  onCommit,
}: {
  value: string;
  disabled: boolean;
  onCommit: (next: string) => void;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);

  return (
    <div className="mt-3 flex flex-wrap items-center gap-3">
      <input
        type="color"
        className="h-9 w-14 cursor-pointer rounded-sm border border-line-strong bg-surface"
        value={draft || "#1f7a4d"}
        disabled={disabled}
        aria-label="Widget colour"
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => draft !== value && onCommit(draft)}
      />
      <Input
        className="w-32"
        value={draft}
        placeholder="#1f7a4d"
        maxLength={7}
        disabled={disabled}
        aria-label="Widget colour hex"
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => draft !== value && onCommit(draft)}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
        }}
      />
      {value ? (
        <Button type="button" variant="secondary" disabled={disabled} onClick={() => onCommit("")}>
          <T>Clear</T>
        </Button>
      ) : (
        <span className="text-sm text-ink-muted">
          <T>Using the site brand colour</T>
        </span>
      )}
    </div>
  );
}

interface KnowledgeFormValues {
  scope: SupportBotScope;
  title: string;
  keywords: string;
  content: string;
}

function KnowledgeFormModal({
  initial,
  onClose,
  onSave,
  isSaving,
  allowScopeChange,
}: {
  initial: KnowledgeFormValues;
  onClose: () => void;
  onSave: (values: KnowledgeFormValues) => void;
  isSaving: boolean;
  allowScopeChange: boolean;
}) {
  const [values, setValues] = useState<KnowledgeFormValues>(initial);

  return (
    <Modal
      title={allowScopeChange ? "Add knowledge entry" : "Edit knowledge entry"}
      onClose={onClose}
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          onSave(values);
        }}
      >
        <Field label="Applies to" htmlFor="sbk-scope">
          <Select
            id="sbk-scope"
            value={values.scope}
            disabled={!allowScopeChange}
            onChange={(event) =>
              setValues((v) => ({ ...v, scope: event.target.value as SupportBotScope }))
            }
          >
            <option value="admin">
              <T>Admin panel bot</T>
            </option>
            <option value="storefront">
              <T>Storefront bot</T>
            </option>
          </Select>
        </Field>
        <Field label="Title" htmlFor="sbk-title">
          <Input
            id="sbk-title"
            value={values.title}
            maxLength={120}
            required
            onChange={(event) => setValues((v) => ({ ...v, title: event.target.value }))}
          />
        </Field>
        <Field label="Keywords" htmlFor="sbk-keywords" error={undefined}>
          <Input
            id="sbk-keywords"
            value={values.keywords}
            maxLength={500}
            required
            placeholder="space separated, e.g. product publish visibility"
            onChange={(event) => setValues((v) => ({ ...v, keywords: event.target.value }))}
          />
          <p className="mt-1 text-xs text-ink-muted">
            <T>Words the bot matches against a question to decide this entry is relevant.</T>
          </p>
        </Field>
        <Field label="Content" htmlFor="sbk-content">
          <Textarea
            id="sbk-content"
            value={values.content}
            maxLength={2000}
            required
            rows={6}
            onChange={(event) => setValues((v) => ({ ...v, content: event.target.value }))}
          />
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSaving}>
            <T>Cancel</T>
          </Button>
          <Button type="submit" variant="primary" disabled={isSaving}>
            {isSaving ? <T>Saving…</T> : <T>Save</T>}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

const EMPTY_FORM: KnowledgeFormValues = { scope: "admin", title: "", keywords: "", content: "" };

export function SupportBotSettingsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [scopeFilter, setScopeFilter] = useState<SupportBotScope | "all">("all");
  const [editingEntry, setEditingEntry] = useState<SupportBotKnowledgeEntry | null>(null);
  const [creating, setCreating] = useState(false);
  const [deletingEntry, setDeletingEntry] = useState<SupportBotKnowledgeEntry | null>(null);

  const { data: settings } = useQuery({
    queryKey: ["support-bot-settings"],
    queryFn: api.supportBotSettings,
  });
  const { data: entries, isLoading } = useQuery({
    queryKey: ["support-bot-knowledge", scopeFilter],
    queryFn: () => api.supportBotKnowledge(scopeFilter === "all" ? undefined : scopeFilter),
  });

  const invalidateKnowledge = () =>
    queryClient.invalidateQueries({ queryKey: ["support-bot-knowledge"] });

  const toggleBot = useMutation({
    mutationFn: ({ scope, enabled }: { scope: SupportBotScope; enabled: boolean }) =>
      api.setSupportBotEnabled(scope, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["support-bot-settings"] }),
    onError: (error) => toast.error(errorMessage(error, "Could not update the switch.")),
  });

  const tuneBot = useMutation({
    mutationFn: ({ key, value }: { key: SupportBotTuningKey; value: number }) =>
      api.setSupportBotTuning(key, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["support-bot-settings"] }),
    onError: (error) => toast.error(errorMessage(error, "Could not update that setting.")),
  });

  const { data: policyFacts } = useQuery({
    queryKey: ["support-bot-policy-facts"],
    queryFn: api.supportBotPolicyFacts,
  });
  const { data: escalations } = useQuery({
    queryKey: ["support-bot-escalations"],
    queryFn: () => api.supportBotEscalations({ status: "open", limit: 25 }),
  });

  const setPolicyFact = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      api.setSupportBotPolicyFact(key, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["support-bot-policy-facts"] }),
    onError: (error) => toast.error(errorMessage(error, "Could not update that fact.")),
  });

  const resolveEscalation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: SupportBotEscalationStatus }) =>
      api.setSupportBotEscalationStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["support-bot-escalations"] });
      toast.success("Marked as handled.");
    },
    onError: (error) => toast.error(errorMessage(error, "Could not update that item.")),
  });

  const setColor = useMutation({
    mutationFn: (widgetColor: string) => api.setSupportBotWidgetColor(widgetColor),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["support-bot-settings"] }),
    onError: (error) => toast.error(errorMessage(error, "Could not update the widget colour.")),
  });

  const createEntry = useMutation({
    mutationFn: api.createSupportBotKnowledge,
    onSuccess: () => {
      invalidateKnowledge();
      setCreating(false);
      toast.success("Knowledge entry added.");
    },
    onError: (error) => toast.error(errorMessage(error, "Could not add the entry.")),
  });

  const updateEntry = useMutation({
    mutationFn: ({ id, ...input }: KnowledgeFormValues & { id: string }) =>
      api.updateSupportBotKnowledge(id, input),
    onSuccess: () => {
      invalidateKnowledge();
      setEditingEntry(null);
      toast.success("Knowledge entry updated.");
    },
    onError: (error) => toast.error(errorMessage(error, "Could not update the entry.")),
  });

  const deleteEntry = useMutation({
    mutationFn: (id: string) => api.deleteSupportBotKnowledge(id),
    onSuccess: () => {
      invalidateKnowledge();
      setDeletingEntry(null);
      toast.success("Knowledge entry deleted.");
    },
    onError: (error) => toast.error(errorMessage(error, "Could not delete the entry.")),
  });

  return (
    <div>
      <PageHeader
        title="Help Assistant"
        description="Control whether each bot is available, and edit what it knows."
        actions={
          <Button type="button" variant="primary" onClick={() => setCreating(true)}>
            <Plus size={15} />
            <T>Add entry</T>
          </Button>
        }
      />

      <section className="mb-6 rounded-md border border-line bg-surface p-4">
        <h2 className="font-display text-base text-ink">
          <T>Availability</T>
        </h2>
        <ul>
          <AvailabilityRow
            label="Admin panel bot"
            description="The floating Help Assistant staff see on every admin page."
            checked={settings?.admin ?? true}
            disabled={toggleBot.isPending}
            onChange={(enabled) => toggleBot.mutate({ scope: "admin", enabled })}
          />
          <AvailabilityRow
            label="Storefront bot"
            description="The chat widget customers and visitors see on the storefront."
            checked={settings?.storefront ?? true}
            disabled={toggleBot.isPending}
            onChange={(enabled) => toggleBot.mutate({ scope: "storefront", enabled })}
          />
        </ul>
      </section>

      <section className="mb-6 rounded-md border border-line bg-surface p-4">
        <h2 className="font-display text-base text-ink">
          <T>Storefront answers</T>
        </h2>
        <p className="mt-1 text-sm text-ink-muted">
          <T>
            The storefront bot only states figures you have entered here. Anything left blank is
            sent to a person instead, so it can never quote a policy nobody set.
          </T>
        </p>
        <ul className="mt-2">
          {(policyFacts ?? []).map((fact) => (
            <PolicyFactRow
              key={fact.key}
              fact={fact}
              disabled={setPolicyFact.isPending}
              onCommit={(value) => setPolicyFact.mutate({ key: fact.key, value })}
            />
          ))}
        </ul>
      </section>

      <section className="mb-6 rounded-md border border-line bg-surface p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-base text-ink">
            <T>Handed to a person</T>
          </h2>
          <span className="text-sm text-ink-muted">
            {escalations?.total ?? 0} <T>open</T>
          </span>
        </div>
        <p className="mt-1 text-sm text-ink-muted">
          <T>
            Questions the storefront bot would not answer, worst first. The phrasings it nearly
            matched are shown against each one, which is what tells you what to add to its
            vocabulary.
          </T>
        </p>
        {escalations && escalations.items.length > 0 ? (
          <ul className="mt-2">
            {escalations.items.map((escalation) => (
              <EscalationRow
                key={escalation.id}
                escalation={escalation}
                disabled={resolveEscalation.isPending}
                onResolve={(status) => resolveEscalation.mutate({ id: escalation.id, status })}
              />
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-ink-muted">
            <T>Nothing waiting. Everything asked so far was answered or refused cleanly.</T>
          </p>
        )}
      </section>

      <section className="mb-6 rounded-md border border-line bg-surface p-4">
        <h2 className="font-display text-base text-ink">
          <T>Admin bot answer tuning</T>
        </h2>
        <p className="mt-1 text-sm text-ink-muted">
          <T>
            Applies to the admin panel bot only. The storefront bot does not use a language model,
            so it has nothing to tune here.
          </T>
        </p>
        <ul className="mt-2">
          <TuningRow
            label="Conversation turns remembered"
            description="How much of the current chat is sent back with each question. 0 answers every question in isolation."
            value={settings?.historyTurns ?? 10}
            min={0}
            max={40}
            disabled={tuneBot.isPending}
            onCommit={(value) => tuneBot.mutate({ key: "historyTurns", value })}
          />
          <TuningRow
            label="Knowledge entries per answer"
            description="How many entries from the list below are given to the assistant as reference."
            value={settings?.knowledgeSnippets ?? 6}
            min={1}
            max={30}
            disabled={tuneBot.isPending}
            onCommit={(value) => tuneBot.mutate({ key: "knowledgeSnippets", value })}
          />
        </ul>
      </section>

      <section className="mb-6 rounded-md border border-line bg-surface p-4">
        <h2 className="font-display text-base text-ink">
          <T>Widget colour</T>
        </h2>
        <p className="mt-1 text-sm text-ink-muted">
          <T>
            Applies to both chat widgets. Leave it cleared to follow the site brand colour from
            Colours &amp; Effects.
          </T>
        </p>
        <WidgetColorRow
          value={settings?.widgetColor ?? ""}
          disabled={setColor.isPending}
          onCommit={(value) => setColor.mutate(value)}
        />
      </section>

      <div className="mb-4 flex items-center gap-2">
        <span className="text-sm font-medium text-ink">
          <T>Scope</T>
        </span>
        <Select
          value={scopeFilter}
          onChange={(event) => setScopeFilter(event.target.value as SupportBotScope | "all")}
          className="w-auto"
        >
          <option value="all">
            <T>All</T>
          </option>
          <option value="admin">
            <T>Admin panel bot</T>
          </option>
          <option value="storefront">
            <T>Storefront bot</T>
          </option>
        </Select>
      </div>

      {!isLoading && (entries ?? []).length === 0 ? (
        <EmptyState
          title="No knowledge entries"
          hint="Add one so the bot has something to reference for this scope."
        />
      ) : (
        <DataTableShell>
          <thead>
            <tr className="border-b border-line">
              <Th>
                <T>Title</T>
              </Th>
              <Th>
                <T>Scope</T>
              </Th>
              <Th>
                <T>Keywords</T>
              </Th>
              <Th>
                <T>Updated</T>
              </Th>
              <Th />
            </tr>
          </thead>
          {isLoading ? (
            <LoadingRows columns={5} />
          ) : (
            <tbody>
              {(entries ?? []).map((entry) => (
                <tr key={entry.id} className="border-t border-line">
                  <Td className="font-medium">
                    {entry.title}
                    {entry.isBuiltin ? (
                      <span className="ml-2 rounded-full border border-line bg-canvas px-2 py-0.5 text-[11px] text-ink-muted">
                        <T>Built-in</T>
                      </span>
                    ) : null}
                  </Td>
                  <Td className="text-ink-muted">
                    {entry.scope === "admin" ? <T>Admin</T> : <T>Storefront</T>}
                  </Td>
                  <Td className="max-w-xs truncate text-ink-muted">{entry.keywords}</Td>
                  <Td className="text-ink-muted">{formatDateTime(entry.updatedAt)}</Td>
                  <Td>
                    <div className="flex justify-end gap-1">
                      <button
                        type="button"
                        aria-label="Edit entry"
                        className="flex h-8 w-8 items-center justify-center rounded-sm text-ink-muted hover:bg-canvas hover:text-ink"
                        onClick={() => setEditingEntry(entry)}
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        type="button"
                        aria-label="Delete entry"
                        className="flex h-8 w-8 items-center justify-center rounded-sm text-ink-muted hover:bg-danger/10 hover:text-danger"
                        onClick={() => setDeletingEntry(entry)}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          )}
        </DataTableShell>
      )}

      {creating ? (
        <KnowledgeFormModal
          initial={{ ...EMPTY_FORM, scope: scopeFilter === "storefront" ? "storefront" : "admin" }}
          onClose={() => setCreating(false)}
          onSave={(values) => createEntry.mutate(values)}
          isSaving={createEntry.isPending}
          allowScopeChange
        />
      ) : null}

      {editingEntry ? (
        <KnowledgeFormModal
          initial={{
            scope: editingEntry.scope,
            title: editingEntry.title,
            keywords: editingEntry.keywords,
            content: editingEntry.content,
          }}
          onClose={() => setEditingEntry(null)}
          onSave={(values) => updateEntry.mutate({ id: editingEntry.id, ...values })}
          isSaving={updateEntry.isPending}
          allowScopeChange={false}
        />
      ) : null}

      {deletingEntry ? (
        <ConfirmDialog
          title="Delete knowledge entry?"
          description={`"${deletingEntry.title}" will no longer be available to the bot. This cannot be undone.`}
          confirmLabel="Delete"
          pendingLabel="Deleting…"
          isPending={deleteEntry.isPending}
          onCancel={() => setDeletingEntry(null)}
          onConfirm={() => deleteEntry.mutate(deletingEntry.id)}
        />
      ) : null}
    </div>
  );
}
