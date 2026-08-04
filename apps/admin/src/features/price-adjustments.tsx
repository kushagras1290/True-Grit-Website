/**
 * Sale & Discounts — one signed price adjustment percentage, applied on top
 * of a product's real price.
 *
 * Positive is a genuine markup: it raises what a customer actually pays, and
 * the storefront shows only the new price — never a fabricated "was" price
 * to dress it up as a discount. Negative is a genuine discount: it lowers
 * what a customer actually pays, and the storefront shows the real price
 * struck through next to the lower one. There is exactly one real price;
 * this page adjusts it, it never invents a second one.
 *
 * A rule targets one product, one whole category, or every product, and
 * applies either everywhere ("global") or in one country. When more than one
 * active rule could apply to the same product and visitor, the most specific
 * one wins: a product-specific rule beats a category rule, a category rule
 * beats the "every product" default, and a country rule beats the global one
 * within each of those tiers. See `services/price_adjustments.py`.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useToast } from "../components/toast";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
} from "../components/ui";
import { ApiError, api, type PriceAdjustmentRule } from "../lib/api";
import { T } from "../lib/i18n";

type Target = "all" | "product" | "category";

const formSchema = z.object({
  scope: z.string().min(1),
  target: z.enum(["all", "product", "category"]),
  productId: z.string(),
  categoryId: z.string(),
  percent: z.coerce.number().int().min(-90).max(500),
  active: z.boolean(),
});

type FormValues = z.infer<typeof formSchema>;

const DEFAULTS: FormValues = {
  scope: "global",
  target: "all",
  productId: "",
  categoryId: "",
  percent: -10,
  active: true,
};

function targetLabel(rule: PriceAdjustmentRule): string {
  if (rule.productId) return rule.productName ?? "Unknown product";
  if (rule.categoryId) return `Category: ${rule.categoryName ?? "Unknown category"}`;
  return "Every product";
}

function percentLabel(percent: number): string {
  return percent > 0 ? `+${percent}% markup` : percent < 0 ? `${percent}% discount` : "No change";
}

export function PriceAdjustmentsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["price-adjustments"],
    queryFn: api.priceAdjustments,
  });
  const { data: productOptions } = useQuery({
    queryKey: ["admin-products", "price-adjustments-picker"],
    queryFn: () => api.products({ limit: 200 }),
  });
  const { data: categoryOptions } = useQuery({
    queryKey: ["admin-categories", "price-adjustments-picker"],
    queryFn: () => api.categories({ limit: 200 }),
  });
  const [newCountry, setNewCountry] = useState("");
  const [countryScopes, setCountryScopes] = useState<string[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<PriceAdjustmentRule | null>(null);

  const form = useForm<FormValues>({ resolver: zodResolver(formSchema), defaultValues: DEFAULTS });
  const target = form.watch("target");

  const rules = data?.rules ?? [];
  useEffect(() => {
    const known = new Set(rules.map((rule) => rule.scope).filter((scope) => scope !== "global"));
    setCountryScopes((current) => [...new Set([...current, ...known])]);
  }, [rules]);

  function applyResult(result: Awaited<ReturnType<typeof api.priceAdjustments>>) {
    queryClient.setQueryData(["price-adjustments"], result);
  }

  const saveMutation = useMutation({
    mutationFn: (values: FormValues) =>
      api.savePriceAdjustment({
        scope: values.scope,
        productId: values.target === "product" ? values.productId || null : null,
        categoryId: values.target === "category" ? values.categoryId || null : null,
        percent: values.percent,
        active: values.active,
      }),
    onSuccess: (result) => {
      applyResult(result);
      toast.success("Price adjustment saved.");
      form.reset({ ...DEFAULTS, scope: form.getValues("scope") });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the adjustment."),
  });

  const toggleMutation = useMutation({
    mutationFn: (rule: PriceAdjustmentRule) =>
      api.savePriceAdjustment({
        scope: rule.scope,
        productId: rule.productId,
        categoryId: rule.categoryId,
        percent: rule.percent,
        active: !rule.active,
      }),
    onSuccess: applyResult,
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update the adjustment."),
  });

  const deleteMutation = useMutation({
    mutationFn: (ruleId: string) => api.deletePriceAdjustment(ruleId),
    onSuccess: (result) => {
      applyResult(result);
      setConfirmDelete(null);
      toast.success("Price adjustment removed.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not remove the adjustment."),
  });

  function addCountry() {
    const code = newCountry.trim().toUpperCase();
    if (!/^[A-Z]{2}$/.test(code)) {
      toast.error("A country needs a two-letter code, for example IN, US or DE.");
      return;
    }
    setNewCountry("");
    setCountryScopes((current) => [...new Set([...current, code])]);
    form.setValue("scope", code);
  }

  function onInvalidSubmit(errors: typeof form.formState.errors) {
    const firstError = Object.values(errors).find((error): error is { message?: string } =>
      Boolean(error?.message),
    );
    toast.error(firstError?.message ?? "Fix the highlighted fields before saving.");
  }

  function onSubmit(values: FormValues) {
    if (values.target === "product" && !values.productId) {
      toast.error("Choose a product for a product-specific rule.");
      return;
    }
    if (values.target === "category" && !values.categoryId) {
      toast.error("Choose a category for a category-specific rule.");
      return;
    }
    saveMutation.mutate(values);
  }

  if (isLoading)
    return (
      <p className="text-sm text-ink-muted">
        <T>Loading price adjustments...</T>
      </p>
    );
  if (isError) {
    return (
      <EmptyState title="Price adjustments unavailable" hint="Requires owner settings access." />
    );
  }

  return (
    <div>
      <PageHeader
        title="Sale & Discounts"
        description="A signed price adjustment: positive raises the real price (a markup), negative genuinely lowers it (a discount). Target one product, one category, or every product — globally or in one country."
      />

      <form
        className="grid gap-6 border-t border-line pt-5 xl:grid-cols-[minmax(0,1fr)_22rem]"
        onSubmit={form.handleSubmit(onSubmit, onInvalidSubmit)}
      >
        <div className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-56">
              <Field label="Applies to" htmlFor="pa-scope">
                <Select id="pa-scope" {...form.register("scope")}>
                  <option value="global">
                    <T>Whole site</T>
                  </option>
                  {countryScopes.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <div className="min-w-32">
              <Field label="Add a country" htmlFor="pa-new-country">
                <Input
                  id="pa-new-country"
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

          <fieldset>
            <legend className="text-sm font-medium text-ink">
              <T>Target</T>
            </legend>
            <div className="mt-2 flex flex-wrap gap-4">
              {(
                [
                  ["all", "Every product"],
                  ["product", "One product"],
                  ["category", "One category"],
                ] as Array<[Target, string]>
              ).map(([value, label]) => (
                <label key={value} className="flex items-center gap-2 text-sm text-ink">
                  <input type="radio" value={value} {...form.register("target")} />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>

          {target === "product" ? (
            <Field label="Product" htmlFor="pa-product">
              <Select id="pa-product" {...form.register("productId")}>
                <option value="">
                  <T>Choose a product…</T>
                </option>
                {(productOptions ?? []).map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name}
                  </option>
                ))}
              </Select>
            </Field>
          ) : null}

          {target === "category" ? (
            <Field label="Category" htmlFor="pa-category">
              <Select id="pa-category" {...form.register("categoryId")}>
                <option value="">
                  <T>Choose a category…</T>
                </option>
                {(categoryOptions ?? []).map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </Select>
            </Field>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2">
            <Field
              label="Adjustment %"
              htmlFor="pa-percent"
              error={form.formState.errors.percent?.message}
            >
              <Input
                id="pa-percent"
                type="number"
                min={-90}
                max={500}
                step={1}
                {...form.register("percent")}
              />
            </Field>
            <label className="flex items-center gap-2 self-end pb-2.5 text-sm text-ink">
              <input type="checkbox" {...form.register("active")} />
              <T>Active</T>
            </label>
          </div>
          <p className="text-xs text-ink-muted">
            <T>
              Positive raises the price (a markup, shown as the new price alone). Negative lowers it
              (a discount, shown with the real price struck through). Between −90% and 500%. Saving
              a rule for the same target and scope replaces it rather than adding a duplicate.
            </T>
          </p>
        </div>

        <aside className="h-fit border-t border-line pt-5 xl:border-t-0 xl:pt-0">
          <h2 className="font-display text-lg text-ink">
            <T>Save</T>
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            <T>New and updated rules apply to the live storefront immediately.</T>
          </p>
          <Button
            type="submit"
            variant="primary"
            className="mt-5 w-full"
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending ? <T>{"Saving..."}</T> : <T>{"Save rule"}</T>}
          </Button>
        </aside>
      </form>

      <section className="mt-8 space-y-4 border-t border-line pt-5">
        <h2 className="font-display text-lg text-ink">
          <T>Active rules</T>
        </h2>
        {rules.length === 0 ? (
          <EmptyState title="No price adjustments yet" hint="Add one above to get started." />
        ) : (
          <ul className="divide-y divide-line rounded-md border border-line">
            {rules.map((rule) => (
              <li
                key={rule.id}
                className="flex flex-wrap items-center justify-between gap-3 px-3 py-3"
              >
                <div className="min-w-0">
                  <span className="block text-sm font-medium text-ink">
                    {rule.scope === "global" ? <T>{"Whole site"}</T> : rule.scope} ·{" "}
                    {targetLabel(rule)}
                  </span>
                  <span
                    className={`block text-xs ${rule.percent < 0 ? "text-success" : rule.percent > 0 ? "text-accent" : "text-ink-muted"}`}
                  >
                    {percentLabel(rule.percent)}
                    {rule.active ? "" : <T>{" · inactive"}</T>}
                  </span>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <Button
                    type="button"
                    variant="secondary"
                    className="min-h-8 px-2.5 text-xs"
                    disabled={toggleMutation.isPending}
                    onClick={() => toggleMutation.mutate(rule)}
                  >
                    {rule.active ? <T>{"Deactivate"}</T> : <T>{"Activate"}</T>}
                  </Button>
                  <Button
                    type="button"
                    variant="tertiary"
                    className="min-h-8 px-2.5 text-xs"
                    onClick={() => setConfirmDelete(rule)}
                  >
                    <T>Delete</T>
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {confirmDelete ? (
        <ConfirmDialog
          title="Delete this price adjustment?"
          description={`"${targetLabel(confirmDelete)}" (${confirmDelete.scope === "global" ? "whole site" : confirmDelete.scope}) reverts to whatever rule applies next. This cannot be undone.`}
          confirmLabel="Delete rule"
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => deleteMutation.mutate(confirmDelete.id)}
        />
      ) : null}
    </div>
  );
}
