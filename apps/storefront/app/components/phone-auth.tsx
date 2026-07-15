/**
 * Mobile-number verification UI.
 *
 * One primitive — `PhoneVerifier` — drives every place a number gets proven:
 * signing in, creating an account, and adding a number to an account that
 * already exists. It owns the two-step dance (enter number, enter passcode),
 * the resend cooldown, and the error surface, and hands its caller a single-use
 * verification token. What that token is worth is the caller's decision, which
 * mirrors how the API splits `verify` from `complete`/`attach`.
 */

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import {
  AuthError,
  DEMO_OTP_CODE,
  authDemoMode,
  resendPhoneCode,
  startPhoneVerification,
  useCustomer,
  verifyPhoneCode,
  type PhoneChallenge,
  type PhoneIntent,
  type PhoneVerification,
} from "../lib/customer-auth";

const FIELD_CLASS =
  "min-h-11 w-full rounded-sm border border-line bg-canvas px-3 text-sm text-ink" +
  " placeholder:text-ink-muted focus:border-brand focus:outline-none";

const PRIMARY_BUTTON_CLASS =
  "min-h-11 w-full rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse" +
  " hover:opacity-95 disabled:opacity-60";

/** Matches the API's own cooldown (`otp_resend_cooldown_seconds`). Duplicated
 *  rather than fetched: it only drives a countdown label, and the server stays
 *  the authority — a client that lies just gets a 422. */
const RESEND_COOLDOWN_SECONDS = 30;

function messageFrom(caught: unknown, fallback: string): string {
  return caught instanceof AuthError ? caught.message : fallback;
}

/** Seconds remaining on a countdown that ticks to zero and stops. */
function useCountdown(from: number): [number, (seconds: number) => void] {
  const [remaining, setRemaining] = useState(from);

  useEffect(() => {
    if (remaining <= 0) return;
    const timer = window.setTimeout(() => setRemaining((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [remaining]);

  return [remaining, setRemaining];
}

export function PhoneVerifier({
  intent,
  onVerified,
  onCancel,
  heading,
  hint,
}: {
  intent: PhoneIntent;
  onVerified: (verification: PhoneVerification, phoneMasked: string) => void | Promise<void>;
  onCancel?: () => void;
  heading?: string;
  hint?: string;
}) {
  const [challenge, setChallenge] = useState<PhoneChallenge | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [cooldown, setCooldown] = useCountdown(0);
  const codeInputRef = useRef<HTMLInputElement>(null);

  // Move focus to the passcode box the moment it appears: the customer is
  // switching to their SMS app and back, and landing on the right field saves a
  // tap at exactly the point they are most likely to give up.
  useEffect(() => {
    if (challenge) codeInputRef.current?.focus();
  }, [challenge]);

  const sendCode = useCallback(
    async (phone: string) => {
      setError(null);
      setPending(true);
      try {
        const issued = await startPhoneVerification(phone, intent);
        setChallenge(issued);
        setCooldown(RESEND_COOLDOWN_SECONDS);
      } catch (caught) {
        setError(messageFrom(caught, "We couldn't send that code. Please try again."));
      } finally {
        setPending(false);
      }
    },
    [intent, setCooldown],
  );

  async function handlePhoneSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const phone = String(new FormData(event.currentTarget).get("phone") ?? "");
    await sendCode(phone);
  }

  async function handleCodeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!challenge) return;
    const code = String(new FormData(event.currentTarget).get("code") ?? "");
    setError(null);
    setPending(true);
    try {
      const verification = await verifyPhoneCode(challenge.challengeId, code);
      await onVerified(verification, challenge.phoneMasked);
    } catch (caught) {
      setError(messageFrom(caught, "That code didn't work. Please try again."));
    } finally {
      setPending(false);
    }
  }

  async function handleResend() {
    if (!challenge || cooldown > 0) return;
    setError(null);
    setPending(true);
    try {
      const reissued = await resendPhoneCode(challenge.challengeId);
      setChallenge(reissued);
      setCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (caught) {
      setError(messageFrom(caught, "We couldn't resend that code."));
    } finally {
      setPending(false);
    }
  }

  if (challenge === null) {
    return (
      <form className="space-y-3" onSubmit={handlePhoneSubmit}>
        {heading ? <p className="text-sm font-medium text-ink">{heading}</p> : null}
        {hint ? <p className="text-xs text-ink-muted">{hint}</p> : null}
        <label className="block space-y-1">
          <span className="text-xs font-medium text-ink-muted">Mobile number</span>
          <input
            name="phone"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            required
            className={FIELD_CLASS}
            placeholder="98765 43210"
            aria-describedby="phone-help"
          />
        </label>
        <p id="phone-help" className="text-xs text-ink-muted">
          Indian mobile numbers. We'll text you a 6-digit code.
        </p>

        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}

        <button type="submit" className={PRIMARY_BUTTON_CLASS} disabled={pending}>
          {pending ? "Sending code…" : "Send code"}
        </button>
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="min-h-9 w-full text-xs text-ink-muted underline-offset-4 hover:underline"
          >
            Cancel
          </button>
        ) : null}
      </form>
    );
  }

  return (
    <form className="space-y-3" onSubmit={handleCodeSubmit}>
      <div>
        <p className="text-sm font-medium text-ink">Enter the code</p>
        <p className="text-xs text-ink-muted">
          Sent to <span className="font-medium text-ink">{challenge.phoneMasked}</span>
        </p>
      </div>

      <label className="block space-y-1">
        <span className="text-xs font-medium text-ink-muted">6-digit code</span>
        <input
          ref={codeInputRef}
          name="code"
          type="text"
          // `one-time-code` is what lets iOS and Android offer the passcode from
          // the SMS straight above the keyboard.
          autoComplete="one-time-code"
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={8}
          required
          className={`${FIELD_CLASS} text-center font-mono text-lg tracking-[0.4em]`}
          placeholder="••••••"
        />
      </label>

      {authDemoMode ? (
        <p className="rounded-sm border border-dashed border-line px-3 py-2 text-xs text-ink-muted">
          Demo mode — no SMS is sent. Use code <span className="font-mono">{DEMO_OTP_CODE}</span>.
        </p>
      ) : null}

      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <button type="submit" className={PRIMARY_BUTTON_CLASS} disabled={pending}>
        {pending ? "Checking…" : "Verify"}
      </button>

      <div className="flex items-center justify-between text-xs">
        <button
          type="button"
          onClick={() => {
            setChallenge(null);
            setError(null);
          }}
          className="text-ink-muted underline-offset-4 hover:underline"
        >
          Change number
        </button>
        <button
          type="button"
          onClick={handleResend}
          disabled={pending || cooldown > 0 || challenge.resendsRemaining <= 0}
          className="text-brand underline-offset-4 hover:underline disabled:text-ink-muted disabled:no-underline"
        >
          {challenge.resendsRemaining <= 0
            ? "No resends left"
            : cooldown > 0
              ? `Resend in ${cooldown}s`
              : "Resend code"}
        </button>
      </div>
    </form>
  );
}

/**
 * Phone-first sign in and sign up.
 *
 * The name field appears only after verification, and only when the API reports
 * the number is new — asking earlier would mean guessing whether the account
 * exists, which is exactly what `start` refuses to disclose.
 */
export function PhoneAuthPanel({ onDone }: { onDone: () => void }) {
  const [verification, setVerification] = useState<PhoneVerification | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const { loginWithPhone } = useCustomer();

  const handleVerified = useCallback(
    async (result: PhoneVerification) => {
      if (!result.registered) {
        // New number: fall through to the name step rather than signing in.
        setVerification(result);
        return;
      }
      setPending(true);
      try {
        await loginWithPhone(result.verificationToken);
        onDone();
      } catch (caught) {
        setError(messageFrom(caught, "We couldn't sign you in. Please try again."));
        setPending(false);
      }
    },
    [loginWithPhone, onDone],
  );

  async function handleNameSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!verification) return;
    const name = String(new FormData(event.currentTarget).get("name") ?? "");
    setError(null);
    setPending(true);
    try {
      await loginWithPhone(verification.verificationToken, name);
      onDone();
    } catch (caught) {
      setError(messageFrom(caught, "We couldn't create your account. Please try again."));
      setPending(false);
    }
  }

  if (verification !== null) {
    return (
      <form className="space-y-3" onSubmit={handleNameSubmit}>
        <div>
          <p className="text-sm font-medium text-ink">Almost there</p>
          <p className="text-xs text-ink-muted">Your number is verified. What should we call you?</p>
        </div>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-ink-muted">Name</span>
          <input
            name="name"
            type="text"
            autoComplete="name"
            required
            autoFocus
            className={FIELD_CLASS}
            placeholder="Priya Sharma"
          />
        </label>
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}
        <button type="submit" className={PRIMARY_BUTTON_CLASS} disabled={pending}>
          {pending ? "Creating account…" : "Create account"}
        </button>
      </form>
    );
  }

  return (
    <div className="space-y-3">
      <PhoneVerifier
        intent="signin"
        onVerified={handleVerified}
        hint="No password needed — we'll text you a code."
      />
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/**
 * Asks an existing customer to add a mobile, and lets them decline.
 *
 * Skipping is remembered per browser, not per account: the point is to stop
 * nagging someone who has already said no this session, and checkout — where a
 * reachable number actually matters — asks again regardless.
 */
export function AddPhonePrompt({ onDone }: { onDone?: () => void }) {
  const { customer, attachPhone } = useCustomer();
  const [dismissed, setDismissed] = useState(() => readPhonePromptDismissed());
  const [error, setError] = useState<string | null>(null);
  const [started, setStarted] = useState(false);

  const handleVerified = useCallback(
    async (result: PhoneVerification) => {
      setError(null);
      try {
        await attachPhone(result.verificationToken);
        onDone?.();
      } catch (caught) {
        setError(messageFrom(caught, "We couldn't add that number."));
      }
    },
    [attachPhone, onDone],
  );

  if (customer === null || customer.phoneVerified || dismissed) return null;

  if (!started) {
    return (
      <div className="space-y-2 rounded-sm border border-line bg-canvas px-3 py-3">
        <p className="text-sm font-medium text-ink">Add your mobile number</p>
        <p className="text-xs text-ink-muted">
          We use it for delivery updates. You'll need a verified number to check out.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setStarted(true)}
            className="min-h-9 flex-1 rounded-sm bg-brand px-3 text-xs font-medium text-ink-inverse hover:opacity-95"
          >
            Add number
          </button>
          <button
            type="button"
            onClick={() => {
              writePhonePromptDismissed();
              setDismissed(true);
            }}
            className="min-h-9 rounded-sm border border-line px-3 text-xs text-ink-muted hover:bg-surface"
          >
            Not now
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-sm border border-line bg-canvas px-3 py-3">
      <PhoneVerifier
        intent="attach"
        onVerified={handleVerified}
        onCancel={() => setStarted(false)}
        heading="Add your mobile number"
      />
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

const PHONE_PROMPT_DISMISSED_KEY = "truegrit.customer.phonePromptDismissed";

function readPhonePromptDismissed(): boolean {
  if (typeof window === "undefined") return false;
  return window.sessionStorage.getItem(PHONE_PROMPT_DISMISSED_KEY) === "1";
}

function writePhonePromptDismissed(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(PHONE_PROMPT_DISMISSED_KEY, "1");
}
