/** Category list, create dialog, and editor. The editor has a Settings tab
 * (real, persisted fields) and a Layout tab — the keyboard-accessible block
 * builder (dnd-kit) with a live preview. Publish hits the real workflow. */

import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { PublicPageBlock } from "@truegrit/contracts";
import { Eye, EyeOff, GripVertical } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router";
import { z } from "zod";

import {
  Button,
  ConfirmDialog,
  DataTableShell,
  EmptyState,
  Field,
  ImagePreview,
  Input,
  LoadingRows,
  Modal,
  PageHeader,
  Select,
  StatusPill,
  Td,
  Textarea,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api, type AdminCategoryDetail } from "../lib/api";
import { formatDate } from "../lib/format";
import { PermissionGate } from "../lib/permissions";
import { blockTitle, reorderBlocks, toggleBlock, type BuilderState } from "./builder";

const createSchema = z.object({
  name: z.string().min(3, "At least 3 characters").max(140),
  slug: z
    .string()
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Lowercase letters, numbers and single hyphens")
    .optional()
    .or(z.literal("")),
});

type CreateForm = z.infer<typeof createSchema>;

function CreateCategoryModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: "", slug: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: CreateForm) =>
      api.createCategory({ name: values.name, slug: values.slug || undefined }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["admin-categories"] });
      toast.success("Category created as a draft.");
      onClose();
      navigate(`/categories/${result.id}`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not create the category."),
  });

  return (
    <Modal title="New category" onClose={onClose}>
      <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Name" htmlFor="cat-name" error={form.formState.errors.name?.message}>
          <Input id="cat-name" placeholder="Fresh Fruits" {...form.register("name")} />
        </Field>
        <Field
          label="Slug (optional)"
          htmlFor="cat-slug"
          error={form.formState.errors.slug?.message}
        >
          <Input id="cat-slug" placeholder="fresh-fruits" {...form.register("slug")} />
        </Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating…" : "Create draft"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function CategoryListPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["admin-categories"], queryFn: api.categories });
  const [creating, setCreating] = useState(false);
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<string[]>([]);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const categories = data ?? [];
  const allSelected =
    categories.length > 0 && categories.every((category) => selectedCategoryIds.includes(category.id));

  const deleteMutation = useMutation({
    mutationFn: (categoryIds: string[]) => api.deleteCategories(categoryIds),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["admin-categories"] });
      setSelectedCategoryIds([]);
      setConfirmingDelete(false);
      toast.success(`${result.count} categor${result.count === 1 ? "y" : "ies"} deleted.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete categories."),
  });

  function toggleCategory(categoryId: string) {
    setSelectedCategoryIds((current) =>
      current.includes(categoryId)
        ? current.filter((id) => id !== categoryId)
        : [...current, categoryId],
    );
  }

  function toggleAllCategories() {
    setSelectedCategoryIds(allSelected ? [] : categories.map((category) => category.id));
  }

  return (
    <div>
      <PageHeader
        title="Categories"
        description="One composition engine renders every category — no code per category."
        actions={
          <div className="flex gap-2">
            <PermissionGate permission="categories.edit">
              {selectedCategoryIds.length > 0 ? (
                <Button
                  variant="destructive"
                  onClick={() => setConfirmingDelete(true)}
                  disabled={deleteMutation.isPending}
                >
                  Delete selected ({selectedCategoryIds.length})
                </Button>
              ) : null}
            </PermissionGate>
            <PermissionGate permission="categories.create">
              <Button variant="primary" onClick={() => setCreating(true)}>
                New category
              </Button>
            </PermissionGate>
          </div>
        }
      />
      {creating ? <CreateCategoryModal onClose={() => setCreating(false)} /> : null}
      {confirmingDelete ? (
        <ConfirmDialog
          title={
            selectedCategoryIds.length === 1
              ? "Delete category"
              : `Delete ${selectedCategoryIds.length} categories`
          }
          description="Selected categories will be hidden from the storefront and removed from the active catalogue."
          confirmLabel={selectedCategoryIds.length === 1 ? "Delete category" : "Delete categories"}
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={() => deleteMutation.mutate(selectedCategoryIds)}
        />
      ) : null}

      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>
              <input
                type="checkbox"
                aria-label="Select all categories"
                checked={allSelected}
                onChange={toggleAllCategories}
              />
            </Th>
            <Th>Category</Th>
            <Th>Slug</Th>
            <Th>Products</Th>
            <Th>Visibility</Th>
            <Th>Status</Th>
            <Th>Updated</Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={7} />
        ) : (
          <tbody>
            {categories.map((category) => (
              <tr key={category.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <input
                    type="checkbox"
                    aria-label={`Select ${category.name}`}
                    checked={selectedCategoryIds.includes(category.id)}
                    onChange={() => toggleCategory(category.id)}
                  />
                </Td>
                <Td>
                  <Link
                    to={`/categories/${category.id}`}
                    className="flex min-w-56 items-center gap-3 font-medium text-brand hover:underline"
                  >
                    <ImagePreview
                      src={category.imageUrl}
                      alt={category.imageAlt}
                      label={category.name}
                      className="h-11 w-11"
                    />
                    <span>{category.name}</span>
                  </Link>
                </Td>
                <Td className="text-ink-muted">/{category.slug}</Td>
                <Td>{category.productCount}</Td>
                <Td className="text-ink-muted">{category.visibility}</Td>
                <Td>
                  <StatusPill status={category.status} />
                </Td>
                <Td>{formatDate(category.updatedAt)}</Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
    </div>
  );
}

function SortableBlockRow({
  block,
  selected,
  onSelect,
  onToggle,
}: {
  block: PublicPageBlock;
  selected: boolean;
  onSelect: () => void;
  onToggle: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: block.id,
  });
  const style = {
    transform: transform ? `translate3d(0, ${transform.y}px, 0)` : undefined,
    transition,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-2 rounded-sm border px-2 py-2 ${
        selected ? "border-brand bg-subtle/50" : "border-line bg-surface"
      } ${block.enabled ? "" : "opacity-50"}`}
    >
      <button
        type="button"
        aria-label={`Reorder ${blockTitle(block)}`}
        className="cursor-grab touch-none text-ink-muted"
        {...attributes}
        {...listeners}
      >
        <GripVertical size={15} />
      </button>
      <button
        type="button"
        onClick={onSelect}
        className="min-h-8 flex-1 truncate text-left text-sm text-ink"
      >
        {blockTitle(block)}
      </button>
      <button
        type="button"
        onClick={onToggle}
        aria-label={block.enabled ? `Hide ${blockTitle(block)}` : `Show ${blockTitle(block)}`}
        className="text-ink-muted hover:text-ink"
      >
        {block.enabled ? <Eye size={15} /> : <EyeOff size={15} />}
      </button>
    </li>
  );
}

function BlockPreview({ block }: { block: PublicPageBlock }) {
  if (!block.enabled) return null;
  switch (block.type) {
    case "hero":
      return (
        <div className="bg-brand px-5 py-8 text-ink-inverse">
          <p className="text-[10px] tracking-[0.14em] uppercase opacity-80">
            {block.props.eyebrow}
          </p>
          <p className="mt-2 font-display text-xl leading-tight">{block.props.heading}</p>
          <p className="mt-2 max-w-md text-xs opacity-90">{block.props.text}</p>
        </div>
      );
    case "category_collection":
      return (
        <div className="px-5 py-5">
          <p className="font-display text-base">{block.props.heading}</p>
          <div className="mt-2 grid grid-cols-4 gap-2">
            {block.props.categorySlugs.map((slug) => (
              <div key={slug} className="rounded-sm bg-subtle px-2 py-4 text-center text-[10px]">
                {slug}
              </div>
            ))}
          </div>
        </div>
      );
    case "product_collection":
      return (
        <div className="bg-canvas px-5 py-5">
          <p className="font-display text-base">{block.props.heading}</p>
          <div className="mt-2 grid grid-cols-5 gap-2">
            {block.props.productSlugs.slice(0, block.props.limit).map((slug) => (
              <div
                key={slug}
                className="h-14 rounded-sm border border-line bg-surface"
                title={slug}
              />
            ))}
          </div>
        </div>
      );
    case "farmer_story":
      return (
        <blockquote className="border-l-4 border-accent px-5 py-5 font-display text-sm italic">
          “{block.props.quote}”{" "}
          <cite className="mt-1 block text-xs not-italic">{block.props.attribution}</cite>
        </blockquote>
      );
    case "faq":
      return (
        <div className="px-5 py-5">
          <p className="font-display text-base">{block.props.heading}</p>
          <ul className="mt-2 space-y-1 text-xs text-ink-muted">
            {block.props.items.map((item) => (
              <li key={item.question}>• {item.question}</li>
            ))}
          </ul>
        </div>
      );
    case "rich_text":
      return (
        <div className="space-y-1 px-5 py-5 text-xs text-ink-muted">
          {block.props.paragraphs.map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
      );
    case "newsletter":
      return (
        <div className="bg-subtle px-5 py-5">
          <p className="font-display text-base">{block.props.heading}</p>
          <p className="mt-1 text-[10px] text-ink-muted">{block.props.consentText}</p>
        </div>
      );
  }
}

const settingsSchema = z.object({
  name: z.string().min(3, "At least 3 characters").max(140),
  slug: z
    .string()
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Lowercase letters, numbers and single hyphens only"),
  shortDescription: z.string().max(300),
  heroEyebrow: z.string().max(120),
  heroTitle: z.string().max(160),
  heroDescription: z.string().max(500),
  seasonLabel: z.string().max(80),
  visibility: z.enum(["public", "hidden", "private"]),
  heroImageUrl: z
    .string()
    .max(1000)
    .refine(
      (value) =>
        value === "" ||
        (value.startsWith("/") && !value.startsWith("//")) ||
        z.string().url().safeParse(value).success,
      "Enter a valid image URL",
    ),
  heroImageAlt: z.string().max(200),
});

type SettingsForm = z.infer<typeof settingsSchema>;

function CategorySettingsForm({
  category,
  onSave,
  saving,
}: {
  category: AdminCategoryDetail;
  onSave: (values: SettingsForm) => void;
  saving: boolean;
}) {
  const toast = useToast();
  const form = useForm<SettingsForm>({
    resolver: zodResolver(settingsSchema),
    values: {
      name: category.name,
      slug: category.slug,
      shortDescription: category.shortDescription,
      heroEyebrow: category.heroEyebrow,
      heroTitle: category.heroTitle,
      heroDescription: category.heroDescription,
      seasonLabel: category.seasonLabel,
      visibility: (["public", "hidden", "private"].includes(category.visibility)
        ? category.visibility
        : "public") as SettingsForm["visibility"],
      heroImageUrl: category.heroImageUrl,
      heroImageAlt: category.heroImageAlt,
    },
  });
  const watchedHeroImageUrl = form.watch("heroImageUrl");
  const watchedHeroImageAlt = form.watch("heroImageAlt");
  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadImage(file),
    onSuccess: (result) => {
      const heroImageAlt = form.getValues("heroImageAlt") || category.name;
      const nextValues = { ...form.getValues(), heroImageUrl: result.url, heroImageAlt };
      form.setValue("heroImageUrl", result.url, { shouldDirty: true, shouldValidate: true });
      form.setValue("heroImageAlt", heroImageAlt, { shouldDirty: true, shouldValidate: true });
      onSave(nextValues);
      toast.success("Hero image uploaded; saving thumbnail.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not upload image."),
  });

  return (
    <form className="max-w-2xl space-y-5" onSubmit={form.handleSubmit(onSave)}>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Name" htmlFor="c-name" error={form.formState.errors.name?.message}>
          <Input id="c-name" {...form.register("name")} />
        </Field>
        <Field label="Slug" htmlFor="c-slug" error={form.formState.errors.slug?.message}>
          <Input id="c-slug" {...form.register("slug")} />
        </Field>
      </div>
      <Field label="Short description" htmlFor="c-short">
        <Textarea id="c-short" {...form.register("shortDescription")} />
      </Field>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Hero eyebrow" htmlFor="c-eyebrow">
          <Input id="c-eyebrow" placeholder="In season now" {...form.register("heroEyebrow")} />
        </Field>
        <Field label="Season label" htmlFor="c-season">
          <Input id="c-season" placeholder="Summer" {...form.register("seasonLabel")} />
        </Field>
      </div>
      <Field label="Hero title" htmlFor="c-hero-title">
        <Input id="c-hero-title" {...form.register("heroTitle")} />
      </Field>
      <Field label="Hero description" htmlFor="c-hero-desc">
        <Textarea id="c-hero-desc" {...form.register("heroDescription")} />
      </Field>
      <Field
        label="Hero image URL"
        htmlFor="c-hero-image"
        error={form.formState.errors.heroImageUrl?.message}
      >
        <Input
          id="c-hero-image-upload"
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
          id="c-hero-image"
          placeholder={uploadMutation.isPending ? "Uploading image..." : "Hero image URL"}
          {...form.register("heroImageUrl")}
        />
        {watchedHeroImageUrl ? (
          <div className="mt-3">
            <ImagePreview
              src={watchedHeroImageUrl}
              alt={watchedHeroImageAlt}
              label={category.name}
              className="h-32 w-48"
            />
          </div>
        ) : null}
      </Field>
      <Field
        label="Hero image alt text"
        htmlFor="c-hero-image-alt"
        error={form.formState.errors.heroImageAlt?.message}
      >
        <Input
          id="c-hero-image-alt"
          placeholder="Seasonal organic fruit arranged on a table"
          {...form.register("heroImageAlt")}
        />
      </Field>
      <Field label="Visibility" htmlFor="c-visibility">
        <Select id="c-visibility" {...form.register("visibility")}>
          <option value="public">Public</option>
          <option value="hidden">Hidden</option>
          <option value="private">Private</option>
        </Select>
      </Field>
      <Button type="submit" variant="primary" disabled={saving || !form.formState.isDirty}>
        {saving ? "Saving…" : "Save settings"}
      </Button>
    </form>
  );
}

const EDITOR_TABS = ["Settings", "Layout"] as const;

export function CategoryEditorPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<(typeof EDITOR_TABS)[number]>("Settings");
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const {
    data: category,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["admin-category", id],
    queryFn: () => api.getCategory(id),
    retry: false,
  });

  const blocksQuery = useQuery({ queryKey: ["home-blocks"], queryFn: api.homeBlocks });
  const [state, setState] = useState<BuilderState>({
    blocks: [],
    selectedBlockId: null,
    dirty: false,
  });

  useEffect(() => {
    if (blocksQuery.data && state.blocks.length === 0) {
      setState({ blocks: blocksQuery.data, selectedBlockId: null, dirty: false });
    }
  }, [blocksQuery.data, state.blocks.length]);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const saveMutation = useMutation({
    mutationFn: (input: Record<string, unknown>) => api.updateCategory(id, input),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-category", id] }),
        queryClient.invalidateQueries({ queryKey: ["admin-categories"] }),
      ]);
      toast.success("Settings saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save settings."),
  });

  const publishMutation = useMutation({
    mutationFn: () => api.publishCategory(id),
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-category", id] }),
        queryClient.invalidateQueries({ queryKey: ["admin-categories"] }),
      ]);
      setState((current) => ({ ...current, dirty: false }));
      toast.success(`Published — version ${result.version} is now live.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not publish."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteCategory(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-categories"] });
      toast.success("Category deleted from active catalogue.");
      navigate("/categories");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete."),
  });

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setState((current) => reorderBlocks(current, String(active.id), String(over.id)));
    }
  }

  if (isLoading) return <p className="text-sm text-ink-muted">Loading category…</p>;
  if (isError || !category) return <EmptyState title="Category not found" />;

  return (
    <div>
      <PageHeader
        title={category.name}
        description={`/${category.slug}`}
        actions={
          <div className="flex items-center gap-2">
            <StatusPill status={category.status} />
            <PermissionGate permission="categories.edit">
              <Button
                variant="secondary"
                onClick={() => setConfirmingDelete(true)}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </Button>
            </PermissionGate>
            <PermissionGate
              permission="categories.publish"
              fallback={
                <Button disabled title="Requires categories.publish">
                  Publish
                </Button>
              }
            >
              <Button
                variant="primary"
                onClick={() => publishMutation.mutate()}
                disabled={publishMutation.isPending}
              >
                {publishMutation.isPending ? "Publishing…" : "Publish"}
              </Button>
            </PermissionGate>
          </div>
        }
      />
      {confirmingDelete ? (
        <ConfirmDialog
          title="Delete category"
          description={`${category.name} will be hidden from the storefront and removed from the active catalogue.`}
          confirmLabel="Delete category"
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={() => deleteMutation.mutate()}
        />
      ) : null}

      <div
        role="tablist"
        aria-label="Category editor sections"
        className="mb-5 flex gap-1 border-b border-line"
      >
        {EDITOR_TABS.map((entry) => (
          <button
            key={entry}
            role="tab"
            aria-selected={tab === entry}
            onClick={() => setTab(entry)}
            className={`min-h-9 px-3 text-sm ${
              tab === entry
                ? "border-b-2 border-brand font-medium text-brand"
                : "text-ink-muted hover:text-ink"
            }`}
          >
            {entry}
          </button>
        ))}
      </div>

      {tab === "Settings" ? (
        <CategorySettingsForm
          category={category}
          onSave={(values) => saveMutation.mutate(values)}
          saving={saveMutation.isPending}
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          <section aria-label="Page outline">
            <h2 className="mb-2 text-xs font-semibold tracking-wide text-ink-muted uppercase">
              Layout — drag or use arrow keys
            </h2>
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={state.blocks.map((block) => block.id)}
                strategy={verticalListSortingStrategy}
              >
                <ul className="space-y-1.5">
                  {state.blocks.map((block) => (
                    <SortableBlockRow
                      key={block.id}
                      block={block}
                      selected={state.selectedBlockId === block.id}
                      onSelect={() =>
                        setState((current) => ({ ...current, selectedBlockId: block.id }))
                      }
                      onToggle={() => setState((current) => toggleBlock(current, block.id))}
                    />
                  ))}
                </ul>
              </SortableContext>
            </DndContext>
          </section>

          <section aria-label="Live preview">
            <h2 className="mb-2 text-xs font-semibold tracking-wide text-ink-muted uppercase">
              Live preview
            </h2>
            <div className="overflow-hidden rounded-md border border-line bg-surface shadow-card">
              {state.blocks.filter((block) => block.enabled).length === 0 ? (
                <div className="px-5 py-10">
                  <EmptyState title="No visible blocks" hint="Enable at least one block." />
                </div>
              ) : (
                state.blocks.map((block) => <BlockPreview key={block.id} block={block} />)
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
