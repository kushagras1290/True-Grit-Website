import { LOCALES, type LocaleDefinition } from "@truegrit/i18n";
import { cn } from "@truegrit/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BookOpenText,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Eye,
  EyeOff,
  ExternalLink,
  FileText,
  Globe2,
  Languages,
  Loader2,
  LogOut,
  Menu,
  MessageSquareText,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  UserCircle,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";

import { EN_MESSAGES } from "../../storefront/app/lib/i18n/messages";
import ADMIN_SOURCE_STRINGS from "../../admin/src/lib/i18n/source-strings";
import TRUE_GRIT_MARK from "../../storefront/public/brand/true-grit-mark.webp";
import {
  ApiError,
  languageApi,
  type CustomLocale,
  type StaffUser,
  type TranslationField,
  type TranslationBatch,
  type TranslationResourceRow,
} from "./api";

type Tab = "content" | "interface" | "languages" | "account";

const RESOURCE_TYPES = [
  ["announcement", "Announcements"],
  ["page", "Pages"],
  ["article", "Blogs"],
  ["recipe", "Recipes"],
  ["discussion", "Discussions"],
  ["discussion_comment", "Discussion comments"],
  ["content_comment", "Post comments"],
  ["product", "Products"],
  ["category", "Categories"],
  ["farm", "Farms"],
  ["bundle", "Bundles"],
  ["navigation_item", "Navigation"],
  ["promotion", "Promotions"],
  ["review", "Reviews"],
] as const;

const TAB_ITEMS: Array<{ key: Tab; label: string; icon: ReactNode }> = [
  { key: "content", label: "Content", icon: <BookOpenText size={17} /> },
  { key: "interface", label: "Interface text", icon: <FileText size={17} /> },
  { key: "languages", label: "Languages", icon: <Globe2 size={17} /> },
  { key: "account", label: "Your account", icon: <UserCircle size={17} /> },
];

function errorText(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

function hashString(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function storefrontInterfaceSources(): Array<[string, string]> {
  return (Object.entries(EN_MESSAGES) as Array<[string, string]>).filter(([, source]) => {
    const value = source.trim();
    // The JSX extractor also sees a small set of runtime tokens. They are
    // implementation details, not words a visitor can read, and translating
    // them would break CSS theming or phone-auth requests.
    return !value.startsWith("--") && !value.startsWith("/v1/");
  });
}

function Button({
  variant = "secondary",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
}) {
  const variants = {
    primary: "bg-brand text-ink-inverse hover:opacity-90",
    secondary: "border border-line-strong bg-surface text-ink hover:bg-subtle",
    danger: "border border-danger/30 bg-danger/5 text-danger hover:bg-danger/10",
    ghost: "text-ink-muted hover:bg-subtle hover:text-ink",
  };
  return (
    <button
      className={cn(
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-sm px-3.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}

const controlClass =
  "min-h-10 w-full rounded-sm border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-ink-muted focus:border-brand focus:outline-none";

function PasswordInput({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        className={cn(controlClass, "pr-9", className)}
        {...props}
      />
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

function Login({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const login = useMutation({
    mutationFn: () => languageApi.login(email, password),
    onSuccess: onDone,
    onError: (caught) => setError(errorText(caught, "Could not sign in.")),
  });

  return (
    <main className="grid min-h-screen bg-canvas lg:grid-cols-[1.05fr_.95fr]">
      <section className="hidden overflow-hidden bg-inverse px-12 py-14 text-ink-inverse lg:flex lg:flex-col">
        <div className="flex items-center gap-3">
          <img
            src={TRUE_GRIT_MARK}
            alt="True Grit"
            width={40}
            height={40}
            className="h-10 w-10 rounded-full object-cover"
          />
          <div>
            <p className="font-display text-xl">TRUE GRIT</p>
            <p className="text-xs text-white/60">Language studio</p>
          </div>
        </div>
        <div className="my-auto max-w-xl">
          <p className="text-xs font-semibold tracking-[.16em] text-accent uppercase">
            Every word, one home
          </p>
          <h1 className="mt-5 font-display text-5xl leading-tight">
            Make every True Grit story readable everywhere.
          </h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-white/70">
            Translate storefront labels, products, pages, blogs, recipes and community conversations
            from one reviewable workspace.
          </p>
        </div>
        <p className="text-xs text-white/45">
          Runtime translations · Source-change tracking · 100+ languages
        </p>
      </section>
      <section className="flex items-center justify-center px-5 py-12 sm:px-10">
        <form
          className="w-full max-w-md rounded-md border border-line bg-surface p-7 shadow-card sm:p-9"
          onSubmit={(event) => {
            event.preventDefault();
            setError(null);
            login.mutate();
          }}
        >
          <div className="mb-7 flex items-center gap-3 lg:hidden">
            <img
              src={TRUE_GRIT_MARK}
              alt="True Grit"
              width={38}
              height={38}
              className="h-10 w-10 rounded-full object-cover"
            />
            <div>
              <p className="font-display text-xl text-brand">TRUE GRIT</p>
              <p className="text-xs text-ink-muted">Language studio</p>
            </div>
          </div>
          <p className="text-xs font-semibold tracking-[.14em] text-accent uppercase">
            Staff access
          </p>
          <h1 className="mt-2 font-display text-3xl text-ink">Sign in to translate</h1>
          <p className="mt-2 text-sm text-ink-muted">
            Use the same account as the True Grit admin panel.
          </p>
          {error ? (
            <p className="mt-5 rounded-sm border border-danger/30 bg-danger/5 p-3 text-sm text-danger">
              {error}
            </p>
          ) : null}
          <label className="mt-6 block text-sm font-medium text-ink">
            Email
            <input
              className={`${controlClass} mt-1.5`}
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label className="mt-4 block text-sm font-medium text-ink">
            Password
            <PasswordInput
              className="mt-1.5"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <Button
            className="mt-6 w-full"
            variant="primary"
            type="submit"
            disabled={login.isPending}
          >
            {login.isPending ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Languages size={17} />
            )}
            Sign in
          </Button>
        </form>
      </section>
    </main>
  );
}

function LocaleSelect({
  value,
  onChange,
  locales,
}: {
  value: string;
  onChange: (value: string) => void;
  locales: readonly LocaleDefinition[];
}) {
  return (
    <select
      className={`${controlClass} min-w-48`}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      {locales
        .filter((entry) => entry.code !== "en")
        .map((entry) => (
          <option key={entry.code} value={entry.code}>
            {entry.nativeName} — {entry.englishName} ({entry.code})
          </option>
        ))}
    </select>
  );
}

function Coverage({ row }: { row: TranslationResourceRow }) {
  const percent = row.fieldCount ? Math.round((row.translatedCount / row.fieldCount) * 100) : 100;
  return (
    <div className="mt-3 flex items-center gap-3">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-subtle">
        <div
          className={cn("h-full rounded-full", row.staleCount ? "bg-warning" : "bg-success")}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="w-10 text-right text-xs tabular-nums text-ink-muted">{percent}%</span>
    </div>
  );
}

function BatchProgress({ batch }: { batch: TranslationBatch }) {
  const finished = batch.completedTasks + batch.failedTasks;
  const percent = batch.totalTasks ? Math.round((finished / batch.totalTasks) * 100) : 0;
  return (
    <div className="border-b border-line bg-accent/5 px-4 py-3 sm:px-5">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <p className="font-medium text-ink">
          Translation run: {batch.status} · {finished}/{batch.totalTasks} tasks
        </p>
        <p className="text-xs text-ink-muted">
          {batch.translatedStrings} strings translated
          {batch.failedTasks ? ` · ${batch.failedTasks} failed` : ""}
        </p>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-subtle">
        <div
          className="h-full rounded-full bg-accent transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
      {batch.failures.length ? (
        <p className="mt-2 text-xs text-danger">
          {batch.failures.map((failure) => failure.locale).join(", ")} could not be translated.
          Existing English fallbacks remain safe.
        </p>
      ) : null}
    </div>
  );
}

function ContentWorkspace({
  locale,
  locales,
}: {
  locale: string;
  locales: readonly LocaleDefinition[];
}) {
  const queryClient = useQueryClient();
  const [resourceType, setResourceType] = useState("article");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedResources, setSelectedResources] = useState<Set<string>>(new Set());
  const [selectedFields, setSelectedFields] = useState<Set<string>>(new Set());
  const [fieldFilter, setFieldFilter] = useState<"all" | "missing" | "translated" | "stale">("all");
  const [overwriteExisting, setOverwriteExisting] = useState(false);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search), 250);
    return () => window.clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    setOffset(0);
    setSelectedId(null);
    setSelectedResources(new Set());
  }, [locale, resourceType, debouncedSearch]);

  const resources = useQuery({
    queryKey: ["resources", resourceType, locale, debouncedSearch, offset],
    queryFn: () => languageApi.resources(resourceType, locale, debouncedSearch, offset),
    refetchInterval: 30_000,
  });
  const detail = useQuery({
    queryKey: ["resource", resourceType, selectedId, locale],
    queryFn: () => languageApi.resource(resourceType, selectedId!, locale),
    enabled: Boolean(selectedId),
  });
  useEffect(() => {
    if (detail.data) {
      setValues(
        Object.fromEntries(detail.data.fields.map((field) => [field.key, field.translation])),
      );
      setSelectedFields(new Set(detail.data.fields.map((field) => field.key)));
    }
  }, [detail.data]);
  const batch = useQuery({
    queryKey: ["translation-batch", batchId],
    queryFn: () => languageApi.batch(batchId!),
    enabled: Boolean(batchId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ["completed", "partial", "failed"].includes(status) ? false : 2_000;
    },
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["resource", resourceType, selectedId, locale] }),
      queryClient.invalidateQueries({ queryKey: ["resources", resourceType, locale] }),
    ]);
  };
  const save = useMutation({
    mutationFn: () => languageApi.saveResource(resourceType, selectedId!, locale, values),
    onSuccess: async () => {
      await refresh();
      setNotice({ kind: "ok", text: "Reviewed translation saved and live." });
    },
    onError: (error) =>
      setNotice({ kind: "error", text: errorText(error, "Could not save translations.") }),
  });
  const auto = useMutation({
    mutationFn: () => languageApi.autoTranslateResource(resourceType, selectedId!, locale),
    onSuccess: async () => {
      await refresh();
      setNotice({
        kind: "ok",
        text: "Machine translation generated. Review it before final save.",
      });
    },
    onError: (error) =>
      setNotice({
        kind: "error",
        text: errorText(error, "Could not machine translate this item."),
      }),
  });
  const remove = useMutation({
    mutationFn: () => languageApi.deleteResource(resourceType, selectedId!, locale),
    onSuccess: async () => {
      await refresh();
      setNotice({
        kind: "ok",
        text: "Translations removed; the storefront now falls back to English.",
      });
    },
    onError: (error) =>
      setNotice({ kind: "error", text: errorText(error, "Could not remove translations.") }),
  });
  const allLanguageCodes = locales
    .filter((entry) => entry.code !== "en")
    .map((entry) => entry.code);
  const bulk = useMutation({
    mutationFn: (resources: Array<{ resourceId: string; fieldKeys?: string[] }>) =>
      languageApi.createContentBatch(resourceType, resources, allLanguageCodes, overwriteExisting),
    onSuccess: (created) => {
      setBatchId(created.id);
      setNotice({
        kind: "ok",
        text: `Queued ${created.totalTasks} safe translation tasks across ${allLanguageCodes.length} languages.`,
      });
    },
    onError: (error) =>
      setNotice({ kind: "error", text: errorText(error, "Could not start bulk translation.") }),
  });
  const busy = save.isPending || auto.isPending || remove.isPending || bulk.isPending;
  const visibleFields = (detail.data?.fields ?? []).filter((field) => {
    if (fieldFilter === "missing") return !field.translation.trim();
    if (fieldFilter === "translated") return Boolean(field.translation.trim());
    if (fieldFilter === "stale") return field.stale;
    return true;
  });

  return (
    <div className="grid min-h-[calc(100vh-12.5rem)] overflow-hidden rounded-md border border-line bg-surface shadow-card lg:grid-cols-[23rem_minmax(0,1fr)]">
      <section className={cn("border-line lg:border-r", selectedId ? "hidden lg:block" : "block")}>
        <div className="space-y-3 border-b border-line p-4">
          <p className="text-xs leading-5 text-ink-muted">
            Live inventory · new content appears automatically within 30 seconds.
          </p>
          <select
            className={controlClass}
            value={resourceType}
            onChange={(event) => setResourceType(event.target.value)}
          >
            {RESOURCE_TYPES.map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          <label className="relative block">
            <Search size={15} className="absolute top-3 left-3 text-ink-muted" />
            <input
              className={`${controlClass} pl-9`}
              placeholder="Search source content"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <button
              type="button"
              className="font-medium text-brand hover:underline"
              disabled={!resources.data?.items.length}
              onClick={() =>
                setSelectedResources(new Set(resources.data?.items.map((row) => row.id) ?? []))
              }
            >
              Select visible
            </button>
            <button
              type="button"
              className="text-ink-muted hover:text-ink"
              onClick={() => setSelectedResources(new Set())}
            >
              Clear · {selectedResources.size} selected
            </button>
          </div>
          <Button
            variant="primary"
            className="w-full"
            disabled={!selectedResources.size || busy}
            onClick={() =>
              bulk.mutate([...selectedResources].map((resourceId) => ({ resourceId })))
            }
          >
            {bulk.isPending ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Sparkles size={15} />
            )}
            Translate selected to all {allLanguageCodes.length} languages
          </Button>
          <label className="flex items-start gap-2 text-xs leading-5 text-ink-muted">
            <input
              type="checkbox"
              className="mt-1 accent-[var(--brand)]"
              checked={overwriteExisting}
              onChange={(event) => setOverwriteExisting(event.target.checked)}
            />
            Replace existing reviewed translations. Leave off to translate only missing or stale
            text.
          </label>
        </div>
        {batch.data && !selectedId ? <BatchProgress batch={batch.data} /> : null}
        <div className="max-h-[calc(100vh-21rem)] overflow-y-auto">
          {resources.isLoading ? (
            <Loading label="Loading content…" />
          ) : resources.isError ? (
            <InlineError text={errorText(resources.error, "Could not load content.")} />
          ) : resources.data?.items.length ? (
            <ul>
              {resources.data.items.map((row) => (
                <li key={row.id} className="flex border-b border-line hover:bg-canvas">
                  <label className="flex w-11 shrink-0 items-start justify-center pt-5">
                    <input
                      type="checkbox"
                      aria-label={`Select ${row.title}`}
                      className="accent-[var(--brand)]"
                      checked={selectedResources.has(row.id)}
                      onChange={(event) =>
                        setSelectedResources((current) => {
                          const next = new Set(current);
                          if (event.target.checked) next.add(row.id);
                          else next.delete(row.id);
                          return next;
                        })
                      }
                    />
                  </label>
                  <button
                    type="button"
                    className={cn(
                      "min-w-0 flex-1 px-1 py-4 pr-4 text-left",
                      selectedId === row.id && "bg-subtle",
                    )}
                    onClick={() => setSelectedId(row.id)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-ink">{row.title}</p>
                        <p className="mt-1 text-xs text-ink-muted">
                          {row.translatedCount}/{row.fieldCount} strings · {row.status || "active"}
                        </p>
                      </div>
                      {row.staleCount ? (
                        <span className="rounded-full bg-warning/10 px-2 py-1 text-[10px] font-semibold text-warning">
                          {row.staleCount} stale
                        </span>
                      ) : row.translatedCount === row.fieldCount ? (
                        <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-success" />
                      ) : null}
                    </div>
                    <Coverage row={row} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <Empty title="Nothing found" body="Try a different content type or search." />
          )}
        </div>
        {resources.data && resources.data.total > 25 ? (
          <div className="flex items-center justify-between border-t border-line p-3">
            <Button
              variant="ghost"
              disabled={!offset}
              onClick={() => setOffset(Math.max(0, offset - 25))}
            >
              <ChevronLeft size={15} /> Previous
            </Button>
            <span className="text-xs text-ink-muted">
              {offset + 1}–{Math.min(offset + 25, resources.data.total)} of {resources.data.total}
            </span>
            <Button
              variant="ghost"
              disabled={offset + 25 >= resources.data.total}
              onClick={() => setOffset(offset + 25)}
            >
              Next <ChevronRight size={15} />
            </Button>
          </div>
        ) : null}
      </section>

      <section className={cn(selectedId ? "block" : "hidden lg:block")}>
        {!selectedId ? (
          <Empty
            title="Choose something to translate"
            body="Select a page, article, recipe, discussion or catalogue item from the left."
            icon={<Languages size={28} />}
          />
        ) : detail.isLoading ? (
          <Loading label="Loading every source string…" />
        ) : detail.isError ? (
          <InlineError text={errorText(detail.error, "Could not load this item.")} />
        ) : detail.data ? (
          <div>
            <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface/95 px-4 py-4 backdrop-blur sm:px-6">
              <div className="flex min-w-0 items-center gap-3">
                <Button
                  className="lg:hidden"
                  variant="ghost"
                  aria-label="Back to content"
                  onClick={() => setSelectedId(null)}
                >
                  <ChevronLeft size={18} />
                </Button>
                <div className="min-w-0">
                  <p className="truncate font-display text-xl text-ink">{detail.data.title}</p>
                  <p className="text-xs text-ink-muted">
                    {detail.data.fields.length} translatable strings · {locale}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" disabled={busy} onClick={() => auto.mutate()}>
                  {auto.isPending ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Sparkles size={15} />
                  )}{" "}
                  Translate current language
                </Button>
                <Button
                  variant="secondary"
                  disabled={busy || !selectedFields.size}
                  onClick={() =>
                    bulk.mutate([{ resourceId: selectedId, fieldKeys: [...selectedFields] }])
                  }
                >
                  {bulk.isPending ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Languages size={15} />
                  )}
                  Selected → all {allLanguageCodes.length}
                </Button>
                <Button variant="primary" disabled={busy} onClick={() => save.mutate()}>
                  {save.isPending ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Check size={15} />
                  )}{" "}
                  Review & save
                </Button>
              </div>
            </header>
            {notice ? <Notice notice={notice} onClose={() => setNotice(null)} /> : null}
            {batch.data ? <BatchProgress batch={batch.data} /> : null}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-6">
              <div className="flex flex-wrap gap-2">
                {(["all", "missing", "translated", "stale"] as const).map((filter) => (
                  <button
                    key={filter}
                    type="button"
                    className={cn(
                      "rounded-full border px-3 py-1 text-xs capitalize",
                      fieldFilter === filter
                        ? "border-brand bg-brand text-ink-inverse"
                        : "border-line-strong text-ink-muted",
                    )}
                    onClick={() => setFieldFilter(filter)}
                  >
                    {filter}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-3 text-xs">
                <button
                  type="button"
                  className="font-medium text-brand hover:underline"
                  onClick={() =>
                    setSelectedFields(new Set(visibleFields.map((field) => field.key)))
                  }
                >
                  Select shown
                </button>
                <button
                  type="button"
                  className="text-ink-muted hover:text-ink"
                  onClick={() => setSelectedFields(new Set())}
                >
                  Clear · {selectedFields.size} selected
                </button>
              </div>
            </div>
            <div className="space-y-4 p-4 sm:p-6">
              {visibleFields.map((field) => (
                <TranslationEditor
                  key={field.key}
                  field={field}
                  value={values[field.key] ?? ""}
                  locale={locale}
                  selected={selectedFields.has(field.key)}
                  onSelected={(checked) =>
                    setSelectedFields((current) => {
                      const next = new Set(current);
                      if (checked) next.add(field.key);
                      else next.delete(field.key);
                      return next;
                    })
                  }
                  onChange={(value) => setValues((current) => ({ ...current, [field.key]: value }))}
                />
              ))}
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
                <p className="max-w-xl text-xs leading-5 text-ink-muted">
                  Blank translations fall back safely to English. Saving marks every filled field as
                  human-reviewed and makes it live immediately.
                </p>
                <Button
                  variant="danger"
                  disabled={busy}
                  onClick={() =>
                    window.confirm("Remove every translation for this item and language?") &&
                    remove.mutate()
                  }
                >
                  <Trash2 size={15} /> Remove locale copy
                </Button>
              </div>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function TranslationEditor({
  field,
  value,
  locale,
  selected,
  onSelected,
  onChange,
}: {
  field: TranslationField;
  value: string;
  locale: string;
  selected: boolean;
  onSelected: (checked: boolean) => void;
  onChange: (value: string) => void;
}) {
  const multiline = field.source.length > 100 || field.source.includes("\n");
  return (
    <article
      className={cn(
        "rounded-md border bg-canvas p-4",
        field.stale ? "border-warning/50" : "border-line",
      )}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <label className="flex min-w-0 items-center gap-2">
          <input
            type="checkbox"
            className="accent-[var(--brand)]"
            checked={selected}
            onChange={(event) => onSelected(event.target.checked)}
          />
          <code className="max-w-full truncate text-[11px] text-ink-muted">{field.key}</code>
        </label>
        <div className="flex items-center gap-2">
          {field.stale ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-warning/10 px-2 py-1 text-[10px] font-semibold text-warning">
              <AlertTriangle size={11} /> Source changed
            </span>
          ) : null}
          <span
            className={cn(
              "rounded-full px-2 py-1 text-[10px] font-semibold",
              field.status === "reviewed"
                ? "bg-success/10 text-success"
                : field.status === "machine"
                  ? "bg-accent/10 text-accent"
                  : "bg-subtle text-ink-muted",
            )}
          >
            {field.status}
          </span>
        </div>
      </div>
      <div className="grid gap-3 xl:grid-cols-2">
        <div>
          <p className="mb-1.5 text-[11px] font-semibold tracking-[.12em] text-ink-muted uppercase">
            English source
          </p>
          <div className="min-h-12 whitespace-pre-wrap rounded-sm border border-line bg-surface px-3 py-2.5 text-sm leading-6 text-ink">
            {field.source}
          </div>
        </div>
        <label>
          <span className="mb-1.5 block text-[11px] font-semibold tracking-[.12em] text-ink-muted uppercase">
            {locale} translation
          </span>
          {multiline ? (
            <textarea
              rows={Math.min(8, Math.max(3, Math.ceil(field.source.length / 100)))}
              dir="auto"
              className={`${controlClass} resize-y py-2.5 leading-6`}
              value={value}
              onChange={(event) => onChange(event.target.value)}
            />
          ) : (
            <input
              dir="auto"
              className={controlClass}
              value={value}
              onChange={(event) => onChange(event.target.value)}
            />
          )}
        </label>
      </div>
    </article>
  );
}

function InterfaceWorkspace({
  locale,
  locales,
}: {
  locale: string;
  locales: readonly LocaleDefinition[];
}) {
  const queryClient = useQueryClient();
  const [target, setTarget] = useState<"storefront" | "admin">("storefront");
  const sources = useMemo<Array<[string, string]>>(
    () =>
      target === "storefront"
        ? storefrontInterfaceSources()
        : ADMIN_SOURCE_STRINGS.map((source) => [`admin.${hashString(source)}`, source]),
    [target],
  );
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState<"all" | "missing" | "translated">("all");
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [overwriteExisting, setOverwriteExisting] = useState(false);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const saved = useQuery({
    queryKey: ["interface", target, locale],
    queryFn: () => languageApi.interfaceMessages(locale, target),
  });
  useEffect(() => {
    if (!saved.data) return;
    setValues(
      target === "storefront"
        ? saved.data.messages
        : Object.fromEntries(
            sources.map(([key, source]) => [key, saved.data.messages[source] ?? ""]),
          ),
    );
  }, [saved.data, sources, target]);
  useEffect(() => {
    setPage(0);
    setSelectedKeys(new Set());
  }, [locale, search, target, statusFilter]);
  const filtered = sources.filter(([key, source]) => {
    const matchesSearch = `${key} ${source}`.toLowerCase().includes(search.trim().toLowerCase());
    const translated = Boolean(values[key]?.trim());
    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "translated" && translated) ||
      (statusFilter === "missing" && !translated);
    return matchesSearch && matchesStatus;
  });
  const visible = filtered.slice(page * 50, page * 50 + 50);
  const entries = Object.fromEntries(
    visible.map(([key, source]) => [key, { source, translation: values[key] ?? "" }]),
  );
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["interface", target, locale] });
  const save = useMutation({
    mutationFn: () => languageApi.saveInterface(locale, target, entries),
    onSuccess: async () => {
      await refresh();
      setNotice({ kind: "ok", text: "Interface corrections are live." });
    },
    onError: (error) =>
      setNotice({ kind: "error", text: errorText(error, "Could not save interface text.") }),
  });
  const auto = useMutation({
    mutationFn: () => languageApi.autoTranslateInterface(locale, target, entries),
    onSuccess: async () => {
      await refresh();
      setNotice({
        kind: "ok",
        text: "This page was machine-translated. Review and save any corrections.",
      });
    },
    onError: (error) =>
      setNotice({
        kind: "error",
        text: errorText(error, "Could not machine translate this page."),
      }),
  });
  const allLanguageCodes = locales
    .filter((entry) => entry.code !== "en")
    .map((entry) => entry.code);
  const currentLanguage = locales.find((entry) => entry.code === locale);
  const selectedEntries = Object.fromEntries(
    sources
      .filter(([key]) => selectedKeys.has(key))
      .map(([key, source]) => [key, { source, translation: values[key] ?? "" }]),
  );
  const batch = useQuery({
    queryKey: ["translation-batch", batchId],
    queryFn: () => languageApi.batch(batchId!),
    enabled: Boolean(batchId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ["completed", "partial", "failed"].includes(status) ? false : 2_000;
    },
  });
  const bulk = useMutation({
    mutationFn: (languageCodes: string[]) =>
      languageApi.createInterfaceBatch(target, selectedEntries, languageCodes, overwriteExisting),
    onSuccess: (created, languageCodes) => {
      setBatchId(created.id);
      setNotice({
        kind: "ok",
        text: `Queued ${selectedKeys.size} selected texts across ${languageCodes.length} language${languageCodes.length === 1 ? "" : "s"}.`,
      });
    },
    onError: (error) =>
      setNotice({ kind: "error", text: errorText(error, "Could not start bulk translation.") }),
  });

  return (
    <section className="overflow-hidden rounded-md border border-line bg-surface shadow-card">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4 sm:p-5">
        <div>
          <h2 className="font-display text-xl text-ink">
            {target === "storefront" ? "Storefront" : "Admin panel"} interface
          </h2>
          <p className="mt-1 text-xs text-ink-muted">
            Buttons, forms, headings, messages and states · {sources.length} source strings
          </p>
          <p className="mt-1 text-xs text-ink-muted">
            New website and admin strings are included automatically with every release.
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Button
            disabled={bulk.isPending || auto.isPending || save.isPending || !selectedKeys.size}
            onClick={() => bulk.mutate(allLanguageCodes)}
          >
            {bulk.isPending ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Languages size={15} />
            )}
            Selected → all {allLanguageCodes.length}
          </Button>
          <Button
            disabled={bulk.isPending || auto.isPending || save.isPending || !selectedKeys.size}
            onClick={() => bulk.mutate([locale])}
          >
            {bulk.isPending ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Languages size={15} />
            )}
            Selected → {currentLanguage?.englishName ?? locale}
          </Button>
          <Button disabled={auto.isPending || save.isPending} onClick={() => auto.mutate()}>
            <Sparkles size={15} /> Translate visible 50
          </Button>
          <Button
            variant="primary"
            disabled={auto.isPending || save.isPending}
            onClick={() => save.mutate()}
          >
            <Check size={15} /> Save visible 50
          </Button>
        </div>
      </header>
      {notice ? <Notice notice={notice} onClose={() => setNotice(null)} /> : null}
      {batch.data ? <BatchProgress batch={batch.data} /> : null}
      <div className="flex flex-wrap gap-3 border-b border-line p-4">
        <select
          className={`${controlClass} max-w-52`}
          value={target}
          onChange={(event) => setTarget(event.target.value as "storefront" | "admin")}
        >
          <option value="storefront">Storefront UI</option>
          <option value="admin">Admin panel UI</option>
        </select>
        <label className="relative block min-w-64 max-w-xl flex-1">
          <Search size={15} className="absolute top-3 left-3 text-ink-muted" />
          <input
            className={`${controlClass} pl-9`}
            placeholder="Find a button, message or catalogue key"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          {(["all", "missing", "translated"] as const).map((filter) => (
            <button
              key={filter}
              type="button"
              className={cn(
                "rounded-full border px-3 py-2 text-xs capitalize",
                statusFilter === filter
                  ? "border-brand bg-brand text-ink-inverse"
                  : "border-line-strong text-ink-muted",
              )}
              onClick={() => setStatusFilter(filter)}
            >
              {filter}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3 text-xs sm:px-5">
        <div className="flex gap-3">
          <button
            type="button"
            className="font-medium text-brand hover:underline"
            onClick={() => setSelectedKeys(new Set(visible.map(([key]) => key)))}
          >
            Select visible 50
          </button>
          <button
            type="button"
            className="font-medium text-brand hover:underline"
            disabled={!filtered.length}
            onClick={() => setSelectedKeys(new Set(filtered.map(([key]) => key)))}
          >
            Select all {filtered.length} results
          </button>
          <button
            type="button"
            className="text-ink-muted hover:text-ink"
            onClick={() => setSelectedKeys(new Set())}
          >
            Clear
          </button>
        </div>
        <span className="text-ink-muted">
          {selectedKeys.size}/{filtered.length} selected
        </span>
        <label className="flex items-center gap-2 text-ink-muted">
          <input
            type="checkbox"
            className="accent-[var(--brand)]"
            checked={overwriteExisting}
            onChange={(event) => setOverwriteExisting(event.target.checked)}
          />
          Replace existing reviewed translations
        </label>
      </div>
      {saved.isLoading ? (
        <Loading label="Loading runtime corrections…" />
      ) : (
        <div className="divide-y divide-line">
          {visible.map(([key, source]) => (
            <div
              key={key}
              className="grid gap-3 p-4 lg:grid-cols-[2rem_minmax(0,1fr)_minmax(0,1fr)] sm:p-5"
            >
              <input
                type="checkbox"
                aria-label={`Select ${source}`}
                className="mt-1 accent-[var(--brand)]"
                checked={selectedKeys.has(key)}
                onChange={(event) =>
                  setSelectedKeys((current) => {
                    const next = new Set(current);
                    if (event.target.checked) {
                      next.add(key);
                    } else next.delete(key);
                    return next;
                  })
                }
              />
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <code className="text-[11px] text-ink-muted">{key}</code>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                      values[key]?.trim()
                        ? "bg-success/10 text-success"
                        : "bg-subtle text-ink-muted",
                    )}
                  >
                    {values[key]?.trim() ? "translated" : "missing"}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-ink">{source}</p>
              </div>
              <textarea
                dir="auto"
                rows={source.length > 100 ? 4 : 2}
                className={`${controlClass} resize-y py-2.5 leading-6`}
                value={values[key] ?? ""}
                placeholder="Falls back to English when blank"
                onChange={(event) =>
                  setValues((current) => ({ ...current, [key]: event.target.value }))
                }
              />
            </div>
          ))}
        </div>
      )}
      <footer className="flex items-center justify-between border-t border-line p-4">
        <Button variant="ghost" disabled={!page} onClick={() => setPage(page - 1)}>
          <ChevronLeft size={15} /> Previous
        </Button>
        <span className="text-xs text-ink-muted">
          {filtered.length ? page * 50 + 1 : 0}–{Math.min((page + 1) * 50, filtered.length)} of{" "}
          {filtered.length}
        </span>
        <Button
          variant="ghost"
          disabled={(page + 1) * 50 >= filtered.length}
          onClick={() => setPage(page + 1)}
        >
          Next <ChevronRight size={15} />
        </Button>
      </footer>
    </section>
  );
}

function LanguagesWorkspace({
  customLocales,
  onChanged,
}: {
  customLocales: CustomLocale[];
  onChanged: () => Promise<unknown>;
}) {
  const [editing, setEditing] = useState<CustomLocale | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const save = useMutation({
    mutationFn: (locale: Omit<CustomLocale, "updatedAt">) => languageApi.saveLocale(locale),
    onSuccess: async () => {
      await onChanged();
      setShowForm(false);
      setEditing(null);
      setNotice({
        kind: "ok",
        text: "Language saved. It is now available to the storefront and translation tabs.",
      });
    },
    onError: (error) =>
      setNotice({ kind: "error", text: errorText(error, "Could not save the language.") }),
  });
  const remove = useMutation({
    mutationFn: languageApi.deleteLocale,
    onSuccess: async () => {
      await onChanged();
      setNotice({ kind: "ok", text: "Custom language removed from the storefront selector." });
    },
    onError: (error) =>
      setNotice({ kind: "error", text: errorText(error, "Could not remove the language.") }),
  });
  return (
    <div className="space-y-5">
      <section className="rounded-md border border-line bg-inverse p-6 text-ink-inverse shadow-card sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold tracking-[.14em] text-accent uppercase">
              Live language registry
            </p>
            <h2 className="mt-2 font-display text-3xl">100 built in. Add as many as you need.</h2>
            <p className="mt-3 text-sm leading-6 text-white/65">
              New languages appear in the storefront selector immediately. English remains the safe
              fallback while you translate interface and content strings.
            </p>
          </div>
          <Button
            variant="primary"
            onClick={() => {
              setEditing(null);
              setShowForm(true);
            }}
          >
            <Plus size={16} /> Add language
          </Button>
        </div>
      </section>
      {notice ? <Notice notice={notice} onClose={() => setNotice(null)} /> : null}
      {showForm ? (
        <LocaleForm
          initial={editing}
          busy={save.isPending}
          onCancel={() => {
            setShowForm(false);
            setEditing(null);
          }}
          onSave={(value) => save.mutate(value)}
        />
      ) : null}
      <section className="overflow-hidden rounded-md border border-line bg-surface shadow-card">
        <header className="border-b border-line p-5">
          <h3 className="font-display text-xl text-ink">Custom languages</h3>
          <p className="mt-1 text-xs text-ink-muted">
            Runtime additions beyond the shipped language catalogue.
          </p>
        </header>
        {customLocales.length ? (
          <div className="divide-y divide-line">
            {customLocales.map((locale) => (
              <div
                key={locale.code}
                className="flex flex-wrap items-center justify-between gap-4 p-4 sm:px-5"
              >
                <div className="flex min-w-0 items-center gap-4">
                  <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-subtle text-xs font-semibold text-brand">
                    {locale.code}
                  </span>
                  <div>
                    <p className="font-medium text-ink" dir={locale.direction}>
                      {locale.nativeName}
                    </p>
                    <p className="text-xs text-ink-muted">
                      {locale.englishName} · {locale.direction.toUpperCase()} · {locale.groupName} ·{" "}
                      {locale.active ? "Active" : "Hidden"}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setEditing(locale);
                      setShowForm(true);
                    }}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="danger"
                    disabled={remove.isPending}
                    onClick={() =>
                      window.confirm(
                        `Remove ${locale.englishName}? Existing translations will remain stored.`,
                      ) && remove.mutate(locale.code)
                    }
                  >
                    <Trash2 size={15} />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Empty
            title="No custom languages yet"
            body="The original 100 languages are still active. Add another when you are ready."
            icon={<Globe2 size={28} />}
          />
        )}
      </section>
    </div>
  );
}

function LocaleForm({
  initial,
  busy,
  onCancel,
  onSave,
}: {
  initial: CustomLocale | null;
  busy: boolean;
  onCancel: () => void;
  onSave: (value: Omit<CustomLocale, "updatedAt">) => void;
}) {
  const [code, setCode] = useState(initial?.code ?? "");
  const [nativeName, setNativeName] = useState(initial?.nativeName ?? "");
  const [englishName, setEnglishName] = useState(initial?.englishName ?? "");
  const [direction, setDirection] = useState<"ltr" | "rtl">(initial?.direction ?? "ltr");
  const [groupName, setGroupName] = useState<"indian" | "world">(initial?.groupName ?? "world");
  const [active, setActive] = useState(initial?.active ?? true);
  return (
    <form
      className="rounded-md border border-line bg-surface p-5 shadow-card"
      onSubmit={(event) => {
        event.preventDefault();
        onSave({
          code: code.trim(),
          nativeName: nativeName.trim(),
          englishName: englishName.trim(),
          direction,
          groupName,
          active,
        });
      }}
    >
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-display text-xl text-ink">
            {initial ? "Edit language" : "Add a language"}
          </h3>
          <p className="mt-1 text-xs text-ink-muted">
            Use a standard BCP-47 code such as ga, zu, pt-BR or zh-HK.
          </p>
        </div>
        <button type="button" className="p-2 text-ink-muted" onClick={onCancel}>
          <X size={18} />
        </button>
      </div>
      <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <label className="text-sm font-medium text-ink">
          Language code
          <input
            className={`${controlClass} mt-1.5`}
            required
            disabled={Boolean(initial)}
            value={code}
            onChange={(event) => setCode(event.target.value)}
            placeholder="ga"
          />
        </label>
        <label className="text-sm font-medium text-ink">
          Native name
          <input
            className={`${controlClass} mt-1.5`}
            required
            dir="auto"
            value={nativeName}
            onChange={(event) => setNativeName(event.target.value)}
            placeholder="Gaeilge"
          />
        </label>
        <label className="text-sm font-medium text-ink">
          English name
          <input
            className={`${controlClass} mt-1.5`}
            required
            value={englishName}
            onChange={(event) => setEnglishName(event.target.value)}
            placeholder="Irish"
          />
        </label>
        <label className="text-sm font-medium text-ink">
          Direction
          <select
            className={`${controlClass} mt-1.5`}
            value={direction}
            onChange={(event) => setDirection(event.target.value as "ltr" | "rtl")}
          >
            <option value="ltr">Left to right</option>
            <option value="rtl">Right to left</option>
          </select>
        </label>
        <label className="text-sm font-medium text-ink">
          Menu group
          <select
            className={`${controlClass} mt-1.5`}
            value={groupName}
            onChange={(event) => setGroupName(event.target.value as "indian" | "world")}
          >
            <option value="world">World languages</option>
            <option value="indian">Indian languages</option>
          </select>
        </label>
        <label className="flex min-h-10 items-center gap-3 self-end rounded-sm border border-line px-3 text-sm text-ink">
          <input
            type="checkbox"
            checked={active}
            onChange={(event) => setActive(event.target.checked)}
          />{" "}
          Show on storefront
        </label>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button type="button" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" type="submit" disabled={busy}>
          {busy ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />} Save
          language
        </Button>
      </div>
    </form>
  );
}

function Notice({
  notice,
  onClose,
}: {
  notice: { kind: "ok" | "error"; text: string };
  onClose: () => void;
}) {
  return (
    <div
      role="status"
      className={cn(
        "m-4 flex items-center gap-3 rounded-sm border px-4 py-3 text-sm",
        notice.kind === "ok"
          ? "border-success/30 bg-success/5 text-success"
          : "border-danger/30 bg-danger/5 text-danger",
      )}
    >
      {notice.kind === "ok" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
      <span className="flex-1">{notice.text}</span>
      <button onClick={onClose}>
        <X size={14} />
      </button>
    </div>
  );
}
function Loading({ label }: { label: string }) {
  return (
    <div className="flex min-h-52 items-center justify-center gap-3 text-sm text-ink-muted">
      <Loader2 size={18} className="animate-spin" />
      {label}
    </div>
  );
}
function InlineError({ text }: { text: string }) {
  return (
    <div className="m-4 rounded-sm border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
      {text}
    </div>
  );
}
function Empty({ title, body, icon }: { title: string; body: string; icon?: ReactNode }) {
  return (
    <div className="flex min-h-72 flex-col items-center justify-center px-6 text-center">
      {icon ? <div className="mb-4 text-ink-muted">{icon}</div> : null}
      <h3 className="font-display text-xl text-ink">{title}</h3>
      <p className="mt-2 max-w-sm text-sm leading-6 text-ink-muted">{body}</p>
    </div>
  );
}

function AccountWorkspace({ user }: { user: StaffUser }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const change = useMutation({
    mutationFn: () => languageApi.changePassword(currentPassword, newPassword),
    onSuccess: () => {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setNotice({ kind: "ok", text: "Password changed. Every other session was signed out." });
    },
    onError: (error) =>
      setNotice({ kind: "error", text: errorText(error, "Could not change your password.") }),
  });
  return (
    <section className="mx-auto max-w-3xl overflow-hidden rounded-md border border-line bg-surface shadow-card">
      <header className="border-b border-line p-5 sm:p-6">
        <h2 className="font-display text-2xl text-ink">Your account</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Password-protected staff identity for Language Studio.
        </p>
      </header>
      {notice ? <Notice notice={notice} onClose={() => setNotice(null)} /> : null}
      <div className="grid gap-8 p-5 sm:p-6 md:grid-cols-[1fr_1.25fr]">
        <div>
          <p className="text-xs font-semibold tracking-[.12em] text-ink-muted uppercase">
            Signed in as
          </p>
          <p className="mt-3 font-medium text-ink">{user.displayName}</p>
          <p className="mt-1 text-sm text-ink-muted">{user.email}</p>
          <p className="mt-4 text-xs leading-5 text-ink-muted">
            Changing your password keeps this session open and revokes every other active session.
          </p>
        </div>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (newPassword.length < 10) {
              setNotice({
                kind: "error",
                text: "Use at least 10 characters for the new password.",
              });
              return;
            }
            if (newPassword !== confirmPassword) {
              setNotice({ kind: "error", text: "The two new passwords do not match." });
              return;
            }
            change.mutate();
          }}
        >
          <label className="block text-sm font-medium text-ink">
            Current password
            <PasswordInput
              className="mt-1.5"
              autoComplete="current-password"
              required
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
          </label>
          <label className="block text-sm font-medium text-ink">
            New password
            <PasswordInput
              className="mt-1.5"
              autoComplete="new-password"
              required
              minLength={10}
              maxLength={256}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </label>
          <label className="block text-sm font-medium text-ink">
            Confirm new password
            <PasswordInput
              className="mt-1.5"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </label>
          <Button variant="primary" type="submit" disabled={change.isPending}>
            {change.isPending ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Check size={15} />
            )}
            Change password
          </Button>
        </form>
      </div>
    </section>
  );
}

function Studio({ user }: { user: StaffUser }) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("content");
  const [mobileOpen, setMobileOpen] = useState(false);
  const custom = useQuery({ queryKey: ["locales"], queryFn: languageApi.locales });
  const allLocales = useMemo(
    () =>
      Array.from(
        new Map(
          [
            ...LOCALES,
            ...(custom.data?.items ?? [])
              .filter((entry) => entry.active)
              .map(
                (entry) =>
                  ({
                    code: entry.code,
                    nativeName: entry.nativeName,
                    englishName: entry.englishName,
                    dir: entry.direction,
                    group: entry.groupName,
                  }) satisfies LocaleDefinition,
              ),
          ].map((entry) => [entry.code.toLowerCase(), entry]),
        ).values(),
      ),
    [custom.data],
  );
  const [locale, setLocale] = useState("hi");
  const logout = useMutation({
    mutationFn: languageApi.logout,
    onSuccess: () => window.location.reload(),
  });
  const nav = (
    <nav className="space-y-1 p-3">
      {TAB_ITEMS.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={() => {
            setTab(item.key);
            setMobileOpen(false);
          }}
          className={cn(
            "flex min-h-10 w-full items-center gap-3 rounded-sm px-3 text-sm",
            tab === item.key ? "bg-subtle font-medium text-brand" : "text-ink hover:bg-canvas",
          )}
        >
          {item.icon}
          {item.label}
        </button>
      ))}
    </nav>
  );
  return (
    <div className="flex min-h-screen bg-canvas">
      <aside className="hidden w-60 shrink-0 border-r border-line bg-surface md:flex md:flex-col">
        <Brand />
        {nav}
        <div className="mt-auto border-t border-line p-3">
          <a
            className="flex min-h-10 items-center gap-3 rounded-sm px-3 text-sm text-ink-muted hover:bg-canvas hover:text-ink"
            href="https://admin.truegritin.com"
            target="_blank"
            rel="noreferrer"
          >
            <ExternalLink size={16} /> Admin panel
          </a>
          <a
            className="flex min-h-10 items-center gap-3 rounded-sm px-3 text-sm text-ink-muted hover:bg-canvas hover:text-ink"
            href="https://process.truegritin.com"
            target="_blank"
            rel="noreferrer"
          >
            <ExternalLink size={16} /> Process panel
          </a>
        </div>
      </aside>
      {mobileOpen ? (
        <div
          className="fixed inset-0 z-40 bg-black/30 md:hidden"
          onClick={() => setMobileOpen(false)}
        >
          <aside className="h-full w-72 bg-surface" onClick={(event) => event.stopPropagation()}>
            <Brand />
            {nav}
          </aside>
        </div>
      ) : null}
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex min-h-16 items-center justify-between gap-4 border-b border-line bg-surface px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button className="p-2 text-ink md:hidden" onClick={() => setMobileOpen(true)}>
              <Menu size={20} />
            </button>
            <div>
              <h1 className="font-display text-xl text-ink">
                {TAB_ITEMS.find((item) => item.key === tab)?.label}
              </h1>
              <p className="hidden text-xs text-ink-muted sm:block">
                Translate, review and publish every customer-facing word.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={
                tab === "languages" || tab === "account" ? "hidden" : "hidden min-w-56 sm:block"
              }
            >
              <LocaleSelect locales={allLocales} value={locale} onChange={setLocale} />
            </div>
            <Button variant="ghost" title="Refresh" onClick={() => queryClient.invalidateQueries()}>
              <RefreshCw size={16} />
            </Button>
            <Button
              variant="ghost"
              title={`Sign out ${user.displayName}`}
              disabled={logout.isPending}
              onClick={() => logout.mutate()}
            >
              <LogOut size={16} />
            </Button>
          </div>
        </header>
        <main className="p-4 sm:p-6">
          {tab !== "languages" && tab !== "account" ? (
            <div className="mb-4 sm:hidden">
              <LocaleSelect locales={allLocales} value={locale} onChange={setLocale} />
            </div>
          ) : null}
          {tab === "content" ? (
            <ContentWorkspace locale={locale} locales={allLocales} />
          ) : tab === "interface" ? (
            <InterfaceWorkspace locale={locale} locales={allLocales} />
          ) : tab === "languages" ? (
            <LanguagesWorkspace
              customLocales={custom.data?.items ?? []}
              onChanged={() => queryClient.invalidateQueries({ queryKey: ["locales"] })}
            />
          ) : (
            <AccountWorkspace user={user} />
          )}
        </main>
      </div>
    </div>
  );
}

function Brand() {
  return (
    <div className="border-b border-line px-5 py-5">
      <div className="flex items-center gap-3">
        <img
          src={TRUE_GRIT_MARK}
          alt="True Grit"
          width={36}
          height={36}
          className="h-9 w-9 rounded-full object-cover"
        />
        <div>
          <p className="font-display text-lg text-brand">TRUE GRIT</p>
          <p className="text-xs text-ink-muted">Language studio</p>
        </div>
      </div>
    </div>
  );
}

export function App() {
  const queryClient = useQueryClient();
  const session = useQuery({ queryKey: ["session"], queryFn: languageApi.me, retry: false });
  if (session.isLoading)
    return (
      <div className="flex min-h-screen items-center justify-center gap-3 bg-canvas text-sm text-ink-muted">
        <Loader2 size={20} className="animate-spin" /> Checking translation access…
      </div>
    );
  if (!session.data)
    return <Login onDone={() => queryClient.invalidateQueries({ queryKey: ["session"] })} />;
  if (!session.data.isSuperAdmin && !session.data.permissions.includes("translations.manage"))
    return (
      <main className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <AlertTriangle size={30} className="text-warning" />
        <h1 className="mt-4 font-display text-2xl text-ink">Translation access required</h1>
        <p className="mt-2 text-sm text-ink-muted">
          Ask an owner to grant translations.manage to your role.
        </p>
      </main>
    );
  return <Studio user={session.data} />;
}
