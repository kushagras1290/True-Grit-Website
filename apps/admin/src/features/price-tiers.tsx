/**
 * Price Tiers — country pricing brackets.
 *
 * A bracket ("Tier 1" at +100%, say) groups countries that should all pay the
 * same markup over India's base price. Assigning a country to a bracket
 * writes a global, no-product, no-category `price_adjustments` row for that
 * country — the same engine the Sale & Discounts page uses — so a manual
 * per-product or per-category rule added there later still overrides a
 * bracket for that one case. See `services/price_tiers.py`.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useState } from "react";

import { useToast } from "../components/toast";
import { Button, ConfirmDialog, EmptyState, Field, Input, PageHeader } from "../components/ui";
import { ApiError, api, type PriceTierBracket, type PriceTiersResponse } from "../lib/api";
import { T } from "../lib/i18n";
import { usePermissions } from "../lib/permissions";

function percentLabel(percent: number): string {
  return percent > 0 ? `+${percent}%` : percent < 0 ? `${percent}%` : "No change";
}

function BracketCard({
  bracket,
  canEdit,
  onDelete,
}: {
  bracket: PriceTierBracket;
  canEdit: boolean;
  onDelete: (bracket: PriceTierBracket) => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [label, setLabel] = useState(bracket.label);
  const [percent, setPercent] = useState(String(bracket.percent));
  const [newCountry, setNewCountry] = useState("");

  function applyResult(result: PriceTiersResponse) {
    queryClient.setQueryData(["price-tiers"], result);
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      api.updatePriceTierBracket(bracket.id, { label: label.trim(), percent: Number(percent) }),
    onSuccess: (result) => {
      applyResult(result);
      toast.success(`${label.trim()} saved.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save this bracket."),
  });

  const assignMutation = useMutation({
    mutationFn: (countryCode: string) =>
      api.assignPriceTierCountry({ countryCode, bracketId: bracket.id }),
    onSuccess: (result) => {
      applyResult(result);
      setNewCountry("");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not assign that country."),
  });

  const unassignMutation = useMutation({
    mutationFn: (countryCode: string) => api.unassignPriceTierCountry(countryCode),
    onSuccess: applyResult,
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not remove that country."),
  });

  function addCountry() {
    const code = newCountry.trim().toUpperCase();
    if (!/^[A-Z]{2}$/.test(code)) {
      toast.error("A country needs a two-letter code, for example US, GB or DE.");
      return;
    }
    assignMutation.mutate(code);
  }

  const changed = label.trim() !== bracket.label || Number(percent) !== bracket.percent;

  return (
    <div className="rounded-md border border-line bg-surface p-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-40 flex-1">
          <Field label="Bracket name" htmlFor={`pt-label-${bracket.id}`}>
            <Input
              id={`pt-label-${bracket.id}`}
              value={label}
              disabled={!canEdit}
              onChange={(event) => setLabel(event.target.value)}
            />
          </Field>
        </div>
        <div className="w-32">
          <Field label="Markup %" htmlFor={`pt-percent-${bracket.id}`}>
            <Input
              id={`pt-percent-${bracket.id}`}
              type="number"
              min={-90}
              max={500}
              step={1}
              value={percent}
              disabled={!canEdit}
              onChange={(event) => setPercent(event.target.value)}
            />
          </Field>
        </div>
        {canEdit ? (
          <Button
            type="button"
            variant="secondary"
            disabled={!changed || saveMutation.isPending}
            onClick={() => saveMutation.mutate()}
          >
            {saveMutation.isPending ? <T>{"Saving…"}</T> : <T>{"Save"}</T>}
          </Button>
        ) : null}
        {canEdit ? (
          <Button type="button" variant="tertiary" onClick={() => onDelete(bracket)}>
            <T>Delete</T>
          </Button>
        ) : null}
      </div>

      <p className="mt-2 text-xs text-ink-muted">
        {percentLabel(bracket.percent)} <T>over India's base price</T>
      </p>

      <div className="mt-4 border-t border-line pt-3">
        <p className="mb-2 text-xs font-semibold tracking-wide text-ink-muted uppercase">
          <T>Countries in this bracket</T>
        </p>
        {bracket.countries.length === 0 ? (
          <p className="text-sm text-ink-muted">
            <T>No countries assigned yet.</T>
          </p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {bracket.countries.map((code) => (
              <li
                key={code}
                className="flex items-center gap-1 rounded-full border border-line bg-subtle/40 px-2.5 py-1 text-sm text-ink"
              >
                {code}
                {canEdit ? (
                  <button
                    type="button"
                    aria-label={`Remove ${code} from ${bracket.label}`}
                    className="text-ink-muted hover:text-ink"
                    disabled={unassignMutation.isPending}
                    onClick={() => unassignMutation.mutate(code)}
                  >
                    <X size={12} />
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        )}

        {canEdit ? (
          <div className="mt-3 flex items-end gap-2">
            <div className="w-28">
              <Field label="Add country" htmlFor={`pt-country-${bracket.id}`}>
                <Input
                  id={`pt-country-${bracket.id}`}
                  value={newCountry}
                  placeholder="US"
                  maxLength={2}
                  onChange={(event) => setNewCountry(event.target.value)}
                />
              </Field>
            </div>
            <Button
              type="button"
              variant="secondary"
              disabled={!newCountry.trim() || assignMutation.isPending}
              onClick={addCountry}
            >
              <T>Add</T>
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function PriceTiersPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const permissions = usePermissions();
  const canEdit = permissions.has("settings.edit");
  const { data, isLoading, isError } = useQuery({
    queryKey: ["price-tiers"],
    queryFn: api.priceTiers,
  });
  const [adding, setAdding] = useState(false);
  const [newBracket, setNewBracket] = useState({ label: "", percent: "0" });
  const [confirmDelete, setConfirmDelete] = useState<PriceTierBracket | null>(null);

  function applyResult(result: PriceTiersResponse) {
    queryClient.setQueryData(["price-tiers"], result);
  }

  const createMutation = useMutation({
    mutationFn: () =>
      api.createPriceTierBracket({
        label: newBracket.label.trim(),
        percent: Number(newBracket.percent),
      }),
    onSuccess: (result) => {
      applyResult(result);
      setNewBracket({ label: "", percent: "0" });
      setAdding(false);
      toast.success("Bracket created.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not create the bracket."),
  });

  const deleteMutation = useMutation({
    mutationFn: (bracketId: string) => api.deletePriceTierBracket(bracketId),
    onSuccess: (result) => {
      applyResult(result);
      setConfirmDelete(null);
      toast.success("Bracket removed.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not remove the bracket."),
  });

  if (isLoading)
    return (
      <p className="text-sm text-ink-muted">
        <T>Loading price tiers…</T>
      </p>
    );
  if (isError || !data) {
    return <EmptyState title="Price tiers unavailable" hint="Requires settings access." />;
  }

  return (
    <div>
      <PageHeader
        title="Price Tiers"
        description="Group countries into brackets that each pay a markup over India's base price. Both the percentage and which countries sit in each bracket are yours to adjust at any time."
        actions={
          canEdit ? (
            <Button type="button" variant="primary" onClick={() => setAdding((value) => !value)}>
              <Plus size={16} />
              <T>Add bracket</T>
            </Button>
          ) : undefined
        }
      />

      {adding ? (
        <form
          className="mb-6 grid gap-4 rounded-md border border-line bg-surface p-4 md:grid-cols-[1fr_10rem_auto] md:items-end"
          onSubmit={(event) => {
            event.preventDefault();
            if (!newBracket.label.trim()) {
              toast.error("Give the bracket a name.");
              return;
            }
            createMutation.mutate();
          }}
        >
          <Field label="Bracket name" htmlFor="new-bracket-label">
            <Input
              id="new-bracket-label"
              placeholder="Tier 4"
              value={newBracket.label}
              onChange={(event) =>
                setNewBracket((value) => ({ ...value, label: event.target.value }))
              }
            />
          </Field>
          <Field label="Markup %" htmlFor="new-bracket-percent">
            <Input
              id="new-bracket-percent"
              type="number"
              min={-90}
              max={500}
              step={1}
              value={newBracket.percent}
              onChange={(event) =>
                setNewBracket((value) => ({ ...value, percent: event.target.value }))
              }
            />
          </Field>
          <Button type="submit" variant="primary" disabled={createMutation.isPending}>
            {createMutation.isPending ? <T>{"Adding…"}</T> : <T>{"Add"}</T>}
          </Button>
        </form>
      ) : null}

      {data.brackets.length === 0 ? (
        <EmptyState title="No pricing brackets yet" hint="Add one above to get started." />
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {data.brackets.map((bracket) => (
            <BracketCard
              key={bracket.id}
              bracket={bracket}
              canEdit={canEdit}
              onDelete={setConfirmDelete}
            />
          ))}
        </div>
      )}

      {confirmDelete ? (
        <ConfirmDialog
          title="Delete this pricing bracket?"
          description={`"${confirmDelete.label}" and every country assigned to it (${confirmDelete.countries.length || 0}) will stop getting this markup. This cannot be undone.`}
          confirmLabel="Delete bracket"
          pendingLabel="Deleting…"
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => deleteMutation.mutate(confirmDelete.id)}
        />
      ) : null}
    </div>
  );
}
