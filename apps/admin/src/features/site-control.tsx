import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button, EmptyState, Field, Input, PageHeader, Textarea } from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api, type SiteControl } from "../lib/api";

const siteSchema = z.object({
  announcementActive: z.boolean(),
  announcementMessage: z.string().max(220),
  announcementPath: z.string().max(200),
  heroEyebrow: z.string().max(120),
  heroHeading: z.string().min(3).max(160),
  heroText: z.string().max(500),
  primaryActionLabel: z.string().max(80),
  primaryActionHref: z.string().max(200),
  secondaryActionLabel: z.string().max(80),
  secondaryActionHref: z.string().max(200),
  seoTitle: z.string().min(3).max(160),
  seoDescription: z.string().max(320),
  seoKeywords: z.string().max(500),
});

type SiteForm = z.infer<typeof siteSchema>;

function defaults(data?: SiteControl): SiteForm {
  return {
    announcementActive: data?.announcementActive ?? false,
    announcementMessage: data?.announcementMessage ?? "",
    announcementPath: data?.announcementPath ?? "",
    heroEyebrow: data?.heroEyebrow ?? "",
    heroHeading: data?.heroHeading ?? "",
    heroText: data?.heroText ?? "",
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

  useEffect(() => {
    if (data) form.reset(defaults(data));
  }, [data, form]);

  const mutation = useMutation({
    mutationFn: (values: SiteForm) => api.updateSiteControl(values),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["site-control"] });
      form.reset(defaults(result));
      toast.success("Site controls saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save site controls."),
  });

  if (isLoading) return <p className="text-sm text-ink-muted">Loading site controls...</p>;
  if (isError) {
    return <EmptyState title="Site controls unavailable" hint="Requires owner settings access." />;
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
              <Input id="announcementPath" placeholder="/category/fresh-fruits" {...form.register("announcementPath")} />
            </Field>
          </section>

          <section className="space-y-4 border-t border-line pt-5">
            <div>
              <h2 className="font-display text-lg text-ink">Homepage hero</h2>
              <p className="text-sm text-ink-muted">Primary homepage banner copy and calls to action.</p>
            </div>
            <Field label="Eyebrow" htmlFor="heroEyebrow">
              <Input id="heroEyebrow" {...form.register("heroEyebrow")} />
            </Field>
            <Field label="Headline" htmlFor="heroHeading" error={form.formState.errors.heroHeading?.message}>
              <Input id="heroHeading" {...form.register("heroHeading")} />
            </Field>
            <Field label="Supporting text" htmlFor="heroText">
              <Textarea id="heroText" {...form.register("heroText")} />
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
              <p className="text-sm text-ink-muted">Metadata used by search engines and social previews.</p>
            </div>
            <Field label="SEO title" htmlFor="seoTitle" error={form.formState.errors.seoTitle?.message}>
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
    </div>
  );
}
