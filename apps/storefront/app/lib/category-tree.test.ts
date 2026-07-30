import type { CategorySummary } from "@truegrit/contracts";
import { describe, expect, it } from "vitest";

import { buildCategoryTree, findCategoryBranch } from "./category-tree";

function category(overrides: Partial<CategorySummary> & { id: string }): CategorySummary {
  return {
    name: overrides.id,
    slug: overrides.id,
    shortDescription: "",
    themeKey: "forest",
    seasonLabel: null,
    imageUrl: null,
    productCount: 0,
    parentId: null,
    level: 0,
    ...overrides,
  };
}

describe("buildCategoryTree", () => {
  it("groups subcategories under their department, preserving API order", () => {
    const tree = buildCategoryTree([
      category({ id: "fruits", productCount: 32 }),
      category({ id: "tropical", parentId: "fruits", level: 1, productCount: 8 }),
      category({ id: "citrus", parentId: "fruits", level: 1, productCount: 8 }),
      category({ id: "grains", productCount: 16 }),
      category({ id: "millets", parentId: "grains", level: 1, productCount: 16 }),
    ]);

    expect(tree.map((node) => node.department.id)).toEqual(["fruits", "grains"]);
    expect(tree[0]!.children.map((child) => child.id)).toEqual(["tropical", "citrus"]);
    expect(tree[1]!.children.map((child) => child.id)).toEqual(["millets"]);
  });

  it("does not double count products assigned to both a section and its department", () => {
    // Live data assigns each product twice, so the department's own count
    // already covers its sections. Summing both would report 64 for 32 products.
    const [node] = buildCategoryTree([
      category({ id: "fruits", productCount: 32 }),
      category({ id: "tropical", parentId: "fruits", level: 1, productCount: 8 }),
      category({ id: "citrus", parentId: "fruits", level: 1, productCount: 8 }),
      category({ id: "berries", parentId: "fruits", level: 1, productCount: 8 }),
      category({ id: "melons", parentId: "fruits", level: 1, productCount: 8 }),
    ]);
    expect(node!.totalProductCount).toBe(32);
  });

  it("falls back to the children's sum when products are only assigned at the leaf", () => {
    const [node] = buildCategoryTree([
      category({ id: "fruits", productCount: 0 }),
      category({ id: "tropical", parentId: "fruits", level: 1, productCount: 8 }),
      category({ id: "citrus", parentId: "fruits", level: 1, productCount: 5 }),
    ]);
    expect(node!.totalProductCount).toBe(13);
  });

  it("drops orphans rather than promoting them to departments", () => {
    // An editor un-publishing a department removes it from the API response
    // while its sections still name it as parent. Promoting them would leak a
    // hidden department's contents into the top-level rail.
    const tree = buildCategoryTree([
      category({ id: "grains" }),
      category({ id: "tropical", parentId: "unpublished-fruits", level: 1, productCount: 8 }),
    ]);
    expect(tree.map((node) => node.department.id)).toEqual(["grains"]);
  });

  it("ignores rows whose level and parent disagree", () => {
    const tree = buildCategoryTree([category({ id: "odd", level: 0, parentId: "somewhere" })]);
    expect(tree).toEqual([]);
  });

  it("keeps a childless department, so a flat catalogue still renders", () => {
    const tree = buildCategoryTree([category({ id: "oils", productCount: 4 })]);
    expect(tree).toHaveLength(1);
    expect(tree[0]!.children).toEqual([]);
    expect(tree[0]!.totalProductCount).toBe(4);
  });

  it("returns an empty tree for an empty catalogue", () => {
    expect(buildCategoryTree([])).toEqual([]);
  });
});

describe("findCategoryBranch", () => {
  const tree = buildCategoryTree([
    category({ id: "fruits", productCount: 32 }),
    category({ id: "tropical", parentId: "fruits", level: 1, productCount: 8 }),
    category({ id: "grains", productCount: 16 }),
  ]);

  it("resolves a department", () => {
    const branch = findCategoryBranch(tree, "fruits");
    expect(branch.department?.id).toBe("fruits");
    expect(branch.subcategory).toBeNull();
  });

  it("resolves a subcategory together with its department", () => {
    const branch = findCategoryBranch(tree, "tropical");
    expect(branch.department?.id).toBe("fruits");
    expect(branch.subcategory?.id).toBe("tropical");
  });

  it("resolves nothing for an unknown slug, so the page can show an empty state", () => {
    expect(findCategoryBranch(tree, "not-real")).toEqual({
      department: null,
      subcategory: null,
    });
  });

  it("treats no filter as no branch", () => {
    expect(findCategoryBranch(tree, null)).toEqual({ department: null, subcategory: null });
  });
});
