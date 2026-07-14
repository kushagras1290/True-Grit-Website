import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router";

import { Button, Field, Input } from "../components/ui";
import { ApiError, api, demoMode } from "../lib/api";
import { useMe } from "../lib/permissions";

function ForgotPassword() {
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(false);
  const mutation = useMutation({
    mutationFn: (email: string) => api.requestPasswordReset(email),
    onSuccess: () => setDone(true),
  });

  if (!open) {
    return (
      <button
        type="button"
        className="text-sm text-brand underline-offset-4 hover:underline"
        onClick={() => setOpen(true)}
      >
        Forgot password?
      </button>
    );
  }
  if (done) {
    return (
      <p className="text-sm text-ink-muted">
        If that email has an account, a reset link is on its way.
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
      <Button type="submit" variant="secondary" disabled={mutation.isPending}>
        {mutation.isPending ? "Sending…" : "Send reset link"}
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
        <h1 className="font-display text-2xl text-ink">Set a new password</h1>
        {!token ? (
          <p className="mt-3 text-sm text-danger">This reset link is missing its token.</p>
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
              {mutation.isPending ? "Saving…" : "Reset password"}
            </Button>
            <Link
              to="/login"
              className="block text-sm text-brand underline-offset-4 hover:underline"
            >
              Back to sign in
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
    mutationFn: async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      await api.login(String(form.get("email") ?? ""), String(form.get("password") ?? ""));
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate(from, { replace: true });
    },
  });
  const error =
    mutation.error instanceof ApiError ? mutation.error.message : "Sign in failed. Try again.";

  return (
    <main className="grid min-h-screen grid-cols-1 bg-canvas lg:grid-cols-[minmax(0,1fr)_28rem]">
      <section className="flex min-h-[18rem] items-end bg-brand px-6 py-10 text-ink-inverse lg:min-h-screen lg:px-12">
        <div className="max-w-xl">
          <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-75">
            True Grit Admin
          </p>
          <h1 className="mt-4 font-display text-4xl leading-tight lg:text-5xl">
            Live marketplace control room.
          </h1>
          <p className="mt-4 max-w-md text-sm opacity-80">
            Catalogue, inventory, content, orders, users and audit events in one operating surface.
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
              <h2 className="font-display text-2xl text-ink">Staff sign in</h2>
              <p className="text-sm text-ink-muted">
                {demoMode ? "Demo console access" : "Connected API session"}
              </p>
            </div>
          </div>

          <form className="space-y-4" onSubmit={(event) => mutation.mutate(event)}>
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
              {mutation.isPending ? "Signing in" : "Sign in"}
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

  if (me.isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-canvas px-6">
        <div className="text-sm text-ink-muted">Checking session</div>
      </main>
    );
  }

  if (me.error instanceof ApiError && me.error.status === 401) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (me.isError) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-canvas px-6 text-center">
        <div>
          <p className="font-medium text-ink">Admin API is unavailable</p>
          <p className="mt-1 text-sm text-ink-muted">Refresh once the API is back online.</p>
        </div>
      </main>
    );
  }

  return children;
}
