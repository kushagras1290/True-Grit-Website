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
import { formatDateTime } from "../lib/format";

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
  freshFavourites: z.array(z.string()),
});

type SiteForm = z.infer<typeof siteSchema>;

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
    freshFavourites: data?.freshFavourites ?? [],
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
      primaryActionHref: values.primaryActionHref.trim(),
      secondaryActionHref: values.secondaryActionHref.trim(),
      announcementPath: values.announcementPath.trim(),
      heroImageUrl: (first?.imageUrl ?? values.heroImageUrl).trim(),
      heroImageAlt: first?.imageAlt ?? values.heroImageAlt,
      heroSlides: slides,
    };
  }

  function onInvalidSubmit(errors: typeof form.formState.errors) {
    const firstError = Object.values(errors).find(
      (error): error is { message?: string } => Boolean(error?.message),
    );
    toast.error(firstError?.message ?? "Fix the highlighted fields before saving.");
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
        onSubmit={form.handleSubmit((values) => mutation.mutate(values), onInvalidSubmit)}
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
              <Field
                label="Primary button link"
                htmlFor="primaryActionHref"
                error={form.formState.errors.primaryActionHref?.message}
              >
                <Input id="primaryActionHref" {...form.register("primaryActionHref")} />
              </Field>
              <Field label="Secondary button label" htmlFor="secondaryActionLabel">
                <Input id="secondaryActionLabel" {...form.register("secondaryActionLabel")} />
              </Field>
              <Field
                label="Secondary button link"
                htmlFor="secondaryActionHref"
                error={form.formState.errors.secondaryActionHref?.message}
              >
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
            disabled={mutation.isPending}
          >
            {mutation.isPending ? "Saving..." : "Save site controls"}
          </Button>
        </aside>
      </form>

      <CmsPagesSection />
      <SiteDocumentsSection />
      <FreshFavouritesSection form={form} />
      <HighlightsSection />
    </div>
  );
}

function FreshFavouritesSection({ form }: { form: ReturnType<typeof useForm<SiteForm>> }) {
  const { data: allProducts, isLoading } = useQuery({
    queryKey: ["admin-products", "all"],
    queryFn: () => api.products({ limit: 100 }),
  });
  const [pendingId, setPendingId] = useState("");
  
  const currentSlugs = form.watch("freshFavourites");
  const currentProducts = currentSlugs.map(slug => allProducts?.find(p => p.slug === slug)).filter(Boolean) as AdminLinkedProduct[];
  const addable = (allProducts ?? []).filter(row => !currentSlugs.includes(row.slug));

  function move(index: number, delta: number) {
    const current = form.getValues("freshFavourites") || [];
    const target = index + delta;
    if (target < 0 || target >= current.length) return;
    const next = [...current];
    const sourceItem = next[index];
    const targetItem = next[target];
    if (!sourceItem || !targetItem) return;
    next[index] = targetItem;
    next[target] = sourceItem;
    form.setValue("freshFavourites", next, { shouldDirty: true, shouldValidate: true });
  }

  return (
    <section className="mt-10 space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">Fresh Favourites</h2>
        <p className="text-sm text-ink-muted">
          Shown in the Fresh favourites section on the homepage. Only published
          products appear to customers. Saves with "Save site controls" button.
        </p>
      </div>
      {isLoading ? (
        <p className="text-sm text-ink-muted">Loading products...</p>
      ) : currentProducts.length === 0 ? (
        <p className="max-w-xl rounded-md border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
          No fresh favourites yet. Add a few below.
        </p>
      ) : (
        <ul className="max-w-xl divide-y divide-line rounded-md border border-line">
          {currentProducts.map((entry, index) => (
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
                disabled={index === currentSlugs.length - 1}
                onClick={() => move(index, 1)}
              >
                ↓
              </button>
              <button
                type="button"
                aria-label={`Remove ${entry.name}`}
                className="min-h-8 rounded-sm border border-line px-2 text-xs text-danger"
                onClick={() => {
                  const current = form.getValues("freshFavourites") || [];
                  form.setValue("freshFavourites", current.filter(slug => slug !== entry.slug), { shouldDirty: true, shouldValidate: true });
                }}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex max-w-xl gap-2">
        <Select
          aria-label="Product to add to fresh favourites"
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
          disabled={!pendingId || currentSlugs.length >= 12}
          onClick={() => {
            const row = addable.find((entry) => entry.id === pendingId);
            if (!row) return;
            const current = form.getValues("freshFavourites") || [];
            form.setValue("freshFavourites", [...current, row.slug], { shouldDirty: true, shouldValidate: true });
            setPendingId("");
          }}
        >
          Add to favourites
        </Button>
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
          Edit CMS page metadata, indexing and page blocks. Homepage quick controls above still
          update the same homepage record.
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
