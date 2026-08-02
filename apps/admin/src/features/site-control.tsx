import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  Button,
  ConfirmDialog,
  EmptyState,
  Field,
  ImagePreview,
  Input,
  PageHeader,
  Select,
  StatusPill,
  Textarea,
} from "../components/ui";
import { useToast } from "../components/toast";
import {
  ApiError,
  api,
  type AnnouncementScopeRow,
  type CmsPageDetail,
  type AdminLinkedProduct,
  type SiteDocuments,
} from "../lib/api";
import type { StorefrontSettings, StorefrontSettingsEffective } from "@truegrit/contracts";
import { formatDateTime } from "../lib/format";

/** Mirrors the identical helpers in `appearance.tsx` — a scope here is either
 *  `'global'` or a two-letter country code, never a page path. */
function isCountryScope(scope: string): boolean {
  return scope !== "global";
}

const siteDocumentsSchema = z.object({
  robotsTxt: z.string().max(20_000),
  sitemapXml: z.string().max(200_000),
  llmsTxt: z.string().max(40_000),
});

type SiteDocumentsForm = z.infer<typeof siteDocumentsSchema>;

const cmsPageSchema = z.object({
  title: z.string().min(3).max(180),
  slug: z
    .string()
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Lowercase letters, numbers and single hyphens"),
  status: z.enum(["draft", "published", "unpublished", "archived"]),
  indexingPolicy: z.enum(["index", "noindex"]),
  seoTitle: z.string().max(160),
  seoDescription: z.string().max(320),
  seoKeywords: z.string().max(500),
  blocksJson: z.string().min(2),
  changeSummary: z.string().max(300),
});

type CmsPageForm = z.infer<typeof cmsPageSchema>;

export function SiteControlPage() {
  return (
    <div>
      <PageHeader
        title="Site Settings"
        description="Site-wide controls: the announcement banner, storefront switches, CMS pages, per-route SEO and crawler files. The homepage itself has its own page."
      />
      <AnnouncementSection />
      <StorefrontSwitchesSection />
      <CmsPagesSection />
      <RouteSeoSection />
      <SiteDocumentsSection />
      <CuratedListSizeSection />
      <HighlightsSection />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Curated list size: the shared cap for Fresh Favourites, Featured
// Categories (Homepage Settings) and Highlighted products (below) -- one
// setting rather than three, since all three are the same shape of feature
// (pick up to N items, in order).
// ---------------------------------------------------------------------------

const FALLBACK_CURATED_MAX_ITEMS = 12;

function CuratedListSizeSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["curated-settings"],
    queryFn: api.curatedSettings,
  });
  const [draft, setDraft] = useState<string | null>(null);

  useEffect(() => {
    setDraft(null);
  }, [data]);

  const mutation = useMutation({
    mutationFn: (maxItems: number) => api.updateCuratedSettings({ maxItems }),
    onSuccess: async (result) => {
      queryClient.setQueryData(["curated-settings"], result);
      setDraft(null);
      toast.success("Curated list size saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the setting."),
  });

  const value = draft ?? String(data?.maxItems ?? FALLBACK_CURATED_MAX_ITEMS);
  const parsed = Number(value);
  const isValid = Number.isInteger(parsed) && parsed >= 1 && parsed <= 50;

  return (
    <section className="mt-10 space-y-3 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">Curated list size</h2>
        <p className="max-w-2xl text-sm text-ink-muted">
          How many products or categories an operator may pick into Fresh Favourites, Featured
          Categories (Homepage Settings) and Highlighted products (below). Raising it saves
          immediately, no deploy needed; up to 50, the ceiling the block format itself enforces.
        </p>
      </div>
      {isLoading ? (
        <p className="text-sm text-ink-muted">Loading...</p>
      ) : (
        <div className="flex items-end gap-2">
          <Field label="Maximum items" htmlFor="curatedMaxItems">
            <Input
              id="curatedMaxItems"
              type="number"
              min={1}
              max={50}
              step={1}
              className="w-28"
              value={value}
              onChange={(event) => setDraft(event.target.value)}
            />
          </Field>
          <Button
            type="button"
            variant="secondary"
            disabled={mutation.isPending || !isValid || parsed === data?.maxItems}
            onClick={() => mutation.mutate(parsed)}
          >
            {mutation.isPending ? "Saving..." : "Save"}
          </Button>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Announcement banner: site-wide, or one per visitor country. Mirrors the
// Colours scope pattern in appearance.tsx (a country row fully replaces the
// global banner for its visitors rather than merging with it — see
// `services/announcements.py`).
// ---------------------------------------------------------------------------

const announcementFormSchema = z.object({
  active: z.boolean(),
  message: z.string().max(220),
  path: z.string().max(200),
});

type AnnouncementFormValues = z.infer<typeof announcementFormSchema>;

function announcementFormDefaults(row?: AnnouncementScopeRow): AnnouncementFormValues {
  return {
    active: row?.active ?? false,
    message: row?.message ?? "",
    path: row?.path ?? "",
  };
}

function AnnouncementSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["announcements"],
    queryFn: api.announcements,
  });
  const [scope, setScope] = useState("global");
  const [newCountry, setNewCountry] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const scopes = data?.scopes ?? [];
  const savedRow = scopes.find((row) => row.scope === scope);
  const countryScopes = scopes.filter((row) => row.scope !== "global").map((row) => row.scope);

  const form = useForm<AnnouncementFormValues>({
    resolver: zodResolver(announcementFormSchema),
    defaultValues: announcementFormDefaults(),
  });

  useEffect(() => {
    form.reset(announcementFormDefaults(savedRow));
    // `savedRow` is derived from `data` each render; comparing by scope + data
    // keeps this from re-running (and clobbering an in-progress edit) on every
    // unrelated query refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, data]);

  function applyResult(result: { scopes: AnnouncementScopeRow[] }) {
    queryClient.setQueryData(["announcements"], result);
    return queryClient.invalidateQueries({ queryKey: ["announcements"] });
  }

  const saveMutation = useMutation({
    mutationFn: (values: AnnouncementFormValues) =>
      api.saveAnnouncement({ scope, ...values, path: values.path.trim() }),
    onSuccess: async (result) => {
      await applyResult(result);
      toast.success(
        scope === "global" ? "Announcement saved." : `Announcement saved for ${scope}.`,
      );
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the announcement."),
  });

  const deleteMutation = useMutation({
    mutationFn: (target: string) => api.deleteAnnouncement(target),
    onSuccess: async (result) => {
      await applyResult(result);
      setConfirmDelete(null);
      setScope("global");
      toast.success("Country announcement removed; it uses the site-wide banner again.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not remove the announcement."),
  });

  function addCountry() {
    const code = newCountry.trim().toUpperCase();
    if (!/^[A-Z]{2}$/.test(code)) {
      toast.error("A country needs a two-letter code, for example IN, US or DE.");
      return;
    }
    setNewCountry("");
    setScope(code);
  }

  if (isLoading) {
    return (
      <section className="space-y-4 border-t border-line pt-5">
        <p className="text-sm text-ink-muted">Loading announcements...</p>
      </section>
    );
  }
  if (isError) {
    return (
      <section className="space-y-4 border-t border-line pt-5">
        <EmptyState title="Announcements unavailable" hint="Requires owner settings access." />
      </section>
    );
  }

  return (
    <section className="space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">Announcement banner</h2>
        <p className="max-w-3xl text-sm text-ink-muted">
          Appears above the customer storefront, on every page. A country's banner fully replaces
          the site-wide one for its visitors when it is on — an owner silencing a market-specific
          announcement does not have the general one reappear underneath it.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56">
          <Field label="Editing" htmlFor="announcement-scope">
            <Select
              id="announcement-scope"
              value={scope}
              onChange={(event) => setScope(event.target.value)}
            >
              <option value="global">Whole site</option>
              {countryScopes.map((countryScope) => (
                <option key={countryScope} value={countryScope}>
                  {countryScope}
                </option>
              ))}
              {isCountryScope(scope) && !countryScopes.includes(scope) ? (
                <option value={scope}>{scope} (unsaved)</option>
              ) : null}
            </Select>
          </Field>
        </div>
        <div className="min-w-32">
          <Field label="Give one country its own banner" htmlFor="announcement-new-country">
            <Input
              id="announcement-new-country"
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
        {isCountryScope(scope) && countryScopes.includes(scope) ? (
          <Button type="button" variant="tertiary" onClick={() => setConfirmDelete(scope)}>
            Remove country banner
          </Button>
        ) : null}
      </div>

      <form
        className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]"
        onSubmit={form.handleSubmit((values) => saveMutation.mutate(values))}
      >
        <div className="space-y-4">
          <label className="flex items-center gap-2 text-sm text-ink">
            <input type="checkbox" {...form.register("active")} />
            Show announcement
          </label>
          <Field label="Banner message" htmlFor="announcementMessage">
            <Input id="announcementMessage" {...form.register("message")} />
          </Field>
          <Field label="Banner link" htmlFor="announcementPath">
            <Input
              id="announcementPath"
              placeholder="/category/fresh-fruits"
              {...form.register("path")}
            />
          </Field>
        </div>

        <aside className="h-fit">
          <Button
            type="submit"
            variant="primary"
            className="w-full"
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending
              ? "Saving..."
              : scope === "global"
                ? "Save announcement"
                : `Save announcement for ${scope}`}
          </Button>
        </aside>
      </form>

      {confirmDelete ? (
        <ConfirmDialog
          title={`Remove the announcement for ${confirmDelete}?`}
          description="Visitors from this country go back to seeing the site-wide banner (or none, if that is off)."
          confirmLabel="Remove country banner"
          pendingLabel="Removing..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => deleteMutation.mutate(confirmDelete)}
        />
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Storefront switches: sign-in methods, taking payments, and the blog banner.
//
// Each switch saves on its own the moment it is toggled — there is no "save"
// button to forget. A kill-switch that only half-applied because someone
// navigated away would be worse than no kill-switch at all.
// ---------------------------------------------------------------------------

interface SignInSwitch {
  field: keyof StorefrontSettings;
  effectiveField: keyof StorefrontSettingsEffective;
  label: string;
  description: string;
  /** Shown when the switch is on but the deployment cannot honour it. */
  unavailableHint: string;
}

const SIGN_IN_SWITCHES: SignInSwitch[] = [
  {
    field: "phoneOtpSignIn",
    effectiveField: "phoneOtpSignIn",
    label: "Mobile number + SMS passcode",
    description: "Sign in and sign up with nothing but a phone number.",
    unavailableHint: "No SMS provider configured (FAST2SMS_API_KEY), so passcodes cannot be sent.",
  },
  {
    field: "passwordSignIn",
    effectiveField: "passwordSignIn",
    label: "Email + password",
    description: "The classic credential pair, including the password-reset flow.",
    unavailableHint: "",
  },
  {
    field: "registration",
    effectiveField: "registration",
    label: "New account sign-ups",
    description:
      "Turn off to freeze new registrations while existing customers keep signing in normally.",
    unavailableHint: "Needs email + password or mobile passcodes to be on as well.",
  },
  {
    field: "googleSignIn",
    effectiveField: "googleSignIn",
    label: "Sign in with Google",
    description: "Google Identity Services button in the storefront account menu.",
    unavailableHint: "No GOOGLE_CLIENT_ID configured on the API, so the button stays hidden.",
  },
  {
    field: "facebookSignIn",
    effectiveField: "facebookSignIn",
    label: "Continue with Facebook",
    description: "Facebook Login button in the storefront account menu.",
    unavailableHint:
      "No FACEBOOK_APP_ID / FACEBOOK_APP_SECRET configured on the API, so the button stays hidden.",
  },
];

function SwitchRow({
  label,
  description,
  checked,
  effective,
  unavailableHint,
  disabled,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  effective: boolean;
  unavailableHint: string;
  disabled: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <li className="flex items-start justify-between gap-4 border-t border-line py-3 first:border-t-0">
      <div className="min-w-0">
        <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-ink">
          <input
            type="checkbox"
            checked={checked}
            disabled={disabled}
            onChange={(event) => onChange(event.target.checked)}
          />
          {label}
        </label>
        <p className="mt-1 text-sm text-ink-muted">{description}</p>
        {/* Ticked but inert. Saying nothing here is how an operator ends up
            certain a method is live when the API cannot offer it. */}
        {checked && !effective && unavailableHint ? (
          <p className="mt-1 text-sm text-warning">{unavailableHint}</p>
        ) : null}
      </div>
      {/* What customers get, which is not always what the box says — hence its
          own wording rather than echoing the checkbox. */}
      <span
        className={
          "inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-medium " +
          (effective ? "bg-success/10 text-success" : "border border-line bg-canvas text-ink-muted")
        }
      >
        {effective ? "Live" : "Off"}
      </span>
    </li>
  );
}

function StorefrontSwitchesSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["storefront-settings"],
    queryFn: api.storefrontSettings,
  });

  // Local drafts for the free-text fields; the checkboxes save immediately.
  const [notice, setNotice] = useState<string | null>(null);
  const [bannerUrl, setBannerUrl] = useState<string | null>(null);
  const [bannerAlt, setBannerAlt] = useState<string | null>(null);
  const [farmsBannerUrl, setFarmsBannerUrl] = useState<string | null>(null);
  const [farmsBannerAlt, setFarmsBannerAlt] = useState<string | null>(null);

  useEffect(() => {
    if (!data) return;
    setNotice(null);
    setBannerUrl(null);
    setBannerAlt(null);
    setFarmsBannerUrl(null);
    setFarmsBannerAlt(null);
  }, [data]);

  // Delivery charges: a separate stored setting, not a boolean switch, so it
  // gets its own query/mutation pair rather than folding into `settings`.
  const { data: delivery } = useQuery({
    queryKey: ["delivery-settings"],
    queryFn: api.deliverySettings,
  });
  const [deliveryFee, setDeliveryFee] = useState<string | null>(null);
  const [freeThreshold, setFreeThreshold] = useState<string | null>(null);

  useEffect(() => {
    if (!delivery) return;
    setDeliveryFee(null);
    setFreeThreshold(null);
  }, [delivery]);

  const deliveryMutation = useMutation({
    mutationFn: (input: { feeMinor: number; freeThresholdMinor: number }) =>
      api.updateDeliverySettings(input),
    onSuccess: async (result) => {
      queryClient.setQueryData(["delivery-settings"], result);
      toast.success("Delivery charges saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save delivery charges."),
  });

  // Subscribe & Save's own incentive -- a separate stored percent, not a
  // boolean switch, the same reasoning delivery charges get their own
  // query/mutation pair above.
  const { data: subscriptionSettings } = useQuery({
    queryKey: ["subscription-settings"],
    queryFn: api.subscriptionSettings,
  });
  const [subscriptionDiscount, setSubscriptionDiscount] = useState<string | null>(null);

  useEffect(() => {
    if (!subscriptionSettings) return;
    setSubscriptionDiscount(null);
  }, [subscriptionSettings]);

  const subscriptionDiscountMutation = useMutation({
    mutationFn: (percent: number) => api.updateSubscriptionSettings({ percent }),
    onSuccess: async (result) => {
      queryClient.setQueryData(["subscription-settings"], result);
      toast.success("Subscription discount saved.");
    },
    onError: (error) =>
      toast.error(
        error instanceof ApiError ? error.message : "Could not save the subscription discount.",
      ),
  });

  const mutation = useMutation({
    mutationFn: (input: Partial<StorefrontSettings>) => api.updateStorefrontSettings(input),
    onSuccess: async (result) => {
      queryClient.setQueryData(["storefront-settings"], result);
      await queryClient.invalidateQueries({ queryKey: ["storefront-settings"] });
      toast.success("Storefront switches saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the switches."),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadImage(file),
    onSuccess: (result) => {
      setBannerUrl(result.url);
      mutation.mutate({ blogBannerImageUrl: result.url });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not upload the banner."),
  });

  const farmsUploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadImage(file),
    onSuccess: (result) => {
      setFarmsBannerUrl(result.url);
      mutation.mutate({ farmsBannerImageUrl: result.url });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not upload the banner."),
  });

  if (isLoading) {
    return (
      <section className="mt-10 border-t border-line pt-5">
        <p className="text-sm text-ink-muted">Loading storefront switches...</p>
      </section>
    );
  }
  if (isError || !data) {
    return (
      <section className="mt-10 border-t border-line pt-5">
        <EmptyState
          title="Storefront switches unavailable"
          hint="Requires owner settings access."
        />
      </section>
    );
  }

  const { settings, effective } = data;
  const noticeValue = notice ?? settings.paymentsDisabledNotice;
  const bannerUrlValue = bannerUrl ?? settings.blogBannerImageUrl;
  const bannerAltValue = bannerAlt ?? settings.blogBannerImageAlt;
  const farmsBannerUrlValue = farmsBannerUrl ?? settings.farmsBannerImageUrl;
  const farmsBannerAltValue = farmsBannerAlt ?? settings.farmsBannerImageAlt;

  return (
    <section className="mt-10 space-y-8 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">Storefront switches</h2>
        <p className="text-sm text-ink-muted">
          Turn sign-in methods and ordering on or off without a deploy. The pill on the right is
          what customers actually get: a switch can only ever take a feature away, never add one the
          API is not configured for.
        </p>
      </div>

      <div>
        <h3 className="text-sm font-semibold tracking-[0.08em] text-ink-muted uppercase">
          Sign-in methods
        </h3>
        {/* Locking every route out of a live storefront is a legitimate thing to
            want, but never a thing to do by accident. */}
        {!effective.anySignInAvailable ? (
          <p className="mt-3 rounded-md border border-danger/40 bg-danger/5 px-4 py-3 text-sm text-danger">
            No sign-in method is available. Customers cannot sign in or reach their orders until at
            least one is switched back on.
          </p>
        ) : null}
        <ul className="mt-3 max-w-3xl">
          {SIGN_IN_SWITCHES.map((entry) => (
            <SwitchRow
              key={entry.field}
              label={entry.label}
              description={entry.description}
              checked={Boolean(settings[entry.field])}
              effective={effective[entry.effectiveField]}
              unavailableHint={entry.unavailableHint}
              disabled={mutation.isPending}
              onChange={(next) => mutation.mutate({ [entry.field]: next })}
            />
          ))}
        </ul>
      </div>

      <div>
        <h3 className="text-sm font-semibold tracking-[0.08em] text-ink-muted uppercase">
          Taking payments
        </h3>
        <ul className="mt-3 max-w-3xl">
          <SwitchRow
            label="Accept orders and payments"
            description="Off closes checkout entirely and shows customers a contact form instead, so interest is still captured. Baskets are left untouched."
            checked={settings.payments}
            effective={effective.payments}
            unavailableHint="No payment method is configured on the API (cash on delivery, Razorpay, PayPal or Stripe)."
            disabled={mutation.isPending}
            onChange={(next) => mutation.mutate({ payments: next })}
          />
        </ul>
        <div className="mt-4 max-w-2xl">
          <Field label="Message shown when ordering is off" htmlFor="paymentsDisabledNotice">
            <Textarea
              id="paymentsDisabledNotice"
              rows={3}
              value={noticeValue}
              onChange={(event) => setNotice(event.target.value)}
              maxLength={600}
            />
          </Field>
          <p className="mt-1 text-xs text-ink-muted">
            Appears above the contact form on checkout and in the basket summary. Up to 600
            characters.
          </p>
          <Button
            type="button"
            variant="secondary"
            className="mt-2"
            disabled={mutation.isPending || noticeValue === settings.paymentsDisabledNotice}
            onClick={() => mutation.mutate({ paymentsDisabledNotice: noticeValue })}
          >
            {mutation.isPending ? "Saving..." : "Save message"}
          </Button>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold tracking-[0.08em] text-ink-muted uppercase">
          Coupons &amp; promotions
        </h3>
        <ul className="mt-3 max-w-3xl">
          <SwitchRow
            label="Enable coupons and promotions"
            description="Off hides the promotions banner on the homepage and checkout, and any coupon code is refused at checkout. Existing promotions and coupons are kept, just not applied."
            checked={settings.promotions}
            effective={effective.promotions}
            unavailableHint=""
            disabled={mutation.isPending}
            onChange={(next) => mutation.mutate({ promotions: next })}
          />
        </ul>
      </div>

      <div>
        <h3 className="text-sm font-semibold tracking-[0.08em] text-ink-muted uppercase">
          Recommendations
        </h3>
        <ul className="mt-3 max-w-3xl">
          <SwitchRow
            label="Show product recommendations"
            description="Real bestsellers and “customers also bought” rows, computed live from actual orders — on the homepage, product pages, basket, category pages, search and the shop. Off removes every one of them; nothing is curated, so there is nothing to lose by switching it back on."
            checked={settings.recommendations}
            effective={effective.recommendations}
            unavailableHint=""
            disabled={mutation.isPending}
            onChange={(next) => mutation.mutate({ recommendations: next })}
          />
        </ul>
      </div>

      <div>
        <h3 className="text-sm font-semibold tracking-[0.08em] text-ink-muted uppercase">
          Subscribe &amp; Save
        </h3>
        <ul className="mt-3 max-w-3xl">
          <SwitchRow
            label="Enable Subscribe & Save"
            description="Lets customers set up recurring cash-on-delivery deliveries of a product from its product page. Off by default and not needed at launch — existing subscriptions are kept and viewable in Subscriptions, just not renewed, while this is off."
            checked={settings.subscriptions}
            effective={effective.subscriptions}
            unavailableHint=""
            disabled={mutation.isPending}
            onChange={(next) => mutation.mutate({ subscriptions: next })}
          />
        </ul>
        <div className="mt-4 flex items-end gap-2">
          <Field label="Discount on each renewal, %" htmlFor="subscriptionDiscountPercent">
            <Input
              id="subscriptionDiscountPercent"
              type="number"
              min={0}
              max={50}
              step={1}
              className="w-28"
              value={subscriptionDiscount ?? String(subscriptionSettings?.discountPercent ?? 5)}
              onChange={(event) => setSubscriptionDiscount(event.target.value)}
            />
          </Field>
          <Button
            type="button"
            variant="secondary"
            disabled={
              subscriptionDiscountMutation.isPending ||
              subscriptionDiscount === null ||
              !Number.isInteger(Number(subscriptionDiscount)) ||
              Number(subscriptionDiscount) < 0 ||
              Number(subscriptionDiscount) > 50
            }
            onClick={() => subscriptionDiscountMutation.mutate(Number(subscriptionDiscount))}
          >
            {subscriptionDiscountMutation.isPending ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold tracking-[0.08em] text-ink-muted uppercase">
          Delivery charges
        </h3>
        <p className="mt-1 max-w-2xl text-sm text-ink-muted">
          Applied at checkout before any coupon or promotion discount. Orders at or above the
          free-delivery threshold pay no delivery fee.
        </p>
        <DeliveryChargesForm
          feeMinor={delivery?.feeMinor}
          freeThresholdMinor={delivery?.freeThresholdMinor}
          feeDraft={deliveryFee}
          freeThresholdDraft={freeThreshold}
          onFeeDraftChange={setDeliveryFee}
          onFreeThresholdDraftChange={setFreeThreshold}
          onSave={(feeMinor, freeThresholdMinor) =>
            deliveryMutation.mutate({ feeMinor, freeThresholdMinor })
          }
          saving={deliveryMutation.isPending}
        />
      </div>

      <div>
        <h3 className="text-sm font-semibold tracking-[0.08em] text-ink-muted uppercase">
          Blog banner
        </h3>
        <p className="mt-1 max-w-2xl text-sm text-ink-muted">
          The banner across the top of <code>/blog</code>, rendered at the same size as the homepage
          hero. Left blank, the shipped hero image is used so the space is never empty.
        </p>
        <div className="mt-4 grid max-w-3xl gap-4 md:grid-cols-[minmax(0,1fr)_16rem] md:items-start">
          <div className="space-y-4">
            <Field label="Banner image URL" htmlFor="blogBannerImageUrl">
              <Input
                id="blogBannerImageUrl"
                placeholder="/homepage-hero.png"
                value={bannerUrlValue}
                onChange={(event) => setBannerUrl(event.target.value)}
              />
            </Field>
            <Field label="Banner alt text" htmlFor="blogBannerImageAlt">
              <Input
                id="blogBannerImageAlt"
                value={bannerAltValue}
                onChange={(event) => setBannerAlt(event.target.value)}
              />
            </Field>
            <p className="-mt-2 text-xs text-ink-muted">
              Describe the image for screen readers. Leave blank if it is purely decorative — the
              banner heading already carries the meaning.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={
                  mutation.isPending ||
                  (bannerUrlValue === settings.blogBannerImageUrl &&
                    bannerAltValue === settings.blogBannerImageAlt)
                }
                onClick={() =>
                  mutation.mutate({
                    blogBannerImageUrl: bannerUrlValue,
                    blogBannerImageAlt: bannerAltValue,
                  })
                }
              >
                {mutation.isPending ? "Saving..." : "Save banner"}
              </Button>
              <label className="inline-flex min-h-9 cursor-pointer items-center rounded-sm border border-line px-3 text-sm text-ink hover:bg-canvas">
                {uploadMutation.isPending ? "Uploading..." : "Upload image"}
                <input
                  type="file"
                  accept="image/*"
                  className="sr-only"
                  disabled={uploadMutation.isPending}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.target.value = "";
                    if (file) uploadMutation.mutate(file);
                  }}
                />
              </label>
            </div>
          </div>
          <ImagePreview
            src={bannerUrlValue}
            alt={bannerAltValue}
            label="Blog banner"
            className="h-32 w-full"
          />
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold tracking-[0.08em] text-ink-muted uppercase">
          Farms banner
        </h3>
        <p className="mt-1 max-w-2xl text-sm text-ink-muted">
          The banner across the top of <code>/farms</code>, rendered at the same size as the
          homepage hero. Left blank, the shipped hero image is used so the space is never empty.
          Each individual farm page has its own banner image, set on that farm's edit page.
        </p>
        <div className="mt-4 grid max-w-3xl gap-4 md:grid-cols-[minmax(0,1fr)_16rem] md:items-start">
          <div className="space-y-4">
            <Field label="Banner image URL" htmlFor="farmsBannerImageUrl">
              <Input
                id="farmsBannerImageUrl"
                placeholder="/homepage-hero.png"
                value={farmsBannerUrlValue}
                onChange={(event) => setFarmsBannerUrl(event.target.value)}
              />
            </Field>
            <Field label="Banner alt text" htmlFor="farmsBannerImageAlt">
              <Input
                id="farmsBannerImageAlt"
                value={farmsBannerAltValue}
                onChange={(event) => setFarmsBannerAlt(event.target.value)}
              />
            </Field>
            <p className="-mt-2 text-xs text-ink-muted">
              Describe the image for screen readers. Leave blank if it is purely decorative — the
              banner heading already carries the meaning.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={
                  mutation.isPending ||
                  (farmsBannerUrlValue === settings.farmsBannerImageUrl &&
                    farmsBannerAltValue === settings.farmsBannerImageAlt)
                }
                onClick={() =>
                  mutation.mutate({
                    farmsBannerImageUrl: farmsBannerUrlValue,
                    farmsBannerImageAlt: farmsBannerAltValue,
                  })
                }
              >
                {mutation.isPending ? "Saving..." : "Save banner"}
              </Button>
              <label className="inline-flex min-h-9 cursor-pointer items-center rounded-sm border border-line px-3 text-sm text-ink hover:bg-canvas">
                {farmsUploadMutation.isPending ? "Uploading..." : "Upload image"}
                <input
                  type="file"
                  accept="image/*"
                  className="sr-only"
                  disabled={farmsUploadMutation.isPending}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.target.value = "";
                    if (file) farmsUploadMutation.mutate(file);
                  }}
                />
              </label>
            </div>
          </div>
          <ImagePreview
            src={farmsBannerUrlValue}
            alt={farmsBannerAltValue}
            label="Farms banner"
            className="h-32 w-full"
          />
        </div>
      </div>
    </section>
  );
}

function minorToRupeeString(minor: number): string {
  return (minor / 100).toString();
}

function rupeeStringToMinor(value: string): number | null {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) return null;
  return Math.round(parsed * 100);
}

function DeliveryChargesForm({
  feeMinor,
  freeThresholdMinor,
  feeDraft,
  freeThresholdDraft,
  onFeeDraftChange,
  onFreeThresholdDraftChange,
  onSave,
  saving,
}: {
  feeMinor: number | undefined;
  freeThresholdMinor: number | undefined;
  feeDraft: string | null;
  freeThresholdDraft: string | null;
  onFeeDraftChange: (value: string) => void;
  onFreeThresholdDraftChange: (value: string) => void;
  onSave: (feeMinor: number, freeThresholdMinor: number) => void;
  saving: boolean;
}) {
  if (feeMinor === undefined || freeThresholdMinor === undefined) {
    return <p className="mt-3 text-sm text-ink-muted">Loading delivery charges...</p>;
  }

  const feeValue = feeDraft ?? minorToRupeeString(feeMinor);
  const freeThresholdValue = freeThresholdDraft ?? minorToRupeeString(freeThresholdMinor);
  const parsedFee = rupeeStringToMinor(feeValue);
  const parsedFreeThreshold = rupeeStringToMinor(freeThresholdValue);
  const isValid = parsedFee !== null && parsedFreeThreshold !== null;
  const isUnchanged = parsedFee === feeMinor && parsedFreeThreshold === freeThresholdMinor;

  return (
    <div className="mt-4 grid max-w-3xl gap-4 sm:grid-cols-2">
      <Field label="Delivery fee (₹)" htmlFor="deliveryFeeMinor">
        <Input
          id="deliveryFeeMinor"
          type="number"
          min="0"
          step="0.01"
          value={feeValue}
          onChange={(event) => onFeeDraftChange(event.target.value)}
        />
      </Field>
      <Field label="Free delivery above (₹)" htmlFor="freeDeliveryThresholdMinor">
        <Input
          id="freeDeliveryThresholdMinor"
          type="number"
          min="0"
          step="0.01"
          value={freeThresholdValue}
          onChange={(event) => onFreeThresholdDraftChange(event.target.value)}
        />
      </Field>
      <div className="sm:col-span-2">
        <Button
          type="button"
          variant="secondary"
          disabled={!isValid || isUnchanged || saving}
          onClick={() => {
            if (parsedFee !== null && parsedFreeThreshold !== null) {
              onSave(parsedFee, parsedFreeThreshold);
            }
          }}
        >
          {saving ? "Saving..." : "Save delivery charges"}
        </Button>
      </div>
    </div>
  );
}

function cmsPageDefaults(page?: CmsPageDetail): CmsPageForm {
  return {
    title: page?.title ?? "",
    slug: page?.slug ?? "",
    status: (page?.status as CmsPageForm["status"]) ?? "published",
    indexingPolicy: page?.indexingPolicy ?? "index",
    seoTitle: page?.seoTitle ?? "",
    seoDescription: page?.seoDescription ?? "",
    seoKeywords: page?.seoKeywords ?? "",
    blocksJson: page ? JSON.stringify(page.blocks, null, 2) : "[]",
    changeSummary: "",
  };
}

function CmsPagesSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const pages = useQuery({ queryKey: ["cms-pages"], queryFn: api.cmsPages });
  const [selectedId, setSelectedId] = useState("");
  const selected = useQuery({
    queryKey: ["cms-page", selectedId],
    queryFn: () => api.cmsPage(selectedId),
    enabled: Boolean(selectedId),
  });
  const form = useForm<CmsPageForm>({
    resolver: zodResolver(cmsPageSchema),
    defaultValues: cmsPageDefaults(),
  });

  useEffect(() => {
    const firstPageId = pages.data?.[0]?.id;
    if (!selectedId && firstPageId) setSelectedId(firstPageId);
  }, [pages.data, selectedId]);

  useEffect(() => {
    if (selected.data) form.reset(cmsPageDefaults(selected.data));
  }, [form, selected.data]);

  const mutation = useMutation({
    mutationFn: (values: CmsPageForm) => {
      let blocks: unknown;
      try {
        blocks = JSON.parse(values.blocksJson);
      } catch {
        throw new ApiError("Blocks JSON is not valid.", 422, "validation_error");
      }
      if (!Array.isArray(blocks)) {
        throw new ApiError("Blocks JSON must be an array.", 422, "validation_error");
      }
      return api.updateCmsPage(selectedId, {
        title: values.title,
        slug: values.slug,
        status: values.status,
        indexingPolicy: values.indexingPolicy,
        seoTitle: values.seoTitle,
        seoDescription: values.seoDescription,
        seoKeywords: values.seoKeywords,
        blocks: blocks as CmsPageDetail["blocks"],
        changeSummary: values.changeSummary || "Updated CMS page from admin.",
      });
    },
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["cms-pages"] }),
        queryClient.invalidateQueries({ queryKey: ["cms-page", result.id] }),
      ]);
      form.reset(cmsPageDefaults(result));
      toast.success("CMS page saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save CMS page."),
  });

  return (
    <section className="mt-10 space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">CMS pages & SEO</h2>
        <p className="text-sm text-ink-muted">
          Edit CMS page metadata, indexing and raw page blocks. The homepage record is listed here
          too, but Homepage Settings is the safer way to change it — this editor takes raw JSON.
        </p>
      </div>
      {pages.isError ? (
        <EmptyState
          title="CMS pages unavailable"
          hint="Requires pages.view permission and a connected API."
        />
      ) : (
        <div className="grid gap-6 xl:grid-cols-[20rem_minmax(0,1fr)]">
          <div className="space-y-3">
            {pages.isLoading ? (
              <p className="text-sm text-ink-muted">Loading CMS pages...</p>
            ) : (pages.data ?? []).length === 0 ? (
              <EmptyState title="No CMS pages found" hint="No page records have been seeded." />
            ) : (
              (pages.data ?? []).map((page) => (
                <button
                  key={page.id}
                  type="button"
                  className={`block w-full rounded-md border px-3 py-3 text-left text-sm ${
                    selectedId === page.id
                      ? "border-brand bg-subtle/60"
                      : "border-line bg-surface hover:bg-subtle/40"
                  }`}
                  onClick={() => setSelectedId(page.id)}
                >
                  <span className="block font-medium text-ink">{page.title}</span>
                  <span className="mt-1 block text-xs text-ink-muted">/{page.slug}</span>
                  <span className="mt-2 flex items-center justify-between gap-2">
                    <StatusPill status={page.status} />
                    <span className="text-xs text-ink-muted">{page.blockCount} blocks</span>
                  </span>
                </button>
              ))
            )}
          </div>

          {selected.isLoading ? (
            <p className="text-sm text-ink-muted">Loading selected page...</p>
          ) : selected.isError ? (
            <EmptyState
              title="Page unavailable"
              hint="The selected CMS page could not be loaded."
            />
          ) : selected.data ? (
            <div className="space-y-8">
            <form
              className="space-y-5"
              onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
            >
              <div className="grid gap-4 md:grid-cols-2">
                <Field
                  label="Title"
                  htmlFor="cms-title"
                  error={form.formState.errors.title?.message}
                >
                  <Input id="cms-title" {...form.register("title")} />
                </Field>
                <Field label="Slug" htmlFor="cms-slug" error={form.formState.errors.slug?.message}>
                  <Input id="cms-slug" {...form.register("slug")} />
                </Field>
                <Field label="Status" htmlFor="cms-status">
                  <Select id="cms-status" {...form.register("status")}>
                    <option value="draft">Draft</option>
                    <option value="published">Published</option>
                    <option value="unpublished">Unpublished</option>
                    <option value="archived">Archived</option>
                  </Select>
                </Field>
                <Field label="Search indexing" htmlFor="cms-indexing">
                  <Select id="cms-indexing" {...form.register("indexingPolicy")}>
                    <option value="index">Index</option>
                    <option value="noindex">No index</option>
                  </Select>
                </Field>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <Field
                  label="SEO title"
                  htmlFor="cms-seo-title"
                  error={form.formState.errors.seoTitle?.message}
                >
                  <Input id="cms-seo-title" {...form.register("seoTitle")} />
                </Field>
                <Field label="SEO keywords" htmlFor="cms-seo-keywords">
                  <Input id="cms-seo-keywords" {...form.register("seoKeywords")} />
                </Field>
              </div>
              <Field label="SEO description" htmlFor="cms-seo-description">
                <Textarea id="cms-seo-description" rows={3} {...form.register("seoDescription")} />
              </Field>
              <Field
                label="Page blocks JSON"
                htmlFor="cms-blocks"
                error={form.formState.errors.blocksJson?.message}
              >
                <Textarea
                  id="cms-blocks"
                  rows={18}
                  className="font-mono text-xs"
                  {...form.register("blocksJson")}
                />
              </Field>
              <Field label="Change summary" htmlFor="cms-change-summary">
                <Input
                  id="cms-change-summary"
                  placeholder="What changed?"
                  {...form.register("changeSummary")}
                />
              </Field>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-ink-muted">
                  Last updated {formatDateTime(selected.data.updatedAt)}
                </p>
                <Button type="submit" variant="primary" disabled={mutation.isPending}>
                  {mutation.isPending ? "Saving..." : "Save CMS page"}
                </Button>
              </div>
            </form>
            <PageTranslationsPanel pageId={selectedId} />
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Per-locale page content (migration 0067). The homepage and static pages
// both use `pages`/`page_versions`, so this one editor translates both --
// see PageTranslationsPanel below, rendered alongside CmsPagesSection's own
// English-content form for whichever page is selected there.
//
// The locale list mirrors `apps/storefront/app/lib/i18n/locales.ts` (kept
// as a small local copy rather than a shared import: that module lives in
// the storefront package, and a plain list of BCP-47 codes and names is
// static reference data, not logic worth a cross-package dependency for).
// ---------------------------------------------------------------------------

const TRANSLATION_LOCALES: { code: string; label: string }[] = [
  { code: "hi", label: "Hindi (हिन्दी)" },
  { code: "bn", label: "Bengali (বাংলা)" },
  { code: "mr", label: "Marathi (मराठी)" },
  { code: "te", label: "Telugu (తెలుగు)" },
  { code: "ta", label: "Tamil (தமிழ்)" },
  { code: "gu", label: "Gujarati (ગુજરાતી)" },
  { code: "ur", label: "Urdu (اردو)" },
  { code: "kn", label: "Kannada (ಕನ್ನಡ)" },
  { code: "or", label: "Odia (ଓଡ଼ିଆ)" },
  { code: "ml", label: "Malayalam (മലയാളം)" },
  { code: "pa", label: "Punjabi (ਪੰਜਾਬੀ)" },
  { code: "as", label: "Assamese (অসমীয়া)" },
  { code: "mai", label: "Maithili (मैथिली)" },
  { code: "sat", label: "Santali (ᱥᱟᱱᱛᱟᱲᱤ)" },
  { code: "ks", label: "Kashmiri (کٲشُر)" },
  { code: "ne", label: "Nepali (नेपाली)" },
  { code: "sd", label: "Sindhi (سنڌي)" },
  { code: "kok", label: "Konkani (कोंकणी)" },
  { code: "doi", label: "Dogri (डोगरी)" },
  { code: "mni", label: "Manipuri (ꯃꯤꯇꯩꯂꯣꯟ)" },
  { code: "brx", label: "Bodo (बर’)" },
  { code: "sa", label: "Sanskrit (संस्कृतम्)" },
  { code: "zh-Hans", label: "Chinese, Simplified (简体中文)" },
  { code: "es", label: "Spanish (Español)" },
  { code: "ar", label: "Arabic (العربية)" },
  { code: "pt", label: "Portuguese (Português)" },
  { code: "fr", label: "French (Français)" },
  { code: "ru", label: "Russian (Русский)" },
  { code: "id", label: "Indonesian (Bahasa Indonesia)" },
  { code: "de", label: "German (Deutsch)" },
  { code: "ja", label: "Japanese (日本語)" },
  { code: "tr", label: "Turkish (Türkçe)" },
  { code: "vi", label: "Vietnamese (Tiếng Việt)" },
  { code: "ko", label: "Korean (한국어)" },
  { code: "it", label: "Italian (Italiano)" },
  { code: "fa", label: "Persian (فارسی)" },
  { code: "zh-Hant", label: "Chinese, Traditional (繁體中文)" },
  { code: "th", label: "Thai (ไทย)" },
  { code: "pl", label: "Polish (Polski)" },
  { code: "uk", label: "Ukrainian (Українська)" },
  { code: "nl", label: "Dutch (Nederlands)" },
  { code: "fil", label: "Filipino" },
  { code: "sw", label: "Swahili (Kiswahili)" },
  { code: "he", label: "Hebrew (עברית)" },
  { code: "sv", label: "Swedish (Svenska)" },
  { code: "nb", label: "Norwegian (Norsk bokmål)" },
  { code: "da", label: "Danish (Dansk)" },
  { code: "fi", label: "Finnish (Suomi)" },
  { code: "el", label: "Greek (Ελληνικά)" },
  { code: "cs", label: "Czech (Čeština)" },
  { code: "hu", label: "Hungarian (Magyar)" },
  { code: "ro", label: "Romanian (Română)" },
  { code: "sk", label: "Slovak (Slovenčina)" },
  { code: "bg", label: "Bulgarian (Български)" },
];

function PageTranslationsPanel({ pageId }: { pageId: string }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [locale, setLocale] = useState(TRANSLATION_LOCALES[0]!.code);
  const [blocksJson, setBlocksJson] = useState("");

  const translation = useQuery({
    queryKey: ["page-translation", pageId, locale],
    queryFn: () => api.pageTranslation(pageId, locale),
  });
  const translatedLocales = useQuery({
    queryKey: ["page-translations", pageId],
    queryFn: () => api.pageTranslations(pageId),
  });

  useEffect(() => {
    if (translation.data) setBlocksJson(JSON.stringify(translation.data.content.blocks, null, 2));
  }, [translation.data]);

  function invalidate() {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["page-translation", pageId, locale] }),
      queryClient.invalidateQueries({ queryKey: ["page-translations", pageId] }),
    ]);
  }

  const saveMutation = useMutation({
    mutationFn: () => {
      let blocks: unknown;
      try {
        blocks = JSON.parse(blocksJson);
      } catch {
        throw new ApiError("Translated blocks JSON is not valid.", 422, "validation_error");
      }
      if (!Array.isArray(blocks)) {
        throw new ApiError("Translated blocks JSON must be an array.", 422, "validation_error");
      }
      return api.savePageTranslation(pageId, locale, blocks as CmsPageDetail["blocks"]);
    },
    onSuccess: async () => {
      await invalidate();
      toast.success("Translation saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the translation."),
  });

  const autoTranslateMutation = useMutation({
    mutationFn: () => api.autoTranslatePage(pageId, locale),
    onSuccess: async () => {
      await invalidate();
      toast.success("Auto-translated — review the result before it goes live.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not auto-translate."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deletePageTranslation(pageId, locale),
    onSuccess: async () => {
      await invalidate();
      toast.success("Translation removed — this locale now falls back to English.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not remove the translation."),
  });

  const translatedLocaleCodes = new Set((translatedLocales.data ?? []).map((entry) => entry.locale));
  const busy =
    saveMutation.isPending || autoTranslateMutation.isPending || deleteMutation.isPending;

  return (
    <div className="border-t border-line pt-5">
      <h3 className="font-display text-lg text-ink">Translations</h3>
      <p className="mt-1 text-sm text-ink-muted">
        A parallel copy of this page's blocks for one language at a time. A locale with no saved
        translation falls back to English on the storefront — nothing breaks by leaving one blank.
        "Auto-translate" runs a real machine-translation model on the Worker's own AI binding
        (free, but not perfect) and fills the box below for review, it does not save on its own.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Select
          value={locale}
          onChange={(event) => setLocale(event.target.value)}
          aria-label="Locale to translate"
          className="max-w-xs"
        >
          {TRANSLATION_LOCALES.map((entry) => (
            <option key={entry.code} value={entry.code}>
              {translatedLocaleCodes.has(entry.code) ? "✓ " : ""}
              {entry.label}
            </option>
          ))}
        </Select>
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          onClick={() => autoTranslateMutation.mutate()}
        >
          {autoTranslateMutation.isPending ? "Translating..." : "Auto-translate"}
        </Button>
      </div>

      {translation.data?.autoTranslated ? (
        <p className="mt-3 rounded-md border border-warning/40 bg-warning/5 px-4 py-2 text-sm text-warning">
          Machine-translated, not yet reviewed by a person.
        </p>
      ) : null}

      <Textarea
        className="mt-3 font-mono text-xs"
        rows={16}
        value={blocksJson}
        onChange={(event) => setBlocksJson(event.target.value)}
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-ink-muted">
          {translation.data?.updatedAt
            ? `Last saved ${formatDateTime(translation.data.updatedAt)}`
            : "No saved translation for this locale yet — showing English as a starting point."}
        </p>
        <div className="flex gap-2">
          {translation.data?.updatedAt ? (
            <Button
              type="button"
              variant="destructive"
              disabled={busy}
              onClick={() => deleteMutation.mutate()}
            >
              Remove translation
            </Button>
          ) : null}
          <Button
            type="button"
            variant="primary"
            disabled={busy}
            onClick={() => saveMutation.mutate()}
          >
            {saveMutation.isPending ? "Saving..." : "Save translation"}
          </Button>
        </div>
      </div>
    </div>
  );
}

/** Storefront routes that carry SEO metadata but have no single-segment CMS
 * page record to hold it (see migration 0035 — `pages.slug` can't contain a
 * `/`, so nested routes like `/blog/submit` can't use the CMS page editor
 * above). Each entry falls back to sensible hardcoded metadata in its own
 * route file until an admin saves an override here. */
const MANAGEABLE_ROUTES = [
  { path: "/blog/submit", label: "Post a blog (submission form)" },
  { path: "/recipes/submit", label: "Post a recipe (submission form)" },
  { path: "/community", label: "Community" },
] as const;

const routeSeoSchema = z.object({
  seoTitle: z.string().max(160),
  seoDescription: z.string().max(320),
  seoKeywords: z.string().max(500),
  indexingPolicy: z.enum(["index", "noindex"]),
});

type RouteSeoForm = z.infer<typeof routeSeoSchema>;

function routeSeoDefaults(entry?: {
  seoTitle: string | null;
  seoDescription: string | null;
  seoKeywords: string | null;
  indexingPolicy: "index" | "noindex";
}): RouteSeoForm {
  return {
    seoTitle: entry?.seoTitle ?? "",
    seoDescription: entry?.seoDescription ?? "",
    seoKeywords: entry?.seoKeywords ?? "",
    indexingPolicy: entry?.indexingPolicy ?? "index",
  };
}

function RouteSeoSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [selectedPath, setSelectedPath] = useState<string>(MANAGEABLE_ROUTES[0].path);
  const { data: overrides, isLoading } = useQuery({
    queryKey: ["route-seo"],
    queryFn: api.routeSeoList,
  });
  const selected = overrides?.find((entry) => entry.path === selectedPath);
  const form = useForm<RouteSeoForm>({
    resolver: zodResolver(routeSeoSchema),
    defaultValues: routeSeoDefaults(),
  });

  useEffect(() => {
    form.reset(routeSeoDefaults(selected));
  }, [selectedPath, selected, form]);

  const mutation = useMutation({
    mutationFn: (values: RouteSeoForm) =>
      api.updateRouteSeo({
        path: selectedPath,
        seoTitle: values.seoTitle,
        seoDescription: values.seoDescription,
        seoKeywords: values.seoKeywords,
        indexingPolicy: values.indexingPolicy,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["route-seo"] });
      toast.success("Route SEO saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save route SEO."),
  });

  return (
    <section className="mt-10 space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">Page SEO</h2>
        <p className="text-sm text-ink-muted">
          Title, description, keywords and indexing for storefront routes that aren't backed by a
          CMS page above. Leave a field blank to keep that route's built-in default.
        </p>
      </div>
      <div className="grid gap-6 xl:grid-cols-[16rem_minmax(0,1fr)]">
        <div className="space-y-2">
          {MANAGEABLE_ROUTES.map((route) => (
            <button
              key={route.path}
              type="button"
              className={`block w-full rounded-md border px-3 py-3 text-left text-sm ${
                selectedPath === route.path
                  ? "border-brand bg-subtle/60"
                  : "border-line bg-surface hover:bg-subtle/40"
              }`}
              onClick={() => setSelectedPath(route.path)}
            >
              <span className="block font-medium text-ink">{route.label}</span>
              <span className="mt-1 block text-xs text-ink-muted">{route.path}</span>
            </button>
          ))}
        </div>

        {isLoading ? (
          <p className="text-sm text-ink-muted">Loading...</p>
        ) : (
          <form
            className="space-y-4"
            onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
          >
            <Field label="SEO title" htmlFor="route-seo-title">
              <Input
                id="route-seo-title"
                placeholder="Falls back to the route's built-in title"
                {...form.register("seoTitle")}
              />
            </Field>
            <Field label="SEO description" htmlFor="route-seo-description">
              <Textarea
                id="route-seo-description"
                rows={3}
                placeholder="Falls back to the route's built-in description"
                {...form.register("seoDescription")}
              />
            </Field>
            <Field label="SEO keywords" htmlFor="route-seo-keywords">
              <Input id="route-seo-keywords" {...form.register("seoKeywords")} />
            </Field>
            <Field label="Search indexing" htmlFor="route-seo-indexing">
              <Select id="route-seo-indexing" {...form.register("indexingPolicy")}>
                <option value="index">Index</option>
                <option value="noindex">No index</option>
              </Select>
            </Field>
            <Button type="submit" variant="primary" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving..." : "Save page SEO"}
            </Button>
          </form>
        )}
      </div>
    </section>
  );
}

function siteDocumentsDefaults(data?: SiteDocuments): SiteDocumentsForm {
  return {
    robotsTxt: data?.robotsTxt ?? "",
    sitemapXml: data?.sitemapXml ?? "",
    llmsTxt: data?.llmsTxt ?? "",
  };
}

function SiteDocumentsSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["site-documents"],
    queryFn: api.siteDocuments,
  });
  const form = useForm<SiteDocumentsForm>({
    resolver: zodResolver(siteDocumentsSchema),
    defaultValues: siteDocumentsDefaults(),
  });

  useEffect(() => {
    if (data) form.reset(siteDocumentsDefaults(data));
  }, [data, form]);

  const mutation = useMutation({
    mutationFn: (values: SiteDocumentsForm) => api.updateSiteDocuments(values),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["site-documents"] });
      form.reset(siteDocumentsDefaults(result));
      toast.success("Crawler files saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save crawler files."),
  });

  if (isLoading) return <p className="mt-10 text-sm text-ink-muted">Loading crawler files...</p>;
  if (isError) {
    return (
      <EmptyState
        title="Crawler files unavailable"
        hint="Only the owner account can edit sitemap.xml, robots.txt and llms.txt."
      />
    );
  }

  return (
    <section className="mt-10 space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">Crawler files</h2>
        <p className="text-sm text-ink-muted">
          Owner-only controls for /sitemap.xml, /robots.txt and /llms.txt.
        </p>
      </div>
      <form
        className="grid gap-4"
        onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
      >
        <Field
          label="robots.txt"
          htmlFor="robotsTxt"
          error={form.formState.errors.robotsTxt?.message}
        >
          <Textarea id="robotsTxt" rows={9} {...form.register("robotsTxt")} />
        </Field>
        <Field
          label="sitemap.xml"
          htmlFor="sitemapXml"
          error={form.formState.errors.sitemapXml?.message}
        >
          <Textarea id="sitemapXml" rows={14} {...form.register("sitemapXml")} />
        </Field>
        <Field label="llms.txt" htmlFor="llmsTxt" error={form.formState.errors.llmsTxt?.message}>
          <Textarea id="llmsTxt" rows={12} {...form.register("llmsTxt")} />
        </Field>
        <Button
          type="submit"
          variant="primary"
          className="w-fit"
          disabled={mutation.isPending || !form.formState.isDirty}
        >
          {mutation.isPending ? "Saving..." : "Save crawler files"}
        </Button>
      </form>
    </section>
  );
}

/** The highlighted-products slots shown on the storefront search page. One
 * curated, ordered list — add, remove and reorder to swap products in and out. */
function HighlightsSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data: saved, isLoading } = useQuery({
    queryKey: ["highlights"],
    queryFn: api.highlights,
  });
  const { data: allProducts } = useQuery({
    queryKey: ["admin-products", "all"],
    queryFn: () => api.products({ limit: 100 }),
  });
  const { data: curatedSettings } = useQuery({
    queryKey: ["curated-settings"],
    queryFn: api.curatedSettings,
  });
  const maxHighlights = curatedSettings?.maxItems ?? FALLBACK_CURATED_MAX_ITEMS;
  const [items, setItems] = useState<AdminLinkedProduct[] | null>(null);
  const [pendingId, setPendingId] = useState("");

  const current = items ?? saved ?? [];
  const dirty =
    items !== null &&
    (saved ?? []).map((entry) => entry.id).join(",") !== items.map((entry) => entry.id).join(",");

  const mutation = useMutation({
    mutationFn: (productIds: string[]) => api.setHighlights(productIds),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["highlights"] });
      setItems(null);
      toast.success("Highlighted products saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save highlights."),
  });

  const addable = (allProducts ?? []).filter(
    (row) => !current.some((entry) => entry.id === row.id),
  );

  function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= current.length) return;
    const next = [...current];
    const sourceItem = next[index];
    const targetItem = next[target];
    if (!sourceItem || !targetItem) return;
    next[index] = targetItem;
    next[target] = sourceItem;
    setItems(next);
  }

  return (
    <section className="mt-10 space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">Highlighted products</h2>
        <p className="text-sm text-ink-muted">
          Shown in the highlights box on the storefront search page, in this order. Only published
          products appear to customers.
        </p>
      </div>
      {isLoading ? (
        <p className="text-sm text-ink-muted">Loading highlights...</p>
      ) : current.length === 0 ? (
        <p className="max-w-xl rounded-md border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
          No highlighted products yet. Add a few below.
        </p>
      ) : (
        <ul className="max-w-xl divide-y divide-line rounded-md border border-line">
          {current.map((entry, index) => (
            <li key={entry.id} className="flex items-center gap-2 px-3 py-2 text-sm">
              <span className="w-5 text-xs text-ink-muted">{index + 1}.</span>
              <span className="flex-1 font-medium text-ink">{entry.name}</span>
              <StatusPill status={entry.status} />
              <button
                type="button"
                aria-label={`Move ${entry.name} up`}
                className="min-h-8 min-w-8 rounded-sm border border-line text-xs disabled:opacity-40"
                disabled={index === 0}
                onClick={() => move(index, -1)}
              >
                ↑
              </button>
              <button
                type="button"
                aria-label={`Move ${entry.name} down`}
                className="min-h-8 min-w-8 rounded-sm border border-line text-xs disabled:opacity-40"
                disabled={index === current.length - 1}
                onClick={() => move(index, 1)}
              >
                ↓
              </button>
              <button
                type="button"
                aria-label={`Remove ${entry.name}`}
                className="min-h-8 rounded-sm border border-line px-2 text-xs text-danger"
                onClick={() => setItems(current.filter((item) => item.id !== entry.id))}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex max-w-xl gap-2">
        <Select
          aria-label="Product to highlight"
          value={pendingId}
          onChange={(event) => setPendingId(event.target.value)}
          className="flex-1"
        >
          <option value="">Add a product…</option>
          {addable.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </Select>
        <Button
          type="button"
          variant="secondary"
          disabled={!pendingId || current.length >= maxHighlights}
          onClick={() => {
            const row = addable.find((entry) => entry.id === pendingId);
            if (!row) return;
            setItems([...current, { id: row.id, name: row.name, slug: "", status: row.status }]);
            setPendingId("");
          }}
        >
          Add to highlights
        </Button>
      </div>
      <Button
        type="button"
        variant="primary"
        disabled={mutation.isPending || !dirty}
        onClick={() => mutation.mutate(current.map((entry) => entry.id))}
      >
        {mutation.isPending ? "Saving..." : "Save highlights"}
      </Button>
    </section>
  );
}
