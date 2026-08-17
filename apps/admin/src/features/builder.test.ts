import { homePage } from "@truegrit/contracts/fixtures";
import { describe, expect, it } from "vitest";

import {
  blockTitle,
  reorderBlocks,
  repositionItem,
  toggleBlock,
  type BuilderState,
} from "./builder";

function initialState(): BuilderState {
  return { blocks: structuredClone(homePage.blocks), selectedBlockId: null, dirty: false };
}

describe("reorderBlocks", () => {
  it("moves a block to the target position and marks state dirty", () => {
    const state = initialState();
    const [first, second] = state.blocks;
    const next = reorderBlocks(state, first!.id, second!.id);
    expect(next.blocks[0]!.id).toBe(second!.id);
    expect(next.blocks[1]!.id).toBe(first!.id);
    expect(next.dirty).toBe(true);
    // Original state is untouched.
    expect(state.blocks[0]!.id).toBe(first!.id);
  });

  it("is a no-op for unknown ids or self-drops", () => {
    const state = initialState();
    expect(reorderBlocks(state, "missing", state.blocks[0]!.id)).toBe(state);
    expect(reorderBlocks(state, state.blocks[0]!.id, state.blocks[0]!.id)).toBe(state);
  });

  it("preserves the full block set through arbitrary reorders", () => {
    let state = initialState();
    const ids = state.blocks.map((block) => block.id);
    state = reorderBlocks(state, ids[0]!, ids[4]!);
    state = reorderBlocks(state, ids[3]!, ids[1]!);
    expect(new Set(state.blocks.map((block) => block.id))).toEqual(new Set(ids));
  });
});

describe("toggleBlock", () => {
  it("flips enabled without touching other blocks", () => {
    const state = initialState();
    const target = state.blocks[2]!;
    const next = toggleBlock(state, target.id);
    expect(next.blocks[2]!.enabled).toBe(!target.enabled);
    expect(next.blocks[0]!.enabled).toBe(state.blocks[0]!.enabled);
    expect(next.dirty).toBe(true);
  });
});

describe("repositionItem", () => {
  it("can promote the third carousel slide to the first position", () => {
    const slides = ["first", "second", "third", "fourth"];
    const reordered = repositionItem(slides, 2, 0);
    expect(reordered).toEqual(["third", "first", "second", "fourth"]);
    expect(slides).toEqual(["first", "second", "third", "fourth"]);
  });

  it("is a no-op for an invalid or unchanged position", () => {
    const slides = ["first", "second"];
    expect(repositionItem(slides, 0, 0)).toBe(slides);
    expect(repositionItem(slides, 4, 0)).toBe(slides);
  });
});

describe("blockTitle", () => {
  it("labels every known block type", () => {
    for (const block of initialState().blocks) {
      expect(blockTitle(block)).toBeTruthy();
    }
  });
});
