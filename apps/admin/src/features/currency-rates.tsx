import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { useToast } from "../components/toast";
import { Button, EmptyState, Field, Input, PageHeader, StatusPill } from "../components/ui";
import { ApiError, api, type CurrencyRate } from "../lib/api";
import { T } from "../lib/i18n";
import { usePermissions } from "../lib/permissions";

function preview(rate: CurrencyRate): string {
  const value = Number(rate.ratePerInr) * 1_000;
  if (!Number.isFinite(value)) return "Invalid value";
  try {
    return new Intl.NumberFormat(rate.locale, {
      style: "currency",
      currency: rate.currencyCode,
    }).format(value);
  } catch {
    return "Check currency code and locale";
  }
}

function RateRow({ rate, canEdit }: { rate: CurrencyRate; canEdit: boolean }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(rate);
  useEffect(() => setDraft(rate), [rate]);

  const mutation = useMutation({
    mutationFn: () => api.saveCurrencyRate(draft),
    onSuccess: ({ rate: saved }) => {
      queryClient.setQueryData<{ baseCurrency: "INR"; rates: CurrencyRate[] }>(
        ["currency-rates"],
        (current) =>
          current
            ? {
                ...current,
                rates: current.rates.map((entry) =>
                  entry.currencyCode === saved.currencyCode ? saved : entry,
                ),
              }
            : current,
      );
      toast.success(`${saved.currencyCode} conversion value saved.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save this conversion."),
  });

  const locked = rate.currencyCode === "INR";
  const changed =
    draft.locale !== rate.locale ||
    draft.ratePerInr !== rate.ratePerInr ||
    draft.active !== rate.active;

  return (
    <tr className="border-t border-line align-top">
      <td className="px-3 py-3">
        <span className="font-semibold text-ink">{rate.currencyCode}</span>
        <p className="mt-1 text-xs text-ink-muted">
          <T>1 INR →</T> {draft.ratePerInr || "—"}
        </p>
      </td>
      <td className="px-3 py-3">
        <Input
          aria-label={`${rate.currencyCode} value per INR`}
          inputMode="decimal"
          value={draft.ratePerInr}
          disabled={!canEdit || locked}
          onChange={(event) => setDraft((value) => ({ ...value, ratePerInr: event.target.value }))}
        />
      </td>
      <td className="px-3 py-3">
        <Input
          aria-label={`${rate.currencyCode} formatting locale`}
          value={draft.locale}
          disabled={!canEdit}
          onChange={(event) => setDraft((value) => ({ ...value, locale: event.target.value }))}
        />
      </td>
      <td className="px-3 py-3 text-sm text-ink">{preview(draft)}</td>
      <td className="px-3 py-3">
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={draft.active}
            disabled={!canEdit || locked}
            onChange={(event) => setDraft((value) => ({ ...value, active: event.target.checked }))}
          />
          <StatusPill status={draft.active ? "active" : "disabled"} />
        </label>
      </td>
      <td className="px-3 py-3 text-right">
        <Button
          type="button"
          variant="secondary"
          disabled={!canEdit || !changed || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? <T>{"Saving…"}</T> : <T>{"Save"}</T>}
        </Button>
      </td>
    </tr>
  );
}

export function CurrencyRatesPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const permissions = usePermissions();
  const canEdit = permissions.has("settings.edit");
  const { data, isLoading, isError } = useQuery({
    queryKey: ["currency-rates"],
    queryFn: api.currencyRates,
  });
  const [adding, setAdding] = useState(false);
  const [newRate, setNewRate] = useState({
    currencyCode: "",
    locale: "en-US",
    ratePerInr: "",
    active: true,
  });
  const addMutation = useMutation({
    mutationFn: () => api.saveCurrencyRate(newRate),
    onSuccess: ({ rate }) => {
      queryClient.setQueryData<{ baseCurrency: "INR"; rates: CurrencyRate[] }>(
        ["currency-rates"],
        (current) =>
          current
            ? {
                ...current,
                rates: [
                  ...current.rates.filter((item) => item.currencyCode !== rate.currencyCode),
                  rate,
                ].sort((a, b) => a.currencyCode.localeCompare(b.currencyCode)),
              }
            : current,
      );
      setNewRate({ currencyCode: "", locale: "en-US", ratePerInr: "", active: true });
      setAdding(false);
      toast.success(`${rate.currencyCode} was added.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not add the currency."),
  });

  if (isLoading)
    return (
      <p className="text-sm text-ink-muted">
        <T>Loading currency values…</T>
      </p>
    );
  if (isError || !data) {
    return <EmptyState title="Currency values unavailable" hint="Requires settings access." />;
  }

  return (
    <div>
      <PageHeader
        title="Currency Converter"
        description="Control approximate local-currency prices by setting how much one Indian rupee is worth. Catalogue, checkout and order records stay safely in INR."
        actions={
          canEdit ? (
            <Button type="button" variant="primary" onClick={() => setAdding((value) => !value)}>
              <Plus size={16} />
              <T>Add currency</T>
            </Button>
          ) : undefined
        }
      />

      <div className="mb-5 rounded-md border border-line bg-subtle/40 px-4 py-3 text-sm text-ink-muted">
        <strong className="text-ink">
          <T>Safe geo-lock:</T>
        </strong>{" "}
        <T>
          a visitor’s country selects a currency, this table supplies its display value, and the
          original INR price remains unchanged. Disabled currencies fall back to INR-safe defaults.
        </T>
      </div>

      {adding ? (
        <form
          className="mb-6 grid gap-4 rounded-md border border-line bg-surface p-4 md:grid-cols-[10rem_1fr_1fr_auto] md:items-end"
          onSubmit={(event) => {
            event.preventDefault();
            addMutation.mutate();
          }}
        >
          <Field label="Currency code" htmlFor="new-currency-code">
            <Input
              id="new-currency-code"
              maxLength={3}
              placeholder="USD"
              value={newRate.currencyCode}
              onChange={(event) =>
                setNewRate((value) => ({
                  ...value,
                  currencyCode: event.target.value.toUpperCase(),
                }))
              }
            />
          </Field>
          <Field label="Value of 1 INR" htmlFor="new-currency-rate">
            <Input
              id="new-currency-rate"
              inputMode="decimal"
              placeholder="0.0115"
              value={newRate.ratePerInr}
              onChange={(event) =>
                setNewRate((value) => ({ ...value, ratePerInr: event.target.value }))
              }
            />
          </Field>
          <Field label="Formatting locale" htmlFor="new-currency-locale">
            <Input
              id="new-currency-locale"
              placeholder="en-US"
              value={newRate.locale}
              onChange={(event) =>
                setNewRate((value) => ({ ...value, locale: event.target.value }))
              }
            />
          </Field>
          <Button type="submit" variant="primary" disabled={addMutation.isPending}>
            {addMutation.isPending ? <T>{"Adding…"}</T> : <T>{"Add"}</T>}
          </Button>
        </form>
      ) : null}

      <div className="overflow-x-auto rounded-md border border-line bg-surface">
        <table className="w-full min-w-[850px] border-collapse text-left">
          <thead className="bg-subtle/60 text-xs font-semibold tracking-wide text-ink-muted uppercase">
            <tr>
              <th className="px-3 py-3">
                <T>Currency</T>
              </th>
              <th className="px-3 py-3">
                <T>Value per INR</T>
              </th>
              <th className="px-3 py-3">
                <T>Formatting locale</T>
              </th>
              <th className="px-3 py-3">
                <T>₹1,000 preview</T>
              </th>
              <th className="px-3 py-3">
                <T>Storefront</T>
              </th>
              <th className="px-3 py-3">
                <span className="sr-only">
                  <T>Actions</T>
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.rates.map((rate) => (
              <RateRow key={rate.currencyCode} rate={rate} canEdit={canEdit} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
