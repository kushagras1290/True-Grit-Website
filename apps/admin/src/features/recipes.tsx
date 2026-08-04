/** Recipes list and editor for the `chef` role and reviewers. Chefs draft,
 * edit and submit for review; only `recipes.approve`/`.publish` holders can
 * approve, request changes or publish. Mirrors features/articles.tsx. */

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AdminRecipeDetail, AdminRecipeIngredient } from "@truegrit/contracts";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router";
import { z } from "zod";

import {
  Button,
  DataTableShell,
  EmptyState,
  Field,
  ImagePreview,
  Input,
  LoadingRows,
  Modal,
  PageHeader,
  Pagination,
  SearchBox,
  Select,
  StatusPill,
  Td,
  Textarea,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { PermissionGate, usePermissions } from "../lib/permissions";
import { T } from "../lib/i18n";

const createSchema = z.object({
  title: z.string().min(3, "At least 3 characters").max(180),
  slug: z
    .string()
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Lowercase letters, numbers and single hyphens")
    .optional()
    .or(z.literal("")),
  excerpt: z.string().max(300).optional().or(z.literal("")),
});

type CreateForm = z.infer<typeof createSchema>;

function CreateRecipeModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { title: "", slug: "", excerpt: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: CreateForm) =>
      api.createRecipe({
        title: values.title,
        slug: values.slug || undefined,
        excerpt: values.excerpt || undefined,
      }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["admin-recipes"] });
      toast.success("Recipe created as a draft.");
      onClose();
      navigate(`/recipes/${result.id}`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not create the recipe."),
  });

  return (
    <Modal title="New recipe" onClose={onClose}>
      <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Title" htmlFor="rcp-title" error={form.formState.errors.title?.message}>
          <Input
            id="rcp-title"
            placeholder="Crisp sprouted ragi dosa"
            {...form.register("title")}
          />
        </Field>
        <Field
          label="Slug (optional)"
          htmlFor="rcp-slug"
          error={form.formState.errors.slug?.message}
        >
          <Input id="rcp-slug" placeholder="crisp-sprouted-ragi-dosa" {...form.register("slug")} />
        </Field>
        <Field label="Excerpt (optional)" htmlFor="rcp-excerpt">
          <Textarea id="rcp-excerpt" rows={2} {...form.register("excerpt")} />
        </Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            <T>Cancel</T>
          </Button>
          <Button type="submit" variant="primary" disabled={mutation.isPending}>
            {mutation.isPending ? <T>{"Creating…"}</T> : <T>{"Create draft"}</T>}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

const RECIPES_PAGE_LIMIT = 25;

export function RecipeListPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const offset = (page - 1) * RECIPES_PAGE_LIMIT;
  const { data, isLoading } = useQuery({
    queryKey: ["admin-recipes", page, searchQuery],
    queryFn: () =>
      api.recipes({ limit: RECIPES_PAGE_LIMIT, offset, search: searchQuery || undefined }),
  });
  const [creating, setCreating] = useState(false);
  const recipes = data ?? [];

  // One-click enable/disable — a disabled recipe drops off /recipes via the
  // public API immediately (mirrors the blog list toggle).
  const toggleMutation = useMutation({
    mutationFn: ({ id, publish }: { id: string; publish: boolean }) =>
      publish ? api.publishRecipe(id) : api.unpublishRecipe(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-recipes"] });
      toast.success("Recipe visibility updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update the recipe."),
  });

  return (
    <div>
      <PageHeader
        title="Recipes"
        description="Chefs draft and submit recipes here; reviewers approve and publish."
        actions={
          <PermissionGate permission="recipes.create">
            <Button variant="primary" onClick={() => setCreating(true)}>
              <T>New recipe</T>
            </Button>
          </PermissionGate>
        }
      />
      {creating ? <CreateRecipeModal onClose={() => setCreating(false)} /> : null}

      <div className="mb-4 max-w-sm">
        <SearchBox
          value={searchQuery}
          onSearch={(value) => {
            setSearchQuery(value);
            setPage(1);
          }}
          placeholder="Search by title, slug or excerpt…"
          aria-label="Search recipes"
        />
      </div>

      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>
              <T>Title</T>
            </Th>
            <Th>
              <T>Chef</T>
            </Th>
            <Th>
              <T>Status</T>
            </Th>
            <Th>
              <T>Updated</T>
            </Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={4} />
        ) : recipes.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={4} className="px-3 py-8">
                <EmptyState title="No recipes yet" hint="Create the first draft to get started." />
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {recipes.map((recipe) => (
              <tr key={recipe.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <Link
                    to={`/recipes/${recipe.id}`}
                    className="font-medium text-brand hover:underline"
                  >
                    {recipe.title}
                  </Link>
                  <span className="block text-xs text-ink-muted">
                    <T>/recipes/</T>
                    {recipe.slug}
                  </span>
                </Td>
                <Td className="text-ink-muted">{recipe.chefName}</Td>
                <Td>
                  <div className="flex items-center gap-2">
                    <StatusPill status={recipe.status} />
                    {recipe.hasDraftChanges ? (
                      <span className="rounded-full bg-warning/10 px-2 py-0.5 text-xs text-warning">
                        <T>Draft changes pending</T>
                      </span>
                    ) : null}
                    {recipe.status === "published" || recipe.status === "unpublished" ? (
                      <PermissionGate permission="recipes.publish">
                        <Button
                          variant="secondary"
                          disabled={toggleMutation.isPending}
                          onClick={() =>
                            toggleMutation.mutate({
                              id: recipe.id,
                              publish: recipe.status !== "published",
                            })
                          }
                        >
                          {recipe.status === "published" ? <T>{"Disable"}</T> : <T>{"Enable"}</T>}
                        </Button>
                      </PermissionGate>
                    ) : null}
                  </div>
                </Td>
                <Td>{formatDateTime(recipe.updatedAt)}</Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      <Pagination
        page={page}
        onPageChange={setPage}
        rowCount={recipes.length}
        limit={RECIPES_PAGE_LIMIT}
      />
    </div>
  );
}

const bannerImageUrlSchema = z
  .string()
  .max(1000)
  .refine(
    (value) =>
      value === "" ||
      (value.startsWith("/") && !value.startsWith("//")) ||
      z.string().url().safeParse(value).success,
    "Enter a valid image URL",
  );

const editSchema = z.object({
  title: z.string().min(3, "At least 3 characters").max(180),
  slug: z
    .string()
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Lowercase letters, numbers and single hyphens"),
  excerpt: z.string().max(300),
  prepMinutes: z.coerce.number().int().min(0).max(600),
  cookMinutes: z.coerce.number().int().min(0).max(600),
  servings: z.coerce.number().int().min(1).max(50),
  dietaryTagsText: z.string().max(200),
  heroImageUrl: bannerImageUrlSchema,
  heroImageAlt: z.string().max(200),
  seoTitle: z.string().max(160),
  seoDescription: z.string().max(320),
  seoKeywords: z.string().max(500),
  canonicalUrl: z.string().max(300),
  indexingPolicy: z.enum(["index", "noindex"]),
  stepsText: z.string(),
  blocksJson: z.string().min(2),
});

type EditForm = z.infer<typeof editSchema>;

function recipeDefaults(recipe: AdminRecipeDetail): EditForm {
  return {
    title: recipe.title,
    slug: recipe.slug,
    excerpt: recipe.excerpt,
    prepMinutes: recipe.prepMinutes,
    cookMinutes: recipe.cookMinutes,
    servings: recipe.servings,
    dietaryTagsText: recipe.dietaryTags.join(", "),
    heroImageUrl: recipe.heroImageUrl,
    heroImageAlt: recipe.heroImageAlt,
    seoTitle: recipe.seoTitle,
    seoDescription: recipe.seoDescription,
    seoKeywords: recipe.seoKeywords,
    canonicalUrl: recipe.canonicalUrl,
    indexingPolicy: recipe.indexingPolicy,
    stepsText: recipe.steps.join("\n"),
    blocksJson: JSON.stringify(recipe.blocks, null, 2),
  };
}

function RequestChangesModal({
  onClose,
  onSubmit,
  isPending,
}: {
  onClose: () => void;
  onSubmit: (note: string) => void;
  isPending: boolean;
}) {
  const [note, setNote] = useState("");
  return (
    <Modal title="Request changes" onClose={onClose}>
      <div className="space-y-4">
        <Field label="What needs to change?" htmlFor="rrc-note">
          <Textarea
            id="rrc-note"
            rows={4}
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            <T>Cancel</T>
          </Button>
          <Button
            type="button"
            variant="primary"
            disabled={isPending || note.trim().length === 0}
            onClick={() => onSubmit(note.trim())}
          >
            {isPending ? <T>{"Sending…"}</T> : <T>{"Send back to draft"}</T>}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function IngredientsEditor({
  ingredients,
  onChange,
}: {
  ingredients: AdminRecipeIngredient[];
  onChange: (next: AdminRecipeIngredient[]) => void;
}) {
  function update(index: number, patch: Partial<AdminRecipeIngredient>) {
    onChange(ingredients.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)));
  }
  function remove(index: number) {
    onChange(ingredients.filter((_, i) => i !== index));
  }
  function add() {
    onChange([
      ...ingredients,
      {
        id: `new_${Date.now().toString(36)}`,
        label: "",
        quantityText: "",
        productId: null,
        productSlug: null,
      },
    ]);
  }

  return (
    <div className="space-y-2">
      {ingredients.map((ingredient, index) => (
        <div key={ingredient.id} className="flex items-center gap-2">
          <Input
            aria-label="Ingredient label"
            placeholder="Sprouted ragi flour"
            className="flex-1"
            value={ingredient.label}
            onChange={(event) => update(index, { label: event.target.value })}
          />
          <Input
            aria-label="Quantity"
            placeholder="2 cups"
            className="w-32"
            value={ingredient.quantityText}
            onChange={(event) => update(index, { quantityText: event.target.value })}
          />
          <button
            type="button"
            aria-label="Remove ingredient"
            className="text-ink-muted hover:text-danger"
            onClick={() => remove(index)}
          >
            <Trash2 size={16} />
          </button>
        </div>
      ))}
      <Button type="button" variant="secondary" onClick={add}>
        <Plus size={14} /> <T>Add ingredient</T>
      </Button>
    </div>
  );
}

export function RecipeEditorPage() {
  const { id = "" } = useParams();
  const toast = useToast();
  const queryClient = useQueryClient();
  const permissions = usePermissions();
  const [requestingChanges, setRequestingChanges] = useState(false);
  const [ingredients, setIngredients] = useState<AdminRecipeIngredient[]>([]);

  const {
    data: recipe,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["admin-recipe", id],
    queryFn: () => api.getRecipe(id),
    retry: false,
  });

  const form = useForm<EditForm>({
    resolver: zodResolver(editSchema),
    values: recipe ? recipeDefaults(recipe) : undefined,
  });

  if (recipe && ingredients.length === 0 && recipe.ingredients.length > 0) {
    setIngredients(recipe.ingredients);
  }

  function invalidate() {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin-recipe", id] }),
      queryClient.invalidateQueries({ queryKey: ["admin-recipes"] }),
    ]);
  }

  const saveMutation = useMutation({
    mutationFn: (values: EditForm) => {
      let blocks: unknown;
      try {
        blocks = JSON.parse(values.blocksJson);
      } catch {
        throw new ApiError("Blocks JSON is not valid.", 422, "validation_error");
      }
      if (!Array.isArray(blocks)) {
        throw new ApiError("Blocks JSON must be an array.", 422, "validation_error");
      }
      const steps = values.stepsText
        .split("\n")
        .map((step) => step.trim())
        .filter(Boolean);
      return api.updateRecipe(id, {
        title: values.title,
        slug: values.slug,
        excerpt: values.excerpt,
        prepMinutes: values.prepMinutes,
        cookMinutes: values.cookMinutes,
        servings: values.servings,
        dietaryTags: values.dietaryTagsText
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        heroImageUrl: values.heroImageUrl,
        heroImageAlt: values.heroImageAlt,
        seoTitle: values.seoTitle,
        seoDescription: values.seoDescription,
        seoKeywords: values.seoKeywords,
        canonicalUrl: values.canonicalUrl,
        indexingPolicy: values.indexingPolicy,
        blocks,
        steps,
        ingredients: ingredients
          .filter((entry) => entry.label.trim().length > 0)
          .map((entry) => ({
            label: entry.label,
            quantityText: entry.quantityText || undefined,
            productId: entry.productId || undefined,
          })),
      });
    },
    onSuccess: async () => {
      await invalidate();
      toast.success("Recipe saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the recipe."),
  });

  const submitMutation = useMutation({
    mutationFn: () => api.submitRecipe(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Submitted for review.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not submit."),
  });

  const approveMutation = useMutation({
    mutationFn: () => api.approveRecipe(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Approved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not approve."),
  });

  const requestChangesMutation = useMutation({
    mutationFn: (note: string) => api.requestRecipeChanges(id, note),
    onSuccess: async () => {
      await invalidate();
      setRequestingChanges(false);
      toast.success("Sent back to draft.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not request changes."),
  });

  const publishMutation = useMutation({
    mutationFn: () => api.publishRecipe(id),
    onSuccess: async (result) => {
      await invalidate();
      toast.success(`Published — version ${result.version} is now live.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not publish."),
  });

  const unpublishMutation = useMutation({
    mutationFn: () => api.unpublishRecipe(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Unpublished.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not unpublish."),
  });

  const bannerUploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadImage(file),
    onSuccess: (result) => {
      form.setValue("heroImageUrl", result.url, { shouldDirty: true, shouldValidate: true });
      if (!form.getValues("heroImageAlt")) {
        form.setValue("heroImageAlt", form.getValues("title"), {
          shouldDirty: true,
          shouldValidate: true,
        });
      }
      toast.success("Banner uploaded — save to apply.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not upload the banner."),
  });

  if (isLoading)
    return (
      <p className="text-sm text-ink-muted">
        <T>Loading recipe…</T>
      </p>
    );
  if (isError || !recipe) return <EmptyState title="Recipe not found" />;

  const canEdit = permissions.has("recipes.edit") || permissions.has("recipes.approve");

  return (
    <div>
      <PageHeader
        title={recipe.title}
        description={`/recipes/${recipe.slug}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={recipe.status} />
            {recipe.status === "draft" ? (
              <PermissionGate permission="recipes.edit">
                <Button onClick={() => submitMutation.mutate()} disabled={submitMutation.isPending}>
                  {submitMutation.isPending ? <T>{"Submitting…"}</T> : <T>{"Submit for review"}</T>}
                </Button>
              </PermissionGate>
            ) : null}
            {recipe.status === "in_review" ? (
              <PermissionGate permission="recipes.approve">
                <Button variant="secondary" onClick={() => setRequestingChanges(true)}>
                  <T>Request changes</T>
                </Button>
                <Button
                  onClick={() => approveMutation.mutate()}
                  disabled={approveMutation.isPending}
                >
                  {approveMutation.isPending ? <T>{"Approving…"}</T> : <T>{"Approve"}</T>}
                </Button>
              </PermissionGate>
            ) : null}
            {recipe.status === "published" ? (
              <PermissionGate permission="recipes.publish">
                <Button
                  variant="secondary"
                  onClick={() => unpublishMutation.mutate()}
                  disabled={unpublishMutation.isPending}
                >
                  {unpublishMutation.isPending ? <T>{"Unpublishing…"}</T> : <T>{"Unpublish"}</T>}
                </Button>
              </PermissionGate>
            ) : null}
            <PermissionGate
              permission="recipes.publish"
              fallback={
                recipe.status === "published" ? null : (
                  <Button disabled title="Requires recipes.publish">
                    <T>Publish</T>
                  </Button>
                )
              }
            >
              {recipe.status === "published" ? null : (
                <Button
                  variant="primary"
                  onClick={() => publishMutation.mutate()}
                  disabled={publishMutation.isPending}
                >
                  {publishMutation.isPending ? <T>{"Publishing…"}</T> : <T>{"Publish"}</T>}
                </Button>
              )}
            </PermissionGate>
          </div>
        }
      />
      {requestingChanges ? (
        <RequestChangesModal
          onClose={() => setRequestingChanges(false)}
          onSubmit={(note) => requestChangesMutation.mutate(note)}
          isPending={requestChangesMutation.isPending}
        />
      ) : null}

      <fieldset disabled={!canEdit} className="max-w-3xl space-y-5">
        <form
          className="space-y-5"
          onSubmit={form.handleSubmit((values) => saveMutation.mutate(values))}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Title" htmlFor="rcp-e-title" error={form.formState.errors.title?.message}>
              <Input id="rcp-e-title" {...form.register("title")} />
            </Field>
            <Field label="Slug" htmlFor="rcp-e-slug" error={form.formState.errors.slug?.message}>
              <Input id="rcp-e-slug" {...form.register("slug")} />
            </Field>
          </div>
          <Field label="Excerpt" htmlFor="rcp-e-excerpt">
            <Textarea id="rcp-e-excerpt" rows={2} {...form.register("excerpt")} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Prep minutes" htmlFor="rcp-e-prep">
              <Input id="rcp-e-prep" type="number" min={0} {...form.register("prepMinutes")} />
            </Field>
            <Field label="Cook minutes" htmlFor="rcp-e-cook">
              <Input id="rcp-e-cook" type="number" min={0} {...form.register("cookMinutes")} />
            </Field>
            <Field label="Servings" htmlFor="rcp-e-servings">
              <Input id="rcp-e-servings" type="number" min={1} {...form.register("servings")} />
            </Field>
          </div>
          <Field label="Dietary tags (comma separated)" htmlFor="rcp-e-tags">
            <Input
              id="rcp-e-tags"
              placeholder="gluten-free, plant-based"
              {...form.register("dietaryTagsText")}
            />
          </Field>

          <div className="border-t border-line pt-5">
            <h2 className="font-display text-lg text-ink">
              <T>Banner image</T>
            </h2>
            <p className="text-sm text-ink-muted">
              <T>Shown at the top of the recipe and as its thumbnail on the recipes listing.</T>
            </p>
            <div className="mt-3 space-y-4">
              <Field
                label="Banner image URL"
                htmlFor="rcp-e-hero-url"
                error={form.formState.errors.heroImageUrl?.message}
              >
                <Input
                  id="rcp-e-hero-upload"
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="mb-2"
                  disabled={bannerUploadMutation.isPending || saveMutation.isPending}
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0];
                    if (file) bannerUploadMutation.mutate(file);
                    event.currentTarget.value = "";
                  }}
                />
                <Input
                  id="rcp-e-hero-url"
                  placeholder={
                    bannerUploadMutation.isPending ? "Uploading image…" : "/media/images/…"
                  }
                  {...form.register("heroImageUrl")}
                />
                {form.watch("heroImageUrl") ? (
                  <div className="mt-3">
                    <ImagePreview
                      src={form.watch("heroImageUrl")}
                      alt={form.watch("heroImageAlt")}
                      label={recipe.title || "Recipe banner"}
                      className="h-32 w-full max-w-md"
                    />
                  </div>
                ) : null}
              </Field>
              <Field label="Banner alt text" htmlFor="rcp-e-hero-alt">
                <Input
                  id="rcp-e-hero-alt"
                  placeholder="Describes the banner for screen readers"
                  {...form.register("heroImageAlt")}
                />
              </Field>
            </div>
          </div>

          <div className="border-t border-line pt-5">
            <h2 className="font-display text-lg text-ink">
              <T>Ingredients</T>
            </h2>
            <div className="mt-3">
              <IngredientsEditor ingredients={ingredients} onChange={setIngredients} />
            </div>
          </div>

          <div className="border-t border-line pt-5">
            <h2 className="font-display text-lg text-ink">
              <T>Method</T>
            </h2>
            <Field label="Steps (one per line)" htmlFor="rcp-e-steps">
              <Textarea id="rcp-e-steps" rows={8} {...form.register("stepsText")} />
            </Field>
          </div>

          <div className="border-t border-line pt-5">
            <h2 className="font-display text-lg text-ink">
              <T>SEO</T>
            </h2>
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              <Field label="SEO title" htmlFor="rcp-e-seo-title">
                <Input id="rcp-e-seo-title" {...form.register("seoTitle")} />
              </Field>
              <Field label="SEO keywords" htmlFor="rcp-e-seo-keywords">
                <Input id="rcp-e-seo-keywords" {...form.register("seoKeywords")} />
              </Field>
              <Field label="Canonical URL" htmlFor="rcp-e-canonical">
                <Input
                  id="rcp-e-canonical"
                  placeholder="/recipes/my-recipe"
                  {...form.register("canonicalUrl")}
                />
              </Field>
              <Field label="Search indexing" htmlFor="rcp-e-indexing">
                <Select id="rcp-e-indexing" {...form.register("indexingPolicy")}>
                  <option value="index">
                    <T>Index</T>
                  </option>
                  <option value="noindex">
                    <T>No index</T>
                  </option>
                </Select>
              </Field>
            </div>
            <Field label="SEO description" htmlFor="rcp-e-seo-description">
              <Textarea id="rcp-e-seo-description" rows={3} {...form.register("seoDescription")} />
            </Field>
          </div>

          <div className="border-t border-line pt-5">
            <h2 className="font-display text-lg text-ink">
              <T>Intro / story blocks</T>
            </h2>
            <p className="text-sm text-ink-muted">
              <T>
                Optional content shown above the ingredients — supports the same blocks as blog
                posts, including
              </T>{" "}
              <code className="font-mono text-xs">
                <T>[label](/path)</T>
              </code>{" "}
              <T>
                links and a product_collection block to highlight the products used in this recipe.
              </T>
            </p>
            <Field
              label="Blocks JSON"
              htmlFor="rcp-e-blocks"
              error={form.formState.errors.blocksJson?.message}
            >
              <Textarea
                id="rcp-e-blocks"
                rows={14}
                className="font-mono text-xs"
                {...form.register("blocksJson")}
              />
            </Field>
          </div>

          <div className="flex items-center justify-between">
            <p className="text-xs text-ink-muted">
              <T>Last updated</T> {formatDateTime(recipe.updatedAt)}
            </p>
            <Button type="submit" variant="primary" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? <T>{"Saving…"}</T> : <T>{"Save"}</T>}
            </Button>
          </div>
        </form>
      </fieldset>
    </div>
  );
}
