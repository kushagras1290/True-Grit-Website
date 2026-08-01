import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  Button,
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
  type CmsPageDetail,
  type AdminLinkedProduct,
  type SiteControl,
  type SiteDocuments,
} from "../lib/api";
import type { StorefrontSettings, StorefrontSettingsEffective } from "@truegrit/contracts";
import { formatDateTime } from "../lib/format";

const announcementSchema = z.object({
  announcementActive: z.boolean(),
  announcementMessage: z.string().max(220),
  announcementPath: z.string().max(200),
});

type AnnouncementForm = z.infer<typeof announcementSchema>;

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

function announcementDefaults(data?: SiteControl): AnnouncementForm {
  return {
    announcementActive: data?.announcementActive ?? false,
    announcementMessage: data?.announcementMessage ?? "",
    announcementPath: data?.announcementPath ?? "",
  };
}

export function SiteControlPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["site-control"],
    queryFn: api.siteControl,
  });
  const form = useForm<AnnouncementForm>({
    resolver: zodResolver(announcementSchema),
    defaultValues: announcementDefaults(),
  });

  useEffect(() => {
    if (data) form.reset(announcementDefaults(data));
  }, [data, form]);

  const mutation = useMutation({
    // Only the announcement fields are sent. The homepage fields live on their
    // own page now, and PATCH ignores what it is not given -- so saving here
    // can never quietly revert a banner someone changed there a minute ago.
    mutationFn: (values: AnnouncementForm) =>
      api.updateSiteControl({
        announcementActive: values.announcementActive,
        announcementMessage: values.announcementMessage,
        announcementPath: values.announcementPath.trim(),
      }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["site-control"] });
      form.reset(announcementDefaults(result));
      toast.success("Announcement saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the announcement."),
  });

  return (
    <div>
      <PageHeader
        title="Site Settings"
        description="Site-wide controls: the announcement banner, storefront switches, CMS pages, per-route SEO and crawler files. The homepage itself has its own page."
      />

      {isLoading ? (
        <p className="text-sm text-ink-muted">Loading site settings...</p>
      ) : isError ? (
        <EmptyState title="Site settings unavailable" hint="Requires owner settings access." />
      ) : (
        <form
          className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]"
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
        >
          <section className="space-y-4 border-t border-line pt-5">
            <div>
              <h2 className="font-display text-lg text-ink">Announcement banner</h2>
              <p className="text-sm text-ink-muted">
                Appears above the customer storefront, on every page.
              </p>
            </div>
            <label className="flex items-center gap-2 text-sm text-ink">
              <input type="checkbox" {...form.register("announcementActive")} />
              Show announcement
            </label>
            <Field label="Banner message" htmlFor="announcementMessage">
              <Input id="announcementMessage" {...form.register("announcementMessage")} />
            </Field>
            <Field label="Banner link" htmlFor="announcementPath">
              <Input
                id="announcementPath"
                placeholder="/category/fresh-fruits"
                {...form.register("announcementPath")}
              />
            </Field>
          </section>

          <aside className="h-fit border-t border-line pt-5">
            <h2 className="font-display text-lg text-ink">Owner permissions</h2>
            <p className="mt-1 text-sm text-ink-muted">
              Farm-owner accounts do not receive settings permissions, so they cannot access these
              global storefront controls.
            </p>
            <Button
              type="submit"
              variant="primary"
              className="mt-5 w-full"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "Saving..." : "Save announcement"}
            </Button>
          </aside>
        </form>
      )}

      <StorefrontSwitchesSection />
      <CmsPagesSection />
      <RouteSeoSection />
      <SiteDocumentsSection />
      <HighlightsSection />
    </div>
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

  useEffect(() => {
    if (!data) return;
    setNotice(null);
    setBannerUrl(null);
    setBannerAlt(null);
  }, [data]);

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
    </section>
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
          ) : null}
        </div>
      )}
    </section>
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
          disabled={!pendingId || current.length >= 12}
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
