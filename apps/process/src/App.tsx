import { cn } from "@truegrit/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  CircleDot,
  ExternalLink,
  GitBranch,
  GitCommitHorizontal,
  Key,
  Languages,
  Loader2,
  LockKeyhole,
  LogOut,
  Monitor,
  RefreshCw,
  Rocket,
  Search,
  Shield,
  ShieldCheck,
  Trash2,
  UserPlus,
  Users,
  X,
  XCircle,
} from "lucide-react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import {
  ApiError,
  releaseApi,
  type ReleaseBranch,
  type ReleaseCheck,
  type ReleaseUser,
  type StaffUser,
} from "./api";

/* ─── Constants ────────────────────────────────────────────────────── */

type TabKey = "testing" | "staging" | "main" | "users" | "translations";

const BRANCH_META = {
  testing: { number: "01", label: "Testing", target: "staging", color: "warning" },
  staging: { number: "02", label: "Staging", target: "main", color: "accent" },
  main: { number: "03", label: "Main / Live", target: null, color: "success" },
} as const;

const ENVIRONMENT_LINKS: Record<ReleaseBranch["name"], Array<{ label: string; url: string }>> = {
  testing: [
    { label: "Storefront", url: "https://test.truegritin.com" },
    { label: "Admin", url: "https://adtest.truegritin.com" },
    { label: "API", url: "https://apitest.truegritin.com/health/live" },
  ],
  staging: [
    { label: "Storefront", url: "https://stag.truegritin.com" },
    { label: "Admin", url: "https://adstag.truegritin.com" },
    { label: "API", url: "https://apistag.truegritin.com/health/live" },
  ],
  main: [
    { label: "Storefront", url: "https://truegritin.com" },
    { label: "Admin", url: "https://admin.truegritin.com" },
    { label: "API", url: "https://api.truegritin.com/health/live" },
    { label: "Process", url: "https://process.truegritin.com" },
    { label: "Language Studio", url: "https://lang.truegritin.com" },
  ],
};

const NAV_ITEMS: Array<{ key: TabKey; label: string; icon: ReactNode; superOnly?: boolean }> = [
  { key: "testing", label: "Testing", icon: <GitBranch size={16} /> },
  { key: "staging", label: "Staging", icon: <Monitor size={16} /> },
  { key: "main", label: "Main / Live", icon: <Rocket size={16} /> },
  { key: "translations", label: "Language Studio", icon: <Languages size={16} /> },
  { key: "users", label: "Process Users", icon: <Users size={16} />, superOnly: true },
];

/* ─── Helpers ──────────────────────────────────────────────────────── */

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/* ─── Shared UI Primitives (admin-matching) ────────────────────────── */

function Button({
  variant = "secondary",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "destructive";
}) {
  const styles = {
    primary: "bg-brand text-ink-inverse hover:opacity-90",
    secondary: "border border-line-strong bg-surface text-ink hover:bg-subtle/50",
    destructive: "bg-danger text-ink-inverse hover:opacity-90",
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

function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto bg-ink/40 px-4 py-10"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-full max-w-lg rounded-md border border-line bg-surface shadow-overlay"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h2 className="font-display text-lg text-ink">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-8 w-8 items-center justify-center text-ink-muted hover:text-ink"
          >
            <X size={17} />
          </button>
        </div>
        <div className="px-5 py-5">{children}</div>
      </div>
    </div>
  );
}

function StatusPill({ status, children }: { status: string; children?: ReactNode }) {
  const styles: Record<string, string> = {
    success: "bg-success/10 text-success",
    pending: "bg-warning/10 text-warning",
    failure: "bg-danger/10 text-danger",
    cancelled: "bg-danger/10 text-danger",
    active: "bg-success/10 text-success",
    disabled: "bg-danger/10 text-danger",
    "not-required": "bg-success/10 text-success",
    neutral: "bg-subtle text-ink-muted",
    skipped: "bg-subtle text-ink-muted",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
        styles[status] ?? "bg-subtle text-ink-muted",
      )}
    >
      {children ?? status}
    </span>
  );
}

function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-md border border-dashed border-line-strong bg-surface px-6 py-12 text-center">
      <p className="font-medium text-ink">{title}</p>
      {hint ? <p className="mt-1 text-sm text-ink-muted">{hint}</p> : null}
    </div>
  );
}

/* ─── Login ────────────────────────────────────────────────────────── */

function Login({ onAuthenticated }: { onAuthenticated: (user: StaffUser) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useMutation({
    mutationFn: () => releaseApi.login(email, password),
    onSuccess: async () => onAuthenticated(await releaseApi.me()),
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate();
  }
  return (
    <main className="grid min-h-screen grid-cols-1 bg-canvas lg:grid-cols-[minmax(0,1fr)_28rem]">
      {/* Left: branded hero */}
      <section className="flex min-h-[18rem] items-end bg-brand px-6 py-10 text-ink-inverse lg:min-h-screen lg:px-12">
        <div className="max-w-xl">
          <div className="flex items-center gap-3">
            <img
              src="/brand/true-grit-mark.webp"
              alt=""
              width={40}
              height={40}
              className="h-10 w-10 rounded-full object-cover"
            />
            <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-75">
              True Grit Process
            </p>
          </div>
          <h1 className="mt-4 font-display text-4xl leading-tight lg:text-5xl">
            Move deliberately.
          </h1>
          <p className="mt-4 max-w-md text-sm opacity-80">
            Inspect commits, verify staging, and promote an exact reviewed build to production.
            Every promotion is SHA-locked.
          </p>
        </div>
      </section>

      {/* Right: sign-in form */}
      <section className="flex items-center px-6 py-10">
        <div className="w-full">
          <div className="mb-8 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-sm bg-subtle text-brand">
              <Shield size={20} />
            </span>
            <div>
              <h2 className="font-display text-2xl text-ink">Staff sign in</h2>
              <p className="text-sm text-ink-muted">Protected release system</p>
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
              <Input
                id="password"
                type="password"
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
              {login.isPending ? "Signing in…" : "Enter release cockpit"}
            </Button>
          </form>
        </div>
      </section>
    </main>
  );
}

/* ─── CI Checks ────────────────────────────────────────────────────── */

function statusIcon(state: string) {
  if (["success", "not-required", "neutral", "skipped"].includes(state)) return CheckCircle2;
  if (["failure", "cancelled", "timed_out", "action_required"].includes(state)) return XCircle;
  return Loader2;
}

function checkSeverity(check: ReleaseCheck): number {
  if (check.status !== "completed") return 1;
  return ["success", "neutral", "skipped"].includes(check.conclusion ?? "") ? 2 : 0;
}

function Checks({ checks }: { checks: ReleaseCheck[] }) {
  const sorted = [...checks].sort((left, right) => checkSeverity(left) - checkSeverity(right));
  if (!sorted.length)
    return <p className="py-3 text-sm text-warning">No checks have reported yet.</p>;
  return (
    <ul className="space-y-1.5">
      {sorted.map((check) => {
        const state = check.status === "completed" ? (check.conclusion ?? "failure") : "pending";
        const Icon = statusIcon(state);
        const color =
          state === "pending"
            ? "text-warning"
            : ["success", "not-required", "neutral", "skipped"].includes(state)
              ? "text-success"
              : "text-danger";
        return (
          <li key={check.name} className="flex items-center gap-2 text-sm">
            <Icon size={15} className={cn(color, state === "pending" && "animate-spin-slow")} />
            <span className="min-w-0 flex-1 truncate text-ink">{check.name}</span>
            {check.url ? (
              <a
                href={check.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex shrink-0 items-center gap-1 text-xs text-brand hover:underline"
              >
                Open <ExternalLink size={11} />
              </a>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

/* ─── Commits ──────────────────────────────────────────────────────── */

function Commits({ branch }: { branch: ReleaseBranch }) {
  return (
    <div className="mt-5 border-t border-line pt-4">
      <p className="mb-3 text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
        Recent commits · {branch.commits.length}
      </p>
      <ol className="scrollbar-thin max-h-[360px] space-y-0 overflow-y-auto pl-4">
        {branch.commits.map((commit, index) => (
          <li key={commit.sha} className="relative border-l border-line pb-3 pl-5 last:pb-0">
            <span
              className={cn(
                "absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-surface",
                index === 0 ? "bg-accent" : "bg-line-strong",
              )}
            />
            <a
              href={commit.url}
              target="_blank"
              rel="noreferrer"
              className="line-clamp-2 text-sm font-medium leading-snug text-ink hover:text-accent"
            >
              {commit.message}
            </a>
            <p className="mt-1 text-xs text-ink-muted">
              <code className="mr-1 text-xs">{commit.sha.slice(0, 8)}</code> · {commit.author} ·{" "}
              <time dateTime={commit.authoredAt}>{formatDate(commit.authoredAt)}</time>
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ─── Branch Detail View ───────────────────────────────────────────── */

function BranchDetail({
  branch,
  busy,
  onPromote,
  onVerify,
}: {
  branch: ReleaseBranch;
  busy: boolean;
  onPromote: () => void;
  onVerify: () => void;
}) {
  const meta = BRANCH_META[branch.name];
  const environmentLinks = ENVIRONMENT_LINKS[branch.name];
  const canVerify =
    branch.name === "staging" && branch.ciState === "success" && branch.gate.state !== "success";

  const borderColor = {
    testing: "border-l-warning",
    staging: "border-l-accent",
    main: "border-l-success",
  }[branch.name];

  return (
    <div className="space-y-5">
      {/* Header card */}
      <div
        className={cn(
          "rounded-md border border-line border-l-4 bg-surface p-5 shadow-card",
          borderColor,
        )}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
              Layer {meta.number}
            </p>
            <h2 className="mt-1 font-display text-2xl text-ink">{meta.label}</h2>
            <code className="mt-1 block text-xs text-ink-muted">{branch.name}</code>
          </div>
          {branch.environmentUrl ? (
            <a
              className="inline-flex min-h-9 items-center gap-2 rounded-sm border border-line-strong bg-surface px-3.5 text-sm font-medium text-ink hover:bg-subtle/50"
              href={branch.environmentUrl}
              target="_blank"
              rel="noreferrer"
            >
              Open site <ExternalLink size={14} />
            </a>
          ) : (
            <span className="rounded-sm bg-subtle px-2.5 py-1 text-xs text-ink-muted">CI only</span>
          )}
        </div>

        {/* Status pills */}
        <div className="mt-4 flex flex-wrap gap-2">
          <StatusPill status={branch.ciState}>Checks: {branch.ciState}</StatusPill>
          {branch.name === "main" ? (
            <StatusPill status="success">Live branch</StatusPill>
          ) : (
            <StatusPill status={branch.gate.state}>
              {branch.name === "testing" ? "Agent approval" : "Manual verification"}
            </StatusPill>
          )}
        </div>
      </div>

      {/* Environment shortcuts */}
      <div className="rounded-md border border-line bg-surface p-4 shadow-card">
        <p className="mb-3 text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
          Environment URLs
        </p>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {environmentLinks.map((link) => (
            <a
              key={link.label}
              href={link.url}
              target="_blank"
              rel="noreferrer"
              className="flex min-w-0 items-center justify-between gap-3 rounded-sm border border-line px-3 py-2.5 text-sm hover:border-line-strong hover:bg-subtle/40"
            >
              <span className="min-w-0">
                <span className="block font-medium text-ink">{link.label}</span>
                <span className="block truncate text-xs text-ink-muted">
                  {new URL(link.url).hostname}
                </span>
              </span>
              <ExternalLink size={14} className="shrink-0 text-brand" />
            </a>
          ))}
        </div>
      </div>

      {/* Head commit */}
      <div className="rounded-md border border-line bg-surface p-4 shadow-card">
        <p className="mb-2 flex items-center gap-2 text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
          <GitCommitHorizontal size={14} /> Head commit
        </p>
        <code className="block break-all text-xs text-ink">{branch.headSha}</code>
        {branch.gate.description ? (
          <p className="mt-2 text-sm text-success">{branch.gate.description}</p>
        ) : null}
      </div>

      {/* Checks */}
      <div className="rounded-md border border-line bg-surface p-4 shadow-card">
        <p className="mb-3 text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
          Checks & deployment
        </p>
        <Checks checks={branch.checks} />
      </div>

      {/* Blocked reason */}
      {branch.blockedReason && branch.name !== "main" ? (
        <div className="flex gap-3 rounded-md border border-warning/30 bg-warning/5 p-4">
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warning" />
          <p className="text-sm text-ink">{branch.blockedReason}</p>
        </div>
      ) : null}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-3">
        {branch.name === "staging" ? (
          <Button
            variant={branch.gate.state === "success" ? "secondary" : "primary"}
            className="min-w-48"
            disabled={!canVerify || busy}
            onClick={onVerify}
          >
            <ShieldCheck size={16} />
            {branch.gate.state === "success" ? "Staging verified" : "Mark staging verified"}
          </Button>
        ) : null}
        {meta.target ? (
          <Button
            variant="primary"
            className="min-w-48"
            disabled={!branch.canPromote || busy}
            onClick={onPromote}
          >
            <Rocket size={16} />
            Promote to {meta.target}
          </Button>
        ) : null}
      </div>

      {/* Commits */}
      <Commits branch={branch} />
    </div>
  );
}

/* ─── Users Management ─────────────────────────────────────────────── */

function UsersTab({
  onNotice,
}: {
  onNotice: (notice: { kind: "success" | "error"; text: string }) => void;
}) {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [resetTarget, setResetTarget] = useState<ReleaseUser | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<ReleaseUser | null>(null);

  const users = useQuery({ queryKey: ["release-users"], queryFn: releaseApi.users });
  const addUser = useMutation({
    mutationFn: () => releaseApi.addUser(email, displayName, password),
    onSuccess: () => {
      setEmail("");
      setDisplayName("");
      setPassword("");
      setShowAddForm(false);
      queryClient.invalidateQueries({ queryKey: ["release-users"] });
      onNotice({ kind: "success", text: "Release user added." });
    },
    onError: (error) =>
      onNotice({ kind: "error", text: errorMessage(error, "Could not add user.") }),
  });
  const deleteUser = useMutation({
    mutationFn: (id: string) => releaseApi.deleteUser(id),
    onSuccess: () => {
      setDeleteTarget(null);
      queryClient.invalidateQueries({ queryKey: ["release-users"] });
      onNotice({ kind: "success", text: "User removed." });
    },
    onError: (error) =>
      onNotice({ kind: "error", text: errorMessage(error, "Could not remove user.") }),
  });
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      releaseApi.setUserStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["release-users"] });
      onNotice({ kind: "success", text: "User status updated." });
    },
    onError: (error) =>
      onNotice({ kind: "error", text: errorMessage(error, "Could not update status.") }),
  });
  const resetMutation = useMutation({
    mutationFn: ({ id, pw }: { id: string; pw: string }) => releaseApi.resetUserPassword(id, pw),
    onSuccess: () => {
      setResetTarget(null);
      setResetPassword("");
      onNotice({ kind: "success", text: "Password reset successfully." });
    },
    onError: (error) =>
      onNotice({ kind: "error", text: errorMessage(error, "Could not reset password.") }),
  });

  function submitAdd(event: FormEvent) {
    event.preventDefault();
    addUser.mutate();
  }

  const filtered =
    users.data?.items.filter((user) => {
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return user.displayName.toLowerCase().includes(q) || user.email.toLowerCase().includes(q);
    }) ?? [];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-display text-2xl text-ink">Process Users</h2>
          <p className="mt-1 text-sm text-ink-muted">
            These accounts receive only the Release Manager role. Share temporary passwords
            securely.
          </p>
        </div>
        <Button variant="primary" onClick={() => setShowAddForm(true)}>
          <UserPlus size={16} /> Add user
        </Button>
      </div>

      {/* Search */}
      <div className="max-w-sm">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
          <Input
            type="search"
            placeholder="Search by name or email…"
            aria-label="Search users"
            className="pl-9"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
          />
        </div>
      </div>

      {/* Users table */}
      {users.isLoading ? (
        <div className="py-12 text-center text-sm text-ink-muted">Loading users…</div>
      ) : users.isError ? (
        <EmptyState
          title="Users unavailable"
          hint={errorMessage(users.error, "Could not load users.")}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No users found"
          hint={searchQuery ? "Try a different search term." : "Add a release user to get started."}
        />
      ) : (
        <div className="overflow-x-auto rounded-md border border-line bg-surface shadow-card">
          <table className="w-full min-w-[640px] border-collapse text-left text-sm">
            <thead className="bg-canvas">
              <tr>
                <th className="px-3 py-2.5 text-xs font-semibold tracking-wide text-ink-muted uppercase">
                  Name
                </th>
                <th className="px-3 py-2.5 text-xs font-semibold tracking-wide text-ink-muted uppercase">
                  Email
                </th>
                <th className="px-3 py-2.5 text-xs font-semibold tracking-wide text-ink-muted uppercase">
                  Status
                </th>
                <th className="px-3 py-2.5 text-xs font-semibold tracking-wide text-ink-muted uppercase">
                  Last sign-in
                </th>
                <th className="px-3 py-2.5 text-xs font-semibold tracking-wide text-ink-muted uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((user) => (
                <tr key={user.id} className="border-t border-line">
                  <td className="px-3 py-3 font-medium text-ink">{user.displayName}</td>
                  <td className="px-3 py-3 text-ink-muted">{user.email}</td>
                  <td className="px-3 py-3">
                    <StatusPill status={user.status === "active" ? "active" : "disabled"}>
                      {user.status}
                    </StatusPill>
                  </td>
                  <td className="px-3 py-3 text-ink-muted">{formatDate(user.lastSignInAt)}</td>
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        className="text-sm text-ink-muted underline-offset-4 hover:text-brand hover:underline"
                        onClick={() =>
                          statusMutation.mutate({
                            id: user.id,
                            status: user.status === "disabled" ? "active" : "disabled",
                          })
                        }
                        disabled={statusMutation.isPending}
                      >
                        {user.status === "disabled" ? "Enable" : "Disable"}
                      </button>
                      <button
                        type="button"
                        className="text-sm text-ink-muted underline-offset-4 hover:text-brand hover:underline"
                        onClick={() => setResetTarget(user)}
                      >
                        Password
                      </button>
                      <button
                        type="button"
                        className="text-sm text-ink-muted underline-offset-4 hover:text-danger hover:underline"
                        onClick={() => setDeleteTarget(user)}
                        disabled={deleteUser.isPending}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add user modal */}
      {showAddForm ? (
        <Modal title="Add release user" onClose={() => setShowAddForm(false)}>
          <p className="mb-4 text-sm text-ink-muted">
            This creates a True Grit staff account with only the Release Manager role.
          </p>
          <form className="space-y-4" onSubmit={submitAdd}>
            <Field label="Name" htmlFor="release-user-name">
              <Input
                id="release-user-name"
                required
                minLength={2}
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </Field>
            <Field label="Email" htmlFor="release-user-email">
              <Input
                id="release-user-email"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>
            <Field label="Temporary password" htmlFor="release-user-password">
              <Input
                id="release-user-password"
                type="password"
                autoComplete="new-password"
                required
                minLength={10}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </Field>
            {addUser.isError ? (
              <p role="alert" className="text-sm text-danger">
                {errorMessage(addUser.error, "Could not add release user.")}
              </p>
            ) : null}
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="secondary" onClick={() => setShowAddForm(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={addUser.isPending}>
                {addUser.isPending ? (
                  <Loader2 size={16} className="animate-spin-slow" />
                ) : (
                  <UserPlus size={16} />
                )}
                Add user
              </Button>
            </div>
          </form>
        </Modal>
      ) : null}

      {/* Password reset modal */}
      {resetTarget ? (
        <Modal
          title={`Reset password for ${resetTarget.displayName}`}
          onClose={() => {
            setResetTarget(null);
            setResetPassword("");
          }}
        >
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              resetMutation.mutate({ id: resetTarget.id, pw: resetPassword });
            }}
          >
            <Field label="New password" htmlFor="reset-password-input">
              <Input
                id="reset-password-input"
                type="password"
                autoComplete="new-password"
                required
                minLength={10}
                value={resetPassword}
                onChange={(event) => setResetPassword(event.target.value)}
              />
            </Field>
            {resetMutation.isError ? (
              <p role="alert" className="text-sm text-danger">
                {errorMessage(resetMutation.error, "Could not reset password.")}
              </p>
            ) : null}
            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setResetTarget(null);
                  setResetPassword("");
                }}
              >
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={resetMutation.isPending}>
                {resetMutation.isPending ? (
                  <Loader2 size={16} className="animate-spin-slow" />
                ) : (
                  <Key size={16} />
                )}
                Reset password
              </Button>
            </div>
          </form>
        </Modal>
      ) : null}

      {/* Delete confirmation modal */}
      {deleteTarget ? (
        <Modal title="Remove user" onClose={() => setDeleteTarget(null)}>
          <div className="flex gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-sm bg-danger/10 text-danger">
              <AlertTriangle size={19} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm leading-6 text-ink-muted">
                <strong className="text-ink">{deleteTarget.displayName}</strong> (
                {deleteTarget.email}) will be removed and signed out.
              </p>
              <div className="mt-5 flex flex-wrap justify-end gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setDeleteTarget(null)}
                  disabled={deleteUser.isPending}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => deleteUser.mutate(deleteTarget.id)}
                  disabled={deleteUser.isPending}
                >
                  {deleteUser.isPending ? (
                    <Loader2 size={16} className="animate-spin-slow" />
                  ) : (
                    <Trash2 size={16} />
                  )}
                  Delete user
                </Button>
              </div>
            </div>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}

/* ─── Cockpit Shell ────────────────────────────────────────────────── */

function Cockpit({ user, onLogout }: { user: StaffUser; onLogout: () => void }) {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabKey>("testing");
  const [selectedPromotion, setSelectedPromotion] = useState<ReleaseBranch | null>(null);
  const [selectedVerification, setSelectedVerification] = useState<ReleaseBranch | null>(null);
  const [notes, setNotes] = useState("");
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  const dashboard = useQuery({
    queryKey: ["release-dashboard"],
    queryFn: releaseApi.dashboard,
    refetchInterval: 60_000,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["release-dashboard"] });

  const promote = useMutation({
    mutationFn: (branch: ReleaseBranch) =>
      releaseApi.promote(
        branch.name as "testing" | "staging",
        branch.name === "testing" ? "staging" : "main",
        branch.headSha,
      ),
    onSuccess: (_result, branch) => {
      setNotice({ kind: "success", text: `${branch.headSha.slice(0, 8)} promoted successfully.` });
      setSelectedPromotion(null);
      refresh();
    },
    onError: (error) =>
      setNotice({ kind: "error", text: errorMessage(error, "Promotion failed.") }),
  });
  const verify = useMutation({
    mutationFn: (branch: ReleaseBranch) => releaseApi.verifyStaging(branch.headSha, notes),
    onSuccess: () => {
      setNotice({ kind: "success", text: "Staging verification recorded on the exact commit." });
      setSelectedVerification(null);
      setNotes("");
      refresh();
    },
    onError: (error) =>
      setNotice({ kind: "error", text: errorMessage(error, "Verification failed.") }),
  });
  const busy = promote.isPending || verify.isPending;

  const activeBranch = dashboard.data?.branches.find((branch) => branch.name === activeTab);

  // Filter nav items based on user permissions
  const visibleNav = NAV_ITEMS.filter((item) => !item.superOnly || user.isSuperAdmin);

  return (
    <div className="flex min-h-screen">
      {/* ── Sidebar ── */}
      <aside className="hidden w-60 shrink-0 border-r border-line bg-surface md:flex md:flex-col">
        <div className="flex-1 overflow-y-auto">
          {/* Brand */}
          <div className="border-b border-line px-5 py-5">
            <div className="flex items-center gap-2.5">
              <img
                src="/brand/true-grit-mark.webp"
                alt=""
                width={32}
                height={32}
                className="h-8 w-8 shrink-0 rounded-full object-cover"
              />
              <p className="font-display text-lg tracking-tight text-brand">TRUE GRIT</p>
            </div>
            <p className="mt-1.5 text-xs text-ink-muted">Release cockpit</p>
          </div>

          {/* Navigation */}
          <nav aria-label="Process navigation" className="space-y-1 px-3 py-5">
            <p className="px-2 pb-1.5 text-[11px] font-semibold tracking-[0.14em] text-ink-muted uppercase">
              Branches
            </p>
            {visibleNav.map((item) => {
              // Show status indicator for branch tabs
              const branch =
                item.key !== "users" && item.key !== "translations"
                  ? dashboard.data?.branches.find((branch) => branch.name === item.key)
                  : null;
              const statusColor = branch
                ? branch.ciState === "success"
                  ? "bg-success"
                  : branch.ciState === "failure"
                    ? "bg-danger"
                    : "bg-warning"
                : null;

              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setActiveTab(item.key)}
                  className={cn(
                    "flex min-h-9 w-full items-center gap-2.5 rounded-sm px-2 text-sm",
                    activeTab === item.key
                      ? "bg-subtle font-medium text-brand"
                      : "text-ink hover:bg-canvas",
                  )}
                >
                  {item.icon}
                  <span className="flex flex-1 items-center justify-between gap-2">
                    {item.label}
                    {statusColor ? (
                      <span className={cn("h-2 w-2 rounded-full", statusColor)} />
                    ) : null}
                  </span>
                </button>
              );
            })}
          </nav>
        </div>
      </aside>

      {/* ── Main Content ── */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="flex items-center justify-between gap-4 border-b border-line bg-surface px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            {/* Mobile tab selector */}
            <select
              className="min-h-9 rounded-sm border border-line-strong bg-surface px-2 text-sm text-ink md:hidden"
              value={activeTab}
              onChange={(event) => setActiveTab(event.target.value as TabKey)}
            >
              {visibleNav.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label}
                </option>
              ))}
            </select>
            <div className="flex items-center gap-2 text-sm text-ink-muted">
              <GitBranch size={16} className="hidden sm:block" />
              {dashboard.data?.repository ? (
                <code className="text-xs">{dashboard.data.repository}</code>
              ) : (
                <span>Branch promotion system</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm text-ink">
            <button
              type="button"
              className="inline-flex min-h-9 items-center gap-2 rounded-sm border border-line-strong bg-surface px-2.5 text-sm text-ink hover:bg-subtle/50 disabled:opacity-50"
              disabled={dashboard.isFetching}
              onClick={() => dashboard.refetch()}
            >
              <RefreshCw
                size={14}
                className={dashboard.isFetching ? "animate-spin-slow" : undefined}
              />
              <span className="hidden sm:inline">Refresh</span>
            </button>
            <span className="hidden text-ink-muted sm:inline">{user.displayName}</span>
            <Button
              type="button"
              variant="secondary"
              className="min-h-8 px-2.5"
              onClick={onLogout}
              aria-label="Sign out"
            >
              <LogOut size={15} />
            </Button>
          </div>
        </header>

        {/* Content area */}
        <main className="flex-1 px-4 py-6 sm:px-6">
          {/* Process strip */}
          <div className="mb-6 hidden rounded-md border border-line bg-inverse p-1 text-ink-inverse md:flex">
            {(["testing", "staging", "main"] as const).map((branchName, index) => {
              const branch = dashboard.data?.branches.find((b) => b.name === branchName);
              return (
                <div key={branchName} className="relative flex flex-1 items-center gap-3 px-4 py-3">
                  {index > 0 ? (
                    <ArrowRight size={14} className="absolute -left-2 text-accent opacity-60" />
                  ) : null}
                  <CircleDot size={16} className="shrink-0 text-accent" />
                  <div>
                    <p className="text-[10px] font-semibold tracking-[0.14em] uppercase opacity-60">
                      Gate {index + 1}
                    </p>
                    <p className="text-sm font-medium">{BRANCH_META[branchName].label}</p>
                  </div>
                  {branch ? (
                    <span
                      className={cn(
                        "ml-auto h-2 w-2 rounded-full",
                        branch.ciState === "success"
                          ? "bg-success"
                          : branch.ciState === "failure"
                            ? "bg-danger"
                            : "bg-warning",
                      )}
                    />
                  ) : null}
                </div>
              );
            })}
          </div>

          {/* Notice */}
          {notice ? (
            <div
              className={cn(
                "mb-4 flex items-center gap-3 rounded-md border p-3 text-sm",
                notice.kind === "success"
                  ? "border-success/30 bg-success/5 text-success"
                  : "border-danger/30 bg-danger/5 text-danger",
              )}
              role="status"
            >
              {notice.kind === "success" ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
              <span className="flex-1">{notice.text}</span>
              <button
                aria-label="Dismiss"
                onClick={() => setNotice(null)}
                className="text-current hover:opacity-70"
              >
                <X size={14} />
              </button>
            </div>
          ) : null}

          {/* Main content per tab */}
          {activeTab === "users" ? (
            <UsersTab onNotice={setNotice} />
          ) : activeTab === "translations" ? (
            <section className="mx-auto max-w-3xl rounded-md border border-line bg-surface p-6 shadow-card sm:p-8">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-subtle text-brand">
                <Languages size={23} />
              </div>
              <p className="mt-5 text-xs font-semibold tracking-[0.14em] text-accent uppercase">
                Translation operations
              </p>
              <h2 className="mt-2 font-display text-3xl text-ink">True Grit Language Studio</h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-ink-muted">
                Translate and review storefront and admin interface text, pages, products, blogs,
                recipes, discussions and comments. Manage the live language registry from the same
                workspace.
              </p>
              <a
                href="https://lang.truegritin.com"
                target="_blank"
                rel="noreferrer"
                className="mt-6 inline-flex min-h-10 items-center gap-2 rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-90"
              >
                Open Language Studio <ExternalLink size={15} />
              </a>
            </section>
          ) : dashboard.isError ? (
            <div className="py-20 text-center">
              <XCircle size={28} className="mx-auto text-danger" />
              <h2 className="mt-3 font-display text-xl text-ink">Could not load GitHub</h2>
              <p className="mt-1 text-sm text-ink-muted">
                {errorMessage(dashboard.error, "Dashboard request failed.")}
              </p>
            </div>
          ) : dashboard.isLoading ? (
            <div className="flex items-center justify-center gap-3 py-20 text-sm text-ink-muted">
              <Loader2 size={20} className="animate-spin-slow" /> Loading release state…
            </div>
          ) : activeBranch ? (
            <BranchDetail
              branch={activeBranch}
              busy={busy}
              onPromote={() => setSelectedPromotion(activeBranch)}
              onVerify={() => setSelectedVerification(activeBranch)}
            />
          ) : (
            <EmptyState
              title="Branch not found"
              hint={`The "${activeTab}" branch was not returned by the API.`}
            />
          )}
        </main>

        {/* Auto-refresh indicator */}
        <footer className="border-t border-line px-4 py-2 text-xs text-ink-muted sm:px-6">
          Auto-refresh · 60 seconds
        </footer>
      </div>

      {/* ── Modals ── */}
      {selectedPromotion ? (
        <Modal
          title={`Promote ${selectedPromotion.name} → ${BRANCH_META[selectedPromotion.name].target}`}
          onClose={() => setSelectedPromotion(null)}
        >
          <div className="flex gap-3 rounded-md border border-warning/30 bg-warning/5 p-4">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-warning" />
            <p className="text-sm text-ink">
              This merges only{" "}
              <code className="text-xs">{selectedPromotion.headSha.slice(0, 12)}</code>. If the
              branch advances, the server rejects the action.
            </p>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setSelectedPromotion(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={promote.isPending}
              onClick={() => promote.mutate(selectedPromotion)}
            >
              {promote.isPending ? (
                <Loader2 size={16} className="animate-spin-slow" />
              ) : (
                <ArrowRight size={16} />
              )}
              Confirm promotion
            </Button>
          </div>
        </Modal>
      ) : null}

      {selectedVerification ? (
        <Modal title="Verify the staging deployment" onClose={() => setSelectedVerification(null)}>
          <p className="text-sm text-ink-muted">
            Open the staging domain, test this exact release, then record what you checked. Main
            remains locked until this step passes.
          </p>
          {selectedVerification.environmentUrl ? (
            <a
              className="mt-3 inline-flex items-center gap-1.5 text-sm text-brand hover:underline"
              href={selectedVerification.environmentUrl}
              target="_blank"
              rel="noreferrer"
            >
              Open staging website <ExternalLink size={14} />
            </a>
          ) : null}
          <div className="mt-4">
            <Field label="Verification notes" htmlFor="verification-notes">
              <Input
                id="verification-notes"
                maxLength={100}
                value={notes}
                placeholder="Checkout, login, catalogue and mobile verified"
                onChange={(event) => setNotes(event.target.value)}
              />
            </Field>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setSelectedVerification(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={notes.trim().length < 3 || verify.isPending}
              onClick={() => verify.mutate(selectedVerification)}
            >
              {verify.isPending ? (
                <Loader2 size={16} className="animate-spin-slow" />
              ) : (
                <Check size={16} />
              )}
              Record verification
            </Button>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}

/* ─── App Root ─────────────────────────────────────────────────────── */

export function App() {
  const [user, setUser] = useState<StaffUser | null>(null);
  const session = useQuery({
    queryKey: ["session"],
    queryFn: releaseApi.me,
    retry: false,
    enabled: user === null,
  });
  const authenticated = user ?? session.data ?? null;

  if (session.isLoading && !authenticated)
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas text-sm text-ink-muted">
        <Loader2 size={20} className="animate-spin-slow" />
        <span className="ml-3">Checking access…</span>
      </div>
    );

  if (!authenticated) return <Login onAuthenticated={setUser} />;

  if (!authenticated.isSuperAdmin && !authenticated.permissions.includes("deployments.manage"))
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-3 bg-canvas px-6 text-center">
        <LockKeyhole size={34} className="text-ink-muted" />
        <h1 className="font-display text-2xl text-ink">Release access required</h1>
        <p className="text-sm text-ink-muted">
          Ask the True Grit owner to add you as a Process release user.
        </p>
      </main>
    );

  return (
    <Cockpit
      user={authenticated}
      onLogout={async () => {
        await releaseApi.logout();
        window.location.reload();
      }}
    />
  );
}
