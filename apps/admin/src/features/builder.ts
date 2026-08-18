/** Pure page-builder state logic — tested independently of drag-and-drop UI. */

import type { PublicPageBlock } from "@truegrit/contracts";

export interface BuilderState {
  blocks: PublicPageBlock[];
  selectedBlockId: string | null;
  dirty: boolean;
}

/** Move one ordered editor item to an exact zero-based position without
 * mutating the form state that React Hook Form is currently rendering. */
export function repositionItem<T>(items: T[], fromIndex: number, toIndex: number): T[] {
  if (
    fromIndex === toIndex ||
    fromIndex < 0 ||
    toIndex < 0 ||
    fromIndex >= items.length ||
    toIndex >= items.length
  ) {
    return items;
  }
  const reordered = [...items];
  const [moved] = reordered.splice(fromIndex, 1);
  reordered.splice(toIndex, 0, moved!);
  return reordered;
}

export function reorderBlocks(state: BuilderState, activeId: string, overId: string): BuilderState {
  if (activeId === overId) return state;
  const fromIndex = state.blocks.findIndex((block) => block.id === activeId);
  const toIndex = state.blocks.findIndex((block) => block.id === overId);
  if (fromIndex === -1 || toIndex === -1) return state;
  const blocks = [...state.blocks];
  const [moved] = blocks.splice(fromIndex, 1);
  blocks.splice(toIndex, 0, moved!);
  return { ...state, blocks, dirty: true };
}

export function toggleBlock(state: BuilderState, blockId: string): BuilderState {
  const blocks = state.blocks.map((block) =>
    block.id === blockId ? { ...block, enabled: !block.enabled } : block,
  );
  return { ...state, blocks, dirty: true };
}

export function blockTitle(block: PublicPageBlock): string {
  switch (block.type) {
    case "hero":
      return `Hero — ${block.props.heading}`;
    case "category_collection":
      return `Categories — ${block.props.heading}`;
    case "product_collection":
      return `Products — ${block.props.heading}`;
    case "farmer_story":
      return `Farmer story — ${block.props.attribution}`;
    case "faq":
      return `FAQ — ${block.props.heading}`;
    case "rich_text":
      return "Rich text";
    case "bullet_list":
      return block.props.heading ? `Bullet list — ${block.props.heading}` : "Bullet list";
    case "newsletter":
      return `Newsletter — ${block.props.heading}`;
    case "page_links":
      return `Page snippets — ${block.props.heading}`;
    case "reviews_showcase":
      return `Reviews — ${block.props.heading}`;
    case "promotion_banner":
      return "Promotions banner";
    case "recommendations":
      return `Recommended products — ${block.props.heading}`;
    case "image_banner":
      return `Image banner — ${block.props.imageAlt}`;
  }
}
