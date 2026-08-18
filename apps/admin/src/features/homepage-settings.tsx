/**
 * Homepage Settings — everything that decides what a customer sees on `/`.
 *
 * Split out of Site Control so the two jobs stop competing for one page: this
 * one is the homepage itself (which sections run, in what order, and what is
 * inside them), while Site Control keeps the site-wide switches, crawler files
 * and per-route SEO.
 *
 * The section list is the spine. Every homepage block appears there with a
 * tickbox; the three sections that have dedicated curators below (banner
 * carousel, category row, product row) can be switched off and reordered but
 * not deleted, because deleting one would silently discard a curated list the
 * editor below still believes it owns.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
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
  type AdminLinkedProduct,
  type HomepageSection,
  type SiteControl,
} from "../lib/api";
import { IMAGE_SPECIFICATIONS_BY_ID } from "../lib/image-specifications";
import { usePermissions } from "../lib/permissions";
import { T, useT } from "../lib/i18n";
import { repositionItem } from "./builder";

/** Mirrors the identical helper in `site-control.tsx` / `appearance.tsx` — a
 *  scope here is always a two-letter country code, never `'global'`; the
 *  homepage's own section list (above) already is the global default. */
function isRealCountryCode(code: string): boolean {
  return /^[A-Z]{2}$/.test(code);
}

// The hard ceiling the block format itself enforces (mirrors the API's
// `CURATED_MAX_ITEMS_HARD_LIMIT`) -- a generous static bound for client-side
// validation. The *configured* limit an operator actually sees and is held
// to in the UI is `curatedMaxItems`, fetched from `/v1/admin/curated-settings`
// and editable on Site Control (one shared setting for Fresh Favourites,
// Featured Categories and Highlights, since all three are the same shape of
// feature).
const CURATED_SLOTS_HARD_LIMIT = 50;
const FALLBACK_CURATED_MAX_ITEMS = 12;

/** Fallback for the banner-slide cap while `site-control` is still loading, or
 *  if an older API omits it. The real number is `heroMaxSlides`, stored in
 *  `app_settings` and editable in the form below, so growing the carousel needs
 *  no deploy. Validation is the API's job either way. */
const FALLBACK_MAX_HERO_SLIDES = 12;
const FALLBACK_HERO_SLIDES_HARD_LIMIT = 40;

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

const homepageSchema = z.object({
  heroEyebrow: z.string().max(120),
  heroHeading: z.string().min(3).max(160),
  heroText: z.string().max(500),
  heroImageUrl: imageUrlSchema,
  heroImageAlt: z.string().max(200),
  // Bounded by the structural ceiling only. The operator's own cap is a
  // setting on this very form, so hard-coding it into the resolver would mean
  // a saved increase could not be used until the next deploy.
  heroSlides: z.array(heroSlideSchema).max(FALLBACK_HERO_SLIDES_HARD_LIMIT),
  heroMaxSlides: z.coerce
    .number()
    .int("Enter a whole number of slides")
    .min(1, "The carousel needs at least one slide")
    .max(FALLBACK_HERO_SLIDES_HARD_LIMIT),
  primaryActionLabel: z.string().max(80),
  primaryActionHref: optionalHrefSchema,
  secondaryActionLabel: z.string().max(80),
  secondaryActionHref: optionalHrefSchema,
  seoTitle: z.string().min(3).max(160),
  seoDescription: z.string().max(320),
  seoKeywords: z.string().max(500),
  featuredCategories: z.array(z.string()).max(CURATED_SLOTS_HARD_LIMIT),
  freshFavourites: z.array(z.string()).max(CURATED_SLOTS_HARD_LIMIT),
});

type HomepageForm = z.infer<typeof homepageSchema>;

function defaultHeroSlides(data?: SiteControl): HomepageForm["heroSlides"] {
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

function defaults(data?: SiteControl): HomepageForm {
  return {
    heroEyebrow: data?.heroEyebrow ?? "",
    heroHeading: data?.heroHeading ?? "",
    heroText: data?.heroText ?? "",
    heroImageUrl: data?.heroImageUrl ?? "",
    heroImageAlt: data?.heroImageAlt ?? "",
    heroSlides: defaultHeroSlides(data),
    heroMaxSlides: data?.heroMaxSlides ?? FALLBACK_MAX_HERO_SLIDES,
    primaryActionLabel: data?.primaryActionLabel ?? "",
    primaryActionHref: data?.primaryActionHref ?? "",
    secondaryActionLabel: data?.secondaryActionLabel ?? "",
    secondaryActionHref: data?.secondaryActionHref ?? "",
    seoTitle: data?.seoTitle ?? "",
    seoDescription: data?.seoDescription ?? "",
    seoKeywords: data?.seoKeywords ?? "",
    featuredCategories: data?.featuredCategories ?? [],
    freshFavourites: data?.freshFavourites ?? [],
  };
}

/** A plain `<input type="file">` renders as the browser's own, unlabelled
 *  "Choose file" control -- nothing on it says the file goes to R2, and long
 *  filenames get truncated into something like "Choose file N...en". This
 *  hides that control and drives it from a real button instead, so the
 *  action reads the way every other action in this console does. */
function UploadImageButton({
  onSelect,
  disabled,
  pending,
}: {
  onSelect: (file: File) => void;
  disabled?: boolean;
  pending?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        disabled={disabled}
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          event.currentTarget.value = "";
          if (file) onSelect(file);
        }}
      />
      <Button
        type="button"
        variant="secondary"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        {pending ? <T>{"Uploading..."}</T> : <T>{"Upload to R2"}</T>}
      </Button>
    </>
  );
}

export function HomepageSettingsPage() {
  const t = useT();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["site-control"],
    queryFn: api.siteControl,
  });
  const form = useForm<HomepageForm>({
    resolver: zodResolver(homepageSchema),
    defaultValues: defaults(),
  });
  const watchedHeroImageUrl = form.watch("heroImageUrl");
  const watchedHeroImageAlt = form.watch("heroImageAlt");
  const watchedHeroSlides = form.watch("heroSlides");
  // The cap the operator is currently editing, not the saved one: raising it
  // to fifteen should let the fifteenth slide be added in the same visit.
  const maxHeroSlides = Number(form.watch("heroMaxSlides")) || FALLBACK_MAX_HERO_SLIDES;
  const heroSlidesHardLimit = data?.heroSlidesHardLimit ?? FALLBACK_HERO_SLIDES_HARD_LIMIT;

  useEffect(() => {
    if (data) form.reset(defaults(data));
  }, [data, form]);

  function payload(values: HomepageForm): HomepageForm {
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
      heroMaxSlides: Number(values.heroMaxSlides),
      primaryActionHref: values.primaryActionHref.trim(),
      secondaryActionHref: values.secondaryActionHref.trim(),
      heroImageUrl: (first?.imageUrl ?? values.heroImageUrl).trim(),
      heroImageAlt: first?.imageAlt ?? values.heroImageAlt,
      heroSlides: slides,
    };
  }

  function onInvalidSubmit(errors: typeof form.formState.errors) {
    const firstError = Object.values(errors).find((error): error is { message?: string } =>
      Boolean(error?.message),
    );
    toast.error(firstError?.message ?? "Fix the highlighted fields before saving.");
  }

  const mutation = useMutation({
    mutationFn: (values: HomepageForm) => api.updateSiteControl(payload(values)),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["site-control"] });
      // The curated rows live in the same page record as the section list, so
      // the section summaries ("12 products") go stale the moment this saves.
      await queryClient.invalidateQueries({ queryKey: ["homepage-sections"] });
      form.reset(defaults(result));
      toast.success("Homepage saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the homepage."),
  });

  const uploadMutation = useMutation({
    mutationFn: ({ file }: { file: File; index: number }) =>
      api.uploadImage(file, IMAGE_SPECIFICATIONS_BY_ID["home-page-banner"]),
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
      toast.success("Banner slide uploaded; saving carousel.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not upload image."),
  });

  if (isLoading)
    return (
      <p className="text-sm text-ink-muted">
        <T>Loading homepage settings...</T>
      </p>
    );
  if (isError) {
    return (
      <EmptyState title="Homepage settings unavailable" hint="Requires owner settings access." />
    );
  }
  const heroSlides = watchedHeroSlides ?? [];

  function updateSlide(index: number, patch: Partial<HomepageForm["heroSlides"][number]>) {
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
    if (slides.length >= maxHeroSlides) {
      toast.error(
        `The banner carousel is limited to ${maxHeroSlides} slides.` +
          " Raise the limit below to add more.",
      );
      return;
    }
    form.setValue(
      "heroSlides",
      [...slides, { imageUrl: "", imageAlt: "", href: "/shop", label: "Explore", enabled: true }],
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

  function moveSlide(index: number, nextIndex: number) {
    const slides = repositionItem(form.getValues("heroSlides"), index, nextIndex);
    form.setValue("heroSlides", slides, { shouldDirty: true, shouldValidate: true });
    form.setValue("heroImageUrl", slides[0]?.imageUrl ?? "", {
      shouldDirty: true,
      shouldValidate: true,
    });
    form.setValue("heroImageAlt", slides[0]?.imageAlt ?? "", {
      shouldDirty: true,
      shouldValidate: true,
    });
  }

  return (
    <div>
      <PageHeader
        title="Homepage Settings"
        description="What customers see on the homepage: which sections run, in what order, and the copy inside them."
      />

      <HomepageSectionsSection />
      <HomepageCountryOverridesSection />

      <form
        className="mt-10 grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]"
        onSubmit={form.handleSubmit((values) => mutation.mutate(values), onInvalidSubmit)}
      >
        <div className="space-y-6">
          <section className="space-y-4 border-t border-line pt-5">
            <div>
              <h2 className="font-display text-lg text-ink">
                <T>Banner carousel</T>
              </h2>
              <p className="text-sm text-ink-muted">
                <T>
                  The rotating banner at the top of the homepage, plus the fallback copy shown when
                  no slide has an image.
                </T>
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
              label="Banner image URL"
              htmlFor="heroImageUrl"
              error={form.formState.errors.heroImageUrl?.message}
            >
              <div className="mb-2">
                <UploadImageButton
                  disabled={uploadMutation.isPending || mutation.isPending}
                  pending={uploadMutation.isPending}
                  onSelect={(file) => uploadMutation.mutate({ file, index: 0 })}
                />
              </div>
              <Input
                id="heroImageUrl"
                placeholder={uploadMutation.isPending ? "Uploading image..." : "Banner image URL"}
                {...form.register("heroImageUrl")}
              />
              {watchedHeroImageUrl ? (
                <div className="mt-3">
                  <ImagePreview
                    src={watchedHeroImageUrl}
                    alt={watchedHeroImageAlt}
                    label={form.getValues("heroHeading") || "Homepage banner"}
                    className="h-32 w-full max-w-md"
                  />
                </div>
              ) : null}
            </Field>
            <div className="max-w-sm">
              <Field
                label="Maximum carousel slides"
                htmlFor="heroMaxSlides"
                error={form.formState.errors.heroMaxSlides?.message}
              >
                <Input
                  id="heroMaxSlides"
                  type="number"
                  min={1}
                  max={heroSlidesHardLimit}
                  step={1}
                  {...form.register("heroMaxSlides")}
                />
              </Field>
              <p className="mt-1.5 text-xs text-ink-muted">
                <T>Raise this to curate more than</T> {FALLBACK_MAX_HERO_SLIDES}{" "}
                <T>banners — it saves with the rest of the homepage, no deploy needed. Up to</T>{" "}
                {heroSlidesHardLimit}
                <T>
                  , which is the ceiling the block format itself enforces. Lowering it never deletes
                  slides you have already saved; it only stops new ones being added.
                </T>
              </p>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-ink">
                  <T>Carousel slides (</T>
                  {heroSlides.length} of {maxHeroSlides})
                </p>
                <Button type="button" variant="secondary" onClick={addSlide}>
                  <T>Add slide</T>
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
                      <UploadImageButton
                        disabled={uploadMutation.isPending || mutation.isPending}
                        pending={uploadMutation.isPending}
                        onSelect={(file) => uploadMutation.mutate({ file, index })}
                      />
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="flex items-end justify-between gap-4 md:col-span-2">
                        <label className="flex min-h-9 items-center gap-2 text-sm text-ink">
                          <input
                            type="checkbox"
                            checked={slide.enabled}
                            onChange={(event) =>
                              updateSlide(index, { enabled: event.target.checked })
                            }
                          />
                          <T>Enabled</T>
                        </label>
                        <Field label={t("Position")} htmlFor={`slide-position-${index}`}>
                          <Select
                            id={`slide-position-${index}`}
                            value={index}
                            onChange={(event) => moveSlide(index, Number(event.target.value))}
                            className="w-28"
                          >
                            {heroSlides.map((_, position) => (
                              <option key={position} value={position}>
                                {position + 1}
                              </option>
                            ))}
                          </Select>
                        </Field>
                      </div>
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
                          <T>Remove</T>
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <Field
              label="Banner image alt text"
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

          <FeaturedCategoriesSection form={form} />
          <FreshFavouritesSection form={form} />

          <section className="space-y-4 border-t border-line pt-5">
            <div>
              <h2 className="font-display text-lg text-ink">
                <T>Homepage SEO</T>
              </h2>
              <p className="text-sm text-ink-muted">
                <T>Metadata used by search engines and social previews for `/`.</T>
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
          <h2 className="font-display text-lg text-ink">
            <T>Saving</T>
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            <T>
              The banner, category row, product row and SEO fields save together. Section tickboxes,
              ordering and custom section copy save on their own, as you change them.
            </T>
          </p>
          <Button
            type="submit"
            variant="primary"
            className="mt-5 w-full"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? <T>{"Saving..."}</T> : <T>{"Save homepage"}</T>}
          </Button>
        </aside>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section list: what runs on the homepage, in what order.
//
// Every change here saves immediately. A visibility switch you have to
// remember to save is a switch that gets left half-applied, which for a
// customer-facing section is worse than not having the switch at all.
// ---------------------------------------------------------------------------

function HomepageSectionsSection() {
  const t = useT();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["homepage-sections"],
    queryFn: api.homepageSections,
  });
  const [pendingType, setPendingType] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<HomepageSection | null>(null);

  function applyResult(result: Awaited<ReturnType<typeof api.homepageSections>>) {
    queryClient.setQueryData(["homepage-sections"], result);
    // The curated rows are read back through Site Control's shape too. This
    // revalidation is best-effort: the change itself already landed via
    // setQueryData above, so a failure here (e.g. the session expiring
    // between the action and this follow-up fetch) must not surface as an
    // unhandled rejection -- react-query does not route errors thrown from
    // inside onSuccess to onError, so an uncaught one here would otherwise
    // propagate straight to the browser instead of the toast below.
    return queryClient.invalidateQueries({ queryKey: ["site-control"] }).catch(() => {});
  }

  function reportError(fallback: string) {
    return (error: unknown) => toast.error(error instanceof ApiError ? error.message : fallback);
  }

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.updateHomepageSection(id, { enabled }),
    onSuccess: async (result) => {
      await applyResult(result);
      toast.success("Homepage sections updated.");
    },
    onError: reportError("Could not update the section."),
  });

  const orderMutation = useMutation({
    mutationFn: (ids: string[]) => api.reorderHomepageSections(ids),
    onSuccess: applyResult,
    onError: reportError("Could not reorder the sections."),
  });

  const addMutation = useMutation({
    mutationFn: (type: string) => api.addHomepageSection(type),
    onSuccess: async (result) => {
      await applyResult(result);
      setPendingType("");
      const added = result.sections[result.sections.length - 1];
      if (added) setEditingId(added.id);
      toast.success("Section added, switched off. Write the copy, then tick it on.");
    },
    onError: reportError("Could not add the section."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteHomepageSection(id),
    onSuccess: async (result) => {
      await applyResult(result);
      setConfirmDelete(null);
      setEditingId(null);
      toast.success("Section deleted.");
    },
    onError: reportError("Could not delete the section."),
  });

  const propsMutation = useMutation({
    mutationFn: ({ id, props }: { id: string; props: Record<string, unknown> }) =>
      api.updateHomepageSection(id, { props }),
    onSuccess: async (result) => {
      await applyResult(result);
      toast.success("Section content saved.");
    },
    onError: reportError("Could not save the section content."),
  });

  const busy =
    toggleMutation.isPending ||
    orderMutation.isPending ||
    addMutation.isPending ||
    deleteMutation.isPending ||
    propsMutation.isPending;

  if (isLoading) {
    return (
      <p className="text-sm text-ink-muted">
        <T>Loading homepage sections...</T>
      </p>
    );
  }
  if (isError || !data) {
    return (
      <EmptyState
        title="Homepage sections unavailable"
        hint="Requires owner settings access and a connected API."
      />
    );
  }

  const sections = data.sections;

  function moveTo(index: number, targetIndex: number) {
    const ids = repositionItem(
      sections.map((section) => section.id),
      index,
      targetIndex,
    );
    orderMutation.mutate(ids);
  }

  return (
    <section className="space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">
          <T>Homepage sections</T>
        </h2>
        <p className="max-w-3xl text-sm text-ink-muted">
          <T>
            Untick a section to hide it from customers without losing its content, and use the
            position dropdown to change the order they appear in. Changes here apply as soon as
            you make them.
          </T>
        </p>
      </div>

      {sections.length === 0 ? (
        <EmptyState title="The homepage has no sections" hint="Add one below to get started." />
      ) : (
        <ul className="divide-y divide-line rounded-md border border-line">
          {sections.map((section, index) => (
            <li key={section.id} className="px-3 py-3">
              <div className="flex flex-wrap items-start gap-3">
                <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-2.5">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={section.enabled}
                    disabled={busy}
                    onChange={(event) =>
                      toggleMutation.mutate({ id: section.id, enabled: event.target.checked })
                    }
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-ink">
                      {index + 1}. {section.label}
                      {section.heading ? (
                        <span className="font-normal text-ink-muted"> — {section.heading}</span>
                      ) : null}
                    </span>
                    <span className="mt-0.5 block text-xs text-ink-muted">
                      {section.summary || <T>{"No content yet"}</T>}
                    </span>
                  </span>
                </label>
                <div className="flex shrink-0 items-center gap-3">
                  <StatusPill status={section.enabled ? "published" : "draft"} />
                  <Field label={t("Position")} htmlFor={`section-position-${section.id}`}>
                    <Select
                      id={`section-position-${section.id}`}
                      aria-label={`Position of ${section.label}`}
                      value={index}
                      disabled={busy}
                      onChange={(event) => moveTo(index, Number(event.target.value))}
                      className="w-20"
                    >
                      {sections.map((_, position) => (
                        <option key={position} value={position}>
                          {position + 1}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  {SECTION_EDITORS.has(section.type) ? (
                    <Button
                      type="button"
                      variant="secondary"
                      className="min-h-8 px-2.5 text-xs"
                      onClick={() =>
                        setEditingId((current) => (current === section.id ? null : section.id))
                      }
                    >
                      {editingId === section.id ? <T>{"Close"}</T> : <T>{"Edit content"}</T>}
                    </Button>
                  ) : null}
                  {section.removable ? (
                    <Button
                      type="button"
                      variant="tertiary"
                      className="min-h-8 px-2.5 text-xs"
                      disabled={busy}
                      onClick={() => setConfirmDelete(section)}
                    >
                      <T>Delete</T>
                    </Button>
                  ) : null}
                </div>
              </div>

              {editingId === section.id ? (
                <div className="mt-4 rounded-md border border-line bg-canvas p-4">
                  <SectionContentEditor
                    section={section}
                    saving={propsMutation.isPending}
                    onSave={(props) => propsMutation.mutate({ id: section.id, props })}
                  />
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      <div className="flex max-w-xl flex-wrap gap-2">
        <Select
          aria-label="Type of section to add"
          value={pendingType}
          onChange={(event) => setPendingType(event.target.value)}
          className="flex-1"
        >
          <option value="">
            <T>Add a section…</T>
          </option>
          {data.addableTypes.map((entry) => (
            <option key={entry.type} value={entry.type}>
              {entry.label}
            </option>
          ))}
        </Select>
        <Button
          type="button"
          variant="secondary"
          disabled={!pendingType || busy}
          onClick={() => addMutation.mutate(pendingType)}
        >
          {addMutation.isPending ? <T>{"Adding..."}</T> : <T>{"Add section"}</T>}
        </Button>
      </div>
      <p className="text-xs text-ink-muted">
        <T>
          New sections arrive switched off with placeholder copy, so nothing half-written reaches a
          customer. The banner, category row and product row are edited in their own panels below
          and cannot be deleted — untick them to hide them.
        </T>
      </p>

      {confirmDelete ? (
        <ConfirmDialog
          title={`Delete the ${confirmDelete.label.toLowerCase()} section?`}
          description={`"${confirmDelete.heading || confirmDelete.summary}" and its content are removed from the homepage. This cannot be undone — untick the section instead if you only want to hide it.`}
          confirmLabel="Delete section"
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => deleteMutation.mutate(confirmDelete.id)}
        />
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Per-country section overrides: "for visitors in this country, force this
// one section on or off", layered on top of the tickboxes above rather than
// replacing them. See `services/homepage_geo.py` — a country absent here
// simply gets the section list as edited above; nothing changes for it.
// ---------------------------------------------------------------------------

type OverrideState = "inherit" | "shown" | "hidden";

function overrideState(
  overrides: Record<string, Record<string, boolean>>,
  country: string,
  sectionId: string,
): OverrideState {
  const value = overrides[country]?.[sectionId];
  if (value === undefined) return "inherit";
  return value ? "shown" : "hidden";
}

function HomepageCountryOverridesSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const sectionsQuery = useQuery({
    queryKey: ["homepage-sections"],
    queryFn: api.homepageSections,
  });
  const overridesQuery = useQuery({
    queryKey: ["homepage-country-overrides"],
    queryFn: api.homepageCountryOverrides,
  });
  const [country, setCountry] = useState<string | null>(null);
  const [newCountry, setNewCountry] = useState("");

  const overrides = overridesQuery.data?.overrides ?? {};
  const knownCountries = Object.keys(overrides).sort();
  const activeCountry = country ?? knownCountries[0] ?? null;

  function applyResult(result: Awaited<ReturnType<typeof api.homepageCountryOverrides>>) {
    queryClient.setQueryData(["homepage-country-overrides"], result);
  }

  const setMutation = useMutation({
    mutationFn: ({ sectionId, enabled }: { sectionId: string; enabled: boolean }) => {
      if (!activeCountry) throw new Error("No country selected.");
      return api.setHomepageCountryOverride(activeCountry, sectionId, enabled);
    },
    onSuccess: applyResult,
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the override."),
  });

  const clearMutation = useMutation({
    mutationFn: (sectionId: string) => {
      if (!activeCountry) throw new Error("No country selected.");
      return api.clearHomepageCountryOverride(activeCountry, sectionId);
    },
    onSuccess: applyResult,
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not clear the override."),
  });

  function addCountry() {
    const code = newCountry.trim().toUpperCase();
    if (!isRealCountryCode(code)) {
      toast.error("A country needs a two-letter code, for example IN, US or DE.");
      return;
    }
    setNewCountry("");
    setCountry(code);
  }

  function setState(sectionId: string, state: OverrideState) {
    if (state === "inherit") clearMutation.mutate(sectionId);
    else setMutation.mutate({ sectionId, enabled: state === "shown" });
  }

  if (sectionsQuery.isLoading || overridesQuery.isLoading) {
    return (
      <section className="space-y-4 border-t border-line pt-5">
        <p className="text-sm text-ink-muted">
          <T>Loading country overrides...</T>
        </p>
      </section>
    );
  }
  if (sectionsQuery.isError || overridesQuery.isError || !sectionsQuery.data) {
    return (
      <section className="space-y-4 border-t border-line pt-5">
        <EmptyState title="Country overrides unavailable" hint="Requires owner settings access." />
      </section>
    );
  }

  const sections = sectionsQuery.data.sections;
  const busy = setMutation.isPending || clearMutation.isPending;

  return (
    <section className="space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">
          <T>Homepage sections by country</T>
        </h2>
        <p className="max-w-3xl text-sm text-ink-muted">
          <T>
            Force a section on or off for visitors in one country, without changing what everyone
            else sees. Leave a section on "Inherit" and it just follows the tickbox in the section
            list above.
          </T>
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56">
          <Field label="Editing" htmlFor="homepage-override-country">
            <Select
              id="homepage-override-country"
              value={activeCountry ?? ""}
              onChange={(event) => setCountry(event.target.value || null)}
            >
              {activeCountry ? null : (
                <option value="">
                  <T>Add a country to begin…</T>
                </option>
              )}
              {knownCountries.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
              {activeCountry && !knownCountries.includes(activeCountry) ? (
                <option value={activeCountry}>
                  {activeCountry} <T>(new)</T>
                </option>
              ) : null}
            </Select>
          </Field>
        </div>
        <div className="min-w-32">
          <Field label="Add a country" htmlFor="homepage-override-new-country">
            <Input
              id="homepage-override-new-country"
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
          <T>Add country</T>
        </Button>
      </div>

      {activeCountry ? (
        <ul className="divide-y divide-line rounded-md border border-line">
          {sections.map((section) => {
            const state = overrideState(overrides, activeCountry, section.id);
            return (
              <li
                key={section.id}
                className="flex flex-wrap items-center justify-between gap-3 px-3 py-3"
              >
                <div className="min-w-0">
                  <span className="block text-sm font-medium text-ink">{section.label}</span>
                  <span className="block text-xs text-ink-muted">
                    <T>Site-wide default:</T> {section.enabled ? "shown" : "hidden"}
                  </span>
                </div>
                <div
                  className="flex shrink-0 gap-1.5"
                  role="radiogroup"
                  aria-label={`${section.label} for ${activeCountry}`}
                >
                  {(
                    [
                      ["inherit", "Inherit"],
                      ["shown", "Always show"],
                      ["hidden", "Always hide"],
                    ] as const
                  ).map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      role="radio"
                      aria-checked={state === value}
                      disabled={busy}
                      className={`min-h-8 rounded-sm border px-2.5 text-xs disabled:opacity-40 ${
                        state === value
                          ? "border-ink bg-ink text-ink-inverse"
                          : "border-line text-ink"
                      }`}
                      onClick={() => setState(section.id, value)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="max-w-xl rounded-md border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
          <T>
            No country overrides yet. Add a country above to give it its own section visibility.
          </T>
        </p>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Per-type content editors
//
// Props arrive as untyped JSON from the API, so every reader below is
// defensive: a block saved by an older build, or hand-edited in the CMS page
// editor, must open in this form rather than crash the page.
// ---------------------------------------------------------------------------

const SECTION_EDITORS = new Set([
  "page_links",
  "rich_text",
  "faq",
  "farmer_story",
  "newsletter",
  "reviews_showcase",
  "promotion_banner",
  "recommendations",
  "image_banner",
]);

type Props = Record<string, unknown>;

function readString(props: Props, key: string): string {
  const value = props[key];
  return typeof value === "string" ? value : "";
}

function readObjects(props: Props, key: string): Props[] {
  const value = props[key];
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is Props => typeof entry === "object" && entry !== null);
}

function readStrings(props: Props, key: string): string[] {
  const value = props[key];
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === "string");
}

function readNumber(props: Props, key: string, fallback: number): number {
  const value = props[key];
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function SectionContentEditor({
  section,
  saving,
  onSave,
}: {
  section: HomepageSection;
  saving: boolean;
  onSave: (props: Props) => void;
}) {
  switch (section.type) {
    case "page_links":
      return <PageLinksEditor section={section} saving={saving} onSave={onSave} />;
    case "rich_text":
      return <RichTextEditor section={section} saving={saving} onSave={onSave} />;
    case "faq":
      return <FaqEditor section={section} saving={saving} onSave={onSave} />;
    case "farmer_story":
      return <FarmerStoryEditor section={section} saving={saving} onSave={onSave} />;
    case "newsletter":
      return <NewsletterEditor section={section} saving={saving} onSave={onSave} />;
    case "reviews_showcase":
      return <ReviewsShowcaseEditor section={section} saving={saving} onSave={onSave} />;
    case "promotion_banner":
      return <PromotionBannerEditor section={section} saving={saving} onSave={onSave} />;
    case "recommendations":
      return <RecommendationsEditor section={section} saving={saving} onSave={onSave} />;
    case "image_banner":
      return <ImageBannerEditor section={section} saving={saving} onSave={onSave} />;
    default:
      return (
        <p className="text-sm text-ink-muted">
          <T>This section is edited in its own panel further down the page.</T>
        </p>
      );
  }
}

function SaveRow({ saving, hint }: { saving: boolean; hint?: string }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
      {hint ? <p className="text-xs text-ink-muted">{hint}</p> : <span />}
      <Button type="submit" variant="primary" disabled={saving}>
        {saving ? <T>{"Saving..."}</T> : <T>{"Save section"}</T>}
      </Button>
    </div>
  );
}

interface PageLinkDraft {
  label: string;
  description: string;
  href: string;
  enabled: boolean;
}

function pageLinkDrafts(section: HomepageSection): PageLinkDraft[] {
  return readObjects(section.props, "items").map((item) => ({
    label: readString(item, "label"),
    description: readString(item, "description"),
    href: readString(item, "href"),
    enabled: item.enabled !== false,
  }));
}

/** The homepage's directory of the rest of the site: one short snippet per
 *  page, so a first-time customer can see what exists without opening the
 *  header menu. */
function PageLinksEditor({
  section,
  saving,
  onSave,
}: {
  section: HomepageSection;
  saving: boolean;
  onSave: (props: Props) => void;
}) {
  const toast = useToast();
  const [heading, setHeading] = useState(() => readString(section.props, "heading"));
  const [intro, setIntro] = useState(() => readString(section.props, "intro"));
  const [items, setItems] = useState<PageLinkDraft[]>(() => pageLinkDrafts(section));

  function update(index: number, patch: Partial<PageLinkDraft>) {
    setItems((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );
  }

  function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= items.length) return;
    const next = [...items];
    const moved = next[index]!;
    next[index] = next[target]!;
    next[target] = moved;
    setItems(next);
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        const cleaned = items
          .map((item) => ({
            label: item.label.trim(),
            description: item.description.trim(),
            href: item.href.trim(),
            enabled: item.enabled,
          }))
          .filter((item) => item.label && item.href);
        if (cleaned.length === 0) {
          toast.error("Add at least one snippet with a title and a link.");
          return;
        }
        onSave({ heading: heading.trim(), intro: intro.trim(), items: cleaned });
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Section heading" htmlFor={`links-heading-${section.id}`}>
          <Input
            id={`links-heading-${section.id}`}
            value={heading}
            maxLength={120}
            onChange={(event) => setHeading(event.target.value)}
          />
        </Field>
        <Field label="Intro line (optional)" htmlFor={`links-intro-${section.id}`}>
          <Input
            id={`links-intro-${section.id}`}
            value={intro}
            maxLength={400}
            onChange={(event) => setIntro(event.target.value)}
          />
        </Field>
      </div>

      <div className="space-y-3">
        {items.map((item, index) => (
          <div key={index} className="rounded-md border border-line bg-surface p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label className="flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  checked={item.enabled}
                  onChange={(event) => update(index, { enabled: event.target.checked })}
                />
                <T>Show this snippet</T>
              </label>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  aria-label={`Move ${item.label || `snippet ${index + 1}`} up`}
                  className="min-h-8 min-w-8 rounded-sm border border-line text-xs disabled:opacity-40"
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label={`Move ${item.label || `snippet ${index + 1}`} down`}
                  className="min-h-8 min-w-8 rounded-sm border border-line text-xs disabled:opacity-40"
                  disabled={index === items.length - 1}
                  onClick={() => move(index, 1)}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="min-h-8 rounded-sm border border-line px-2 text-xs text-danger"
                  onClick={() =>
                    setItems((current) => current.filter((_, itemIndex) => itemIndex !== index))
                  }
                >
                  <T>Remove</T>
                </button>
              </div>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <Field label="Page title" htmlFor={`links-label-${section.id}-${index}`}>
                <Input
                  id={`links-label-${section.id}-${index}`}
                  value={item.label}
                  maxLength={80}
                  onChange={(event) => update(index, { label: event.target.value })}
                />
              </Field>
              <Field label="Link" htmlFor={`links-href-${section.id}-${index}`}>
                <Input
                  id={`links-href-${section.id}-${index}`}
                  value={item.href}
                  maxLength={512}
                  placeholder="/recipes"
                  onChange={(event) => update(index, { href: event.target.value })}
                />
              </Field>
              <div className="md:col-span-2">
                <Field label="Snippet" htmlFor={`links-description-${section.id}-${index}`}>
                  <Textarea
                    id={`links-description-${section.id}-${index}`}
                    rows={2}
                    value={item.description}
                    maxLength={240}
                    placeholder="One line on what the customer will find there."
                    onChange={(event) => update(index, { description: event.target.value })}
                  />
                </Field>
              </div>
            </div>
          </div>
        ))}
      </div>

      <Button
        type="button"
        variant="secondary"
        disabled={items.length >= 24}
        onClick={() =>
          setItems((current) => [
            ...current,
            { label: "", description: "", href: "/", enabled: true },
          ])
        }
      >
        <T>Add a snippet</T>
      </Button>

      <SaveRow
        saving={saving}
        hint={`${items.length} of 24 snippets. Links must start with / , https:// , http:// or mailto:`}
      />
    </form>
  );
}

function RichTextEditor({
  section,
  saving,
  onSave,
}: {
  section: HomepageSection;
  saving: boolean;
  onSave: (props: Props) => void;
}) {
  const toast = useToast();
  const [text, setText] = useState(() => readStrings(section.props, "paragraphs").join("\n\n"));

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        const paragraphs = text
          .split(/\n\s*\n/)
          .map((paragraph) => paragraph.trim())
          .filter(Boolean);
        if (paragraphs.length === 0) {
          toast.error("Write at least one paragraph.");
          return;
        }
        onSave({ paragraphs });
      }}
    >
      <Field label="Paragraphs" htmlFor={`rich-text-${section.id}`}>
        <Textarea
          id={`rich-text-${section.id}`}
          rows={10}
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      </Field>
      <SaveRow
        saving={saving}
        hint="Separate paragraphs with a blank line. Links use [text](/path); HTML is rejected."
      />
    </form>
  );
}

interface FaqDraft {
  question: string;
  answer: string;
}

function FaqEditor({
  section,
  saving,
  onSave,
}: {
  section: HomepageSection;
  saving: boolean;
  onSave: (props: Props) => void;
}) {
  const toast = useToast();
  const [heading, setHeading] = useState(() => readString(section.props, "heading"));
  const [items, setItems] = useState<FaqDraft[]>(() =>
    readObjects(section.props, "items").map((item) => ({
      question: readString(item, "question"),
      answer: readString(item, "answer"),
    })),
  );

  function update(index: number, patch: Partial<FaqDraft>) {
    setItems((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        const cleaned = items
          .map((item) => ({ question: item.question.trim(), answer: item.answer.trim() }))
          .filter((item) => item.question && item.answer);
        if (cleaned.length === 0) {
          toast.error("Add at least one question with an answer.");
          return;
        }
        onSave({ heading: heading.trim(), items: cleaned });
      }}
    >
      <Field label="Section heading" htmlFor={`faq-heading-${section.id}`}>
        <Input
          id={`faq-heading-${section.id}`}
          value={heading}
          maxLength={120}
          onChange={(event) => setHeading(event.target.value)}
        />
      </Field>
      {items.map((item, index) => (
        <div key={index} className="space-y-3 rounded-md border border-line bg-surface p-3">
          <Field label="Question" htmlFor={`faq-question-${section.id}-${index}`}>
            <Input
              id={`faq-question-${section.id}-${index}`}
              value={item.question}
              maxLength={240}
              onChange={(event) => update(index, { question: event.target.value })}
            />
          </Field>
          <Field label="Answer" htmlFor={`faq-answer-${section.id}-${index}`}>
            <Textarea
              id={`faq-answer-${section.id}-${index}`}
              rows={3}
              value={item.answer}
              maxLength={1200}
              onChange={(event) => update(index, { answer: event.target.value })}
            />
          </Field>
          <div className="flex justify-end">
            <Button
              type="button"
              variant="tertiary"
              onClick={() =>
                setItems((current) => current.filter((_, itemIndex) => itemIndex !== index))
              }
            >
              <T>Remove</T>
            </Button>
          </div>
        </div>
      ))}
      <Button
        type="button"
        variant="secondary"
        disabled={items.length >= 20}
        onClick={() => setItems((current) => [...current, { question: "", answer: "" }])}
      >
        <T>Add a question</T>
      </Button>
      <SaveRow saving={saving} hint={`${items.length} of 20 questions`} />
    </form>
  );
}

function FarmerStoryEditor({
  section,
  saving,
  onSave,
}: {
  section: HomepageSection;
  saving: boolean;
  onSave: (props: Props) => void;
}) {
  const toast = useToast();
  const [farmSlug, setFarmSlug] = useState(() => readString(section.props, "farmSlug"));
  const [quote, setQuote] = useState(() => readString(section.props, "quote"));
  const [attribution, setAttribution] = useState(() => readString(section.props, "attribution"));

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!quote.trim() || !attribution.trim()) {
          toast.error("A farmer quote needs both the words and who said them.");
          return;
        }
        onSave({
          farmSlug: farmSlug.trim(),
          quote: quote.trim(),
          attribution: attribution.trim(),
        });
      }}
    >
      <Field label="Quote" htmlFor={`farmer-quote-${section.id}`}>
        <Textarea
          id={`farmer-quote-${section.id}`}
          rows={3}
          value={quote}
          maxLength={400}
          onChange={(event) => setQuote(event.target.value)}
        />
      </Field>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Attribution" htmlFor={`farmer-attribution-${section.id}`}>
          <Input
            id={`farmer-attribution-${section.id}`}
            value={attribution}
            maxLength={160}
            placeholder="Devika Kulkarni, Devika Organics"
            onChange={(event) => setAttribution(event.target.value)}
          />
        </Field>
        <Field label="Farm slug (optional)" htmlFor={`farmer-slug-${section.id}`}>
          <Input
            id={`farmer-slug-${section.id}`}
            value={farmSlug}
            maxLength={96}
            placeholder="devika-organics"
            onChange={(event) => setFarmSlug(event.target.value)}
          />
        </Field>
      </div>
      <SaveRow
        saving={saving}
        hint="A matching farm slug adds a 'visit the farm' link; leave it blank for a quote alone."
      />
    </form>
  );
}

function NewsletterEditor({
  section,
  saving,
  onSave,
}: {
  section: HomepageSection;
  saving: boolean;
  onSave: (props: Props) => void;
}) {
  const toast = useToast();
  const [heading, setHeading] = useState(() => readString(section.props, "heading"));
  const [consentText, setConsentText] = useState(() => readString(section.props, "consentText"));

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!heading.trim() || !consentText.trim()) {
          toast.error(
            "The signup needs a heading and a line telling people what they are opting into.",
          );
          return;
        }
        onSave({ heading: heading.trim(), consentText: consentText.trim() });
      }}
    >
      <Field label="Heading" htmlFor={`newsletter-heading-${section.id}`}>
        <Input
          id={`newsletter-heading-${section.id}`}
          value={heading}
          maxLength={120}
          onChange={(event) => setHeading(event.target.value)}
        />
      </Field>
      <Field label="Consent line" htmlFor={`newsletter-consent-${section.id}`}>
        <Textarea
          id={`newsletter-consent-${section.id}`}
          rows={2}
          value={consentText}
          maxLength={300}
          onChange={(event) => setConsentText(event.target.value)}
        />
      </Field>
      <SaveRow
        saving={saving}
        hint="Say how often you will write and that unsubscribing is easy."
      />
    </form>
  );
}

/** A single full-width graphic -- a brand statement or campaign lockup that
 *  is itself the content, rather than a heading/body pair like every other
 *  section here. Optionally links somewhere. */
function ImageBannerEditor({
  section,
  saving,
  onSave,
}: {
  section: HomepageSection;
  saving: boolean;
  onSave: (props: Props) => void;
}) {
  const toast = useToast();
  const [imageUrl, setImageUrl] = useState(() => readString(section.props, "imageUrl"));
  const [imageAlt, setImageAlt] = useState(() => readString(section.props, "imageAlt"));
  const [href, setHref] = useState(() => readString(section.props, "href"));

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      api.uploadImage(file, IMAGE_SPECIFICATIONS_BY_ID["home-page-banner"]),
    onSuccess: (result) => {
      setImageUrl(result.url);
      toast.success("Image uploaded. Save the section to apply it.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not upload the image."),
  });

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!imageUrl.trim() || !imageAlt.trim()) {
          toast.error("The banner needs an image and alt text describing it.");
          return;
        }
        onSave({
          imageUrl: imageUrl.trim(),
          imageAlt: imageAlt.trim(),
          href: href.trim() || null,
        });
      }}
    >
      <Field label="Image" htmlFor={`image-banner-upload-${section.id}`}>
        <Input
          id={`image-banner-upload-${section.id}`}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          className="mb-2"
          disabled={uploadMutation.isPending || saving}
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            if (file) uploadMutation.mutate(file);
            event.currentTarget.value = "";
          }}
        />
        <Input
          value={imageUrl}
          placeholder={uploadMutation.isPending ? "Uploading image..." : "Image URL"}
          onChange={(event) => setImageUrl(event.target.value)}
        />
        {imageUrl ? (
          <div className="mt-3">
            <ImagePreview
              src={imageUrl}
              alt={imageAlt}
              label="Motto banner"
              className="h-24 w-full max-w-md"
            />
          </div>
        ) : null}
      </Field>
      <Field label="Alt text" htmlFor={`image-banner-alt-${section.id}`}>
        <Input
          id={`image-banner-alt-${section.id}`}
          value={imageAlt}
          maxLength={200}
          onChange={(event) => setImageAlt(event.target.value)}
        />
      </Field>
      <Field label="Link (optional)" htmlFor={`image-banner-href-${section.id}`}>
        <Input
          id={`image-banner-href-${section.id}`}
          placeholder="/shop"
          value={href}
          maxLength={512}
          onChange={(event) => setHref(event.target.value)}
        />
      </Field>
      <SaveRow saving={saving} hint="Leave the link blank for a plain, unclickable image." />
    </form>
  );
}

/**
 * "What customers are saying". `rule` mode resolves live to the current
 * top-rated approved reviews sitewide -- nothing to pick, just a floor and a
 * count. `manual` mode picks specific testimonials from the approved queue, in
 * the order picked; unpicking one just removes it from `reviewIds`, it does
 * not touch the underlying review.
 */
function ReviewsShowcaseEditor({
  section,
  saving,
  onSave,
}: {
  section: HomepageSection;
  saving: boolean;
  onSave: (props: Props) => void;
}) {
  const toast = useToast();
  const [heading, setHeading] = useState(() => readString(section.props, "heading"));
  const [subheading, setSubheading] = useState(() => readString(section.props, "subheading"));
  const [source, setSource] = useState(() =>
    readString(section.props, "source") === "manual" ? "manual" : "rule",
  );
  const [minRating, setMinRating] = useState(() => readNumber(section.props, "minRating", 4));
  const [limit, setLimit] = useState(() => readNumber(section.props, "limit", 8));
  const [reviewIds, setReviewIds] = useState<string[]>(() =>
    readStrings(section.props, "reviewIds"),
  );

  const { data: approved, isLoading } = useQuery({
    queryKey: ["admin-reviews", "homepage-picker"],
    queryFn: () => api.reviews({ status: "approved", limit: 100 }),
    enabled: source === "manual",
  });
  const candidates = approved?.items ?? [];

  function toggle(id: string) {
    setReviewIds((current) =>
      current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id],
    );
  }

  function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= reviewIds.length) return;
    const next = [...reviewIds];
    const moved = next[index]!;
    next[index] = next[target]!;
    next[target] = moved;
    setReviewIds(next);
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!heading.trim()) {
          toast.error("The section needs a heading.");
          return;
        }
        if (source === "manual" && reviewIds.length === 0) {
          toast.error("Pick at least one review, or switch to top-rated reviews.");
          return;
        }
        onSave({
          heading: heading.trim(),
          subheading: subheading.trim(),
          source,
          reviewIds: source === "manual" ? reviewIds : [],
          limit: Math.min(Math.max(Math.round(limit), 1), 24),
          minRating: Math.min(Math.max(Math.round(minRating), 1), 5),
        });
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Section heading" htmlFor={`reviews-heading-${section.id}`}>
          <Input
            id={`reviews-heading-${section.id}`}
            value={heading}
            maxLength={120}
            onChange={(event) => setHeading(event.target.value)}
          />
        </Field>
        <Field label="Subheading (optional)" htmlFor={`reviews-subheading-${section.id}`}>
          <Input
            id={`reviews-subheading-${section.id}`}
            value={subheading}
            maxLength={240}
            onChange={(event) => setSubheading(event.target.value)}
          />
        </Field>
      </div>

      <Field label="Which reviews to show" htmlFor={`reviews-source-${section.id}`}>
        <Select
          id={`reviews-source-${section.id}`}
          value={source}
          onChange={(event) => setSource(event.target.value === "manual" ? "manual" : "rule")}
        >
          <option value="rule">
            <T>Top-rated reviews (updates automatically)</T>
          </option>
          <option value="manual">
            <T>Hand-picked testimonials</T>
          </option>
        </Select>
      </Field>

      {source === "rule" ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Minimum rating" htmlFor={`reviews-min-rating-${section.id}`}>
            <Select
              id={`reviews-min-rating-${section.id}`}
              value={String(minRating)}
              onChange={(event) => setMinRating(Number(event.target.value))}
            >
              {[5, 4, 3, 2, 1].map((value) => (
                <option key={value} value={value}>
                  {value}
                  <T>+ stars</T>
                </option>
              ))}
            </Select>
          </Field>
          <Field label="How many to show" htmlFor={`reviews-limit-${section.id}`}>
            <Input
              id={`reviews-limit-${section.id}`}
              type="number"
              min={1}
              max={24}
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value) || 1)}
            />
          </Field>
        </div>
      ) : (
        <div className="space-y-3">
          {isLoading ? (
            <p className="text-sm text-ink-muted">
              <T>Loading approved reviews...</T>
            </p>
          ) : candidates.length === 0 ? (
            <p className="max-w-xl rounded-md border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
              <T>
                No approved reviews yet. Approve some from the Reviews page, then come back here to
                feature them.
              </T>
            </p>
          ) : (
            <ul className="divide-y divide-line rounded-md border border-line">
              {candidates.map((review) => {
                const picked = reviewIds.includes(review.id);
                const pickedIndex = reviewIds.indexOf(review.id);
                return (
                  <li key={review.id} className="flex items-start gap-3 px-3 py-3">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={picked}
                      onChange={() => toggle(review.id)}
                      aria-label={`Feature review: ${review.title || review.body.slice(0, 40)}`}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-ink">
                        {review.rating}★ — {review.productName}
                      </p>
                      <p className="line-clamp-2 text-sm text-ink-muted">
                        {review.title ? `${review.title} — ` : ""}
                        {review.body}
                      </p>
                    </div>
                    {picked ? (
                      <div className="flex shrink-0 items-center gap-1.5">
                        <button
                          type="button"
                          aria-label="Move up in the showcase"
                          className="min-h-8 min-w-8 rounded-sm border border-line text-xs disabled:opacity-40"
                          disabled={pickedIndex === 0}
                          onClick={() => move(pickedIndex, -1)}
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          aria-label="Move down in the showcase"
                          className="min-h-8 min-w-8 rounded-sm border border-line text-xs disabled:opacity-40"
                          disabled={pickedIndex === reviewIds.length - 1}
                          onClick={() => move(pickedIndex, 1)}
                        >
                          ↓
                        </button>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      <SaveRow
        saving={saving}
        hint={
          source === "rule"
            ? "Resolves live on every homepage load -- nothing to keep up to date."
            : `${reviewIds.length} of 24 reviews featured, in the order shown above.`
        }
      />
    </form>
  );
}

/**
 * "What's on offer". `rule` mode resolves live to the current highest-
 * priority active promotion -- nothing to pick. `manual` mode pins one
 * specific promotion. No heading/subheading here: a promotion already
 * carries its own headline and description (Coupons & Promotions page),
 * which is also what the checkout-page callout reads, so the two surfaces
 * never drift into two hand-maintained versions of the same offer. Requires
 * `promotions.view` to load the manual-mode picker -- an editor without it
 * can still switch to rule mode.
 */
function PromotionBannerEditor({
  section,
  saving,
  onSave,
}: {
  section: HomepageSection;
  saving: boolean;
  onSave: (props: Props) => void;
}) {
  const toast = useToast();
  const permissions = usePermissions();
  const [source, setSource] = useState(() =>
    readString(section.props, "source") === "manual" ? "manual" : "rule",
  );
  const [promotionId, setPromotionId] = useState(() => {
    const value = section.props["promotionId"];
    return typeof value === "string" ? value : "";
  });

  const canPickPromotion = permissions.has("promotions.view");
  const { data: promotions, isLoading } = useQuery({
    queryKey: ["admin-promotions", "homepage-picker"],
    queryFn: () => api.promotions({ status: "active", limit: 100 }),
    enabled: source === "manual" && canPickPromotion,
  });
  const candidates = promotions?.items ?? [];

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (source === "manual" && !promotionId) {
          toast.error("Pick a promotion, or switch to the best-active-promotion mode.");
          return;
        }
        onSave({ source, promotionId: source === "manual" ? promotionId : null });
      }}
    >
      <Field label="Which promotion to show" htmlFor={`promo-source-${section.id}`}>
        <Select
          id={`promo-source-${section.id}`}
          value={source}
          onChange={(event) => setSource(event.target.value === "manual" ? "manual" : "rule")}
        >
          <option value="rule">
            <T>Best active promotion (updates automatically)</T>
          </option>
          <option value="manual">
            <T>One specific promotion</T>
          </option>
        </Select>
      </Field>

      {source === "manual" ? (
        !canPickPromotion ? (
          <p className="text-sm text-ink-muted">
            <T>You need the Coupons & Promotions permission to pick a specific promotion here.</T>
          </p>
        ) : isLoading ? (
          <p className="text-sm text-ink-muted">
            <T>Loading active promotions...</T>
          </p>
        ) : candidates.length === 0 ? (
          <p className="max-w-xl rounded-md border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
            <T>
              No active promotions yet. Create one from Coupons & Promotions, then come back here to
              feature it.
            </T>
          </p>
        ) : (
          <div className="space-y-2 rounded-md border border-line p-3">
            {candidates.map((promotion) => (
              <label key={promotion.id} className="flex items-start gap-2.5 text-sm text-ink">
                <input
                  type="radio"
                  name={`promo-pick-${section.id}`}
                  className="mt-1"
                  checked={promotionId === promotion.id}
                  onChange={() => setPromotionId(promotion.id)}
                />
                <span>
                  <span className="block font-medium">{promotion.name}</span>
                  {promotion.headline ? (
                    <span className="block text-xs text-ink-muted">{promotion.headline}</span>
                  ) : null}
                </span>
              </label>
            ))}
          </div>
        )
      ) : null}

      <SaveRow
        saving={saving}
        hint={
          source === "rule"
            ? "Resolves live on every homepage load -- nothing to keep up to date."
            : "Shown even if a higher-priority automatic promotion is also active."
        }
      />
    </form>
  );
}

/**
 * Best sellers, computed live from real order data -- there is no picker
 * here, only merchandising copy and a count, because the ranking itself
 * updates on its own as orders come in. The sitewide on/off switch for
 * recommendations lives on Site Control, not here: this editor only shapes
 * what shows when the feature is on.
 */
function RecommendationsEditor({
  section,
  saving,
  onSave,
}: {
  section: HomepageSection;
  saving: boolean;
  onSave: (props: Props) => void;
}) {
  const toast = useToast();
  const [heading, setHeading] = useState(() => readString(section.props, "heading"));
  const [subheading, setSubheading] = useState(() => readString(section.props, "subheading"));
  const [limit, setLimit] = useState(() => readNumber(section.props, "limit", 8));

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!heading.trim()) {
          toast.error("The section needs a heading.");
          return;
        }
        onSave({
          heading: heading.trim(),
          subheading: subheading.trim(),
          limit: Math.min(Math.max(Math.round(limit), 1), 24),
        });
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Section heading" htmlFor={`recs-heading-${section.id}`}>
          <Input
            id={`recs-heading-${section.id}`}
            value={heading}
            maxLength={120}
            onChange={(event) => setHeading(event.target.value)}
          />
        </Field>
        <Field label="Subheading (optional)" htmlFor={`recs-subheading-${section.id}`}>
          <Input
            id={`recs-subheading-${section.id}`}
            value={subheading}
            maxLength={240}
            onChange={(event) => setSubheading(event.target.value)}
          />
        </Field>
      </div>

      <Field label="How many products to show" htmlFor={`recs-limit-${section.id}`}>
        <Input
          id={`recs-limit-${section.id}`}
          type="number"
          min={1}
          max={24}
          value={limit}
          onChange={(event) => setLimit(Number(event.target.value) || 1)}
        />
      </Field>

      <SaveRow
        saving={saving}
        hint="Best sellers, resolved live from orders on every homepage load -- nothing to keep stocked."
      />
    </form>
  );
}

// ---------------------------------------------------------------------------
// Curated catalogue rows. Both save with the "Save homepage" button, because
// both are fields on the same site-control record as the banner above.
// ---------------------------------------------------------------------------

function FeaturedCategoriesSection({ form }: { form: ReturnType<typeof useForm<HomepageForm>> }) {
  const { data: allCategories, isLoading } = useQuery({
    queryKey: ["admin-categories", "homepage-picker"],
    queryFn: async () => {
      const [firstPage, secondPage] = await Promise.all([
        api.categories({ limit: 100 }),
        api.categories({ limit: 100, offset: 100 }),
      ]);
      return [...firstPage, ...secondPage];
    },
  });
  const { data: curatedSettings } = useQuery({
    queryKey: ["curated-settings"],
    queryFn: api.curatedSettings,
  });
  const maxCuratedSlots = curatedSettings?.maxItems ?? FALLBACK_CURATED_MAX_ITEMS;
  const [pendingId, setPendingId] = useState("");
  const currentSlugs = form.watch("featuredCategories");
  const currentCategories = currentSlugs
    .map((slug) => allCategories?.find((category) => category.slug === slug))
    .filter(Boolean) as NonNullable<typeof allCategories>;
  const addable = (allCategories ?? []).filter(
    (category) => category.status === "published" && !currentSlugs.includes(category.slug),
  );

  function move(index: number, delta: number) {
    const current = form.getValues("featuredCategories");
    const target = index + delta;
    if (target < 0 || target >= current.length) return;
    const next = [...current];
    [next[index], next[target]] = [next[target]!, next[index]!];
    form.setValue("featuredCategories", next, { shouldDirty: true, shouldValidate: true });
  }

  return (
    <section className="space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">
          <T>Category row</T>
        </h2>
        <p className="text-sm text-ink-muted">
          <T>Choose up to</T> {maxCuratedSlots}{" "}
          <T>
            published categories for the homepage slider. Customers see four at a time on desktop,
            in this order. Raise the limit on Site Control.
          </T>
        </p>
      </div>
      {isLoading ? (
        <p className="text-sm text-ink-muted">
          <T>Loading categories...</T>
        </p>
      ) : currentCategories.length === 0 ? (
        <p className="max-w-xl rounded-md border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
          <T>No homepage categories selected.</T>
        </p>
      ) : (
        <ul className="max-w-xl divide-y divide-line rounded-md border border-line">
          {currentCategories.map((category, index) => (
            <li key={category.id} className="flex items-center gap-2 px-3 py-2 text-sm">
              <span className="w-5 text-xs text-ink-muted">{index + 1}.</span>
              <span className="flex-1 font-medium text-ink">{category.name}</span>
              <StatusPill status={category.status} />
              <button
                type="button"
                aria-label={`Move ${category.name} up`}
                className="min-h-8 min-w-8 rounded-sm border border-line text-xs disabled:opacity-40"
                disabled={index === 0}
                onClick={() => move(index, -1)}
              >
                ↑
              </button>
              <button
                type="button"
                aria-label={`Move ${category.name} down`}
                className="min-h-8 min-w-8 rounded-sm border border-line text-xs disabled:opacity-40"
                disabled={index === currentSlugs.length - 1}
                onClick={() => move(index, 1)}
              >
                ↓
              </button>
              <button
                type="button"
                aria-label={`Remove ${category.name}`}
                className="min-h-8 rounded-sm border border-line px-2 text-xs text-danger"
                onClick={() =>
                  form.setValue(
                    "featuredCategories",
                    currentSlugs.filter((slug) => slug !== category.slug),
                    { shouldDirty: true, shouldValidate: true },
                  )
                }
              >
                <T>Remove</T>
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex max-w-xl gap-2">
        <Select
          aria-label="Category to add to the homepage"
          value={pendingId}
          onChange={(event) => setPendingId(event.target.value)}
          className="flex-1"
        >
          <option value="">
            <T>Add a category…</T>
          </option>
          {addable.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </Select>
        <Button
          type="button"
          variant="secondary"
          disabled={!pendingId || currentSlugs.length >= maxCuratedSlots}
          onClick={() => {
            const category = addable.find((entry) => entry.id === pendingId);
            if (!category) return;
            form.setValue("featuredCategories", [...currentSlugs, category.slug], {
              shouldDirty: true,
              shouldValidate: true,
            });
            setPendingId("");
          }}
        >
          <T>Add category</T>
        </Button>
      </div>
      <p className="text-xs text-ink-muted">
        {currentSlugs.length} of {maxCuratedSlots} <T>slots used</T>
      </p>
    </section>
  );
}

function FreshFavouritesSection({ form }: { form: ReturnType<typeof useForm<HomepageForm>> }) {
  const { data: allProducts, isLoading } = useQuery({
    queryKey: ["admin-products", "all"],
    queryFn: () => api.products({ limit: 100 }),
  });
  const { data: curatedSettings } = useQuery({
    queryKey: ["curated-settings"],
    queryFn: api.curatedSettings,
  });
  const maxCuratedSlots = curatedSettings?.maxItems ?? FALLBACK_CURATED_MAX_ITEMS;
  const [pendingId, setPendingId] = useState("");

  const currentSlugs = form.watch("freshFavourites");
  const currentProducts = currentSlugs
    .map((slug) => allProducts?.find((p) => p.slug === slug))
    .filter(Boolean) as AdminLinkedProduct[];
  const addable = (allProducts ?? []).filter((row) => !currentSlugs.includes(row.slug));

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
    <section className="space-y-4 border-t border-line pt-5">
      <div>
        <h2 className="font-display text-lg text-ink">
          <T>Product row (Fresh favourites)</T>
        </h2>
        <p className="text-sm text-ink-muted">
          <T>
            Shown in the Fresh favourites slider on the homepage. Only published products appear to
            customers.
          </T>
        </p>
      </div>
      {isLoading ? (
        <p className="text-sm text-ink-muted">
          <T>Loading products...</T>
        </p>
      ) : currentProducts.length === 0 ? (
        <p className="max-w-xl rounded-md border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
          <T>No fresh favourites yet. Add a few below.</T>
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
                  form.setValue(
                    "freshFavourites",
                    current.filter((slug) => slug !== entry.slug),
                    { shouldDirty: true, shouldValidate: true },
                  );
                }}
              >
                <T>Remove</T>
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
          <option value="">
            <T>Add a product…</T>
          </option>
          {addable.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </Select>
        <Button
          type="button"
          variant="secondary"
          disabled={!pendingId || currentSlugs.length >= maxCuratedSlots}
          onClick={() => {
            const row = addable.find((entry) => entry.id === pendingId);
            if (!row) return;
            const current = form.getValues("freshFavourites") || [];
            form.setValue("freshFavourites", [...current, row.slug], {
              shouldDirty: true,
              shouldValidate: true,
            });
            setPendingId("");
          }}
        >
          <T>Add to favourites</T>
        </Button>
      </div>
      <p className="text-xs text-ink-muted">
        {currentSlugs.length} of {maxCuratedSlots} <T>slots used</T>
      </p>
    </section>
  );
}
