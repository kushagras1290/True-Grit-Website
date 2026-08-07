import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  CircleDot,
  ExternalLink,
  GitCommitHorizontal,
  LoaderCircle,
  LockKeyhole,
  LogOut,
  RefreshCw,
  Rocket,
  ShieldCheck,
  UserPlus,
  Users,
  X,
  XCircle,
} from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import { ApiError, releaseApi, type ReleaseBranch, type ReleaseCheck, type StaffUser } from "./api";

const BRANCH_META = {
  testing: { number: "01", label: "Testing", target: "staging" },
  staging: { number: "02", label: "Staging", target: "main" },
  main: { number: "03", label: "Main / Live", target: null },
} as const;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

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
    <main className="login-shell">
      <section className="login-card" aria-labelledby="login-title">
        <Brand />
        <p className="eyebrow">Protected release system</p>
        <h1 id="login-title">Move deliberately.</h1>
        <p className="login-copy">
          Sign in with your True Grit staff account to inspect commits, verify staging, and promote
          an exact reviewed build.
        </p>
        <form onSubmit={submit} className="login-form">
          <label htmlFor="email">Staff email</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {login.isError ? (
            <p className="error-banner" role="alert">
              {errorMessage(login.error, "Sign in failed.")}
            </p>
          ) : null}
          <button className="button button-primary" disabled={login.isPending}>
            {login.isPending ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <LockKeyhole size={17} />
            )}
            Enter release cockpit
          </button>
        </form>
      </section>
    </main>
  );
}

function Brand() {
  return (
    <div className="brand" aria-label="True Grit">
      <span className="brand-mark">TG</span>
      <span>TRUE GRIT</span>
    </div>
  );
}

function statusIcon(state: string) {
  if (["success", "not-required", "neutral", "skipped"].includes(state)) return CheckCircle2;
  if (["failure", "cancelled", "timed_out", "action_required"].includes(state)) return XCircle;
  return LoaderCircle;
}

function StatusPill({ state, children }: { state: string; children: ReactNode }) {
  const Icon = statusIcon(state);
  return (
    <span className={`status status-${state}`}>
      <Icon size={13} className={state === "pending" ? "spin" : undefined} /> {children}
    </span>
  );
}

function checkSeverity(check: ReleaseCheck): number {
  if (check.status !== "completed") return 1;
  return ["success", "neutral", "skipped"].includes(check.conclusion ?? "") ? 2 : 0;
}

function Checks({ checks }: { checks: ReleaseCheck[] }) {
  const sorted = [...checks].sort((left, right) => checkSeverity(left) - checkSeverity(right));
  if (!sorted.length) return <p className="empty-check">No checks have reported yet.</p>;
  return (
    <ul className="checks-list">
      {sorted.map((check) => {
        const state = check.status === "completed" ? (check.conclusion ?? "failure") : "pending";
        const Icon = statusIcon(state);
        return (
          <li key={check.name} className={`check-row check-${state}`}>
            <Icon size={15} className={state === "pending" ? "spin" : undefined} />
            <span>{check.name}</span>
            {check.url ? (
              <a href={check.url} target="_blank" rel="noreferrer">
                Open run <ExternalLink size={12} />
              </a>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function Commits({ branch }: { branch: ReleaseBranch }) {
  return (
    <div className="commit-section">
      <p className="section-label">Recent commits · {branch.commits.length}</p>
      <ol className="commit-list">
        {branch.commits.map((commit, index) => (
          <li key={commit.sha} className={index === 0 ? "commit commit-head" : "commit"}>
            <span className="commit-dot" />
            <a href={commit.url} target="_blank" rel="noreferrer">
              {commit.message}
            </a>
            <p>
              <code>{commit.sha.slice(0, 8)}</code> · {commit.author} ·{" "}
              <time dateTime={commit.authoredAt}>
                {commit.authoredAt ? new Date(commit.authoredAt).toLocaleString() : "Unknown time"}
              </time>
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}

function BranchLane({
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
  const canVerify =
    branch.name === "staging" && branch.ciState === "success" && branch.gate.state !== "success";
  return (
    <article className={`branch branch-${branch.name}`}>
      <header className="branch-header">
        <div>
          <span className="layer-number">LAYER {meta.number}</span>
          <h2>{meta.label}</h2>
          <code>{branch.name}</code>
        </div>
        {branch.environmentUrl ? (
          <a
            className="button button-small"
            href={branch.environmentUrl}
            target="_blank"
            rel="noreferrer"
          >
            Open site <ExternalLink size={14} />
          </a>
        ) : (
          <span className="ci-only">CI only</span>
        )}
      </header>
      <div className="status-row">
        <StatusPill state={branch.ciState}>Checks: {branch.ciState}</StatusPill>
        {branch.name === "main" ? (
          <StatusPill state="success">Live branch</StatusPill>
        ) : (
          <StatusPill state={branch.gate.state}>
            {branch.name === "testing" ? "Agent approval" : "Manual verification"}
          </StatusPill>
        )}
      </div>
      <div className="head-commit">
        <p>
          <GitCommitHorizontal size={14} /> Head commit
        </p>
        <code>{branch.headSha}</code>
        {branch.gate.description ? <small>{branch.gate.description}</small> : null}
      </div>
      <div className="checks-panel">
        <p className="section-label">Checks & deployment failures</p>
        <Checks checks={branch.checks} />
      </div>
      {branch.blockedReason && branch.name !== "main" ? (
        <div className="blocked">
          <AlertTriangle size={16} /> <span>{branch.blockedReason}</span>
        </div>
      ) : null}
      {branch.name === "staging" ? (
        <button
          className="button button-secondary button-wide"
          disabled={!canVerify || busy}
          onClick={onVerify}
        >
          <ShieldCheck size={16} />
          {branch.gate.state === "success" ? "Staging verified" : "Mark staging verified"}
        </button>
      ) : null}
      {meta.target ? (
        <button
          className="button button-primary button-wide"
          disabled={!branch.canPromote || busy}
          onClick={onPromote}
        >
          <Rocket size={16} /> Promote to {meta.target}
        </button>
      ) : null}
      <Commits branch={branch} />
    </article>
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
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <h2>{title}</h2>
          <button aria-label="Close" onClick={onClose}>
            <X size={18} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
      </section>
    </div>
  );
}

function ReleaseUsers({
  onNotice,
}: {
  onNotice: (notice: { kind: "success" | "error"; text: string }) => void;
}) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const users = useQuery({ queryKey: ["release-users"], queryFn: releaseApi.users });
  const addUser = useMutation({
    mutationFn: () => releaseApi.addUser(email, displayName, password),
    onSuccess: () => {
      setEmail("");
      setDisplayName("");
      setPassword("");
      queryClient.invalidateQueries({ queryKey: ["release-users"] });
      onNotice({ kind: "success", text: "Release user added with scoped process access." });
    },
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    addUser.mutate();
  }
  return (
    <div className="users-panel">
      <p className="modal-copy">
        These accounts use the same True Grit login system, but receive only the Release Manager
        role. Share the temporary password securely.
      </p>
      <form className="user-form" onSubmit={submit}>
        <label htmlFor="release-user-name">Name</label>
        <input
          id="release-user-name"
          required
          minLength={2}
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
        />
        <label htmlFor="release-user-email">Email</label>
        <input
          id="release-user-email"
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <label htmlFor="release-user-password">Temporary password</label>
        <input
          id="release-user-password"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        {addUser.isError ? (
          <p className="error-banner" role="alert">
            {errorMessage(addUser.error, "Could not add release user.")}
          </p>
        ) : null}
        <button className="button button-primary" disabled={addUser.isPending}>
          {addUser.isPending ? <LoaderCircle className="spin" size={16} /> : <UserPlus size={16} />}
          Add release user
        </button>
      </form>
      <div className="release-user-list">
        <p className="section-label">Current release users</p>
        {users.isLoading ? (
          <p className="modal-copy">Loading users…</p>
        ) : users.isError ? (
          <p className="error-banner">{errorMessage(users.error, "Could not load users.")}</p>
        ) : users.data?.items.length ? (
          <ul>
            {users.data.items.map((releaseUser) => (
              <li key={releaseUser.id}>
                <span>
                  <strong>{releaseUser.displayName}</strong>
                  <small>{releaseUser.email}</small>
                </span>
                <StatusPill state={releaseUser.status === "active" ? "success" : "pending"}>
                  {releaseUser.status}
                </StatusPill>
              </li>
            ))}
          </ul>
        ) : (
          <p className="modal-copy">No additional release users yet.</p>
        )}
      </div>
    </div>
  );
}

function Cockpit({ user, onLogout }: { user: StaffUser; onLogout: () => void }) {
  const queryClient = useQueryClient();
  const [selectedPromotion, setSelectedPromotion] = useState<ReleaseBranch | null>(null);
  const [selectedVerification, setSelectedVerification] = useState<ReleaseBranch | null>(null);
  const [showUsers, setShowUsers] = useState(false);
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
  return (
    <div className="app-shell">
      <header className="topbar">
        <Brand />
        <div className="topbar-actions">
          <span>{user.displayName}</span>
          {user.isSuperAdmin ? (
            <button className="topbar-user-button" onClick={() => setShowUsers(true)}>
              <Users size={16} /> Process users
            </button>
          ) : null}
          <button className="icon-button" aria-label="Sign out" onClick={onLogout}>
            <LogOut size={17} />
          </button>
        </div>
      </header>
      <main id="main-content" className="page">
        <section className="page-heading">
          <div>
            <p className="eyebrow">Branch promotion system</p>
            <h1>Release Cockpit</h1>
            <p>
              Testing is reviewed by an agent. Staging is verified by you. Only then can main move.
            </p>
          </div>
          <button
            className="button button-secondary"
            disabled={dashboard.isFetching}
            onClick={() => dashboard.refetch()}
          >
            <RefreshCw size={16} className={dashboard.isFetching ? "spin" : undefined} /> Refresh
          </button>
        </section>
        <section className="process-strip" aria-label="Release sequence">
          {(["testing", "staging", "main"] as const).map((branch, index) => (
            <div className="process-step" key={branch}>
              {index ? <ArrowRight className="process-arrow" size={18} /> : null}
              <CircleDot size={17} />
              <span>
                <small>GATE {index + 1}</small>
                {BRANCH_META[branch].label}
              </span>
            </div>
          ))}
        </section>
        {notice ? (
          <div className={`notice notice-${notice.kind}`} role="status">
            {notice.kind === "success" ? <CheckCircle2 size={17} /> : <XCircle size={17} />}
            {notice.text}
            <button aria-label="Dismiss" onClick={() => setNotice(null)}>
              <X size={15} />
            </button>
          </div>
        ) : null}
        {dashboard.isError ? (
          <div className="fatal-error">
            <XCircle size={28} />
            <h2>Could not load GitHub</h2>
            <p>{errorMessage(dashboard.error, "Dashboard request failed.")}</p>
          </div>
        ) : dashboard.isLoading ? (
          <div className="loading">
            <LoaderCircle className="spin" size={28} /> Loading release state…
          </div>
        ) : (
          <>
            <div className="repo-row">
              <code>{dashboard.data?.repository}</code>
              <span>Auto-refresh · 60 seconds</span>
            </div>
            <section className="branches">
              {dashboard.data?.branches.map((branch) => (
                <BranchLane
                  key={branch.name}
                  branch={branch}
                  busy={busy}
                  onPromote={() => setSelectedPromotion(branch)}
                  onVerify={() => setSelectedVerification(branch)}
                />
              ))}
            </section>
          </>
        )}
      </main>
      {selectedPromotion ? (
        <Modal
          title={`Promote ${selectedPromotion.name} to ${BRANCH_META[selectedPromotion.name].target}`}
          onClose={() => setSelectedPromotion(null)}
        >
          <div className="modal-warning">
            <AlertTriangle size={18} />
            <p>
              This merges only <code>{selectedPromotion.headSha.slice(0, 12)}</code>. If the branch
              advances, the server rejects the action.
            </p>
          </div>
          <div className="modal-actions">
            <button className="button button-secondary" onClick={() => setSelectedPromotion(null)}>
              Cancel
            </button>
            <button
              className="button button-primary"
              disabled={promote.isPending}
              onClick={() => promote.mutate(selectedPromotion)}
            >
              {promote.isPending ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <ArrowRight size={16} />
              )}
              Confirm promotion
            </button>
          </div>
        </Modal>
      ) : null}
      {showUsers ? (
        <Modal title="Process access" onClose={() => setShowUsers(false)}>
          <ReleaseUsers onNotice={setNotice} />
        </Modal>
      ) : null}
      {selectedVerification ? (
        <Modal title="Verify the staging deployment" onClose={() => setSelectedVerification(null)}>
          <p className="modal-copy">
            Open the staging domain, test this exact release, then record what you checked. Main
            remains locked until this step passes.
          </p>
          {selectedVerification.environmentUrl ? (
            <a
              className="staging-link"
              href={selectedVerification.environmentUrl}
              target="_blank"
              rel="noreferrer"
            >
              Open staging website <ExternalLink size={14} />
            </a>
          ) : null}
          <label htmlFor="verification-notes">Verification notes</label>
          <input
            id="verification-notes"
            maxLength={100}
            value={notes}
            placeholder="Checkout, login, catalogue and mobile verified"
            onChange={(event) => setNotes(event.target.value)}
          />
          <div className="modal-actions">
            <button
              className="button button-secondary"
              onClick={() => setSelectedVerification(null)}
            >
              Cancel
            </button>
            <button
              className="button button-primary"
              disabled={notes.trim().length < 3 || verify.isPending}
              onClick={() => verify.mutate(selectedVerification)}
            >
              {verify.isPending ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}
              Record verification
            </button>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}

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
      <div className="loading full-screen">
        <LoaderCircle className="spin" size={28} /> Checking access…
      </div>
    );
  if (!authenticated) return <Login onAuthenticated={setUser} />;
  if (!authenticated.isSuperAdmin && !authenticated.permissions.includes("deployments.manage"))
    return (
      <main className="access-denied">
        <LockKeyhole size={34} />
        <h1>Release access required</h1>
        <p>Ask the True Grit owner to add you as a Process release user.</p>
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
