import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router";

import { Button, Field, Input } from "../components/ui";
import {
  ADMIN_AUTH_EXPIRED_EVENT,
  ApiError,
  api,
  demoMode,
  describeRateLimitError,
} from "../lib/api";
import { useMe } from "../lib/permissions";
import { T } from "../lib/i18n";

function isUnauthorizedError(error: unknown) {
  if (error instanceof ApiError) return error.status === 401;
  if (typeof error !== "object" || error === null) return false;
  const status = (error as { status?: unknown }).status;
  return Number(status) === 401;
}

function ForgotPassword() {
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(false);
  const mutation = useMutation({
    mutationFn: (email: string) => api.requestPasswordReset(email),
    onSuccess: () => setDone(true),
  });
  const error =
    mutation.error instanceof ApiError
      ? describeRateLimitError(mutation.error)
      : "Could not send the reset link. Try again.";

  if (!open) {
    return (
      <button
        type="button"
        className="text-sm text-brand underline-offset-4 hover:underline"
        onClick={() => setOpen(true)}
      >
        <T>Forgot password?</T>
      </button>
    );
  }
  if (done) {
    return (
      <p className="text-sm text-ink-muted">
        <T>If that email has an account, a reset link is on its way.</T>
      </p>
    );
  }
  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate(String(new FormData(event.currentTarget).get("email") ?? ""));
      }}
    >
      <Field label="Email for reset link" htmlFor="reset-email">
        <Input id="reset-email" name="email" type="email" required />
      </Field>
      {mutation.isError ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <Button type="submit" variant="secondary" disabled={mutation.isPending}>
        {mutation.isPending ? <T>{"Sending…"}</T> : <T>{"Send reset link"}</T>}
      </Button>
    </form>
  );
}

export function AdminResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const mutation = useMutation({
    mutationFn: (password: string) => api.confirmPasswordReset(token, password),
    onSuccess: () => navigate("/login", { replace: true }),
  });
  const error =
    mutation.error instanceof ApiError ? mutation.error.message : "Could not reset the password.";

  return (
    <main className="flex min-h-screen items-center justify-center bg-canvas px-6">
      <div className="w-full max-w-sm">
        <h1 className="font-display text-2xl text-ink">
          <T>Set a new password</T>
        </h1>
        {!token ? (
          <p className="mt-3 text-sm text-danger">
            <T>This reset link is missing its token.</T>
          </p>
        ) : (
          <form
            className="mt-5 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              mutation.mutate(String(new FormData(event.currentTarget).get("password") ?? ""));
            }}
          >
            <Field label="New password" htmlFor="new-password">
              <Input
                id="new-password"
                name="password"
                type="password"
                minLength={10}
                autoComplete="new-password"
                required
              />
            </Field>
            {mutation.isError ? (
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
            ) : null}
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? <T>{"Saving…"}</T> : <T>{"Reset password"}</T>}
            </Button>
            <Link
              to="/login"
              className="block text-sm text-brand underline-offset-4 hover:underline"
            >
              <T>Back to sign in</T>
            </Link>
          </form>
        )}
      </div>
    </main>
  );
}

export function AdminLoginPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/";
  const mutation = useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.login(email, password),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate(from, { replace: true });
    },
  });
  const error =
    mutation.error instanceof ApiError
      ? describeRateLimitError(mutation.error)
      : "Sign in failed. Try again.";

  return (
    <main className="grid min-h-screen grid-cols-1 bg-canvas lg:grid-cols-[minmax(0,1fr)_28rem]">
      <section className="flex min-h-[18rem] items-end bg-brand px-6 py-10 text-ink-inverse lg:min-h-screen lg:px-12">
        <div className="max-w-xl">
          {/* Same mark as the storefront and the sidebar — the first screen of
              the console should already look like the product it manages. */}
          <div className="flex items-center gap-3">
            <img
              src="/brand/true-grit-mark.webp"
              alt=""
              width={40}
              height={40}
              className="h-10 w-10 rounded-full object-cover"
            />
            <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-75">
              <T>True Grit Admin</T>
            </p>
          </div>
          <h1 className="mt-4 font-display text-4xl leading-tight lg:text-5xl">
            <T>Live marketplace control room.</T>
          </h1>
          <p className="mt-4 max-w-md text-sm opacity-80">
            <T>
              Catalogue, inventory, content, orders, users and audit events in one operating
              surface.
            </T>
          </p>
        </div>
      </section>

      <section className="flex items-center px-6 py-10">
        <div className="w-full">
          <div className="mb-8 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-sm bg-subtle text-brand">
              <ShieldCheck size={20} />
            </span>
            <div>
              <h2 className="font-display text-2xl text-ink">
                <T>Staff sign in</T>
              </h2>
              <p className="text-sm text-ink-muted">
                {demoMode ? <T>{"Demo console access"}</T> : <T>{"Connected API session"}</T>}
              </p>
            </div>
          </div>

          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              mutation.mutate({
                email: String(form.get("email") ?? ""),
                password: String(form.get("password") ?? ""),
              });
            }}
          >
            <Field label="Email" htmlFor="admin-email">
              <Input
                id="admin-email"
                name="email"
                type="email"
                autoComplete="username"
                defaultValue={demoMode ? "admin@truegrit.test" : ""}
                required
              />
            </Field>
            <Field label="Password" htmlFor="admin-password">
              <Input
                id="admin-password"
                name="password"
                type="password"
                autoComplete="current-password"
                defaultValue={demoMode ? "admin123" : ""}
                required
              />
            </Field>
            {mutation.isError ? (
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
            ) : null}
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? <T>{"Signing in"}</T> : <T>{"Sign in"}</T>}
            </Button>
          </form>

          <div className="mt-4">
            <ForgotPassword />
          </div>
        </div>
      </section>
    </main>
  );
}

export function RequireAdminAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const me = useMe();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  // useLocation() returns a new object on every navigation; reading it
  // through a ref instead of a dependency means the listener below is
  // registered once for the component's lifetime rather than torn down and
  // re-added on every route change, while `handleAuthExpired` still redirects
  // back to whichever page was current when the 401 actually happened.
  const locationRef = useRef(location);
  locationRef.current = location;

  useEffect(() => {
    function handleAuthExpired() {
      queryClient.clear();
      navigate("/login", { replace: true, state: { from: locationRef.current } });
    }

    window.addEventListener(ADMIN_AUTH_EXPIRED_EVENT, handleAuthExpired);
    return () => window.removeEventListener(ADMIN_AUTH_EXPIRED_EVENT, handleAuthExpired);
  }, [navigate, queryClient]);

  if (me.isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-canvas px-6">
        <div className="text-sm text-ink-muted">
          <T>Checking session</T>
        </div>
      </main>
    );
  }

  if (isUnauthorizedError(me.error)) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (me.isError) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-canvas px-6 text-center">
        <div>
          <p className="font-medium text-ink">
            <T>Admin API is unavailable</T>
          </p>
          <p className="mt-1 text-sm text-ink-muted">
            <T>Refresh once the API is back online.</T>
          </p>
          <div className="mt-4 flex justify-center gap-2">
            <Button type="button" variant="secondary" onClick={() => void me.refetch()}>
              <T>Retry</T>
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={() => navigate("/login", { replace: true, state: { from: location } })}
            >
              <T>Sign in</T>
            </Button>
          </div>
        </div>
      </main>
    );
  }

  return children;
}
