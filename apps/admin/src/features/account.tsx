/**
 * Your Account: identity and self-service password change.
 *
 * Deliberately gated on no permission — a farm-scoped sub-admin holds no users.*
 * permission but still owns their own credential.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useToast } from "../components/toast";
import { Button, Field, PageHeader, PasswordInput } from "../components/ui";
import { ApiError, api, demoMode } from "../lib/api";
import { useMe } from "../lib/permissions";
import { T } from "../lib/i18n";

// Mirrors the API's PASSWORD_MIN_LENGTH. The API is the enforcement point; this
// only saves a round trip.
const PASSWORD_MIN_LENGTH = 10;

const passwordSchema = z
  .object({
    currentPassword: z.string().min(1, "Enter your current password."),
    newPassword: z
      .string()
      .min(PASSWORD_MIN_LENGTH, `Use at least ${PASSWORD_MIN_LENGTH} characters.`)
      .max(256),
    confirmPassword: z.string(),
  })
  .refine((values) => values.newPassword === values.confirmPassword, {
    message: "The two new passwords do not match.",
    path: ["confirmPassword"],
  })
  .refine((values) => values.newPassword !== values.currentPassword, {
    message: "The new password must differ from the current one.",
    path: ["newPassword"],
  });

type PasswordForm = z.infer<typeof passwordSchema>;

export function AccountPage() {
  const toast = useToast();
  const { data: me } = useMe();
  const form = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { currentPassword: "", newPassword: "", confirmPassword: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: PasswordForm) =>
      api.changePassword(values.currentPassword, values.newPassword),
    onSuccess: () => {
      form.reset();
      toast.success("Password changed. Your other sessions have been signed out.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not change the password."),
  });

  return (
    <div>
      <PageHeader
        title="Your Account"
        description="The identity this console signs you in as, and the password it uses."
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,28rem)_minmax(0,22rem)]">
        <form
          className="space-y-4"
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
        >
          <section className="space-y-1 border-t border-line pt-5">
            <h2 className="font-display text-lg text-ink">
              <T>Signed in as</T>
            </h2>
            <p className="text-sm text-ink">{me?.displayName ?? "—"}</p>
            <p className="text-sm text-ink-muted">{me?.email ?? "—"}</p>
            {me?.farmName ? (
              <p className="text-sm text-ink-muted">
                <T>Farm ·</T> {me.farmName}
              </p>
            ) : null}
          </section>

          <section className="space-y-4 border-t border-line pt-5">
            <div>
              <h2 className="font-display text-lg text-ink">
                <T>Change password</T>
              </h2>
              <p className="text-sm text-ink-muted">
                <T>
                  Your current password is required, and every other signed-in session is ended.
                </T>
              </p>
            </div>

            <Field
              label="Current password"
              htmlFor="currentPassword"
              error={form.formState.errors.currentPassword?.message}
            >
              <PasswordInput
                id="currentPassword"
                autoComplete="current-password"
                {...form.register("currentPassword")}
              />
            </Field>

            <Field
              label="New password"
              htmlFor="newPassword"
              error={form.formState.errors.newPassword?.message}
            >
              <PasswordInput
                id="newPassword"
                autoComplete="new-password"
                {...form.register("newPassword")}
              />
            </Field>

            <Field
              label="Confirm new password"
              htmlFor="confirmPassword"
              error={form.formState.errors.confirmPassword?.message}
            >
              <PasswordInput
                id="confirmPassword"
                autoComplete="new-password"
                {...form.register("confirmPassword")}
              />
            </Field>

            <Button type="submit" variant="primary" disabled={mutation.isPending}>
              {mutation.isPending ? <T>{"Saving…"}</T> : <T>{"Change password"}</T>}
            </Button>
          </section>
        </form>

        <aside className="space-y-3 border-t border-line pt-5 text-sm text-ink-muted">
          <h2 className="font-display text-lg text-ink">
            <T>How this password works</T>
          </h2>
          <p>
            <T>The owner login starts from</T>{" "}
            <code className="text-xs">
              <T>ADMIN_LOGIN_EMAIL</T>
            </code>{" "}
            and{" "}
            <code className="text-xs">
              <T>ADMIN_LOGIN_PASSWORD</T>
            </code>{" "}
            <T>in the API's</T>{" "}
            <code className="text-xs">
              <T>.env</T>
            </code>
            <T>
              , but only until you sign in once. After that this account owns its password, and
              editing
            </T>{" "}
            <code className="text-xs">
              <T>.env</T>
            </code>{" "}
            <T>
              no longer changes the login — so a password you set here really does replace the old
              one.
            </T>
          </p>
          <p>
            <T>Locked out? Use</T>{" "}
            <span className="text-ink">
              <T>Forgot password?</T>
            </span>{" "}
            <T>on the sign-in page. The reset link goes to the address above.</T>
          </p>
          {demoMode ? (
            <p className="text-warning">
              <T>Demo mode has no API, so a password change cannot be saved. Set</T>{" "}
              <code className="text-xs">VITE_API_URL</code> <T>to connect.</T>
            </p>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
