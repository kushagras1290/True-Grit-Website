import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  Button,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  StatusPill,
  Textarea,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api, type AdminLinkedProduct, type SiteControl } from "../lib/api";

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

      <HighlightsSection />
    </div>
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
