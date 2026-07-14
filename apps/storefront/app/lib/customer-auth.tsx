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
 * public `VITE_GOOGLE_CLIENT_ID` is needed here — never a client secret.
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

const API_URL = import.meta.env.VITE_API_URL as string | undefined;
export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;
export const authDemoMode = !API_URL;

const DEMO_SESSION_KEY = "truegrit.customer.session";
const GIS_SCRIPT_SRC = "https://accounts.google.com/gsi/client";

export interface CustomerAccount {
  id: string;
  displayName: string;
  email: string;
}

export interface RegisterInput {
  name: string;
  email: string;
  password: string;
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
  const response = await fetch(`${API_URL}${path}`, {
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

function demoCustomerFromEmail(email: string, name?: string): CustomerAccount {
  const local = email.split("@")[0] ?? "member";
  const displayName =
    name?.trim() || local.replace(/[._-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return { id: `demo_${local}`, displayName: displayName || "Organic member", email };
}

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
        const me = await apiRequest<CustomerAccount>("/v1/public/auth/me");
        if (active) {
          setCustomer(me);
          setStatus("authenticated");
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
      setCustomer(writeDemoSession(demoCustomerFromEmail(input.email, input.name)));
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
      setCustomer(writeDemoSession(demoCustomerFromEmail(email)));
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
    () => ({ customer, status, register, login, loginWithGoogle, logout }),
    [customer, status, register, login, loginWithGoogle, logout],
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

declare global {
  interface Window {
    google?: { accounts: { id: GoogleAccountsId } };
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

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    let cancelled = false;
    loadGoogleIdentityServices()
      .then(() => {
        if (cancelled || !containerRef.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
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
  }, [onCredential, onError]);

  if (GOOGLE_CLIENT_ID) {
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
        Continue with Google
      </button>
    );
  }

  return (
    <p className="rounded-sm border border-dashed border-line px-3 py-2 text-center text-xs text-ink-muted">
      Google sign-in is not configured.
    </p>
  );
}
