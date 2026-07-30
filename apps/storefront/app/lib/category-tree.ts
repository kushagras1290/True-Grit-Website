/**
 * Groups the flat category list the public API returns into departments and
 * their subcategories.
 *
 * The API deliberately returns one flat, tree-ordered list rather than a nested
 * document, so a single request serves the shop sidebar, the department rail and
 * the homepage collections. Grouping is pure and cheap, so it runs in the route
 * loader and the result is serialized once per navigation.
 */

import type { CategorySummary, CategoryTreeNode } from "@truegrit/contracts";

const DEPARTMENT_LEVEL = 0;

/**
 * Departments in API order, each with its own subcategories.
 *
 * Only `level === 0` rows become departments. A subcategory whose parent is
 * absent from the list — unpublished, geo-excluded, or nested deeper than one
 * level — is dropped rather than promoted, so an editor un-publishing a
 * department never leaks its children into the top-level navigation.
 */
export function buildCategoryTree(categories: CategorySummary[]): CategoryTreeNode[] {
  const nodesById = new Map<string, CategoryTreeNode>();
  const ordered: CategoryTreeNode[] = [];

  for (const category of categories) {
    if (category.level !== DEPARTMENT_LEVEL || category.parentId !== null) continue;
    const node: CategoryTreeNode = {
      department: category,
      children: [],
      totalProductCount: category.productCount,
    };
    nodesById.set(category.id, node);
    ordered.push(node);
  }

  for (const category of categories) {
    if (category.parentId === null) continue;
    nodesById.get(category.parentId)?.children.push(category);
  }

  for (const node of ordered) {
    const childSum = node.children.reduce((sum, child) => sum + child.productCount, 0);
    // See `CategoryTreeNode.totalProductCount`: products are assigned to both
    // their section and their department, so taking the larger of the two
    // counts is correct under either assignment style and never double counts.
    node.totalProductCount = Math.max(node.department.productCount, childSum);
  }

  return ordered;
}

/**
 * The department and subcategory matching `slug`, or nulls when nothing
 * matches. Drives the shop page's "you are here" state: which sidebar branch is
 * expanded, and which heading the product canvas shows.
 */
export function findCategoryBranch(
  tree: CategoryTreeNode[],
  slug: string | null,
): { department: CategorySummary | null; subcategory: CategorySummary | null } {
  if (!slug) return { department: null, subcategory: null };
  for (const node of tree) {
    if (node.department.slug === slug) {
      return { department: node.department, subcategory: null };
    }
    const child = node.children.find((candidate) => candidate.slug === slug);
    if (child) return { department: node.department, subcategory: child };
  }
  return { department: null, subcategory: null };
}
