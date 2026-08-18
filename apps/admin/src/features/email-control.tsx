import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  Button,
  EmptyState,
  Field,
  Input,
  LoadingRows,
  PageHeader,
  Select,
  StatusPill,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api } from "../lib/api";
import type { EmailOutcome } from "@truegrit/contracts";
import { formatDateTime } from "../lib/format";
import { T } from "../lib/i18n";

export function EmailControlPage() {
  return (
    <div>
      <PageHeader
        title="Email"
        description="Which provider sends True Grit's email, which kinds of email are allowed out, how
        fast, and what actually happened recently."
      />
      <ProviderSection />
      <CategoryTogglesSection />
      <RateLimitsSection />
      <ActivityLogSection />
    </div>
  );
}

function useEmailSettingsQuery() {
  return useQuery({ queryKey: ["email-settings"], queryFn: api.emailSettings });
}

// ---------------------------------------------------------------------------
// Provider: which of Resend/Brevo actually sends the mail, plus a way to
// prove it works before relying on it.
// ---------------------------------------------------------------------------

function ProviderSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useEmailSettingsQuery();

  const providerMutation = useMutation({
    mutationFn: (provider: "resend" | "brevo" | null) => api.updateEmailSettings({ provider }),
    onSuccess: (result) => {
      queryClient.setQueryData(["email-settings"], result);
      toast.success("Email provider updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update the provider."),
  });

  const testMutation = useMutation({
    mutationFn: api.sendTestEmail,
    onSuccess: (result) => {
      if (result.sent) {
        toast.success(`Test email sent to ${result.to} via ${result.provider}.`);
      } else {
        toast.error(`Test email via ${result.provider} was not accepted. Check the activity log.`);
      }
      queryClient.invalidateQueries({ queryKey: ["email-activity"] });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not send a test email."),
  });

  if (isLoading) {
    return (
      <p className="mt-6 text-sm text-ink-muted">
        <T>Loading email settings...</T>
      </p>
    );
  }
  if (isError || !data) {
    return (
      <EmptyState
        title="Email settings unavailable"
        hint="Requires owner settings access and a connected API."
      />
    );
  }

  return (
    <section className="mt-6 space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">
          <T>Provider</T>
        </h2>
        <p className="max-w-3xl text-sm text-ink-muted">
          <T>
            An admin preference wins only if that provider's API key is actually configured on the
            server -- picking one here can never send mail through a provider with no key set.
          </T>
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill status={data.configuredProviders.resend ? "active" : "disabled"} />
        <span className="text-sm text-ink-muted">
          <T>Resend</T>
        </span>
        <StatusPill status={data.configuredProviders.brevo ? "active" : "disabled"} />
        <span className="text-sm text-ink-muted">
          <T>Brevo</T>
        </span>
        <span className="ml-2 text-sm text-ink-muted">
          <T>Currently sending via</T> <strong className="text-ink">{data.activeProvider}</strong>
        </span>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Preferred provider" htmlFor="email-provider">
          <Select
            id="email-provider"
            value={data.provider ?? "auto"}
            disabled={providerMutation.isPending}
            onChange={(event) => {
              const value = event.target.value;
              providerMutation.mutate(value === "auto" ? null : (value as "resend" | "brevo"));
            }}
            className="w-48"
          >
            <option value="auto">
              <T>Auto (best configured)</T>
            </option>
            <option value="brevo">
              <T>Brevo</T>
            </option>
            <option value="resend">
              <T>Resend</T>
            </option>
          </Select>
        </Field>
        <Button
          type="button"
          variant="secondary"
          disabled={testMutation.isPending}
          onClick={() => testMutation.mutate()}
        >
          <T>{testMutation.isPending ? "Sending..." : "Send test email"}</T>
        </Button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Category toggles: turn a whole kind of email on or off.
// ---------------------------------------------------------------------------

function CategoryTogglesSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useEmailSettingsQuery();

  const toggleMutation = useMutation({
    mutationFn: ({ category, enabled }: { category: string; enabled: boolean }) =>
      api.updateEmailSettings({ categories: { [category]: { enabled } } }),
    onSuccess: (result) => {
      queryClient.setQueryData(["email-settings"], result);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update the category."),
  });

  if (isLoading || isError || !data) return null;

  return (
    <section className="mt-8 space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">
          <T>Categories</T>
        </h2>
        <p className="max-w-3xl text-sm text-ink-muted">
          <T>Untick a kind of email to stop it from sending, without touching anything else.</T>
        </p>
      </div>
      <ul className="divide-y divide-line rounded-md border border-line">
        {Object.entries(data.categories).map(([category, info]) => (
          <li key={category} className="flex flex-wrap items-start gap-3 px-3 py-3">
            <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-2.5">
              <input
                type="checkbox"
                className="mt-1"
                checked={info.enabled}
                disabled={toggleMutation.isPending}
                onChange={(event) =>
                  toggleMutation.mutate({ category, enabled: event.target.checked })
                }
              />
              <span className="min-w-0">
                <span className="block text-sm font-medium text-ink">{info.label}</span>
                <span className="mt-0.5 block text-xs text-ink-muted">{info.description}</span>
                {category === "staff_account" ? (
                  <span className="mt-1 block text-xs font-medium text-warning">
                    <T>
                      Turning this off can block staff self-service password reset -- the recovery
                      path into this very admin panel.
                    </T>
                  </span>
                ) : null}
              </span>
            </label>
            <StatusPill status={info.enabled ? "active" : "disabled"} />
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Rate limits: a global cap, plus optional per-category overrides.
// ---------------------------------------------------------------------------

function RateLimitsSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useEmailSettingsQuery();
  const [globalDraft, setGlobalDraft] = useState<{ hourly: string; daily: string } | null>(null);
  const [categoryDrafts, setCategoryDrafts] = useState<
    Record<string, { hourly: string; daily: string }>
  >({});

  useEffect(() => {
    setGlobalDraft(null);
    setCategoryDrafts({});
  }, [data]);

  const saveGlobalMutation = useMutation({
    mutationFn: (input: { globalHourlyLimit: number; globalDailyLimit: number }) =>
      api.updateEmailSettings(input),
    onSuccess: (result) => {
      queryClient.setQueryData(["email-settings"], result);
      setGlobalDraft(null);
      toast.success("Global rate limit saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the rate limit."),
  });

  const saveCategoryMutation = useMutation({
    mutationFn: ({
      category,
      hourlyLimit,
      dailyLimit,
    }: {
      category: string;
      hourlyLimit: number | null;
      dailyLimit: number | null;
    }) => api.updateEmailSettings({ categories: { [category]: { hourlyLimit, dailyLimit } } }),
    onSuccess: (result, variables) => {
      queryClient.setQueryData(["email-settings"], result);
      setCategoryDrafts((current) => {
        const next = { ...current };
        delete next[variables.category];
        return next;
      });
      toast.success("Category limit saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the category limit."),
  });

  if (isLoading || isError || !data) return null;

  const hourly = globalDraft?.hourly ?? String(data.globalHourlyLimit);
  const daily = globalDraft?.daily ?? String(data.globalDailyLimit);
  const hourlyValid = Number.isInteger(Number(hourly)) && Number(hourly) >= 1;
  const dailyValid = Number.isInteger(Number(daily)) && Number(daily) >= 1;

  return (
    <section className="mt-8 space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">
          <T>Rate limits</T>
        </h2>
        <p className="max-w-3xl text-sm text-ink-muted">
          <T>
            Once a window fills up, further emails in it wait for the next minute's dispatch
            instead of failing outright -- nothing is lost, it just slows down.
          </T>
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Global — per hour" htmlFor="email-limit-hourly">
          <Input
            id="email-limit-hourly"
            type="number"
            min={1}
            value={hourly}
            onChange={(event) =>
              setGlobalDraft({ hourly: event.target.value, daily: globalDraft?.daily ?? daily })
            }
            className="w-32"
          />
        </Field>
        <Field label="Global — per day" htmlFor="email-limit-daily">
          <Input
            id="email-limit-daily"
            type="number"
            min={1}
            value={daily}
            onChange={(event) =>
              setGlobalDraft({ hourly: globalDraft?.hourly ?? hourly, daily: event.target.value })
            }
            className="w-32"
          />
        </Field>
        <Button
          type="button"
          disabled={!globalDraft || !hourlyValid || !dailyValid || saveGlobalMutation.isPending}
          onClick={() =>
            saveGlobalMutation.mutate({
              globalHourlyLimit: Number(hourly),
              globalDailyLimit: Number(daily),
            })
          }
        >
          <T>Save</T>
        </Button>
      </div>

      <details className="rounded-md border border-line">
        <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-ink">
          <T>Per-category overrides</T>
        </summary>
        <div className="space-y-3 border-t border-line p-3">
          <p className="text-xs text-ink-muted">
            <T>Blank means a category has no cap of its own -- the global limit above still applies.</T>
          </p>
          {Object.entries(data.categories).map(([category, info]) => {
            const draft = categoryDrafts[category];
            const hourlyValue = draft?.hourly ?? String(info.hourlyLimit ?? "");
            const dailyValue = draft?.daily ?? String(info.dailyLimit ?? "");
            const isDirty = draft !== undefined;
            return (
              <div key={category} className="flex flex-wrap items-end gap-3 border-t border-line pt-3 first:border-t-0 first:pt-0">
                <span className="min-w-40 flex-1 text-sm text-ink">{info.label}</span>
                <Field label="Per hour" htmlFor={`email-cat-hourly-${category}`}>
                  <Input
                    id={`email-cat-hourly-${category}`}
                    type="number"
                    min={0}
                    placeholder="—"
                    value={hourlyValue}
                    onChange={(event) =>
                      setCategoryDrafts((current) => ({
                        ...current,
                        [category]: { hourly: event.target.value, daily: dailyValue },
                      }))
                    }
                    className="w-24"
                  />
                </Field>
                <Field label="Per day" htmlFor={`email-cat-daily-${category}`}>
                  <Input
                    id={`email-cat-daily-${category}`}
                    type="number"
                    min={0}
                    placeholder="—"
                    value={dailyValue}
                    onChange={(event) =>
                      setCategoryDrafts((current) => ({
                        ...current,
                        [category]: { hourly: hourlyValue, daily: event.target.value },
                      }))
                    }
                    className="w-24"
                  />
                </Field>
                <Button
                  type="button"
                  variant="secondary"
                  className="min-h-9"
                  disabled={!isDirty || saveCategoryMutation.isPending}
                  onClick={() =>
                    saveCategoryMutation.mutate({
                      category,
                      hourlyLimit: hourlyValue.trim() ? Number(hourlyValue) : null,
                      dailyLimit: dailyValue.trim() ? Number(dailyValue) : null,
                    })
                  }
                >
                  <T>Save</T>
                </Button>
              </div>
            );
          })}
        </div>
      </details>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Activity: what actually happened recently, so a toggle or limit change is
// something you can verify rather than take on faith.
// ---------------------------------------------------------------------------

const OUTCOME_LABELS: Record<EmailOutcome, string> = {
  sent: "Sent",
  blocked_disabled: "Blocked (category off)",
  rate_limited: "Rate limited",
  provider_error: "Provider error",
};

function ActivityLogSection() {
  const [outcomeFilter, setOutcomeFilter] = useState<EmailOutcome | "">("");
  const { data: settingsData } = useEmailSettingsQuery();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["email-activity", outcomeFilter],
    queryFn: () => api.emailActivity({ outcome: outcomeFilter || undefined, limit: 50 }),
    refetchInterval: 30_000,
  });

  const summary = data?.summary24h;

  return (
    <section className="mt-8 space-y-4 border-t border-line pt-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-lg text-ink">
            <T>Recent activity</T>
          </h2>
          <p className="max-w-3xl text-sm text-ink-muted">
            <T>What was actually sent, blocked, throttled or rejected.</T>
          </p>
        </div>
        <Select
          aria-label="Filter by outcome"
          value={outcomeFilter}
          onChange={(event) => setOutcomeFilter(event.target.value as EmailOutcome | "")}
          className="w-48"
        >
          <option value="">
            <T>All outcomes</T>
          </option>
          {(Object.keys(OUTCOME_LABELS) as EmailOutcome[]).map((outcome) => (
            <option key={outcome} value={outcome}>
              {OUTCOME_LABELS[outcome]}
            </option>
          ))}
        </Select>
      </div>

      {summary ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(Object.keys(OUTCOME_LABELS) as EmailOutcome[]).map((outcome) => (
            <div key={outcome} className="rounded-md border border-line bg-surface p-3">
              <p className="text-xs text-ink-muted">{OUTCOME_LABELS[outcome]}</p>
              <p className="mt-1 font-display text-2xl text-ink">{summary[outcome]}</p>
              <p className="text-xs text-ink-muted">
                <T>last 24h</T>
              </p>
            </div>
          ))}
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-md border border-line">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-line bg-canvas text-xs uppercase tracking-wide text-ink-muted">
              <th className="px-3 py-2 font-medium">
                <T>Time</T>
              </th>
              <th className="px-3 py-2 font-medium">
                <T>Category</T>
              </th>
              <th className="px-3 py-2 font-medium">
                <T>Provider</T>
              </th>
              <th className="px-3 py-2 font-medium">
                <T>Outcome</T>
              </th>
              <th className="px-3 py-2 font-medium">
                <T>Recipient</T>
              </th>
            </tr>
          </thead>
          {isLoading ? (
            <LoadingRows columns={5} />
          ) : (
            <tbody>
              {isError || !data || data.entries.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-sm text-ink-muted">
                    <T>No email activity yet.</T>
                  </td>
                </tr>
              ) : (
                data.entries.map((entry) => (
                  <tr key={entry.id} className="border-t border-line">
                    <td className="px-3 py-2 text-ink-muted">{formatDateTime(entry.occurredAt)}</td>
                    <td className="px-3 py-2 text-ink">
                      {settingsData?.categories[entry.category]?.label ??
                        entry.category.replaceAll("_", " ")}
                    </td>
                    <td className="px-3 py-2 text-ink-muted">{entry.provider}</td>
                    <td className="px-3 py-2">
                      <StatusPill status={entry.outcome} />
                    </td>
                    <td className="px-3 py-2 text-ink-muted">{entry.recipientDomain ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          )}
        </table>
      </div>
    </section>
  );
}
