/** Blog (articles) list and editor for the `blogger` role and reviewers.
 * Bloggers can draft, edit and submit for review; only `articles.approve`/
 * `.publish` holders can approve, request changes or publish — the review
 * gate is enforced by the API, this UI just hides actions a role can't use. */

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AdminArticleDetail } from "@truegrit/contracts";
import { useState } from "react";
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

function CreateArticleModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { title: "", slug: "", excerpt: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: CreateForm) =>
      api.createArticle({
        title: values.title,
        slug: values.slug || undefined,
        excerpt: values.excerpt || undefined,
      }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["admin-articles"] });
      toast.success("Article created as a draft.");
      onClose();
      navigate(`/blog/${result.id}`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not create the article."),
  });

  return (
    <Modal title="New blog post" onClose={onClose}>
      <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Title" htmlFor="art-title" error={form.formState.errors.title?.message}>
          <Input
            id="art-title"
            placeholder="The quiet revival of Indian millets"
            {...form.register("title")}
          />
        </Field>
        <Field
          label="Slug (optional)"
          htmlFor="art-slug"
          error={form.formState.errors.slug?.message}
        >
          <Input
            id="art-slug"
            placeholder="quiet-revival-of-indian-millets"
            {...form.register("slug")}
          />
        </Field>
        <Field label="Excerpt (optional)" htmlFor="art-excerpt">
          <Textarea id="art-excerpt" rows={2} {...form.register("excerpt")} />
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

const ARTICLES_PAGE_LIMIT = 25;

export function ArticleListPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const offset = (page - 1) * ARTICLES_PAGE_LIMIT;
  const { data, isLoading } = useQuery({
    queryKey: ["admin-articles", page, searchQuery],
    queryFn: () =>
      api.articles({ limit: ARTICLES_PAGE_LIMIT, offset, search: searchQuery || undefined }),
  });
  const [creating, setCreating] = useState(false);
  const articles = data ?? [];
  const [selectedArticleIds, setSelectedArticleIds] = useState<string[]>([]);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const allSelected =
    articles.length > 0 && articles.every((article) => selectedArticleIds.includes(article.id));

  // One-click enable/disable. The public API only serves published articles,
  // so a disabled post drops off /blog (and anywhere else it is linked)
  // immediately — no storefront redeploy involved.
  const toggleMutation = useMutation({
    mutationFn: ({ id, publish }: { id: string; publish: boolean }) =>
      publish ? api.publishArticle(id) : api.unpublishArticle(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-articles"] });
      toast.success("Article visibility updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update the article."),
  });

  const deleteMutation = useMutation({
    mutationFn: (articleIds: string[]) => api.deleteArticles(articleIds),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["admin-articles"] });
      setSelectedArticleIds([]);
      setConfirmingDelete(false);
      toast.success(`${result.count} post${result.count === 1 ? "" : "s"} deleted.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete the posts."),
  });

  function toggleArticle(articleId: string) {
    setSelectedArticleIds((current) =>
      current.includes(articleId)
        ? current.filter((id) => id !== articleId)
        : [...current, articleId],
    );
  }

  function toggleAllArticles() {
    setSelectedArticleIds(allSelected ? [] : articles.map((article) => article.id));
  }

  return (
    <div>
      <PageHeader
        title="Blog"
        description="Bloggers draft and submit posts here; reviewers approve and publish."
        actions={
          <div className="flex gap-2">
            <PermissionGate permission="articles.edit">
              {selectedArticleIds.length > 0 ? (
                <Button
                  variant="destructive"
                  onClick={() => setConfirmingDelete(true)}
                  disabled={deleteMutation.isPending}
                >
                  <T>Delete selected (</T>
                  {selectedArticleIds.length})
                </Button>
              ) : null}
            </PermissionGate>
            <PermissionGate permission="articles.create">
              <Button variant="primary" onClick={() => setCreating(true)}>
                <T>New post</T>
              </Button>
            </PermissionGate>
          </div>
        }
      />
      {creating ? <CreateArticleModal onClose={() => setCreating(false)} /> : null}
      {confirmingDelete ? (
        <ConfirmDialog
          title={
            selectedArticleIds.length === 1
              ? "Delete blog post"
              : `Delete ${selectedArticleIds.length} blog posts`
          }
          description="Selected posts will be removed from the blog and hidden from the admin list."
          confirmLabel={selectedArticleIds.length === 1 ? "Delete post" : "Delete posts"}
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={() => deleteMutation.mutate(selectedArticleIds)}
        />
      ) : null}

      <div className="mb-4 max-w-sm">
        <SearchBox
          value={searchQuery}
          onSearch={(value) => {
            setSearchQuery(value);
            setPage(1);
          }}
          placeholder="Search by title, slug or excerpt…"
          aria-label="Search blog posts"
        />
      </div>

      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>
              <input
                type="checkbox"
                aria-label="Select all blog posts"
                checked={allSelected}
                onChange={toggleAllArticles}
              />
            </Th>
            <Th>
              <T>Title</T>
            </Th>
            <Th>
              <T>Author</T>
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
          <LoadingRows columns={5} />
        ) : articles.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={5} className="px-3 py-8">
                <EmptyState
                  title="No blog posts yet"
                  hint="Create the first draft to get started."
                />
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {articles.map((article) => (
              <tr key={article.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <input
                    type="checkbox"
                    aria-label={`Select ${article.title}`}
                    checked={selectedArticleIds.includes(article.id)}
                    onChange={() => toggleArticle(article.id)}
                  />
                </Td>
                <Td>
                  <Link
                    to={`/blog/${article.id}`}
                    className="font-medium text-brand hover:underline"
                  >
                    {article.title}
                  </Link>
                  <span className="block text-xs text-ink-muted">
                    <T>/blog/</T>
                    {article.slug}
                  </span>
                </Td>
                <Td className="text-ink-muted">{article.authorName}</Td>
                <Td>
                  <div className="flex items-center gap-2">
                    <StatusPill status={article.status} />
                    {article.hasDraftChanges ? (
                      <span className="rounded-full bg-warning/10 px-2 py-0.5 text-xs text-warning">
                        <T>Draft changes pending</T>
                      </span>
                    ) : null}
                    {article.status === "published" || article.status === "unpublished" ? (
                      <PermissionGate permission="articles.publish">
                        <Button
                          variant="secondary"
                          disabled={toggleMutation.isPending}
                          onClick={() =>
                            toggleMutation.mutate({
                              id: article.id,
                              publish: article.status !== "published",
                            })
                          }
                        >
                          {article.status === "published" ? <T>{"Disable"}</T> : <T>{"Enable"}</T>}
                        </Button>
                      </PermissionGate>
                    ) : null}
                  </div>
                </Td>
                <Td>{formatDateTime(article.updatedAt)}</Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      <Pagination
        page={page}
        onPageChange={setPage}
        rowCount={articles.length}
        limit={ARTICLES_PAGE_LIMIT}
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
  readingMinutes: z.coerce.number().int().min(1).max(60),
  heroImageUrl: bannerImageUrlSchema,
  heroImageAlt: z.string().max(200),
  seoTitle: z.string().max(160),
  seoDescription: z.string().max(320),
  seoKeywords: z.string().max(500),
  canonicalUrl: z.string().max(300),
  indexingPolicy: z.enum(["index", "noindex"]),
  pullQuote: z.string().max(400),
  blocksJson: z.string().min(2),
});

type EditForm = z.infer<typeof editSchema>;

function articleDefaults(article: AdminArticleDetail): EditForm {
  return {
    title: article.title,
    slug: article.slug,
    excerpt: article.excerpt,
    readingMinutes: article.readingMinutes,
    heroImageUrl: article.heroImageUrl,
    heroImageAlt: article.heroImageAlt,
    seoTitle: article.seoTitle,
    seoDescription: article.seoDescription,
    seoKeywords: article.seoKeywords,
    canonicalUrl: article.canonicalUrl,
    indexingPolicy: article.indexingPolicy,
    pullQuote: article.pullQuote ?? "",
    blocksJson: JSON.stringify(article.blocks, null, 2),
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
        <Field label="What needs to change?" htmlFor="rc-note">
          <Textarea
            id="rc-note"
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

export function ArticleEditorPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const permissions = usePermissions();
  const [requestingChanges, setRequestingChanges] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const {
    data: article,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["admin-article", id],
    queryFn: () => api.getArticle(id),
    retry: false,
  });

  const form = useForm<EditForm>({
    resolver: zodResolver(editSchema),
    values: article ? articleDefaults(article) : undefined,
  });

  function invalidate() {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin-article", id] }),
      queryClient.invalidateQueries({ queryKey: ["admin-articles"] }),
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
      return api.updateArticle(id, {
        title: values.title,
        slug: values.slug,
        excerpt: values.excerpt,
        readingMinutes: values.readingMinutes,
        heroImageUrl: values.heroImageUrl,
        heroImageAlt: values.heroImageAlt,
        seoTitle: values.seoTitle,
        seoDescription: values.seoDescription,
        seoKeywords: values.seoKeywords,
        canonicalUrl: values.canonicalUrl,
        indexingPolicy: values.indexingPolicy,
        pullQuote: values.pullQuote || null,
        blocks,
      });
    },
    onSuccess: async () => {
      await invalidate();
      toast.success("Article saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the article."),
  });

  const submitMutation = useMutation({
    mutationFn: () => api.submitArticle(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Submitted for review.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not submit."),
  });

  const approveMutation = useMutation({
    mutationFn: () => api.approveArticle(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Approved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not approve."),
  });

  const requestChangesMutation = useMutation({
    mutationFn: (note: string) => api.requestArticleChanges(id, note),
    onSuccess: async () => {
      await invalidate();
      setRequestingChanges(false);
      toast.success("Sent back to draft.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not request changes."),
  });

  const publishMutation = useMutation({
    mutationFn: () => api.publishArticle(id),
    onSuccess: async (result) => {
      await invalidate();
      toast.success(`Published — version ${result.version} is now live.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not publish."),
  });

  const unpublishMutation = useMutation({
    mutationFn: () => api.unpublishArticle(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Unpublished.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not unpublish."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteArticle(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-articles"] });
      toast.success("Blog post deleted.");
      navigate("/blog");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete."),
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
        <T>Loading article…</T>
      </p>
    );
  if (isError || !article) return <EmptyState title="Article not found" />;

  const canEdit = permissions.has("articles.edit") || permissions.has("articles.approve");

  return (
    <div>
      <PageHeader
        title={article.title}
        description={`/blog/${article.slug}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={article.status} />
            <PermissionGate permission="articles.edit">
              <Button
                variant="secondary"
                onClick={() => setConfirmingDelete(true)}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? <T>{"Deleting..."}</T> : <T>{"Delete"}</T>}
              </Button>
            </PermissionGate>
            {article.status === "draft" ? (
              <PermissionGate permission="articles.edit">
                <Button onClick={() => submitMutation.mutate()} disabled={submitMutation.isPending}>
                  {submitMutation.isPending ? <T>{"Submitting…"}</T> : <T>{"Submit for review"}</T>}
                </Button>
              </PermissionGate>
            ) : null}
            {article.status === "in_review" ? (
              <PermissionGate permission="articles.approve">
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
            {article.status === "published" ? (
              <PermissionGate permission="articles.publish">
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
              permission="articles.publish"
              fallback={
                article.status === "published" ? null : (
                  <Button disabled title="Requires articles.publish">
                    <T>Publish</T>
                  </Button>
                )
              }
            >
              {article.status === "published" ? null : (
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
      {confirmingDelete ? (
        <ConfirmDialog
          title="Delete blog post"
          description={`${article.title} will be removed from the blog and hidden from the admin list.`}
          confirmLabel="Delete post"
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={() => deleteMutation.mutate()}
        />
      ) : null}

      <fieldset disabled={!canEdit} className="max-w-3xl space-y-5">
        <form
          className="space-y-5"
          onSubmit={form.handleSubmit((values) => saveMutation.mutate(values))}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Title" htmlFor="art-e-title" error={form.formState.errors.title?.message}>
              <Input id="art-e-title" {...form.register("title")} />
            </Field>
            <Field label="Slug" htmlFor="art-e-slug" error={form.formState.errors.slug?.message}>
              <Input id="art-e-slug" {...form.register("slug")} />
            </Field>
          </div>
          <Field label="Excerpt" htmlFor="art-e-excerpt">
            <Textarea id="art-e-excerpt" rows={2} {...form.register("excerpt")} />
          </Field>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Reading minutes" htmlFor="art-e-reading">
              <Input
                id="art-e-reading"
                type="number"
                min={1}
                max={60}
                {...form.register("readingMinutes")}
              />
            </Field>
            <Field label="Pull quote" htmlFor="art-e-quote">
              <Input id="art-e-quote" {...form.register("pullQuote")} />
            </Field>
          </div>

          <div className="border-t border-line pt-5">
            <h2 className="font-display text-lg text-ink">
              <T>Banner image</T>
            </h2>
            <p className="text-sm text-ink-muted">
              <T>Shown at the top of the post and as its thumbnail on the blog listing.</T>
            </p>
            <div className="mt-3 space-y-4">
              <Field
                label="Banner image URL"
                htmlFor="art-e-hero-url"
                error={form.formState.errors.heroImageUrl?.message}
              >
                <Input
                  id="art-e-hero-upload"
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
                  id="art-e-hero-url"
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
                      label={article.title || "Article banner"}
                      className="h-32 w-full max-w-md"
                    />
                  </div>
                ) : null}
              </Field>
              <Field label="Banner alt text" htmlFor="art-e-hero-alt">
                <Input
                  id="art-e-hero-alt"
                  placeholder="Describes the banner for screen readers"
                  {...form.register("heroImageAlt")}
                />
              </Field>
            </div>
          </div>

          <div className="border-t border-line pt-5">
            <h2 className="font-display text-lg text-ink">
              <T>SEO</T>
            </h2>
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              <Field label="SEO title" htmlFor="art-e-seo-title">
                <Input id="art-e-seo-title" {...form.register("seoTitle")} />
              </Field>
              <Field label="SEO keywords" htmlFor="art-e-seo-keywords">
                <Input id="art-e-seo-keywords" {...form.register("seoKeywords")} />
              </Field>
              <Field label="Canonical URL" htmlFor="art-e-canonical">
                <Input
                  id="art-e-canonical"
                  placeholder="/blog/my-post"
                  {...form.register("canonicalUrl")}
                />
              </Field>
              <Field label="Search indexing" htmlFor="art-e-indexing">
                <Select id="art-e-indexing" {...form.register("indexingPolicy")}>
                  <option value="index">
                    <T>Index</T>
                  </option>
                  <option value="noindex">
                    <T>No index</T>
                  </option>
                </Select>
              </Field>
            </div>
            <Field label="SEO description" htmlFor="art-e-seo-description">
              <Textarea id="art-e-seo-description" rows={3} {...form.register("seoDescription")} />
            </Field>
          </div>

          <div className="border-t border-line pt-5">
            <h2 className="font-display text-lg text-ink">
              <T>Body</T>
            </h2>
            <p className="text-sm text-ink-muted">
              <T>
                A list of content blocks (rich_text, product_collection, farmer_story, faq). Inside
                a rich_text paragraph, write
              </T>{" "}
              <code className="font-mono text-xs">
                <T>[label](/path)</T>
              </code>{" "}
              <T>to add a link — plain text and internal/external URLs only, never raw HTML.</T>
            </p>
            <Field
              label="Blocks JSON"
              htmlFor="art-e-blocks"
              error={form.formState.errors.blocksJson?.message}
            >
              <Textarea
                id="art-e-blocks"
                rows={18}
                className="font-mono text-xs"
                {...form.register("blocksJson")}
              />
            </Field>
          </div>

          <div className="flex items-center justify-between">
            <p className="text-xs text-ink-muted">
              <T>Last updated</T> {formatDateTime(article.updatedAt)}
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
