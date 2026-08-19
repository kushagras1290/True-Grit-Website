/** A/B testing dashboard: experiment list, lifecycle controls (start / stop /
 * complete), and per-variant statistical results (two-proportion z-test or
 * Welch's t-test, plus mSPRT sequential significance so the "significant"
 * flag stays honest under continuous monitoring -- see
 * services/experiments.py for the stats engine this reads). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";
import {
  ArrowLeft,
  Calendar,
  CheckCircle2,
  LoaderCircle,
  Play,
  StopCircle,
  Users,
} from "lucide-react";

import { ApiError, api, type ExperimentResults } from "../lib/api";
import { Button, DataTableShell, EmptyState, PageHeader, Th, Td } from "../components/ui";
import { useToast } from "../components/toast";
import { T } from "../lib/i18n";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function formatPct(value: number): string {
  return (value * 100).toFixed(1) + "%";
}

const STATUS_PILL_STYLES: Record<string, string> = {
  draft: "border border-line bg-canvas text-ink-muted",
  running: "bg-success/10 text-success",
  completed: "bg-subtle text-brand",
  stopped: "bg-danger/10 text-danger",
};

function ExperimentStatusPill({ status }: { status: string }) {
  return (
    <span
      className={
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize " +
        (STATUS_PILL_STYLES[status] ?? "border border-line bg-canvas text-ink-muted")
      }
    >
      {status}
    </span>
  );
}

function Pill({ tone, children }: { tone: "neutral" | "success"; children: React.ReactNode }) {
  return (
    <span
      className={
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium " +
        (tone === "success"
          ? "bg-success/10 text-success"
          : "border border-line bg-canvas text-ink-muted")
      }
    >
      {children}
    </span>
  );
}

export function ExperimentsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["experiments"],
    queryFn: api.experiments,
  });

  if (isLoading) {
    return (
      <div className="flex justify-center p-12">
        <LoaderCircle className="text-brand animate-spin-slow" size={32} />
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState title="Failed to load experiments" hint={errorMessage(error, "Unknown error")} />
    );
  }

  const experiments = data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="A/B Experiments"
        description="Statistically rigorous sequential testing for product features and growth."
        actions={
          <Button disabled title="Creating experiments from the admin panel is not available yet.">
            <T>New Experiment</T>
          </Button>
        }
      />

      {experiments.length === 0 ? (
        <EmptyState
          title="No experiments"
          hint="Experiments are currently created from the database; the admin panel does not yet have a creation form."
        />
      ) : (
        <DataTableShell>
          <table className="w-full text-left text-sm">
            <thead>
              <tr>
                <Th>
                  <T>Experiment</T>
                </Th>
                <Th>
                  <T>Status</T>
                </Th>
                <Th>
                  <T>Metric</T>
                </Th>
                <Th>
                  <T>Traffic Allocation</T>
                </Th>
                <Th>
                  <T>Started At</T>
                </Th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((experiment) => (
                <tr key={experiment.id} className="border-t border-line">
                  <Td>
                    <Link
                      to={`/experiments/${experiment.id}`}
                      className="font-medium text-brand hover:underline"
                    >
                      {experiment.name}
                    </Link>
                    <div className="text-sm text-ink-muted">{experiment.key}</div>
                  </Td>
                  <Td>
                    <ExperimentStatusPill status={experiment.status} />
                  </Td>
                  <Td>
                    {experiment.primaryMetric === "conversion" ? (
                      <T>Conversion rate</T>
                    ) : (
                      <T>Continuous (e.g. AOV)</T>
                    )}
                  </Td>
                  <Td>{experiment.allocationPct}%</Td>
                  <Td className="text-ink-muted">
                    {experiment.startedAt
                      ? new Date(experiment.startedAt).toLocaleDateString()
                      : "—"}
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </DataTableShell>
      )}
    </div>
  );
}

export function ExperimentDetailView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<ExperimentResults>({
    queryKey: ["experiment", id],
    queryFn: () => api.experimentResults(id!),
    refetchInterval: (query) =>
      query.state.data?.experiment.status === "running" ? 10_000 : false,
  });

  const updateStatus = useMutation({
    mutationFn: (status: "running" | "completed" | "stopped") =>
      api.setExperimentStatus(id!, status),
    onSuccess: (updated) => {
      toast.success(`Experiment ${updated.status}.`);
      queryClient.invalidateQueries({ queryKey: ["experiment", id] });
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
    },
    onError: (mutationError) =>
      toast.error(errorMessage(mutationError, "Could not update the experiment's status.")),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center p-12">
        <LoaderCircle className="text-brand animate-spin-slow" size={32} />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-6">
        <button
          type="button"
          onClick={() => navigate("/experiments")}
          className="-ml-1 flex items-center gap-1.5 rounded-sm px-2 py-1 text-sm text-ink-muted hover:bg-canvas"
        >
          <ArrowLeft size={16} />
          <T>Back to Experiments</T>
        </button>
        <EmptyState title="Failed to load experiment" hint={errorMessage(error, "Unknown error")} />
      </div>
    );
  }

  const { experiment, variants, comparisons } = data;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => navigate("/experiments")}
          aria-label="Back to experiments"
          className="flex h-8 w-8 items-center justify-center rounded-sm text-ink-muted hover:bg-canvas"
        >
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="font-display text-2xl text-ink">{experiment.name}</h1>
            <ExperimentStatusPill status={experiment.status} />
          </div>
          <p className="text-sm text-ink-muted">{experiment.key}</p>
        </div>
        <div className="flex items-center gap-2">
          {experiment.status === "draft" ? (
            <Button
              onClick={() => updateStatus.mutate("running")}
              disabled={updateStatus.isPending}
            >
              <Play size={16} />
              <T>Start Experiment</T>
            </Button>
          ) : null}
          {experiment.status === "running" ? (
            <>
              <Button
                variant="secondary"
                onClick={() => updateStatus.mutate("stopped")}
                disabled={updateStatus.isPending}
              >
                <StopCircle size={16} />
                <T>Stop</T>
              </Button>
              <Button
                onClick={() => updateStatus.mutate("completed")}
                disabled={updateStatus.isPending}
              >
                <CheckCircle2 size={16} />
                <T>Complete</T>
              </Button>
            </>
          ) : null}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-md border border-line bg-surface p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium text-ink-muted">
            <Users size={15} />
            <T>Total Traffic</T>
          </h3>
          <p className="mt-2 text-2xl font-semibold text-ink">
            {data.totalExposures.toLocaleString()}
          </p>
        </div>
        <div className="rounded-md border border-line bg-surface p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium text-ink-muted">
            <CheckCircle2 size={15} />
            <T>Total Conversions</T>
          </h3>
          <p className="mt-2 text-2xl font-semibold text-ink">
            {data.totalConversions.toLocaleString()}
          </p>
        </div>
        <div className="rounded-md border border-line bg-surface p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium text-ink-muted">
            <Calendar size={15} />
            <T>Started At</T>
          </h3>
          <p className="mt-2 text-lg font-medium text-ink">
            {experiment.startedAt ? (
              new Date(experiment.startedAt).toLocaleString()
            ) : (
              <T>Not started</T>
            )}
          </p>
        </div>
      </div>

      <div className="rounded-md border border-line bg-surface">
        <div className="border-b border-line px-4 py-3">
          <h2 className="font-display text-base text-ink">
            <T>Variant Performance</T>
          </h2>
        </div>
        <DataTableShell>
          <table className="w-full text-left text-sm">
            <thead>
              <tr>
                <Th>
                  <T>Variant</T>
                </Th>
                <Th className="text-right">
                  <T>Exposures</T>
                </Th>
                <Th className="text-right">
                  <T>Conversions</T>
                </Th>
                <Th className="text-right">
                  <T>Conv. Rate</T>
                </Th>
                <Th className="text-right">
                  <T>Value (Mean)</T>
                </Th>
              </tr>
            </thead>
            <tbody>
              {variants.map((variant) => (
                <tr key={variant.key} className="border-t border-line">
                  <Td className="font-medium text-ink">
                    {variant.name}
                    {variant.key === "control" ? (
                      <span className="ml-2">
                        <Pill tone="neutral">
                          <T>Control</T>
                        </Pill>
                      </span>
                    ) : null}
                  </Td>
                  <Td className="text-right text-ink-muted">
                    {variant.exposures.toLocaleString()}
                  </Td>
                  <Td className="text-right text-ink-muted">
                    {variant.conversions.toLocaleString()}
                  </Td>
                  <Td className="text-right font-medium text-ink">
                    {variant.exposures > 0 ? formatPct(variant.conversionRate) : "0.0%"}
                  </Td>
                  <Td className="text-right text-ink-muted">
                    {variant.exposures > 0 ? (variant.meanValue / 100).toFixed(2) : "0.00"}
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </DataTableShell>
      </div>

      {comparisons.length > 0 ? (
        <div className="rounded-md border border-line bg-surface">
          <div className="border-b border-line px-4 py-3">
            <h2 className="font-display text-base text-ink">
              <T>Statistical Significance (mSPRT)</T>
            </h2>
            <p className="mt-1 text-sm text-ink-muted">
              <T>
                Sequential testing allows continuous monitoring without p-hacking. Results are valid
                at any time.
              </T>
            </p>
          </div>
          <div className="space-y-6 p-4">
            {comparisons.map((comparison) => (
              <div key={comparison.treatmentKey} className="space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="font-display text-base text-ink">
                      <T>Control vs</T> {comparison.treatmentName}
                    </h3>
                    <div className="mt-1 flex items-center gap-2 text-sm text-ink-muted">
                      {comparison.isSignificant ? (
                        <Pill tone="success">
                          <T>Statistically Significant</T>
                        </Pill>
                      ) : (
                        <Pill tone="neutral">
                          <T>Not Significant (Yet)</T>
                        </Pill>
                      )}
                      <span>
                        <T>p =</T> {comparison.msprtPValue.toExponential(2)}
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-semibold text-ink">
                      {comparison.relativeEffect > 0 ? "+" : ""}
                      {formatPct(comparison.relativeEffect)}
                    </div>
                    <div className="text-sm text-ink-muted">
                      <T>Relative Effect</T>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 rounded-sm bg-canvas p-3 text-sm">
                  <div>
                    <span className="text-ink-muted">
                      <T>Power Achieved:</T>
                    </span>{" "}
                    <span className="font-medium text-ink">
                      {formatPct(comparison.powerAchieved)}
                    </span>
                  </div>
                  <div>
                    <span className="text-ink-muted">
                      <T>Required Sample:</T>
                    </span>{" "}
                    <span className="font-medium text-ink">
                      {comparison.requiredSamplePerVariant?.toLocaleString() ?? <T>N/A</T>}{" "}
                      <T>/ variant</T>
                    </span>
                  </div>
                  <div>
                    <span className="text-ink-muted">
                      <T>mSPRT Test Stat:</T>
                    </span>{" "}
                    <span className="font-medium text-ink">{comparison.msprtStat.toFixed(4)}</span>
                  </div>
                  <div>
                    <span className="text-ink-muted">
                      <T>95% CI:</T>
                    </span>{" "}
                    <span className="font-medium text-ink">
                      [{formatPct(comparison.ciLower)}, {formatPct(comparison.ciUpper)}]
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
