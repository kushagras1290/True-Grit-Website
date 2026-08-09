/**
 * Storefront customer authentication.
 *
 * With `VITE_API_URL` set, the browser talks to the FastAPI customer-auth
 * endpoints with cookies (`credentials: "include"`). Without it — demo-data
 * mode — sessions are faked in localStorage so the storefront is fully
 * reviewable before the API exists, mirroring the catalogue's demo behaviour.
 *
 * Google sign-in uses Google Identity Services: the browser obtains a signed
 * ID token and posts it to the API, which verifies it server-side. Only the
 * public Google client id is delivered through the Worker's runtime bindings
 * (with `VITE_GOOGLE_CLIENT_ID` as a local-build fallback) — never a secret.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  getPublicApiUrl,
  getPublicFacebookAppId,
  getPublicGoogleClientId,
  hasPublicApiUrl,
} from "./public-env";
import { LocalizedText } from "./i18n/localized-text";

export const authDemoMode = !hasPublicApiUrl();

const DEMO_SESSION_KEY = "truegrit.customer.session";
const GIS_SCRIPT_SRC = "https://accounts.google.com/gsi/client";
const FACEBOOK_SDK_SRC = "https://connect.facebook.net/en_US/sdk.js";

export interface CustomerAccount {
  id: string;
  displayName: string;
  /** Null for accounts that signed up with a mobile number and never gave an
   *  address. The API nulls its internal placeholder, so this is never fake. */
  email: string | null;
  /** E.164, and only ever present once verified by SMS passcode. */
  phone: string | null;
  phoneVerified: boolean;
}

export interface RegisterInput {
  name: string;
  email: string;
  password: string;
  /** Single-use proof from `verifyPhoneCode`. Required unless the API has
   *  `phone_required_at_registration` turned off. */
  phoneVerificationToken?: string;
}

/** A passcode has been sent; the UI now collects the code. */
export interface PhoneChallenge {
  challengeId: string;
  /** "+91 ••••• 43210" — safe to display, enough to spot a typo. */
  phoneMasked: string;
  expiresAt: string;
  resendsRemaining: number;
}

export interface PhoneVerification {
  verificationToken: string;
  expiresAt: string;
  /** Whether this number already has an account. Only known after the caller
   *  proves they hold the handset, so it is safe to branch the UI on. */
  registered: boolean;
}

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export class AuthError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
    this.name = "AuthError";
  }
}

interface ApiErrorBody {
  error?: { code?: string; message?: string };
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl = getPublicApiUrl();
  if (!apiUrl) {
    throw new AuthError("This action needs the live API.", 503, "demo_mode");
  }
  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: init?.body
      ? { "content-type": "application/json", ...(init?.headers ?? {}) }
      : init?.headers,
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null;
    throw new AuthError(
      body?.error?.message ?? `Request failed (${response.status})`,
      response.status,
      body?.error?.code ?? "request_failed",
    );
  }
  return (await response.json()) as T;
}

// --- Demo-mode session (no API configured) ----------------------------------

function readDemoSession(): CustomerAccount | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(DEMO_SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CustomerAccount;
  } catch {
    window.localStorage.removeItem(DEMO_SESSION_KEY);
    return null;
  }
}

function writeDemoSession(customer: CustomerAccount): CustomerAccount {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(DEMO_SESSION_KEY, JSON.stringify(customer));
  }
  return customer;
}

/**
 * `phone` defaults to null so demo Google/Facebook sign-ins land without a
 * number — which is the real-world shape (a federated identity carries an email,
 * never a mobile) and keeps the "add your number" prompt reviewable offline.
 */
function demoCustomerFromEmail(
  email: string,
  name?: string,
  phone: string | null = null,
): CustomerAccount {
  const local = email.split("@")[0] ?? "member";
  const displayName =
    name?.trim() || local.replace(/[._-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return {
    id: `demo_${local}`,
    displayName: displayName || "Organic member",
    email,
    phone,
    phoneVerified: phone !== null,
  };
}

function demoCustomerFromPhone(phone: string, name?: string): CustomerAccount {
  return {
    id: `demo_${phone.replace(/\D/g, "")}`,
    displayName: name?.trim() || "Organic member",
    email: null,
    phone,
    phoneVerified: true,
  };
}

// --- Mobile number verification ---------------------------------------------

/**
 * Demo mode fakes the SMS round-trip: no API means no provider, but the OTP
 * screens still need to be reviewable. The passcode is fixed and announced in
 * the UI, and none of this code path exists once `VITE_API_URL` is set.
 */
export const DEMO_OTP_CODE = "000000";
const DEMO_PHONE_E164 = "+919876543210";
const DEMO_CHALLENGE_PREFIX = "demo_challenge_";
const DEMO_TOKEN_PREFIX = "demo_token_";

function demoMaskPhone(phone: string): string {
  const digits = phone.replace(/\D/g, "");
  if (digits.length <= 4) return `+${"•".repeat(digits.length)}`;
  return `+${digits.slice(0, 2)} ${"•".repeat(Math.max(0, digits.length - 6))} ${digits.slice(-4)}`;
}

function demoChallenge(phone: string): PhoneChallenge {
  return {
    challengeId: `${DEMO_CHALLENGE_PREFIX}${encodeURIComponent(phone)}`,
    phoneMasked: demoMaskPhone(phone),
    expiresAt: new Date(Date.now() + 5 * 60_000).toISOString(),
    resendsRemaining: 3,
  };
}

/** Where the passcode is being sent from, which decides what the resulting
 *  proof is allowed to do. Mirrors the API's challenge purposes. */
export type PhoneIntent = "signin" | "register" | "attach";

const START_PATHS: Record<PhoneIntent, string> = {
  signin: "/v1/public/auth/phone/start",
  register: "/v1/public/auth/phone/register/start",
  attach: "/v1/public/auth/phone/attach/start",
};

/** Text a passcode to `phone`. The response is identical whether or not the
 *  number has an account — that is deliberate on the API side. */
export async function startPhoneVerification(
  phone: string,
  intent: PhoneIntent,
): Promise<PhoneChallenge> {
  if (authDemoMode) return demoChallenge(phone);
  return apiRequest<PhoneChallenge>(START_PATHS[intent], {
    method: "POST",
    body: JSON.stringify({ phone }),
  });
}

export async function resendPhoneCode(challengeId: string): Promise<PhoneChallenge> {
  if (authDemoMode) {
    const phone = decodeURIComponent(challengeId.replace(DEMO_CHALLENGE_PREFIX, ""));
    return demoChallenge(phone);
  }
  return apiRequest<PhoneChallenge>("/v1/public/auth/phone/resend", {
    method: "POST",
    body: JSON.stringify({ challengeId }),
  });
}

/** Exchange a passcode for single-use proof of the number. */
export async function verifyPhoneCode(
  challengeId: string,
  code: string,
): Promise<PhoneVerification> {
  if (authDemoMode) {
    if (code.trim() !== DEMO_OTP_CODE) {
      throw new AuthError(`In demo mode the code is ${DEMO_OTP_CODE}.`, 422, "validation_error");
    }
    const phone = decodeURIComponent(challengeId.replace(DEMO_CHALLENGE_PREFIX, ""));
    return {
      verificationToken: `${DEMO_TOKEN_PREFIX}${encodeURIComponent(phone)}`,
      expiresAt: new Date(Date.now() + 15 * 60_000).toISOString(),
      registered: readDemoSession()?.phone === phone,
    };
  }
  return apiRequest<PhoneVerification>("/v1/public/auth/phone/verify", {
    method: "POST",
    body: JSON.stringify({ challengeId, code }),
  });
}

// --- Password reset ---------------------------------------------------------

// --- Password reset ---------------------------------------------------------

export async function requestPasswordReset(email: string): Promise<void> {
  if (authDemoMode) return;
  await apiRequest("/v1/public/auth/password-reset", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function confirmPasswordReset(token: string, newPassword: string): Promise<void> {
  if (authDemoMode) {
    throw new AuthError("Password reset needs the live API (set VITE_API_URL).", 503, "demo_mode");
  }
  await apiRequest("/v1/public/auth/password-reset/confirm", {
    method: "POST",
    body: JSON.stringify({ token, newPassword }),
  });
}

// --- Context ----------------------------------------------------------------

interface CustomerContextValue {
  customer: CustomerAccount | null;
  status: AuthStatus;
  register: (input: RegisterInput) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  loginWithFacebook: (accessToken: string) => Promise<void>;
  /** Exchange proof of a mobile for a session — signing in if the number is
   *  known, creating the account if it is not (hence `name`). */
  loginWithPhone: (verificationToken: string, name?: string) => Promise<void>;
  /** Attach a verified mobile to the account already signed in. */
  attachPhone: (verificationToken: string) => Promise<void>;
  logout: () => Promise<void>;
}

const CustomerContext = createContext<CustomerContextValue | null>(null);

export function CustomerProvider({ children }: { children: ReactNode }) {
  const [customer, setCustomer] = useState<CustomerAccount | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let active = true;
    async function resolveSession() {
      if (authDemoMode) {
        const existing = readDemoSession();
        if (active) {
          setCustomer(existing);
          setStatus(existing ? "authenticated" : "anonymous");
        }
        return;
      }
      try {
        const { customer: me } = await apiRequest<{ customer: CustomerAccount | null }>(
          "/v1/public/auth/session",
        );
        if (active) {
          setCustomer(me);
          setStatus(me ? "authenticated" : "anonymous");
        }
      } catch {
        if (active) {
          setCustomer(null);
          setStatus("anonymous");
        }
      }
    }
    void resolveSession();
    return () => {
      active = false;
    };
  }, []);

  const register = useCallback(async (input: RegisterInput) => {
    if (authDemoMode) {
      // Registration always carries a verified number, so the demo session does
      // too — otherwise the "add your number" prompt would fire immediately.
      setCustomer(
        writeDemoSession(demoCustomerFromEmail(input.email, input.name, DEMO_PHONE_E164)),
      );
      setStatus("authenticated");
      return;
    }
    const { customer: account } = await apiRequest<{ customer: CustomerAccount }>(
      "/v1/public/auth/register",
      { method: "POST", body: JSON.stringify(input) },
    );
    setCustomer(account);
    setStatus("authenticated");
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    if (authDemoMode) {
      setCustomer(writeDemoSession(demoCustomerFromEmail(email, undefined, DEMO_PHONE_E164)));
      setStatus("authenticated");
      return;
    }
    const { customer: account } = await apiRequest<{ customer: CustomerAccount }>(
      "/v1/public/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
    );
    setCustomer(account);
    setStatus("authenticated");
  }, []);

  const loginWithGoogle = useCallback(async (credential: string) => {
    if (authDemoMode) {
      setCustomer(writeDemoSession(demoCustomerFromEmail("member@gmail.com", "Google member")));
      setStatus("authenticated");
      return;
    }
    const { customer: account } = await apiRequest<{ customer: CustomerAccount }>(
      "/v1/public/auth/google",
      { method: "POST", body: JSON.stringify({ credential }) },
    );
    setCustomer(account);
    setStatus("authenticated");
  }, []);

  const loginWithFacebook = useCallback(async (accessToken: string) => {
    if (authDemoMode) {
      setCustomer(
        writeDemoSession(demoCustomerFromEmail("member@facebook.com", "Facebook member")),
      );
      setStatus("authenticated");
      return;
    }
    const { customer: account } = await apiRequest<{ customer: CustomerAccount }>(
      "/v1/public/auth/facebook",
      { method: "POST", body: JSON.stringify({ accessToken }) },
    );
    setCustomer(account);
    setStatus("authenticated");
  }, []);

  const loginWithPhone = useCallback(async (verificationToken: string, name?: string) => {
    if (authDemoMode) {
      const phone = decodeURIComponent(verificationToken.replace(DEMO_TOKEN_PREFIX, ""));
      setCustomer(writeDemoSession(demoCustomerFromPhone(phone, name)));
      setStatus("authenticated");
      return;
    }
    const { customer: account } = await apiRequest<{ customer: CustomerAccount }>(
      "/v1/public/auth/phone/complete",
      { method: "POST", body: JSON.stringify({ verificationToken, name }) },
    );
    setCustomer(account);
    setStatus("authenticated");
  }, []);

  const attachPhone = useCallback(async (verificationToken: string) => {
    if (authDemoMode) {
      const phone = decodeURIComponent(verificationToken.replace(DEMO_TOKEN_PREFIX, ""));
      setCustomer((current) =>
        current ? writeDemoSession({ ...current, phone, phoneVerified: true }) : current,
      );
      return;
    }
    const { customer: account } = await apiRequest<{ customer: CustomerAccount }>(
      "/v1/public/auth/phone/attach",
      { method: "POST", body: JSON.stringify({ verificationToken }) },
    );
    setCustomer(account);
  }, []);

  const logout = useCallback(async () => {
    if (authDemoMode) {
      if (typeof window !== "undefined") window.localStorage.removeItem(DEMO_SESSION_KEY);
    } else {
      await apiRequest<{ ok: boolean }>("/v1/public/auth/logout", { method: "POST" }).catch(
        () => undefined,
      );
    }
    setCustomer(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo<CustomerContextValue>(
    () => ({
      customer,
      status,
      register,
      login,
      loginWithGoogle,
      loginWithFacebook,
      loginWithPhone,
      attachPhone,
      logout,
    }),
    [
      customer,
      status,
      register,
      login,
      loginWithGoogle,
      loginWithFacebook,
      loginWithPhone,
      attachPhone,
      logout,
    ],
  );

  return <CustomerContext.Provider value={value}>{children}</CustomerContext.Provider>;
}

export function useCustomer(): CustomerContextValue {
  const context = useContext(CustomerContext);
  if (!context) throw new Error("useCustomer must be used inside CustomerProvider");
  return context;
}

// --- Google Identity Services -----------------------------------------------

interface GoogleCredentialResponse {
  credential: string;
}

interface GoogleAccountsId {
  initialize: (config: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
  }) => void;
  renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void;
}

interface FacebookLoginResponse {
  status?: string;
  authResponse?: {
    accessToken?: string;
  };
}

interface FacebookSdk {
  init: (config: { appId: string; cookie: boolean; xfbml: boolean; version: string }) => void;
  login: (
    callback: (response: FacebookLoginResponse) => void,
    options: { scope: string; return_scopes: boolean },
  ) => void;
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleAccountsId } };
    FB?: FacebookSdk;
    fbAsyncInit?: () => void;
  }
}

let gisScriptPromise: Promise<void> | null = null;

function loadGoogleIdentityServices(): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("no window"));
  if (window.google?.accounts?.id) return Promise.resolve();
  if (gisScriptPromise) return gisScriptPromise;
  gisScriptPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GIS_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => {
      gisScriptPromise = null;
      reject(new Error("Failed to load Google Identity Services."));
    };
    document.head.appendChild(script);
  });
  return gisScriptPromise;
}

/**
 * Renders the official Google button when a client id is configured. In demo
 * mode it renders a styled stand-in that triggers the faked Google login. When
 * an API is configured but no client id is present, it renders a disabled hint.
 */
export function GoogleSignInButton({
  onCredential,
  onError,
}: {
  onCredential: (credential: string) => void;
  onError?: (message: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const googleClientId = getPublicGoogleClientId();

  useEffect(() => {
    if (!googleClientId) return;
    let cancelled = false;
    loadGoogleIdentityServices()
      .then(() => {
        if (cancelled || !containerRef.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: googleClientId,
          callback: (response) => onCredential(response.credential),
        });
        window.google.accounts.id.renderButton(containerRef.current, {
          theme: "outline",
          size: "large",
          text: "continue_with",
          width: 300,
        });
      })
      .catch(() => onError?.("Could not load Google sign-in. Please try again."));
    return () => {
      cancelled = true;
    };
  }, [googleClientId, onCredential, onError]);

  if (googleClientId) {
    return <div ref={containerRef} className="flex min-h-11 justify-center" />;
  }

  if (authDemoMode) {
    return (
      <button
        type="button"
        className="flex min-h-11 w-full items-center justify-center gap-2 rounded-sm border border-line-strong bg-canvas px-4 text-sm font-medium text-ink hover:bg-subtle/50"
        onClick={() => onCredential("demo")}
      >
        <span className="font-semibold text-brand">G</span>
        <LocalizedText>Continue with Google</LocalizedText>
      </button>
    );
  }

  return (
    <p className="rounded-sm border border-dashed border-line px-3 py-2 text-center text-xs text-ink-muted">
      <LocalizedText>Google sign-in is not configured.</LocalizedText>
    </p>
  );
}

let facebookScriptPromise: Promise<void> | null = null;
let initializedFacebookAppId = "";

function initializeFacebookSdk(appId: string) {
  if (!window.FB || initializedFacebookAppId === appId) return;
  window.FB.init({
    appId,
    cookie: true,
    xfbml: false,
    version: "v25.0",
  });
  initializedFacebookAppId = appId;
}

function loadFacebookSdk(appId: string): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("no window"));
  if (window.FB) {
    initializeFacebookSdk(appId);
    return Promise.resolve();
  }
  if (facebookScriptPromise) {
    return facebookScriptPromise.then(() => initializeFacebookSdk(appId));
  }
  facebookScriptPromise = new Promise<void>((resolve, reject) => {
    window.fbAsyncInit = () => {
      initializeFacebookSdk(appId);
      resolve();
    };
    const script = document.createElement("script");
    script.src = FACEBOOK_SDK_SRC;
    script.async = true;
    script.defer = true;
    script.crossOrigin = "anonymous";
    script.onerror = () => {
      facebookScriptPromise = null;
      reject(new Error("Failed to load Facebook SDK."));
    };
    document.head.appendChild(script);
  });
  return facebookScriptPromise;
}

export function FacebookSignInButton({
  onAccessToken,
  onError,
}: {
  onAccessToken: (accessToken: string) => void;
  onError?: (message: string) => void;
}) {
  const [loading, setLoading] = useState(false);
  const appId = getPublicFacebookAppId();

  const handleClick = useCallback(() => {
    if (authDemoMode) {
      onAccessToken("demo");
      return;
    }
    if (!appId) {
      onError?.("Facebook sign-in is not configured.");
      return;
    }
    setLoading(true);
    loadFacebookSdk(appId)
      .then(() => {
        if (!window.FB) throw new Error("Facebook SDK is unavailable.");
        window.FB.login(
          (response) => {
            setLoading(false);
            const accessToken = response.authResponse?.accessToken;
            if (response.status === "connected" && accessToken) {
              onAccessToken(accessToken);
            } else {
              onError?.("Facebook sign-in was cancelled.");
            }
          },
          { scope: "public_profile,email", return_scopes: true },
        );
      })
      .catch(() => {
        setLoading(false);
        onError?.("Could not load Facebook sign-in. Please try again.");
      });
  }, [appId, onAccessToken, onError]);

  if (!appId && !authDemoMode) {
    return (
      <p className="rounded-sm border border-dashed border-line px-3 py-2 text-center text-xs text-ink-muted">
        <LocalizedText>Facebook sign-in is not configured.</LocalizedText>
      </p>
    );
  }

  return (
    <button
      type="button"
      className="flex min-h-11 w-full items-center justify-center gap-2 rounded-sm border border-[#1877f2] bg-[#1877f2] px-4 text-sm font-medium text-white hover:opacity-95 disabled:opacity-60"
      onClick={handleClick}
      disabled={loading}
    >
      <span className="text-base font-bold">f</span>
      {loading ? (
        <LocalizedText>{"Connecting..."}</LocalizedText>
      ) : (
        <LocalizedText>{"Continue with Facebook"}</LocalizedText>
      )}
    </button>
  );
}
