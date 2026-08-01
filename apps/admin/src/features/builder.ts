/** Pure page-builder state logic — tested independently of drag-and-drop UI. */

import type { PublicPageBlock } from "@truegrit/contracts";

export interface BuilderState {
  blocks: PublicPageBlock[];
  selectedBlockId: string | null;
  dirty: boolean;
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
    case "newsletter":
      return `Newsletter — ${block.props.heading}`;
    case "page_links":
      return `Page snippets — ${block.props.heading}`;
  }
}
