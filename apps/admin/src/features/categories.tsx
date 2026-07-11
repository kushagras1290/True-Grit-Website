/** Category list and editor. The Layout tab is the keyboard-accessible
 * block builder (dnd-kit) with a live preview column. */

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
import { useQuery } from "@tanstack/react-query";
import type { PublicPageBlock } from "@truegrit/contracts";
import { Eye, EyeOff, GripVertical } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import {
  Button,
  DataTableShell,
  EmptyState,
  LoadingRows,
  PageHeader,
  StatusPill,
  Td,
  Th,
} from "../components/ui";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";
import { PermissionGate } from "../lib/permissions";
import { blockTitle, reorderBlocks, toggleBlock, type BuilderState } from "./builder";

export function CategoryListPage() {
  const { data, isLoading } = useQuery({ queryKey: ["admin-categories"], queryFn: api.categories });

  return (
    <div>
      <PageHeader
        title="Categories"
        description="One composition engine renders every category — no code per category."
        actions={
          <PermissionGate permission="categories.create">
            <Button variant="primary">New category</Button>
          </PermissionGate>
        }
      />
      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>Name</Th>
            <Th>Slug</Th>
            <Th>Products</Th>
            <Th>Visibility</Th>
            <Th>Status</Th>
            <Th>Updated</Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={6} />
        ) : (
          <tbody>
            {(data ?? []).map((category) => (
              <tr key={category.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <Link to={`/categories/${category.id}`} className="font-medium text-brand hover:underline">
                    {category.name}
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
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: block.id });
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
      <button type="button" onClick={onSelect} className="min-h-8 flex-1 truncate text-left text-sm text-ink">
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
          <p className="text-[10px] tracking-[0.14em] uppercase opacity-80">{block.props.eyebrow}</p>
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
              <div key={slug} className="h-14 rounded-sm border border-line bg-surface" title={slug} />
            ))}
          </div>
        </div>
      );
    case "farmer_story":
      return (
        <blockquote className="border-l-4 border-accent px-5 py-5 font-display text-sm italic">
          “{block.props.quote}” <cite className="mt-1 block text-xs not-italic">{block.props.attribution}</cite>
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

export function CategoryEditorPage() {
  const { id = "" } = useParams();
  const categories = useQuery({ queryKey: ["admin-categories"], queryFn: api.categories });
  const category = (categories.data ?? []).find((entry) => entry.id === id);

  const blocksQuery = useQuery({ queryKey: ["home-blocks"], queryFn: api.homeBlocks });
  const [state, setState] = useState<BuilderState>({ blocks: [], selectedBlockId: null, dirty: false });
  const [publishState, setPublishState] = useState<"idle" | "published">("idle");

  useEffect(() => {
    if (blocksQuery.data && state.blocks.length === 0) {
      setState({ blocks: blocksQuery.data, selectedBlockId: null, dirty: false });
    }
  }, [blocksQuery.data, state.blocks.length]);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setState((current) => reorderBlocks(current, String(active.id), String(over.id)));
    }
  }

  if (categories.isLoading) return <p className="text-sm text-ink-muted">Loading category…</p>;
  if (!category) return <EmptyState title="Category not found" />;

  return (
    <div>
      <PageHeader
        title={category.name}
        description={`/${category.slug} · ${category.productCount} products resolved by rule`}
        actions={
          <>
            <span role="status" className="self-center text-sm text-ink-muted">
              {publishState === "published" ? "Published — new immutable version created" : state.dirty ? "Unsaved changes" : "Saved"}
            </span>
            <PermissionGate
              permission="categories.publish"
              fallback={<Button disabled title="Requires categories.publish">Publish</Button>}
            >
              <Button
                variant="primary"
                onClick={() => {
                  setPublishState("published");
                  setState((current) => ({ ...current, dirty: false }));
                }}
              >
                Publish
              </Button>
            </PermissionGate>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <section aria-label="Page outline">
          <h2 className="mb-2 text-xs font-semibold tracking-wide text-ink-muted uppercase">
            Layout — drag or use arrow keys
          </h2>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={state.blocks.map((block) => block.id)} strategy={verticalListSortingStrategy}>
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
                <EmptyState title="No visible blocks" hint="Enable at least one block to publish." />
              </div>
            ) : (
              state.blocks.map((block) => <BlockPreview key={block.id} block={block} />)
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
