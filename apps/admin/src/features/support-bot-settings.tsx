/** Help Assistant admin screen: on/off switches for both bots, and the
 * shared knowledge base (`support_bot_knowledge`, scoped 'admin' |
 * 'storefront') both bots draw their static how-to/policy reference from —
 * one screen for both scopes rather than two parallel CRUD surfaces (see
 * services/support_bot_knowledge.py's module docstring). Gated on
 * `support_bot.manage` at the route level (main.tsx). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

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
import { ApiError, api, type SupportBotKnowledgeEntry, type SupportBotScope } from "../lib/api";
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
            <option value="admin"><T>Admin panel bot</T></option>
            <option value="storefront"><T>Storefront bot</T></option>
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

      <div className="mb-4 flex items-center gap-2">
        <span className="text-sm font-medium text-ink">
          <T>Scope</T>
        </span>
        <Select
          value={scopeFilter}
          onChange={(event) => setScopeFilter(event.target.value as SupportBotScope | "all")}
          className="w-auto"
        >
          <option value="all"><T>All</T></option>
          <option value="admin"><T>Admin panel bot</T></option>
          <option value="storefront"><T>Storefront bot</T></option>
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
              <Th><T>Title</T></Th>
              <Th><T>Scope</T></Th>
              <Th><T>Keywords</T></Th>
              <Th><T>Updated</T></Th>
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
