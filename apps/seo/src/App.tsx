/**
 * SEO agent dashboard.
 *
 * The point of this app is the Proposals tab: everything the crawler and the
 * keyword-gap comparison found gets turned into concrete field changes
 * (`apps/seo/worker/proposals.ts`), and this is where a staff member reviews
 * and applies them with one click, instead of opening each product and typing
 * a title by hand. Findings, keywords and content gaps are the evidence;
 * Proposals is the action.
 *
 * Authentication rides the same staff session cookie as every other admin
 * surface (`api.ts`'s `credentials: "include"`) — this app holds no
 * credentials of its own, and every route it calls is gated server-side on
 * `seo.manage` regardless of what this UI shows or hides.
 */

import { cn } from "@truegrit/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  ExternalLink,
  Filter,
  Globe,
  Layers,
  ListChecks,
  Loader2,
  LockKeyhole,
  LogOut,
  Mail,
  Play,
  Plus,
  RefreshCw,
  Search,
  Shield,
  Sparkles,
  Trash2,
  Undo2,
  UserCog,
  Users,
  X,
  XCircle,
} from "lucide-react";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";

import {
  ApiError,
  seoApi,
  type AdminRole,
  type AdminUser,
  type Competitor,
  type ContentGap,
  type Finding,
  type FindingCategory,
  type FindingStatus,
  type KeywordGap,
  type Proposal,
  type StaffUser,
  type UserStatus,
} from "./api";

/* ─── Constants ────────────────────────────────────────────────────── */

type TabKey = "proposals" | "findings" | "keywords" | "content" | "competitors" | "users";

const NAV_ITEMS: Array<{ key: TabKey; label: string; icon: ReactNode }> = [
  { key: "proposals", label: "Proposals", icon: <Sparkles size={16} /> },
  { key: "findings", label: "Findings", icon: <ListChecks size={16} /> },
  { key: "keywords", label: "Keywords", icon: <Search size={16} /> },
  { key: "content", label: "Content gaps", icon: <Layers size={16} /> },
  { key: "competitors", label: "Competitors", icon: <Globe size={16} /> },
  { key: "users", label: "Users", icon: <Users size={16} /> },
];

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-danger/10 text-danger",
  high: "bg-warning/10 text-warning",
  medium: "bg-accent/10 text-accent",
  low: "border border-line bg-canvas text-ink-muted",
};

const CATEGORY_LABELS: Record<FindingCategory, string> = {
  schema: "Schema",
  eeat: "E-E-A-T",
  links: "Links",
  indexing: "Indexing",
  content: "Content",
};

const FIELD_LABELS: Record<Proposal["field"], string> = {
  seo_title: "SEO title",
  seo_description: "Meta description",
  seo_keywords: "Keywords",
  indexing_policy: "Indexing",
};

/* ─── Helpers ──────────────────────────────────────────────────────── */

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function relativeAge(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const days = Math.floor(ms / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "1 day";
  if (days < 30) return `${days} days`;
  const months = Math.floor(days / 30);
  return `${months} month${months === 1 ? "" : "s"}`;
}

function TrueGritMark({ className }: { className?: string }) {
  return (
    <img
      src="/favicon.png"
      alt=""
      aria-hidden="true"
      className={cn("h-6 w-6 object-contain", className)}
    />
  );
}

/* ─── Shared UI atoms ──────────────────────────────────────────────── */

function Button({
  variant = "secondary",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "destructive" | "ghost";
}) {
  const styles = {
    primary: "bg-brand text-ink-inverse hover:opacity-90",
    secondary: "border border-line-strong bg-surface text-ink hover:bg-subtle/50",
    destructive: "bg-danger text-ink-inverse hover:opacity-90",
    ghost: "text-ink-muted hover:bg-subtle/60 hover:text-ink",
  } as const;
  return (
    <button
      className={cn(
        "inline-flex min-h-9 items-center justify-center gap-2 rounded-sm px-3.5 text-sm font-medium",
        "transition-opacity duration-150 disabled:cursor-not-allowed disabled:opacity-50",
        styles[variant],
        className,
      )}
      {...props}
    />
  );
}

function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "min-h-9 w-full rounded-sm border border-line-strong bg-surface px-3 text-sm text-ink",
        "placeholder:text-ink-muted",
        className,
      )}
      {...props}
    />
  );
}

function PasswordInput({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input type={visible ? "text" : "password"} className={cn("pr-9", className)} {...props} />
      <button
        type="button"
        onClick={() => setVisible((value) => !value)}
        className="absolute inset-y-0 right-0 flex items-center px-2.5 text-ink-muted hover:text-ink"
        aria-label={visible ? "Hide password" : "Show password"}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-ink">
        {label}
      </label>
      {children}
    </div>
  );
}

function Pill({ tone = "neutral", children }: { tone?: string; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
        SEVERITY_STYLES[tone] ?? "bg-subtle text-ink-muted",
      )}
    >
      {children}
    </span>
  );
}

function EmptyState({ title, hint, icon }: { title: string; hint?: string; icon?: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-line-strong bg-surface px-6 py-14 text-center">
      {icon ? <div className="mx-auto mb-3 flex justify-center text-ink-muted">{icon}</div> : null}
      <p className="font-medium text-ink">{title}</p>
      {hint ? <p className="mt-1 text-sm text-ink-muted">{hint}</p> : null}
    </div>
  );
}

function Spinner() {
  return (
    <div className="flex justify-center py-14 text-ink-muted">
      <Loader2 size={22} className="animate-spin-slow" />
    </div>
  );
}

/* ─── Login ────────────────────────────────────────────────────────── */

function Login({ onAuthenticated }: { onAuthenticated: (user: StaffUser) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useMutation({
    mutationFn: () => seoApi.login(email, password),
    onSuccess: async () => onAuthenticated(await seoApi.me()),
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate();
  }
  return (
    <main className="grid min-h-screen grid-cols-1 bg-canvas lg:grid-cols-[minmax(0,1fr)_28rem]">
      <section className="flex min-h-[16rem] items-end bg-brand px-6 py-10 text-ink-inverse lg:min-h-screen lg:px-12">
        <div className="max-w-xl">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-ink-inverse/15">
              <TrueGritMark />
            </span>
            <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-75">
              True Grit SEO Agent
            </p>
          </div>
          <h1 className="mt-4 font-display text-4xl leading-tight lg:text-5xl">
            Find what's broken. Fix it in one click.
          </h1>
          <p className="mt-4 max-w-md text-sm opacity-80">
            Crawls the storefront and its competitors, turns what it finds into concrete field
            changes, and applies them to the catalogue directly — nothing here is a PDF report
            somebody has to act on later.
          </p>
        </div>
      </section>
      <section className="flex items-center px-6 py-10">
        <div className="w-full">
          <div className="mb-8 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-sm bg-subtle text-brand">
              <TrueGritMark />
            </span>
            <div>
              <h2 className="font-display text-2xl text-ink">Staff sign in</h2>
              <p className="text-sm text-ink-muted">Requires the seo.manage permission</p>
            </div>
          </div>
          <form className="space-y-4" onSubmit={submit}>
            <Field label="Staff email" htmlFor="email">
              <Input
                id="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>
            <Field label="Password" htmlFor="password">
              <PasswordInput
                id="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </Field>
            {login.isError ? (
              <p role="alert" className="text-sm text-danger">
                {errorMessage(login.error, "Sign in failed.")}
              </p>
            ) : null}
            <Button type="submit" variant="primary" className="w-full" disabled={login.isPending}>
              {login.isPending ? (
                <Loader2 size={16} className="animate-spin-slow" />
              ) : (
                <LockKeyhole size={16} />
              )}
              {login.isPending ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </div>
      </section>
    </main>
  );
}

/* ─── Header ───────────────────────────────────────────────────────── */

const SCHEDULE_OPTIONS: { value: number; label: string }[] = [
  { value: 1, label: "Daily" },
  { value: 3, label: "Every 3 days" },
  { value: 7, label: "Weekly" },
  { value: 0, label: "Manual only" },
];

function Header({ user, onLogout }: { user: StaffUser; onLogout: () => void }) {
  const queryClient = useQueryClient();
  const { data: summary } = useQuery({
    queryKey: ["seo-summary"],
    queryFn: seoApi.summary,
    // Live-updates crawl progress instead of leaving "Crawling..." blank
    // until the user manually refreshes -- only polls while something is
    // actually in flight, so an idle dashboard costs nothing extra.
    refetchInterval: (query) => {
      const latest = query.state.data?.runs[0];
      const inFlight = latest?.status === "queued" || latest?.status === "running";
      return inFlight ? 4_000 : false;
    },
  });

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => seoApi.setEnabled(enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["seo-summary"] }),
  });
  const setSchedule = useMutation({
    mutationFn: (scheduleDays: number) => seoApi.setScheduleDays(scheduleDays),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["seo-summary"] }),
  });
  const queueRun = useMutation({
    mutationFn: seoApi.queueRun,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["seo-summary"] }),
  });

  const latestRun = summary?.runs[0];
  const runInFlight = latestRun?.status === "queued" || latestRun?.status === "running";
  const progressLabel =
    latestRun?.status === "running"
      ? latestRun.pagesDiscovered > 0
        ? `Crawling… ${latestRun.pagesCrawled}/${latestRun.pagesDiscovered} pages`
        : "Crawling… discovering pages"
      : "Queued";

  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand text-ink-inverse">
            <TrueGritMark className="h-5 w-5" />
          </span>
          <div>
            <p className="font-display text-lg text-ink">SEO Agent</p>
            <p className="text-xs text-ink-muted">
              {summary?.settings.enabled ? (
                <span className="text-success">Active</span>
              ) : (
                <span className="text-ink-muted">Switched off</span>
              )}
              {latestRun
                ? ` · last run ${formatDate(latestRun.finishedAt ?? latestRun.queuedAt)}`
                : ""}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-ink-muted">
            Auto-run
            <select
              className="rounded-sm border border-line-strong bg-surface px-1.5 py-1 text-xs text-ink"
              value={summary?.settings.scheduleDays ?? 1}
              disabled={setSchedule.isPending}
              onChange={(event) => setSchedule.mutate(Number(event.target.value))}
            >
              {SCHEDULE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <Button
            variant={summary?.settings.enabled ? "secondary" : "primary"}
            onClick={() => toggle.mutate(!summary?.settings.enabled)}
            disabled={toggle.isPending}
          >
            {summary?.settings.enabled ? "Turn off" : "Turn on"}
          </Button>
          <Button
            variant="secondary"
            disabled={!summary?.settings.enabled || runInFlight || queueRun.isPending}
            onClick={() => queueRun.mutate()}
          >
            {runInFlight ? <Loader2 size={15} className="animate-spin-slow" /> : <Play size={15} />}
            {runInFlight ? progressLabel : "Run crawl"}
          </Button>
          <div className="mx-1 h-6 w-px bg-line" />
          <div className="text-right text-xs">
            <p className="font-medium text-ink">{user.displayName}</p>
            <p className="text-ink-muted">{user.email}</p>
          </div>
          <Button variant="ghost" onClick={onLogout} aria-label="Sign out">
            <LogOut size={16} />
          </Button>
        </div>
      </div>
      {latestRun?.status === "running" && latestRun.pagesDiscovered > 0 ? (
        <div className="border-t border-line bg-canvas px-6 py-2">
          <div className="flex items-center justify-between text-xs text-ink-muted">
            <span>{progressLabel}</span>
            <span>
              {Math.min(
                100,
                Math.round((latestRun.pagesCrawled / latestRun.pagesDiscovered) * 100),
              )}
              %
            </span>
          </div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-line">
            <div
              className="h-full rounded-full bg-brand transition-[width]"
              style={{
                width: `${Math.min(100, Math.round((latestRun.pagesCrawled / latestRun.pagesDiscovered) * 100))}%`,
              }}
            />
          </div>
        </div>
      ) : null}
      {latestRun?.status === "failed" ? (
        <div className="border-t border-danger/20 bg-danger/5 px-6 py-2 text-xs text-danger">
          <AlertTriangle size={13} className="mr-1 inline" />
          The last crawl failed: {latestRun.error ?? "unknown error"}
        </div>
      ) : null}
    </header>
  );
}

function SummaryStrip() {
  const { data: summary } = useQuery({ queryKey: ["seo-summary"], queryFn: seoApi.summary });
  if (!summary) return null;
  const cells: Array<{ label: string; value: number; tone?: string }> = [
    { label: "Critical", value: summary.counts.openBySeverity.critical ?? 0, tone: "critical" },
    { label: "High", value: summary.counts.openBySeverity.high ?? 0, tone: "high" },
    { label: "Medium", value: summary.counts.openBySeverity.medium ?? 0, tone: "medium" },
    { label: "Low", value: summary.counts.openBySeverity.low ?? 0, tone: "low" },
  ];
  return (
    <div className="mx-auto grid max-w-6xl grid-cols-2 gap-3 px-6 pt-6 sm:grid-cols-3 lg:grid-cols-6">
      {cells.map((cell) => (
        <div key={cell.label} className="rounded-md border border-line bg-surface p-3">
          <p className="text-2xl font-semibold text-ink">{cell.value}</p>
          <p className="text-xs text-ink-muted">{cell.label} findings</p>
        </div>
      ))}
      <div className="rounded-md border border-line bg-surface p-3">
        <p className="text-2xl font-semibold text-brand">{summary.counts.pendingProposals}</p>
        <p className="text-xs text-ink-muted">Ready to apply</p>
      </div>
      <div className="rounded-md border border-line bg-surface p-3">
        <p className="text-2xl font-semibold text-success">{summary.counts.appliedProposals}</p>
        <p className="text-xs text-ink-muted">Applied so far</p>
      </div>
    </div>
  );
}

/* ─── Proposals: the one-click surface ─────────────────────────────── */

function ProposalRow({
  proposal,
  selected,
  onToggle,
  onApply,
  onReject,
  busy,
}: {
  proposal: Proposal;
  selected: boolean;
  onToggle: () => void;
  onApply: () => void;
  onReject: () => void;
  busy: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li className="border-t border-line first:border-t-0">
      <div className="flex items-start gap-3 px-4 py-3">
        <input
          type="checkbox"
          className="mt-1.5 h-4 w-4 shrink-0"
          checked={selected}
          onChange={onToggle}
          aria-label={`Select proposal for ${proposal.entityLabel}`}
        />
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="mt-1 shrink-0 text-ink-muted hover:text-ink"
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-medium text-ink">{proposal.entityLabel}</p>
            <Pill tone="low">{FIELD_LABELS[proposal.field]}</Pill>
            <span className="text-xs text-ink-muted">
              {Math.round(proposal.confidence * 100)}% confidence
            </span>
            {proposal.source === "gap" ? (
              <span className="inline-flex items-center gap-1 text-xs text-accent">
                <Search size={11} /> from keyword gap
              </span>
            ) : null}
          </div>
          <a
            href={proposal.path}
            target="_blank"
            rel="noreferrer"
            className="mt-0.5 inline-flex items-center gap-1 text-xs text-ink-muted hover:text-brand"
          >
            {proposal.path} <ExternalLink size={11} />
          </a>
          <p className="mt-1.5 text-sm text-ink">{proposal.proposedValue}</p>
          {expanded ? (
            <div className="mt-3 space-y-2 rounded-sm bg-canvas p-3 text-sm">
              <div>
                <p className="text-xs font-medium text-ink-muted">Before</p>
                <p className={cn("text-ink", !proposal.currentValue && "italic text-ink-muted")}>
                  {proposal.currentValue || "(empty)"}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">After</p>
                <p className="text-ink">{proposal.proposedValue}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">Why</p>
                <p className="text-ink-muted">{proposal.rationale}</p>
              </div>
            </div>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <Button variant="primary" className="px-2.5" onClick={onApply} disabled={busy}>
            <Check size={14} />
          </Button>
          <Button variant="ghost" className="px-2.5" onClick={onReject} disabled={busy}>
            <X size={14} />
          </Button>
        </div>
      </div>
    </li>
  );
}

function AppliedRow({
  proposal,
  onRevert,
  busy,
}: {
  proposal: Proposal;
  onRevert: () => void;
  busy: boolean;
}) {
  return (
    <li className="flex items-center justify-between gap-3 border-t border-line px-4 py-2.5 first:border-t-0">
      <div className="min-w-0">
        <p className="truncate text-sm text-ink">
          {proposal.entityLabel}{" "}
          <span className="text-ink-muted">· {FIELD_LABELS[proposal.field]}</span>
        </p>
        <p className="text-xs text-ink-muted">Applied {formatDate(proposal.appliedAt)}</p>
      </div>
      <Button variant="ghost" onClick={onRevert} disabled={busy}>
        <Undo2 size={14} /> Revert
      </Button>
    </li>
  );
}

function ProposalsTab() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [showApplied, setShowApplied] = useState(false);

  const { data: pending, isLoading } = useQuery({
    queryKey: ["seo-proposals", "pending"],
    queryFn: () => seoApi.proposals("pending"),
  });
  const { data: applied } = useQuery({
    queryKey: ["seo-proposals", "applied"],
    queryFn: () => seoApi.proposals("applied", 50),
    enabled: showApplied,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["seo-proposals"] });
    queryClient.invalidateQueries({ queryKey: ["seo-summary"] });
  };

  const applyOne = useMutation({ mutationFn: seoApi.applyProposal, onSuccess: invalidate });
  const rejectOne = useMutation({ mutationFn: seoApi.rejectProposal, onSuccess: invalidate });
  const revertOne = useMutation({ mutationFn: seoApi.revertProposal, onSuccess: invalidate });
  const applyAll = useMutation({
    mutationFn: (ids?: string[]) => seoApi.applyAll(ids),
    onSuccess: () => {
      setSelected(new Set());
      invalidate();
    },
  });

  const items = pending?.items ?? [];
  const allSelected = items.length > 0 && items.every((item) => selected.has(item.id));

  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(items.map((item) => item.id)));
  }
  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (isLoading) return <Spinner />;

  return (
    <div className="space-y-6">
      <div className="rounded-md border border-line bg-surface">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              disabled={items.length === 0}
              aria-label="Select all"
            />
            <p className="text-sm text-ink-muted">
              {selected.size > 0
                ? `${selected.size} selected`
                : `${items.length} change${items.length === 1 ? "" : "s"} ready to apply`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {selected.size > 0 ? (
              <Button
                variant="secondary"
                disabled={applyAll.isPending}
                onClick={() => applyAll.mutate([...selected])}
              >
                Apply selected ({selected.size})
              </Button>
            ) : null}
            <Button
              variant="primary"
              disabled={items.length === 0 || applyAll.isPending}
              onClick={() => applyAll.mutate(undefined)}
            >
              {applyAll.isPending ? (
                <Loader2 size={15} className="animate-spin-slow" />
              ) : (
                <Sparkles size={15} />
              )}
              Apply all {items.length > 0 ? `(${items.length})` : ""}
            </Button>
          </div>
        </div>

        {applyAll.data && applyAll.data.failed.length > 0 ? (
          <div className="border-b border-warning/30 bg-warning/5 px-4 py-2 text-xs text-warning">
            Applied {applyAll.data.applied} of {applyAll.data.attempted}.{" "}
            {applyAll.data.failed.length} could not be applied (likely deleted since the crawl) —
            see console for detail.
          </div>
        ) : null}

        {items.length === 0 ? (
          <EmptyState
            icon={<CheckCircle2 size={28} />}
            title="Nothing waiting"
            hint="Run a crawl, or check back after the next scheduled one. Every finding the crawl can turn into a concrete change shows up here."
          />
        ) : (
          <ul>
            {items.map((proposal) => (
              <ProposalRow
                key={proposal.id}
                proposal={proposal}
                selected={selected.has(proposal.id)}
                onToggle={() => toggleOne(proposal.id)}
                onApply={() => applyOne.mutate(proposal.id)}
                onReject={() => rejectOne.mutate(proposal.id)}
                busy={applyOne.isPending || rejectOne.isPending || applyAll.isPending}
              />
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-md border border-line bg-surface">
        <button
          type="button"
          onClick={() => setShowApplied((value) => !value)}
          className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-ink"
        >
          Recently applied
          {showApplied ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
        </button>
        {showApplied ? (
          (applied?.items.length ?? 0) === 0 ? (
            <p className="border-t border-line px-4 py-6 text-center text-sm text-ink-muted">
              Nothing applied yet.
            </p>
          ) : (
            <ul>
              {applied!.items.map((proposal) => (
                <AppliedRow
                  key={proposal.id}
                  proposal={proposal}
                  onRevert={() => revertOne.mutate(proposal.id)}
                  busy={revertOne.isPending}
                />
              ))}
            </ul>
          )
        ) : null}
      </div>
    </div>
  );
}

/* ─── Findings ─────────────────────────────────────────────────────── */

function FindingRow({
  finding,
  onStatus,
}: {
  finding: Finding;
  onStatus: (status: FindingStatus) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li className="border-t border-line px-4 py-3 first:border-t-0">
      <div className="flex items-start gap-3">
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="mt-0.5 shrink-0 text-ink-muted hover:text-ink"
        >
          {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone={finding.severity}>{finding.severity}</Pill>
            <Pill tone="low">{CATEGORY_LABELS[finding.category]}</Pill>
            <p className="text-sm font-medium text-ink">{finding.summary}</p>
          </div>
          <p className="mt-0.5 text-xs text-ink-muted">
            {finding.path} · open {relativeAge(finding.firstSeenAt)}
          </p>
          {expanded ? (
            <div className="mt-2 space-y-2 rounded-sm bg-canvas p-3 text-sm">
              <p className="text-ink-muted">{finding.detail}</p>
              <p className="text-ink">
                <span className="font-medium">Fix: </span>
                {finding.fixHint}
              </p>
            </div>
          ) : null}
        </div>
        <div className="flex shrink-0 gap-1.5">
          <Button variant="ghost" className="px-2 text-xs" onClick={() => onStatus("ignored")}>
            Ignore
          </Button>
          <Button variant="ghost" className="px-2 text-xs" onClick={() => onStatus("fixed")}>
            Mark fixed
          </Button>
        </div>
      </div>
    </li>
  );
}

function FindingsTab() {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState<FindingCategory | "">("");

  const { data, isLoading } = useQuery({
    queryKey: ["seo-findings", category],
    queryFn: () => seoApi.findings({ category: category || undefined, limit: 150 }),
  });
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: FindingStatus }) =>
      seoApi.setFindingStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["seo-findings"] });
      queryClient.invalidateQueries({ queryKey: ["seo-summary"] });
    },
  });

  return (
    <div className="rounded-md border border-line bg-surface">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
        <Filter size={14} className="text-ink-muted" />
        <button
          type="button"
          onClick={() => setCategory("")}
          className={cn(
            "rounded-full px-3 py-1 text-xs font-medium",
            category === "" ? "bg-brand text-ink-inverse" : "bg-subtle text-ink-muted",
          )}
        >
          All
        </button>
        {(Object.keys(CATEGORY_LABELS) as FindingCategory[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setCategory(key)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium",
              category === key ? "bg-brand text-ink-inverse" : "bg-subtle text-ink-muted",
            )}
          >
            {CATEGORY_LABELS[key]}
          </button>
        ))}
      </div>
      {isLoading ? (
        <Spinner />
      ) : (data?.items.length ?? 0) === 0 ? (
        <EmptyState
          icon={<CheckCircle2 size={28} />}
          title="No open findings"
          hint="Either nothing is wrong, or a crawl has not run yet."
        />
      ) : (
        <ul>
          {data!.items.map((finding) => (
            <FindingRow
              key={finding.id}
              finding={finding}
              onStatus={(status) => setStatus.mutate({ id: finding.id, status })}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

/* ─── Keywords ─────────────────────────────────────────────────────── */

function KeywordsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["seo-keywords"],
    queryFn: () => seoApi.keywords(150),
  });
  return (
    <div className="space-y-4">
      <div className="rounded-md border border-accent/30 bg-accent/5 px-4 py-3 text-sm text-ink">
        <p className="font-medium">What this measures</p>
        <p className="mt-1 text-ink-muted">
          These are phrases competitors put in their titles and headings more than we do — a real
          signal of where they are investing editorially. This is <strong>not</strong> a ranking or
          a search volume: neither is visible for a site we do not own. Treat a high gap score as a
          research prompt, not proof anyone searches for it.
        </p>
      </div>
      <div className="overflow-x-auto rounded-md border border-line bg-surface">
        {isLoading ? (
          <Spinner />
        ) : (data?.length ?? 0) === 0 ? (
          <EmptyState
            icon={<Search size={28} />}
            title="No gaps yet"
            hint="Add a competitor and run a crawl to compare title and heading usage."
          />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-ink-muted">
                <th className="px-4 py-2 font-medium">Term</th>
                <th className="px-4 py-2 font-medium">Gap score</th>
                <th className="px-4 py-2 font-medium">Their pages</th>
                <th className="px-4 py-2 font-medium">Their competitors</th>
                <th className="px-4 py-2 font-medium">Our pages</th>
              </tr>
            </thead>
            <tbody>
              {data!.map((row) => (
                <tr key={row.term} className="border-b border-line last:border-b-0">
                  <td className="px-4 py-2 font-medium text-ink">{row.term}</td>
                  <td className="px-4 py-2 text-ink">{row.gapScore.toFixed(1)}</td>
                  <td className="px-4 py-2 text-ink-muted">
                    {row.competitorPages} ({row.competitorTitleHits} in titles)
                  </td>
                  <td className="px-4 py-2 text-ink-muted">{row.competitorCount}</td>
                  <td className="px-4 py-2 text-ink-muted">{row.ownPages}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* ─── Content gaps ─────────────────────────────────────────────────── */

function ContentGapsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["seo-content-gaps"],
    queryFn: () => seoApi.contentGaps(80),
  });
  return (
    <div className="overflow-x-auto rounded-md border border-line bg-surface">
      {isLoading ? (
        <Spinner />
      ) : (data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={<Layers size={28} />}
          title="No content gaps found"
          hint="This compares section headings (FAQs, storage, sourcing…) competitors use that we have nowhere on the equivalent page type."
        />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-ink-muted">
              <th className="px-4 py-2 font-medium">Section</th>
              <th className="px-4 py-2 font-medium">Page type</th>
              <th className="px-4 py-2 font-medium">Competitors with it</th>
            </tr>
          </thead>
          <tbody>
            {data!.map((row) => (
              <tr
                key={`${row.pageType}:${row.headingKey}`}
                className="border-b border-line last:border-b-0"
              >
                <td className="px-4 py-2 font-medium text-ink">{row.heading}</td>
                <td className="px-4 py-2 text-ink-muted capitalize">{row.pageType}</td>
                <td className="px-4 py-2 text-ink-muted">{row.competitorCount}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/* ─── Competitors ──────────────────────────────────────────────────── */

function CompetitorsTab() {
  const queryClient = useQueryClient();
  const [label, setLabel] = useState("");
  const [origin, setOrigin] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["seo-competitors"],
    queryFn: seoApi.competitors,
  });
  const add = useMutation({
    mutationFn: () => seoApi.addCompetitor(label, origin),
    onSuccess: () => {
      setLabel("");
      setOrigin("");
      queryClient.invalidateQueries({ queryKey: ["seo-competitors"] });
    },
  });
  const remove = useMutation({
    mutationFn: seoApi.removeCompetitor,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["seo-competitors"] }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (label.trim() && origin.trim()) add.mutate();
  }

  return (
    <div className="space-y-4">
      <form
        onSubmit={submit}
        className="flex flex-wrap items-end gap-3 rounded-md border border-line bg-surface p-4"
      >
        <Field label="Name" htmlFor="competitor-label">
          <Input
            id="competitor-label"
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            placeholder="Rival Foods"
            required
          />
        </Field>
        <Field label="Website" htmlFor="competitor-origin">
          <Input
            id="competitor-origin"
            value={origin}
            onChange={(event) => setOrigin(event.target.value)}
            placeholder="https://rivalfoods.example.com"
            required
          />
        </Field>
        {add.isError ? (
          <p className="w-full text-sm text-danger">
            {errorMessage(add.error, "Could not add that site.")}
          </p>
        ) : null}
        <Button type="submit" variant="primary" disabled={add.isPending}>
          <Plus size={15} /> Add
        </Button>
      </form>

      <div className="rounded-md border border-line bg-surface">
        {isLoading ? (
          <Spinner />
        ) : (data?.length ?? 0) === 0 ? (
          <EmptyState
            icon={<Globe size={28} />}
            title="No competitors yet"
            hint="Add a rival's site above. The crawl respects their robots.txt and identifies itself honestly."
          />
        ) : (
          <ul>
            {data!.map((competitor: Competitor) => (
              <li
                key={competitor.id}
                className="flex items-center justify-between gap-3 border-t border-line px-4 py-3 first:border-t-0"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{competitor.label}</p>
                  <p className="truncate text-xs text-ink-muted">{competitor.origin}</p>
                  {competitor.robotsBlocked ? (
                    <p className="mt-0.5 flex items-center gap-1 text-xs text-warning">
                      <XCircle size={12} /> robots.txt disallows this crawler — not being crawled
                    </p>
                  ) : competitor.lastCrawledAt ? (
                    <p className="mt-0.5 text-xs text-ink-muted">
                      Last crawled {formatDate(competitor.lastCrawledAt)}
                    </p>
                  ) : null}
                </div>
                <Button
                  variant="ghost"
                  onClick={() => remove.mutate(competitor.id)}
                  disabled={remove.isPending}
                  aria-label={`Remove ${competitor.label}`}
                >
                  <Trash2 size={15} />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/* ─── Shell ────────────────────────────────────────────────────────── */

/* Users */

function UserStatusPill({ status }: { status: UserStatus }) {
  const styles: Record<UserStatus, string> = {
    active: "bg-success/10 text-success",
    invited: "bg-accent/10 text-accent",
    disabled: "bg-danger/10 text-danger",
  };
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
        styles[status],
      )}
    >
      {status}
    </span>
  );
}

function UsersTab({ user }: { user: StaffUser }) {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [draftSearch, setDraftSearch] = useState("");
  const [message, setMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);
  const limit = 25;
  const offset = (page - 1) * limit;
  const canViewUsers = user.isSuperAdmin || user.permissions.includes("users.view");
  const canManageUsers = user.isSuperAdmin || user.permissions.includes("users.manage_roles");

  const users = useQuery({
    queryKey: ["admin-users", page, search],
    queryFn: () => seoApi.users({ limit, offset, search: search || undefined }),
    enabled: canViewUsers,
  });
  const roles = useQuery({
    queryKey: ["admin-roles"],
    queryFn: seoApi.roles,
    enabled: canViewUsers,
  });
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: UserStatus }) =>
      seoApi.setUserStatus(id, status),
    onSuccess: async () => {
      setMessage({ tone: "success", text: "User status updated." });
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (error) =>
      setMessage({ tone: "danger", text: errorMessage(error, "Could not update user status.") }),
  });
  const roleMutation = useMutation({
    mutationFn: ({ id, roleId }: { id: string; roleId: string }) =>
      seoApi.setUserRoles(id, roleId ? [roleId] : []),
    onSuccess: async () => {
      setMessage({ tone: "success", text: "User role updated." });
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (error) =>
      setMessage({ tone: "danger", text: errorMessage(error, "Could not update user role.") }),
  });
  const resetMutation = useMutation({
    mutationFn: seoApi.sendUserPasswordReset,
    onSuccess: (result) =>
      setMessage({
        tone: "success",
        text: result.emailSent
          ? `Password reset sent to ${result.email}.`
          : `Password reset created for ${result.email}, but ${result.emailTransport} did not send it.`,
      }),
    onError: (error) =>
      setMessage({ tone: "danger", text: errorMessage(error, "Could not send password reset.") }),
  });

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    setSearch(draftSearch.trim());
    setPage(1);
  }

  if (!canViewUsers) {
    return (
      <EmptyState
        icon={<Users size={28} />}
        title="Users unavailable"
        hint="This account needs users.view permission."
      />
    );
  }

  const rows = users.data ?? [];
  const roleRows = roles.data ?? [];
  const busy = statusMutation.isPending || roleMutation.isPending || resetMutation.isPending;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <form className="flex min-w-72 flex-1 gap-2" onSubmit={submitSearch}>
          <Input
            aria-label="Search users"
            placeholder="Search users..."
            value={draftSearch}
            onChange={(event) => setDraftSearch(event.target.value)}
          />
          <Button type="submit" variant="secondary">
            <Search size={15} /> Search
          </Button>
        </form>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="secondary"
            disabled={page === 1 || users.isLoading}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={rows.length < limit || users.isLoading}
            onClick={() => setPage((value) => value + 1)}
          >
            Next
          </Button>
        </div>
      </div>

      {message ? (
        <p
          role="status"
          className={cn(
            "rounded-sm px-3 py-2 text-sm",
            message.tone === "success" ? "bg-success/10 text-success" : "bg-danger/10 text-danger",
          )}
        >
          {message.text}
        </p>
      ) : null}

      <div className="overflow-x-auto rounded-md border border-line bg-surface">
        {users.isLoading ? (
          <Spinner />
        ) : users.isError ? (
          <EmptyState
            icon={<AlertTriangle size={28} />}
            title="Users could not load"
            hint={errorMessage(users.error, "Check permissions and API connectivity.")}
          />
        ) : rows.length === 0 ? (
          <EmptyState icon={<Users size={28} />} title="No users found" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-canvas text-left text-xs text-ink-muted">
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Email</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Role</th>
                <th className="px-4 py-2 font-medium">Last sign-in</th>
                <th className="px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row: AdminUser) => (
                <tr key={row.id} className="border-b border-line last:border-b-0">
                  <td className="px-4 py-3 font-medium text-ink">{row.displayName}</td>
                  <td className="px-4 py-3 text-ink-muted">{row.email}</td>
                  <td className="px-4 py-3">
                    <UserStatusPill status={row.status} />
                  </td>
                  <td className="px-4 py-3">
                    {canManageUsers ? (
                      <select
                        aria-label={`Role for ${row.displayName}`}
                        className="min-h-9 min-w-44 rounded-sm border border-line-strong bg-surface px-3 text-sm text-ink"
                        value={row.roleIds?.[0] ?? ""}
                        disabled={roles.isLoading || busy}
                        onChange={(event) =>
                          roleMutation.mutate({ id: row.id, roleId: event.target.value })
                        }
                      >
                        <option value="">No role</option>
                        {roleRows.map((role: AdminRole) => (
                          <option key={role.id} value={role.id}>
                            {role.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span>{row.roles.join(", ") || "No role"}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-ink-muted">
                    {row.lastSignInAt ? formatDate(row.lastSignInAt) : "Never"}
                  </td>
                  <td className="px-4 py-3">
                    {canManageUsers ? (
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          variant="secondary"
                          className="px-2.5"
                          disabled={busy}
                          onClick={() =>
                            statusMutation.mutate({
                              id: row.id,
                              status: row.status === "disabled" ? "active" : "disabled",
                            })
                          }
                        >
                          <UserCog size={14} />
                          {row.status === "disabled" ? "Enable" : "Disable"}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          className="px-2.5"
                          disabled={busy}
                          onClick={() => resetMutation.mutate(row.id)}
                        >
                          <Mail size={14} /> Reset
                        </Button>
                      </div>
                    ) : (
                      <span className="text-xs text-ink-muted">View only</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Dashboard({ user, onLogout }: { user: StaffUser; onLogout: () => void }) {
  const [tab, setTab] = useState<TabKey>("proposals");

  if (!user.isSuperAdmin && !user.permissions.includes("seo.manage")) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-6">
        <EmptyState
          icon={<Shield size={28} />}
          title="You don't have access to the SEO agent"
          hint="Ask a super admin to grant the seo.manage permission from Scope Management."
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-canvas">
      <Header user={user} onLogout={onLogout} />
      <SummaryStrip />
      <div className="mx-auto max-w-6xl px-6 py-6">
        <nav className="mb-5 flex gap-1 border-b border-line">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setTab(item.key)}
              className={cn(
                "flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium",
                tab === item.key
                  ? "border-brand text-ink"
                  : "border-transparent text-ink-muted hover:text-ink",
              )}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="ml-auto flex items-center gap-1.5 self-center px-2 text-xs text-ink-muted hover:text-ink"
          >
            <RefreshCw size={13} /> Refresh
          </button>
        </nav>
        {tab === "proposals" ? <ProposalsTab /> : null}
        {tab === "findings" ? <FindingsTab /> : null}
        {tab === "keywords" ? <KeywordsTab /> : null}
        {tab === "content" ? <ContentGapsTab /> : null}
        {tab === "competitors" ? <CompetitorsTab /> : null}
        {tab === "users" ? <UsersTab user={user} /> : null}
      </div>
    </div>
  );
}

export function App() {
  const [user, setUser] = useState<StaffUser | null | undefined>(undefined);

  useMemo(() => {
    seoApi
      .me()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  if (user === undefined) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <Spinner />
      </div>
    );
  }
  if (user === null) {
    return <Login onAuthenticated={setUser} />;
  }
  return (
    <Dashboard
      user={user}
      onLogout={() => {
        seoApi.logout().finally(() => setUser(null));
      }}
    />
  );
}
