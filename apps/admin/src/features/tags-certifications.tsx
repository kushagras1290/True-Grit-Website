/** Editable master lists for the two product-editor checkbox groups that
 * used to be fixed by migration/seed data: dietary tags (`tags` where
 * tag_group = 'diet') and certifications. Both are the same shape of job --
 * a short list of named rows with add/rename/delete -- so one generic list
 * editor drives both sections instead of duplicating the same markup twice. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

import { Button, ConfirmDialog, EmptyState, Input, PageHeader } from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api } from "../lib/api";
import { PermissionGate } from "../lib/permissions";
import { T } from "../lib/i18n";

interface NamedRow {
  id: string;
  name: string;
}

function EditableList({
  title,
  description,
  addPlaceholder,
  deleteWarning,
  items,
  isLoading,
  onCreate,
  onUpdate,
  onDelete,
  creating,
  updating,
  deleting,
}: {
  title: string;
  description: string;
  addPlaceholder: string;
  deleteWarning: (name: string) => string;
  items: NamedRow[];
  isLoading: boolean;
  onCreate: (name: string) => void;
  onUpdate: (id: string, name: string) => void;
  onDelete: (id: string) => void;
  creating: boolean;
  updating: boolean;
  deleting: boolean;
}) {
  const [draft, setDraft] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState("");
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  function startEditing(row: NamedRow) {
    setEditingId(row.id);
    setEditingValue(row.name);
  }

  function saveEditing() {
    const value = editingValue.trim();
    if (!editingId || !value) return;
    onUpdate(editingId, value);
    setEditingId(null);
  }

  const confirmingRow = items.find((row) => row.id === confirmingId) ?? null;

  return (
    <section className="rounded-md border border-line bg-surface p-5 shadow-card">
      <h2 className="font-display text-lg text-ink">{title}</h2>
      <p className="mt-1 text-sm text-ink-muted">{description}</p>

      {confirmingRow ? (
        <ConfirmDialog
          title="Delete this entry"
          description={deleteWarning(confirmingRow.name)}
          confirmLabel="Delete"
          pendingLabel="Deleting..."
          isPending={deleting}
          onCancel={() => setConfirmingId(null)}
          onConfirm={() => {
            onDelete(confirmingRow.id);
            setConfirmingId(null);
          }}
        />
      ) : null}

      <PermissionGate permission="products.edit">
        <form
          className="mt-4 flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            const value = draft.trim();
            if (!value) return;
            onCreate(value);
            setDraft("");
          }}
        >
          <Input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={addPlaceholder}
            aria-label={addPlaceholder}
          />
          <Button type="submit" variant="primary" disabled={creating || !draft.trim()}>
            <Plus size={15} aria-hidden />
            <T>Add</T>
          </Button>
        </form>
      </PermissionGate>

      <ul className="mt-4 divide-y divide-line">
        {isLoading ? (
          <li className="py-3 text-sm text-ink-muted">
            <T>Loading…</T>
          </li>
        ) : items.length === 0 ? (
          <li className="py-3">
            <EmptyState title="Nothing here yet" hint="Add one using the field above." />
          </li>
        ) : (
          items.map((row) => (
            <li key={row.id} className="flex items-center gap-2 py-2.5">
              {editingId === row.id ? (
                <>
                  <Input
                    autoFocus
                    value={editingValue}
                    onChange={(event) => setEditingValue(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        saveEditing();
                      }
                      if (event.key === "Escape") setEditingId(null);
                    }}
                    aria-label={`Rename ${row.name}`}
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    aria-label="Save"
                    disabled={updating || !editingValue.trim()}
                    onClick={saveEditing}
                  >
                    <Check size={15} aria-hidden />
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    aria-label="Cancel"
                    onClick={() => setEditingId(null)}
                  >
                    <X size={15} aria-hidden />
                  </Button>
                </>
              ) : (
                <>
                  <span className="flex-1 text-sm text-ink">{row.name}</span>
                  <PermissionGate permission="products.edit">
                    <Button
                      type="button"
                      variant="secondary"
                      aria-label={`Rename ${row.name}`}
                      onClick={() => startEditing(row)}
                    >
                      <Pencil size={14} aria-hidden />
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      aria-label={`Delete ${row.name}`}
                      onClick={() => setConfirmingId(row.id)}
                    >
                      <Trash2 size={14} aria-hidden />
                    </Button>
                  </PermissionGate>
                </>
              )}
            </li>
          ))
        )}
      </ul>
    </section>
  );
}

export function TagsCertificationsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const { data: dietTags = [], isLoading: dietTagsLoading } = useQuery({
    queryKey: ["diet-tags"],
    queryFn: () => api.dietTags(),
  });
  const { data: certifications = [], isLoading: certificationsLoading } = useQuery({
    queryKey: ["certifications"],
    queryFn: () => api.certifications(),
  });

  function onError(error: unknown, fallback: string) {
    toast.error(error instanceof ApiError ? error.message : fallback);
  }

  const createDietTag = useMutation({
    mutationFn: (label: string) => api.createDietTag(label),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["diet-tags"] });
      toast.success("Dietary tag added.");
    },
    onError: (error) => onError(error, "Could not add the dietary tag."),
  });
  const updateDietTag = useMutation({
    mutationFn: ({ id, label }: { id: string; label: string }) => api.updateDietTag(id, label),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["diet-tags"] });
      toast.success("Dietary tag updated.");
    },
    onError: (error) => onError(error, "Could not update the dietary tag."),
  });
  const deleteDietTag = useMutation({
    mutationFn: (id: string) => api.deleteDietTag(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["diet-tags"] });
      // Product editors may already be showing this tag as checked.
      await queryClient.invalidateQueries({ queryKey: ["admin-product"] });
      toast.success("Dietary tag deleted.");
    },
    onError: (error) => onError(error, "Could not delete the dietary tag."),
  });

  const createCertification = useMutation({
    mutationFn: (name: string) => api.createCertification(name),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["certifications"] });
      toast.success("Certification added.");
    },
    onError: (error) => onError(error, "Could not add the certification."),
  });
  const updateCertification = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api.updateCertification(id, name),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["certifications"] });
      toast.success("Certification updated.");
    },
    onError: (error) => onError(error, "Could not update the certification."),
  });
  const deleteCertification = useMutation({
    mutationFn: (id: string) => api.deleteCertification(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["certifications"] });
      toast.success("Certification deleted.");
    },
    onError: (error) => onError(error, "Could not delete the certification."),
  });

  return (
    <div>
      <PageHeader
        title="Dietary Tags & Certifications"
        description="The checkbox lists shown on every product's General tab. Changes apply everywhere immediately."
      />
      <div className="grid gap-5 lg:grid-cols-2">
        <EditableList
          title="Dietary tags"
          description="E.g. Vegan, Gluten Free. Deleting one removes it from every product that has it checked."
          addPlaceholder="New dietary tag"
          deleteWarning={(name) =>
            `"${name}" will be removed from every product that currently has it checked. This cannot be undone.`
          }
          items={dietTags.map((tag) => ({ id: tag.id, name: tag.label }))}
          isLoading={dietTagsLoading}
          onCreate={(label) => createDietTag.mutate(label)}
          onUpdate={(id, label) => updateDietTag.mutate({ id, label })}
          onDelete={(id) => deleteDietTag.mutate(id)}
          creating={createDietTag.isPending}
          updating={updateDietTag.isPending}
          deleting={deleteDietTag.isPending}
        />
        <EditableList
          title="Certifications"
          description="E.g. India Organic, Fair Trade. A certification assigned to any product cannot be deleted until removed from it."
          addPlaceholder="New certification"
          deleteWarning={(name) => `Delete "${name}"? This cannot be undone.`}
          items={certifications}
          isLoading={certificationsLoading}
          onCreate={(name) => createCertification.mutate(name)}
          onUpdate={(id, name) => updateCertification.mutate({ id, name })}
          onDelete={(id) => deleteCertification.mutate(id)}
          creating={createCertification.isPending}
          updating={updateCertification.isPending}
          deleting={deleteCertification.isPending}
        />
      </div>
    </div>
  );
}
