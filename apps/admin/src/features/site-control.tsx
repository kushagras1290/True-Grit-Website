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
  type AdminLinkedProduct,
  type SiteControl,
  type SiteDocuments,
} from "../lib/api";

const imageUrlSchema = z
  .string()
  .max(1000)
  .refine(
    (value) =>
      value === "" ||
      (value.startsWith("/") && !value.startsWith("//")) ||
      z.string().url().safeParse(value).success,
    "Enter a valid image URL",
  );

const hrefSchema = z
  .string()
  .min(1)
  .max(512)
  .refine(
    (value) =>
      !value.startsWith("//") &&
      (value.startsWith("/") ||
        value.startsWith("https://") ||
        value.startsWith("http://") ||
        value.startsWith("mailto:")),
    "Enter a valid link",
  );
const optionalHrefSchema = z
  .string()
  .max(512)
  .refine(
    (value) =>
      value === "" ||
      (!value.startsWith("//") &&
        (value.startsWith("/") ||
          value.startsWith("https://") ||
          value.startsWith("http://") ||
          value.startsWith("mailto:"))),
    "Enter a valid link",
  );

const heroSlideSchema = z.object({
  imageUrl: imageUrlSchema,
  imageAlt: z.string().max(200),
  href: hrefSchema,
  label: z.string().min(1).max(80),
  enabled: z.boolean(),
});

const siteSchema = z.object({
  announcementActive: z.boolean(),
  announcementMessage: z.string().max(220),
  announcementPath: z.string().max(200),
  heroEyebrow: z.string().max(120),
  heroHeading: z.string().min(3).max(160),
  heroText: z.string().max(500),
  heroImageUrl: imageUrlSchema,
  heroImageAlt: z.string().max(200),
  heroSlides: z.array(heroSlideSchema).max(8),
  primaryActionLabel: z.string().max(80),
  primaryActionHref: optionalHrefSchema,
  secondaryActionLabel: z.string().max(80),
  secondaryActionHref: optionalHrefSchema,
  seoTitle: z.string().min(3).max(160),
  seoDescription: z.string().max(320),
  seoKeywords: z.string().max(500),
});

type SiteForm = z.infer<typeof siteSchema>;

const siteDocumentsSchema = z.object({
  robotsTxt: z.string().max(20_000),
  sitemapXml: z.string().max(200_000),
  llmsTxt: z.string().max(40_000),
});

type SiteDocumentsForm = z.infer<typeof siteDocumentsSchema>;

function defaultHeroSlides(data?: SiteControl): SiteForm["heroSlides"] {
  if (data?.heroSlides?.length) {
    return data.heroSlides.map((slide) => ({
      imageUrl: slide.imageUrl,
      imageAlt: slide.imageAlt,
      href: slide.href,
      label: slide.label,
      enabled: slide.enabled ?? true,
    }));
  }
  if (data?.heroImageUrl) {
    return [
      {
        imageUrl: data.heroImageUrl,
        imageAlt: data.heroImageAlt,
        href: data.primaryActionHref || "/shop",
        label: data.primaryActionLabel || "Explore",
        enabled: true,
      },
    ];
  }
  return [];
}

function defaults(data?: SiteControl): SiteForm {
  return {
    announcementActive: data?.announcementActive ?? false,
    announcementMessage: data?.announcementMessage ?? "",
    announcementPath: data?.announcementPath ?? "",
    heroEyebrow: data?.heroEyebrow ?? "",
    heroHeading: data?.heroHeading ?? "",
    heroText: data?.heroText ?? "",
    heroImageUrl: data?.heroImageUrl ?? "",
    heroImageAlt: data?.heroImageAlt ?? "",
    heroSlides: defaultHeroSlides(data),
    primaryActionLabel: data?.primaryActionLabel ?? "",
    primaryActionHref: data?.primaryActionHref ?? "",
    secondaryActionLabel: data?.secondaryActionLabel ?? "",
    secondaryActionHref: data?.secondaryActionHref ?? "",
    seoTitle: data?.seoTitle ?? "",
    seoDescription: data?.seoDescription ?? "",
    seoKeywords: data?.seoKeywords ?? "",
  };
}

export function SiteControlPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["site-control"],
    queryFn: api.siteControl,
  });
  const form = useForm<SiteForm>({
    resolver: zodResolver(siteSchema),
    defaultValues: defaults(),
  });
  const watchedHeroImageUrl = form.watch("heroImageUrl");
  const watchedHeroImageAlt = form.watch("heroImageAlt");
  const watchedHeroSlides = form.watch("heroSlides");

  useEffect(() => {
    if (data) form.reset(defaults(data));
  }, [data, form]);

  function payload(values: SiteForm): SiteForm {
    const slides = values.heroSlides
      .filter((slide) => slide.imageUrl.trim())
      .map((slide) => ({
        ...slide,
        imageUrl: slide.imageUrl.trim(),
        imageAlt: slide.imageAlt.trim(),
        href: slide.href.trim(),
        label: slide.label.trim(),
      }));
    const first = slides[0];
    return {
      ...values,
      heroImageUrl: first?.imageUrl ?? values.heroImageUrl,
      heroImageAlt: first?.imageAlt ?? values.heroImageAlt,
      heroSlides: slides,
    };
  }

  const mutation = useMutation({
    mutationFn: (values: SiteForm) => api.updateSiteControl(payload(values)),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["site-control"] });
      form.reset(defaults(result));
      toast.success("Site controls saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save site controls."),
  });
  const uploadMutation = useMutation({
    mutationFn: ({ file }: { file: File; index: number }) => api.uploadImage(file),
    onSuccess: (result, variables) => {
      const values = form.getValues();
      const slides = [...values.heroSlides];
      const fallbackAlt =
        slides[variables.index]?.imageAlt || values.heroImageAlt || values.heroHeading;
      slides[variables.index] = {
        imageUrl: result.url,
        imageAlt: fallbackAlt,
        href: slides[variables.index]?.href || values.primaryActionHref || "/shop",
        label: slides[variables.index]?.label || values.primaryActionLabel || "Explore",
        enabled: slides[variables.index]?.enabled ?? true,
      };
      form.setValue("heroSlides", slides, { shouldDirty: true, shouldValidate: true });
      if (variables.index === 0) {
        form.setValue("heroImageUrl", result.url, { shouldDirty: true, shouldValidate: true });
        form.setValue("heroImageAlt", fallbackAlt, { shouldDirty: true, shouldValidate: true });
      }
      mutation.mutate({ ...values, heroSlides: slides });
      toast.success("Hero slide uploaded; saving carousel.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not upload image."),
  });

  if (isLoading) return <p className="text-sm text-ink-muted">Loading site controls...</p>;
  if (isError) {
    return <EmptyState title="Site controls unavailable" hint="Requires owner settings access." />;
  }
  const heroSlides = watchedHeroSlides ?? [];

  function updateSlide(index: number, patch: Partial<SiteForm["heroSlides"][number]>) {
    const slides = [...form.getValues("heroSlides")];
    const current = slides[index];
    if (!current) return;
    slides[index] = { ...current, ...patch };
    form.setValue("heroSlides", slides, { shouldDirty: true, shouldValidate: true });
    if (index === 0) {
      if (patch.imageUrl !== undefined) {
        form.setValue("heroImageUrl", patch.imageUrl, { shouldDirty: true, shouldValidate: true });
      }
      if (patch.imageAlt !== undefined) {
        form.setValue("heroImageAlt", patch.imageAlt, { shouldDirty: true, shouldValidate: true });
      }
    }
  }

  function addSlide() {
    const slides = form.getValues("heroSlides");
    if (slides.length >= 8) {
      toast.error("Hero carousel supports up to 8 slides.");
      return;
    }
    form.setValue(
      "heroSlides",
      [
        ...slides,
        {
          imageUrl: "",
          imageAlt: "",
          href: "/shop",
          label: "Explore",
          enabled: true,
        },
      ],
      { shouldDirty: true, shouldValidate: true },
    );
  }

  function removeSlide(index: number) {
    const slides = form.getValues("heroSlides").filter((_, slideIndex) => slideIndex !== index);
    form.setValue("heroSlides", slides, { shouldDirty: true, shouldValidate: true });
    if (index === 0) {
      form.setValue("heroImageUrl", slides[0]?.imageUrl ?? "", {
        shouldDirty: true,
        shouldValidate: true,
      });
      form.setValue("heroImageAlt", slides[0]?.imageAlt ?? "", {
        shouldDirty: true,
        shouldValidate: true,
      });
    }
  }

  return (
    <div>
      <PageHeader
        title="Site Control"
        description="Owner-only controls for storefront banner, homepage copy, and SEO metadata."
      />
      <form
        className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]"
        onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
      >
        <div className="space-y-6">
          <section className="space-y-4 border-t border-line pt-5">
            <div>
              <h2 className="font-display text-lg text-ink">Announcement banner</h2>
              <p className="text-sm text-ink-muted">Appears above the customer storefront.</p>
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

          <section className="space-y-4 border-t border-line pt-5">
            <div>
              <h2 className="font-display text-lg text-ink">Homepage hero</h2>
              <p className="text-sm text-ink-muted">
                Primary homepage banner copy and calls to action.
              </p>
            </div>
            <Field label="Eyebrow" htmlFor="heroEyebrow">
              <Input id="heroEyebrow" {...form.register("heroEyebrow")} />
            </Field>
            <Field
              label="Headline"
              htmlFor="heroHeading"
              error={form.formState.errors.heroHeading?.message}
            >
              <Input id="heroHeading" {...form.register("heroHeading")} />
            </Field>
            <Field label="Supporting text" htmlFor="heroText">
              <Textarea id="heroText" {...form.register("heroText")} />
            </Field>
            <Field
              label="Hero image URL"
              htmlFor="heroImageUrl"
              error={form.formState.errors.heroImageUrl?.message}
            >
              <Input
                id="heroImageUpload"
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                className="mb-2"
                disabled={uploadMutation.isPending || mutation.isPending}
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0];
                  if (file) uploadMutation.mutate({ file, index: 0 });
                  event.currentTarget.value = "";
                }}
              />
              <Input
                id="heroImageUrl"
                placeholder={uploadMutation.isPending ? "Uploading image..." : "Hero image URL"}
                {...form.register("heroImageUrl")}
              />
              {watchedHeroImageUrl ? (
                <div className="mt-3">
                  <ImagePreview
                    src={watchedHeroImageUrl}
                    alt={watchedHeroImageAlt}
                    label={form.getValues("heroHeading") || "Homepage hero"}
                    className="h-32 w-full max-w-md"
                  />
                </div>
              ) : null}
            </Field>
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-ink">Hero carousel slides</p>
                <Button type="button" variant="secondary" onClick={addSlide}>
                  Add slide
                </Button>
              </div>
              <div className="space-y-3">
                {heroSlides.map((slide, index) => (
                  <div
                    key={`${index}-${slide.imageUrl}`}
                    className="grid gap-3 rounded-md border border-line bg-surface p-3 lg:grid-cols-[9rem_minmax(0,1fr)]"
                  >
                    <div className="space-y-2">
                      <ImagePreview
                        src={slide.imageUrl}
                        alt={slide.imageAlt}
                        label={slide.label || `Slide ${index + 1}`}
                        className="h-20 w-36"
                      />
                      <Input
                        type="file"
                        accept="image/jpeg,image/png,image/webp,image/gif"
                        disabled={uploadMutation.isPending || mutation.isPending}
                        onChange={(event) => {
                          const file = event.currentTarget.files?.[0];
                          if (file) uploadMutation.mutate({ file, index });
                          event.currentTarget.value = "";
                        }}
                      />
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <label className="flex items-center gap-2 text-sm text-ink md:col-span-2">
                        <input
                          type="checkbox"
                          checked={slide.enabled}
                          onChange={(event) =>
                            updateSlide(index, { enabled: event.target.checked })
                          }
                        />
                        Enabled
                      </label>
                      <Field label="Image URL" htmlFor={`slide-image-${index}`}>
                        <Input
                          id={`slide-image-${index}`}
                          value={slide.imageUrl}
                          onChange={(event) => updateSlide(index, { imageUrl: event.target.value })}
                        />
                      </Field>
                      <Field label="Click link" htmlFor={`slide-href-${index}`}>
                        <Input
                          id={`slide-href-${index}`}
                          value={slide.href}
                          onChange={(event) => updateSlide(index, { href: event.target.value })}
                        />
                      </Field>
                      <Field label="Label" htmlFor={`slide-label-${index}`}>
                        <Input
                          id={`slide-label-${index}`}
                          value={slide.label}
                          onChange={(event) => updateSlide(index, { label: event.target.value })}
                        />
                      </Field>
                      <Field label="Alt text" htmlFor={`slide-alt-${index}`}>
                        <Input
                          id={`slide-alt-${index}`}
                          value={slide.imageAlt}
                          onChange={(event) => updateSlide(index, { imageAlt: event.target.value })}
                        />
                      </Field>
                      <div className="flex justify-end md:col-span-2">
                        <Button type="button" variant="tertiary" onClick={() => removeSlide(index)}>
                          Remove
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <Field
              label="Hero image alt text"
              htmlFor="heroImageAlt"
              error={form.formState.errors.heroImageAlt?.message}
            >
              <Input
                id="heroImageAlt"
                placeholder="Organic mangoes held in a sunlit orchard"
                {...form.register("heroImageAlt")}
              />
            </Field>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Primary button label" htmlFor="primaryActionLabel">
                <Input id="primaryActionLabel" {...form.register("primaryActionLabel")} />
              </Field>
              <Field label="Primary button link" htmlFor="primaryActionHref">
                <Input id="primaryActionHref" {...form.register("primaryActionHref")} />
              </Field>
              <Field label="Secondary button label" htmlFor="secondaryActionLabel">
                <Input id="secondaryActionLabel" {...form.register("secondaryActionLabel")} />
              </Field>
              <Field label="Secondary button link" htmlFor="secondaryActionHref">
                <Input id="secondaryActionHref" {...form.register("secondaryActionHref")} />
              </Field>
            </div>
          </section>

          <section className="space-y-4 border-t border-line pt-5">
            <div>
              <h2 className="font-display text-lg text-ink">Homepage SEO</h2>
              <p className="text-sm text-ink-muted">
                Metadata used by search engines and social previews.
              </p>
            </div>
            <Field
              label="SEO title"
              htmlFor="seoTitle"
              error={form.formState.errors.seoTitle?.message}
            >
              <Input id="seoTitle" {...form.register("seoTitle")} />
            </Field>
            <Field label="SEO description" htmlFor="seoDescription">
              <Textarea id="seoDescription" {...form.register("seoDescription")} />
            </Field>
            <Field label="SEO keywords" htmlFor="seoKeywords">
              <Textarea id="seoKeywords" {...form.register("seoKeywords")} />
            </Field>
          </section>
        </div>

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
            disabled={mutation.isPending || !form.formState.isDirty}
          >
            {mutation.isPending ? "Saving..." : "Save site controls"}
          </Button>
        </aside>
      </form>

      <SiteDocumentsSection />
      <HighlightsSection />
    </div>
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
  const { data: allProducts } = useQuery({ queryKey: ["admin-products"], queryFn: api.products });
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
