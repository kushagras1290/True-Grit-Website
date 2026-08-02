/**
 * Appearance — the storefront's colours, and the decoration on top of them.
 *
 * Two jobs on one page because they answer the same question ("what does the
 * site look like") and are almost always adjusted together:
 *
 * * **Colours.** Every themeable role, editable as a swatch or a hex field,
 *   site-wide or for one page. Blank means "keep the shipped colour", so a
 *   theme only ever carries what somebody deliberately changed and clearing a
 *   field is how you undo.
 * * **Effects & Trails.** An ambient particle effect and a cursor trail, both
 *   off by default.
 *
 * The preview renders real storefront chrome — banner, cards, buttons, footer —
 * inside a container carrying the CSS custom properties being edited, so what
 * an owner sees is the same cascade the storefront uses rather than a drawing
 * of it. The effect preview runs the real canvas engine for the same reason.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  THEME_TOKEN_KEYS,
  type AmbientEffectKey,
  type CursorTrailKey,
  type StorefrontEffects,
  type ThemeTokenKey,
  type ThemeTokens,
} from "@truegrit/contracts";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  Button,
  ConfirmDialog,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api, type AppearanceResponse } from "../lib/api";

/** Label, one-line explanation, and the stock value each role falls back to.
 *  The stock values mirror `@truegrit/ui/tokens.css` — they are what the swatch
 *  shows for an untouched role, so an owner is never picking against a blank. */
const TOKEN_META: Record<
  ThemeTokenKey,
  { label: string; hint: string; fallback: string; group: "Surfaces" | "Text" | "Brand" | "Status" }
> = {
  bgCanvas: {
    label: "Page background",
    hint: "Behind everything.",
    fallback: "#f7f4eb",
    group: "Surfaces",
  },
  bgSurface: {
    label: "Card background",
    hint: "Product cards, panels, the header.",
    fallback: "#ffffff",
    group: "Surfaces",
  },
  bgSubtle: {
    label: "Tinted band",
    hint: "Alternating section backgrounds.",
    fallback: "#dde6d8",
    group: "Surfaces",
  },
  bgInverse: {
    label: "Dark band",
    hint: "Footer and inverted sections.",
    fallback: "#1a352b",
    group: "Surfaces",
  },
  bannerBackdrop: {
    label: "Banner backdrop",
    hint: "Shows behind and around banner images.",
    fallback: "#d8c8b4",
    group: "Surfaces",
  },
  textPrimary: {
    label: "Body text",
    hint: "Headings and copy.",
    fallback: "#202820",
    group: "Text",
  },
  textSecondary: {
    label: "Muted text",
    hint: "Captions, hints, metadata.",
    fallback: "#69736b",
    group: "Text",
  },
  textInverse: {
    label: "Text on dark",
    hint: "Copy inside dark bands.",
    fallback: "#f7f4eb",
    group: "Text",
  },
  brandPrimary: {
    label: "Brand",
    hint: "Primary buttons, links, the wordmark.",
    fallback: "#24483a",
    group: "Brand",
  },
  brandAccent: {
    label: "Accent",
    hint: "Eyebrows and small highlights.",
    fallback: "#b96f52",
    group: "Brand",
  },
  brandGold: {
    label: "Gold",
    hint: "Awards, badges, ratings.",
    fallback: "#a8813c",
    group: "Brand",
  },
  borderSubtle: {
    label: "Hairline border",
    hint: "Dividers and card edges.",
    fallback: "#24483a24",
    group: "Brand",
  },
  borderStrong: {
    label: "Strong border",
    hint: "Inputs and emphasised edges.",
    fallback: "#24483a52",
    group: "Brand",
  },
  danger: {
    label: "Danger",
    hint: "Errors and destructive actions.",
    fallback: "#a2442e",
    group: "Status",
  },
  success: {
    label: "Success",
    hint: "Confirmations and in-stock.",
    fallback: "#3d6b50",
    group: "Status",
  },
  warning: {
    label: "Warning",
    hint: "Cautions and low stock.",
    fallback: "#a97a1f",
    group: "Status",
  },
};

const TOKEN_GROUPS = ["Surfaces", "Text", "Brand", "Status"] as const;

/** CSS custom property behind each role — the preview writes these directly, so
 *  it inherits exactly the cascade the storefront uses. */
const TOKEN_PROPERTY: Record<ThemeTokenKey, string> = {
  bgCanvas: "--color-bg-canvas",
  bgSurface: "--color-bg-surface",
  bgSubtle: "--color-bg-subtle",
  bgInverse: "--color-bg-inverse",
  bannerBackdrop: "--color-banner-backdrop",
  textPrimary: "--color-text-primary",
  textSecondary: "--color-text-secondary",
  textInverse: "--color-text-inverse",
  brandPrimary: "--color-brand-primary",
  brandAccent: "--color-brand-accent",
  brandGold: "--color-brand-gold",
  borderSubtle: "--color-border-subtle",
  borderStrong: "--color-border-strong",
  danger: "--color-danger",
  success: "--color-success",
  warning: "--color-warning",
};

const AMBIENT_LABELS: Record<AmbientEffectKey, string> = {
  none: "None",
  snow: "Snowfall",
  leaves: "Falling leaves",
  petals: "Blossom petals",
  rain: "Rain",
  fireflies: "Fireflies",
  bubbles: "Rising bubbles",
  confetti: "Confetti",
  stars: "Twinkling stars",
  embers: "Rising embers",
  dust: "Floating dust",
  seeds: "Dandelion seeds",
  hearts: "Floating hearts",
  sparkles: "Sparkles",
  fog: "Drifting fog",
  meteors: "Meteor shower",
};

const TRAIL_LABELS: Record<CursorTrailKey, string> = {
  none: "None",
  dots: "Fading dots",
  ribbon: "Smooth ribbon",
  comet: "Comet tail",
  sparkle: "Sparkle burst",
  bubbles: "Bubbles",
  stars: "Stars",
  hearts: "Hearts",
  snow: "Snowflakes",
  glow: "Soft glow",
  rings: "Expanding rings",
  paint: "Paint stroke",
  fireflies: "Fireflies",
  leaves: "Leaves",
  petals: "Petals",
  embers: "Embers",
};

/** Mirrors `services/appearance.py`'s own scope helpers — a scope is either
 *  `'global'`, a storefront path (`/shop`), or `country:XX`. */
function countryScope(code: string): string {
  return `country:${code.trim().toUpperCase()}`;
}

function isCountryScope(scope: string): boolean {
  return scope.startsWith("country:");
}

function countryCodeFromScope(scope: string): string {
  return scope.slice("country:".length);
}

const HEX_PATTERN = /^#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i;
const FUNCTIONAL_PATTERN = /^(?:rgb|rgba|hsl|hsla|color-mix)\([a-z0-9\s%,./#-]{1,180}\)$/i;

function isValidColor(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > 200) return false;
  return HEX_PATTERN.test(trimmed) || FUNCTIONAL_PATTERN.test(trimmed);
}

/** `<input type="color">` only understands `#rrggbb`, so anything with alpha or
 *  a function wrapper needs a solid stand-in for the swatch. */
function swatchValue(value: string, fallback: string): string {
  const candidate = (value.trim() || fallback).trim();
  if (/^#[0-9a-f]{6}$/i.test(candidate)) return candidate;
  if (/^#[0-9a-f]{8}$/i.test(candidate)) return candidate.slice(0, 7);
  if (/^#[0-9a-f]{3}$/i.test(candidate)) {
    return `#${candidate
      .slice(1)
      .split("")
      .map((char) => char + char)
      .join("")}`;
  }
  return "#000000";
}

function styleFor(tokens: ThemeTokens): React.CSSProperties {
  const style: Record<string, string> = {};
  for (const key of THEME_TOKEN_KEYS) {
    const value = tokens[key];
    if (value && isValidColor(value)) style[TOKEN_PROPERTY[key]] = value.trim();
    else style[TOKEN_PROPERTY[key]] = TOKEN_META[key].fallback;
  }
  return style as React.CSSProperties;
}

export function AppearancePage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["appearance"],
    queryFn: api.appearance,
  });

  if (isLoading) return <p className="text-sm text-ink-muted">Loading appearance...</p>;
  if (isError || !data) {
    return (
      <div>
        <PageHeader
          title="Colours, Effects & Trails"
          description="The storefront's palette and the decoration on top of it."
        />
        <EmptyState
          title="Appearance unavailable"
          hint="Requires owner settings access and a connected API."
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Colours, Effects & Trails"
        description="Every colour the storefront uses, site-wide or for one page, plus ambient effects and cursor trails. Changes go live as soon as you save."
      />
      <ColoursSection data={data} />
      <EffectsSection data={data} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Colours
// ---------------------------------------------------------------------------

function ColoursSection({ data }: { data: AppearanceResponse }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [scope, setScope] = useState("global");
  const [draft, setDraft] = useState<ThemeTokens>({});
  const [newPath, setNewPath] = useState("");
  const [newCountry, setNewCountry] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const savedTokens = useMemo<ThemeTokens>(() => {
    if (scope === "global") return data.theme.global;
    if (isCountryScope(scope)) return data.theme.countries[scope] ?? {};
    return data.theme.pages[scope] ?? {};
  }, [data, scope]);

  // Re-seeded whenever the selected scope or the server's copy changes, so
  // switching pages never carries half-typed values across to another page.
  useEffect(() => {
    setDraft({ ...savedTokens });
  }, [savedTokens]);

  const dirty = useMemo(() => {
    const keys = new Set([...Object.keys(savedTokens), ...Object.keys(draft)]);
    for (const key of keys) {
      const before = savedTokens[key as ThemeTokenKey] ?? "";
      const after = draft[key as ThemeTokenKey] ?? "";
      if (before.trim() !== after.trim()) return true;
    }
    return false;
  }, [draft, savedTokens]);

  const invalid = useMemo(
    () =>
      THEME_TOKEN_KEYS.filter((key) => {
        const value = draft[key];
        return Boolean(value && value.trim() && !isValidColor(value));
      }),
    [draft],
  );

  function applyResult(result: AppearanceResponse) {
    queryClient.setQueryData(["appearance"], result);
    return queryClient.invalidateQueries({ queryKey: ["appearance"] });
  }

  const saveMutation = useMutation({
    mutationFn: (input: { scope: string; tokens: ThemeTokens }) =>
      api.saveThemeScope(input.scope, input.tokens),
    onSuccess: async (result, input) => {
      await applyResult(result);
      setScope(input.scope);
      toast.success(
        input.scope === "global" ? "Site colours saved." : `Colours saved for ${input.scope}.`,
      );
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the colours."),
  });

  const deleteMutation = useMutation({
    mutationFn: (target: string) => api.deleteThemeScope(target),
    onSuccess: async (result) => {
      await applyResult(result);
      setConfirmDelete(null);
      setScope("global");
      toast.success("Page colours removed; the page uses the site colours again.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not remove the page colours."),
  });

  function update(key: ThemeTokenKey, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function save() {
    if (invalid.length > 0) {
      toast.error(`${TOKEN_META[invalid[0]!].label} is not a valid colour.`);
      return;
    }
    // Blank values are dropped rather than stored: an empty string is how the
    // console says "back to the shipped colour", and storing it would mean the
    // theme carried a role nobody chose.
    const tokens: ThemeTokens = {};
    for (const key of THEME_TOKEN_KEYS) {
      const value = draft[key]?.trim();
      if (value) tokens[key] = value;
    }
    saveMutation.mutate({ scope, tokens });
  }

  function addPage() {
    const path = newPath.trim();
    if (!path.startsWith("/") || path.startsWith("//")) {
      toast.error("A page path starts with a slash, for example /shop.");
      return;
    }
    const normalized = path.replace(/\/+$/, "") || "/";
    setNewPath("");
    setScope(normalized);
    setDraft({ ...data.theme.global });
    toast.success(`Editing ${normalized}. It starts from the site colours; save to apply.`);
  }

  function addCountry() {
    const code = newCountry.trim().toUpperCase();
    if (!/^[A-Z]{2}$/.test(code)) {
      toast.error("A country needs a two-letter code, for example IN, US or DE.");
      return;
    }
    const target = countryScope(code);
    setNewCountry("");
    setScope(target);
    setDraft({ ...data.theme.global });
    toast.success(`Editing ${code}. It starts from the site colours; save to apply.`);
  }

  const pageScopes = Object.keys(data.theme.pages).sort();
  const countryScopes = Object.keys(data.theme.countries).sort();
  const knownScopes = new Set([...pageScopes, ...countryScopes]);
  const editingScope = scope !== "global";
  const editingPage = editingScope && !isCountryScope(scope);
  const editingCountry = isCountryScope(scope);
  const previewTokens: ThemeTokens = editingScope ? { ...data.theme.global, ...draft } : draft;

  return (
    <section className="space-y-5 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">Colours</h2>
        <p className="max-w-3xl text-sm text-ink-muted">
          Leave a colour blank to keep the one True Grit ships with — clearing a field is how you
          undo. A page or country's colours start from the site colours and override only what you
          change, so each is a short list, not a second palette to maintain. When both apply to the
          same visitor, the page wins — an editorial page's design should not be undone by a geo
          experiment.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56">
          <Field label="Editing" htmlFor="theme-scope">
            <Select
              id="theme-scope"
              value={scope}
              onChange={(event) => setScope(event.target.value)}
            >
              <option value="global">Whole site</option>
              {countryScopes.length > 0 ? (
                <optgroup label="Countries">
                  {countryScopes.map((countryScopeValue) => (
                    <option key={countryScopeValue} value={countryScopeValue}>
                      {countryCodeFromScope(countryScopeValue)}
                    </option>
                  ))}
                </optgroup>
              ) : null}
              {pageScopes.length > 0 ? (
                <optgroup label="Pages">
                  {pageScopes.map((path) => (
                    <option key={path} value={path}>
                      {path}
                    </option>
                  ))}
                </optgroup>
              ) : null}
              {editingScope && !knownScopes.has(scope) ? (
                <option value={scope}>
                  {editingCountry ? countryCodeFromScope(scope) : scope} (unsaved)
                </option>
              ) : null}
            </Select>
          </Field>
        </div>
        <div className="min-w-40">
          <Field label="Give one page its own colours" htmlFor="theme-new-path">
            <Input
              id="theme-new-path"
              value={newPath}
              placeholder="/shop"
              onChange={(event) => setNewPath(event.target.value)}
            />
          </Field>
        </div>
        <Button type="button" variant="secondary" disabled={!newPath.trim()} onClick={addPage}>
          Add page
        </Button>
        <div className="min-w-32">
          <Field label="Give one country its own colours" htmlFor="theme-new-country">
            <Input
              id="theme-new-country"
              value={newCountry}
              placeholder="IN"
              maxLength={2}
              onChange={(event) => setNewCountry(event.target.value)}
            />
          </Field>
        </div>
        <Button
          type="button"
          variant="secondary"
          disabled={!newCountry.trim()}
          onClick={addCountry}
        >
          Add country
        </Button>
        {editingScope && knownScopes.has(scope) ? (
          <Button type="button" variant="tertiary" onClick={() => setConfirmDelete(scope)}>
            {editingCountry ? "Remove country colours" : "Remove page colours"}
          </Button>
        ) : null}
      </div>
      {editingPage ? (
        <p className="text-xs text-ink-muted">
          These colours also apply to pages beneath <code>{scope}</code> — an override on{" "}
          <code>/blog</code> dresses every article under it, so you do not have to list them.
        </p>
      ) : null}
      {editingCountry ? (
        <p className="text-xs text-ink-muted">
          Applies to every visitor Cloudflare resolves to <code>{countryCodeFromScope(scope)}</code>
          , on every page that does not have its own colours.
        </p>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
        <div className="space-y-6">
          {TOKEN_GROUPS.map((group) => (
            <div key={group}>
              <h3 className="text-sm font-semibold tracking-[0.08em] text-ink-muted uppercase">
                {group}
              </h3>
              <ul className="mt-3 space-y-3">
                {THEME_TOKEN_KEYS.filter((key) => TOKEN_META[key].group === group).map((key) => {
                  const meta = TOKEN_META[key];
                  const value = draft[key] ?? "";
                  const bad = Boolean(value.trim() && !isValidColor(value));
                  return (
                    <li key={key} className="flex flex-wrap items-center gap-3">
                      <input
                        type="color"
                        aria-label={`${meta.label} swatch`}
                        className="h-9 w-12 shrink-0 cursor-pointer rounded-sm border border-line bg-surface p-0.5"
                        value={swatchValue(value, meta.fallback)}
                        onChange={(event) => update(key, event.target.value)}
                      />
                      <div className="min-w-40 flex-1">
                        <label
                          htmlFor={`token-${key}`}
                          className="block text-sm font-medium text-ink"
                        >
                          {meta.label}
                        </label>
                        <p className="text-xs text-ink-muted">{meta.hint}</p>
                      </div>
                      <div className="w-44">
                        <Input
                          id={`token-${key}`}
                          value={value}
                          placeholder={meta.fallback}
                          aria-invalid={bad || undefined}
                          className={bad ? "border-danger bg-danger/5" : undefined}
                          onChange={(event) => update(key, event.target.value)}
                        />
                      </div>
                      <Button
                        type="button"
                        variant="tertiary"
                        className="min-h-8 px-2 text-xs"
                        disabled={!value}
                        onClick={() => update(key, "")}
                      >
                        Reset
                      </Button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}

          <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
            <Button
              type="button"
              variant="primary"
              disabled={saveMutation.isPending || (!dirty && knownScopes.has(scope))}
              onClick={save}
            >
              {saveMutation.isPending
                ? "Saving..."
                : scope === "global"
                  ? "Save site colours"
                  : `Save colours for ${editingCountry ? countryCodeFromScope(scope) : scope}`}
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={!dirty}
              onClick={() => setDraft({ ...savedTokens })}
            >
              Discard changes
            </Button>
            {invalid.length > 0 ? (
              <p className="text-sm text-danger">
                {TOKEN_META[invalid[0]!].label} is not a valid colour. Use a hex value such as
                #24483a.
              </p>
            ) : null}
          </div>
        </div>

        <ThemePreview tokens={previewTokens} />
      </div>

      {confirmDelete ? (
        <ConfirmDialog
          title={`Remove the colours for ${
            isCountryScope(confirmDelete) ? countryCodeFromScope(confirmDelete) : confirmDelete
          }?`}
          description={
            isCountryScope(confirmDelete)
              ? "Visitors from this country go back to the site-wide colours. Nothing else about the country changes."
              : "The page goes back to the site-wide colours. Nothing else about the page changes."
          }
          confirmLabel={
            isCountryScope(confirmDelete) ? "Remove country colours" : "Remove page colours"
          }
          pendingLabel="Removing..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => deleteMutation.mutate(confirmDelete)}
        />
      ) : null}
    </section>
  );
}

/**
 * A miniature storefront under the colours being edited.
 *
 * Real chrome rather than a row of swatches: the point of a preview is to
 * answer "is the muted text still readable on the tinted band", which a grid of
 * squares cannot show. The CSS custom properties are set on the wrapper, so the
 * markup below inherits them exactly as the storefront's own does.
 */
function ThemePreview({ tokens }: { tokens: ThemeTokens }) {
  return (
    <aside className="h-fit xl:sticky xl:top-6">
      <h3 className="text-sm font-semibold tracking-[0.08em] text-ink-muted uppercase">Preview</h3>
      <p className="mt-1 mb-3 text-xs text-ink-muted">
        Live, and to scale with the real storefront's own styles.
      </p>
      <div
        style={styleFor(tokens)}
        className="overflow-hidden rounded-md border border-line shadow-card"
      >
        <div style={{ background: "var(--color-bg-canvas)", color: "var(--color-text-primary)" }}>
          <div
            className="flex items-center justify-between px-4 py-3"
            style={{
              background: "var(--color-bg-surface)",
              borderBottom: "1px solid var(--color-border-subtle)",
            }}
          >
            <span
              className="font-display text-base tracking-tight"
              style={{ color: "var(--color-brand-primary)" }}
            >
              TRUE GRIT
            </span>
            <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              Shop · Farms · Journal
            </span>
          </div>

          <div
            className="px-4 py-6"
            style={{ background: "var(--color-banner-backdrop)" }}
            aria-hidden
          >
            <p
              className="text-[10px] font-semibold tracking-[0.14em] uppercase"
              style={{ color: "var(--color-brand-accent)" }}
            >
              The market
            </p>
            <p className="mt-1 font-display text-xl leading-tight">
              Food grown the way nature intended.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 px-4 py-4">
            {["Organic mangoes", "Cold-pressed oil"].map((name) => (
              <div
                key={name}
                className="rounded-sm p-3"
                style={{
                  background: "var(--color-bg-surface)",
                  border: "1px solid var(--color-border-subtle)",
                }}
              >
                <p className="text-sm font-medium">{name}</p>
                <p className="mt-0.5 text-xs" style={{ color: "var(--color-text-secondary)" }}>
                  From a verified farm
                </p>
                <p
                  className="mt-2 text-sm font-medium"
                  style={{ color: "var(--color-brand-primary)" }}
                >
                  ₹ 480
                </p>
              </div>
            ))}
          </div>

          <div className="px-4 pb-4" style={{ background: "var(--color-bg-subtle)" }}>
            <p className="pt-4 text-xs" style={{ color: "var(--color-text-secondary)" }}>
              A tinted band — check muted text is still readable here.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2 pb-1">
              <span
                className="inline-flex items-center rounded-sm px-3 py-1.5 text-xs font-medium"
                style={{
                  background: "var(--color-brand-primary)",
                  color: "var(--color-text-inverse)",
                }}
              >
                Add to basket
              </span>
              <span
                className="inline-flex items-center rounded-sm px-3 py-1.5 text-xs font-medium"
                style={{
                  border: "1px solid var(--color-border-strong)",
                  color: "var(--color-text-primary)",
                }}
              >
                Save for later
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 pb-2 text-[11px] font-medium">
              <span style={{ color: "var(--color-success)" }}>In stock</span>
              <span style={{ color: "var(--color-warning)" }}>Low stock</span>
              <span style={{ color: "var(--color-danger)" }}>Sold out</span>
              <span style={{ color: "var(--color-brand-gold)" }}>Award winning</span>
            </div>
          </div>

          <div
            className="px-4 py-5"
            style={{ background: "var(--color-bg-inverse)", color: "var(--color-text-inverse)" }}
          >
            <p className="font-display text-sm">A slower, better way to eat.</p>
            <p className="mt-1 text-xs opacity-80">
              One considered letter a month. Unsubscribe anytime.
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Effects & Trails
// ---------------------------------------------------------------------------

function EffectsSection({ data }: { data: AppearanceResponse }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [scope, setScope] = useState("global");
  const [newCountry, setNewCountry] = useState("");
  const editingCountry = isCountryScope(scope);

  // A country with no saved override starts editing from the global default —
  // the same "start from the site-wide value" contract the colours section
  // uses — so turning on an override for the first time is a deliberate
  // change, not a jump to some other baseline.
  const savedEffects = useMemo<StorefrontEffects>(
    () => (editingCountry ? (data.countryEffects[scope] ?? data.effects) : data.effects),
    [data, scope, editingCountry],
  );
  const [draft, setDraft] = useState<StorefrontEffects>(savedEffects);

  useEffect(() => {
    setDraft(savedEffects);
  }, [savedEffects]);

  const dirty = JSON.stringify(draft) !== JSON.stringify(savedEffects);
  const countryScopes = Object.keys({ ...data.theme.countries, ...data.countryEffects }).sort();
  const hasOverride = editingCountry && scope in data.countryEffects;

  function applyResult(result: AppearanceResponse) {
    queryClient.setQueryData(["appearance"], result);
    return queryClient.invalidateQueries({ queryKey: ["appearance"] });
  }

  const mutation = useMutation({
    mutationFn: (effects: StorefrontEffects) => api.saveEffects(effects, scope),
    onSuccess: async (result) => {
      await applyResult(result);
      toast.success(
        scope === "global" ? "Effects saved." : `Effects saved for ${countryCodeFromScope(scope)}.`,
      );
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the effects."),
  });

  const clearMutation = useMutation({
    mutationFn: () => api.clearCountryEffects(scope),
    onSuccess: async (result) => {
      await applyResult(result);
      toast.success(`${countryCodeFromScope(scope)} now uses the site-wide effects again.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not clear the override."),
  });

  function addCountry() {
    const code = newCountry.trim().toUpperCase();
    if (!/^[A-Z]{2}$/.test(code)) {
      toast.error("A country needs a two-letter code, for example IN, US or DE.");
      return;
    }
    setNewCountry("");
    setScope(countryScope(code));
  }

  return (
    <section className="mt-10 space-y-5 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">Effects & Trails</h2>
        <p className="max-w-3xl text-sm text-ink-muted">
          Decoration on top of the storefront: drifting particles behind the page, and a trail
          following the pointer. Both are off by default, both are skipped entirely for visitors who
          have asked their device for reduced motion, and neither ever appears on the payment window
          — a snowfall over a card form is a distraction at exactly the wrong moment. A country's
          effects replace the site-wide ones outright for its visitors rather than blending with
          them — "some snow" is not a meaningful mix of snow and no effect.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56">
          <Field label="Editing" htmlFor="effects-scope">
            <Select
              id="effects-scope"
              value={scope}
              onChange={(event) => setScope(event.target.value)}
            >
              <option value="global">Whole site (default)</option>
              {countryScopes.map((countryScopeValue) => (
                <option key={countryScopeValue} value={countryScopeValue}>
                  {countryCodeFromScope(countryScopeValue)}
                </option>
              ))}
              {editingCountry && !countryScopes.includes(scope) ? (
                <option value={scope}>{countryCodeFromScope(scope)} (unsaved)</option>
              ) : null}
            </Select>
          </Field>
        </div>
        <div className="min-w-32">
          <Field label="Give one country its own effects" htmlFor="effects-new-country">
            <Input
              id="effects-new-country"
              value={newCountry}
              placeholder="IN"
              maxLength={2}
              onChange={(event) => setNewCountry(event.target.value)}
            />
          </Field>
        </div>
        <Button
          type="button"
          variant="secondary"
          disabled={!newCountry.trim()}
          onClick={addCountry}
        >
          Add country
        </Button>
        {hasOverride ? (
          <Button
            type="button"
            variant="tertiary"
            disabled={clearMutation.isPending}
            onClick={() => clearMutation.mutate()}
          >
            {clearMutation.isPending ? "Clearing..." : "Use site-wide effects instead"}
          </Button>
        ) : null}
      </div>
      {editingCountry ? (
        <p className="text-xs text-ink-muted">
          Applies to every visitor Cloudflare resolves to <code>{countryCodeFromScope(scope)}</code>
          .
          {hasOverride
            ? " Currently its own effects."
            : " Currently the site-wide effects — save below to give it its own."}
        </p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <h3 className="text-sm font-semibold tracking-[0.08em] text-ink-muted uppercase">
            Ambient effect
          </h3>
          <Field label="Effect" htmlFor="ambient-effect">
            <Select
              id="ambient-effect"
              value={draft.ambient.effect}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  ambient: { ...current.ambient, effect: event.target.value as AmbientEffectKey },
                }))
              }
            >
              {data.ambientEffects.map((key) => (
                <option key={key} value={key}>
                  {AMBIENT_LABELS[key] ?? key}
                </option>
              ))}
            </Select>
          </Field>
          <ColorRow
            id="ambient-color"
            label="Particle colour"
            value={draft.ambient.color}
            fallback="#ffffff"
            onChange={(value) =>
              setDraft((current) => ({ ...current, ambient: { ...current.ambient, color: value } }))
            }
          />
          <Field label={`Amount — ${draft.ambient.intensity} of 5`} htmlFor="ambient-intensity">
            <input
              id="ambient-intensity"
              type="range"
              min={1}
              max={5}
              step={1}
              className="w-full"
              value={draft.ambient.intensity}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  ambient: { ...current.ambient, intensity: Number(event.target.value) },
                }))
              }
            />
          </Field>
          <EffectPreview kind="ambient" effects={draft} />
        </div>

        <div className="space-y-4">
          <h3 className="text-sm font-semibold tracking-[0.08em] text-ink-muted uppercase">
            Cursor trail
          </h3>
          <Field label="Trail" htmlFor="cursor-trail">
            <Select
              id="cursor-trail"
              value={draft.cursor.trail}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  cursor: { ...current.cursor, trail: event.target.value as CursorTrailKey },
                }))
              }
            >
              {data.cursorTrails.map((key) => (
                <option key={key} value={key}>
                  {TRAIL_LABELS[key] ?? key}
                </option>
              ))}
            </Select>
          </Field>
          <ColorRow
            id="cursor-color"
            label="Trail colour"
            value={draft.cursor.color}
            fallback="#24483a"
            onChange={(value) =>
              setDraft((current) => ({ ...current, cursor: { ...current.cursor, color: value } }))
            }
          />
          <label className="flex items-start gap-2 text-sm text-ink">
            <input
              type="checkbox"
              className="mt-1"
              checked={draft.cursor.hideNativeCursor}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  cursor: { ...current.cursor, hideNativeCursor: event.target.checked },
                }))
              }
            />
            <span>
              Replace the pointer with the trail
              <span className="mt-0.5 block text-xs text-ink-muted">
                Hides the system cursor so the trail is the cursor. Links, buttons and form fields
                keep a real pointer regardless — losing the hit target on those is not a trade worth
                making.
              </span>
            </span>
          </label>
          <EffectPreview kind="cursor" effects={draft} />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
        <Button
          type="button"
          variant="primary"
          disabled={mutation.isPending || !dirty}
          onClick={() => mutation.mutate(draft)}
        >
          {mutation.isPending
            ? "Saving..."
            : scope === "global"
              ? "Save effects"
              : `Save effects for ${countryCodeFromScope(scope)}`}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={!dirty}
          onClick={() => setDraft(savedEffects)}
        >
          Discard changes
        </Button>
      </div>
    </section>
  );
}

function ColorRow({
  id,
  label,
  value,
  fallback,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  fallback: string;
  onChange: (value: string) => void;
}) {
  const bad = Boolean(value.trim() && !isValidColor(value));
  return (
    <div className="flex items-end gap-3">
      <input
        type="color"
        aria-label={`${label} swatch`}
        className="h-9 w-12 shrink-0 cursor-pointer rounded-sm border border-line bg-surface p-0.5"
        value={swatchValue(value, fallback)}
        onChange={(event) => onChange(event.target.value)}
      />
      <div className="flex-1">
        <Field
          label={label}
          htmlFor={id}
          error={bad ? "Use a hex colour such as #ffffff" : undefined}
        >
          <Input
            id={id}
            value={value}
            placeholder={fallback}
            onChange={(event) => onChange(event.target.value)}
          />
        </Field>
      </div>
    </div>
  );
}

/**
 * The real particle engine, in a box.
 *
 * A self-contained copy rather than an import from the storefront package: the
 * two apps do not share components, and a preview drawn from a different
 * implementation than the live site is a preview that will eventually lie.
 * Kept deliberately small — this is the shape and colour check, not a
 * pixel-accurate rehearsal.
 */
function EffectPreview({
  kind,
  effects,
}: {
  kind: "ambient" | "cursor";
  effects: StorefrontEffects;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const effect = kind === "ambient" ? effects.ambient.effect : effects.cursor.trail;
  const color = kind === "ambient" ? effects.ambient.color : effects.cursor.color;
  const intensity = effects.ambient.intensity;

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return undefined;
    if (effect === "none") {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return undefined;
    }

    const stroke = isValidColor(color) ? color.trim() : "#ffffff";
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.max(1, Math.floor(rect.width * ratio));
    canvas.height = Math.max(1, Math.floor(rect.height * ratio));
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

    const rising = ["bubbles", "embers", "hearts"].includes(effect);
    const still = ["stars", "sparkles", "dust", "fog", "fireflies", "glow"].includes(effect);
    const count = kind === "ambient" ? 14 * intensity : 40;

    interface Speck {
      x: number;
      y: number;
      vx: number;
      vy: number;
      size: number;
      alpha: number;
      phase: number;
    }
    const specks: Speck[] = Array.from({ length: Math.min(120, count) }, () => ({
      x: Math.random() * rect.width,
      y: Math.random() * rect.height,
      vx: (Math.random() - 0.5) * 18,
      vy: still
        ? (Math.random() - 0.5) * 8
        : rising
          ? -(12 + Math.random() * 26)
          : 14 + Math.random() * 34,
      size: 1.4 + Math.random() * (effect === "fog" ? 22 : 3.4),
      alpha: 0.25 + Math.random() * 0.65,
      phase: Math.random() * Math.PI * 2,
    }));

    let frame = 0;
    let last = performance.now();

    function draw(now: number) {
      const delta = Math.min(0.05, (now - last) / 1000);
      last = now;
      ctx!.clearRect(0, 0, rect.width, rect.height);
      ctx!.fillStyle = stroke;
      for (const speck of specks) {
        speck.phase += delta;
        speck.x += (speck.vx + Math.cos(speck.phase) * 10) * delta;
        speck.y += speck.vy * delta;
        if (speck.y > rect.height + 8) speck.y = -8;
        if (speck.y < -8) speck.y = rect.height + 8;
        if (speck.x > rect.width + 8) speck.x = -8;
        if (speck.x < -8) speck.x = rect.width + 8;
        ctx!.globalAlpha = speck.alpha * (still ? 0.55 + 0.45 * Math.sin(speck.phase * 2) : 1);
        ctx!.beginPath();
        ctx!.arc(speck.x, speck.y, speck.size, 0, Math.PI * 2);
        ctx!.fill();
      }
      ctx!.globalAlpha = 1;
      frame = window.requestAnimationFrame(draw);
    }
    frame = window.requestAnimationFrame(draw);
    return () => window.cancelAnimationFrame(frame);
  }, [effect, color, intensity, kind]);

  return (
    <div>
      <p className="mb-1.5 text-xs text-ink-muted">
        {effect === "none"
          ? "Nothing selected — the storefront stays exactly as it is."
          : "An impression of the motion and colour, not a pixel-accurate rehearsal."}
      </p>
      <div className="relative h-36 overflow-hidden rounded-md border border-line bg-inverse">
        <canvas ref={canvasRef} aria-hidden className="absolute inset-0 h-full w-full" />
        <p className="absolute bottom-2 left-3 text-xs text-ink-inverse/70">
          {kind === "ambient" ? "Behind the page" : "Following the pointer"}
        </p>
      </div>
    </div>
  );
}
