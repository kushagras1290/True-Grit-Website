/**
 * Canonical image canvases used by the storefront.
 *
 * Keep this list aligned with the "Image dimensions" table in the repository
 * README. The admin image guide renders these values directly so editors do
 * not have to infer dimensions from previews or CSS aspect ratios.
 */

export type ImageSpecificationGroup = "Banners" | "Catalogue" | "Brand";

export interface ImageSafeArea {
  width: number;
  height: number;
  note: string;
}

export interface ImageSpecification {
  id: string;
  group: ImageSpecificationGroup;
  name: string;
  width: number;
  height: number;
  safeArea: ImageSafeArea;
  usedFor: string[];
  cropBehavior: string;
  preferredFormat: "WebP" | "PNG";
  targetFileSize: string;
}

export const IMAGE_SPECIFICATIONS: readonly ImageSpecification[] = [
  {
    id: "home-page-banner",
    group: "Banners",
    name: "Homepage and landing-page banner",
    width: 1672,
    height: 464,
    safeArea: {
      width: 440,
      height: 400,
      note: "Keep the main subject inside this centred area so narrow mobile screens retain it.",
    },
    usedFor: [
      "Homepage carousel",
      "Blog landing page",
      "Recipes landing page",
      "Community landing page",
    ],
    cropBehavior: "Full canvas on desktop; the left and right edges crop progressively on mobile.",
    preferredFormat: "WebP",
    targetFileSize: "250 KB or less",
  },
  {
    id: "category-image",
    group: "Banners",
    name: "Category image",
    width: 1672,
    height: 464,
    safeArea: {
      width: 360,
      height: 400,
      note: "This stricter centre area survives the category page, 3:2 rail, and 4:5 feature tile.",
    },
    usedFor: ["Category page banner", "Category 3:2 rail tile", "Category 4:5 feature tile"],
    cropBehavior:
      "Tiles use object-cover and retain the centre; the 4:5 tile is the tightest crop.",
    preferredFormat: "WebP",
    targetFileSize: "250 KB or less",
  },
  {
    id: "content-hero",
    group: "Banners",
    name: "Article, recipe, and discussion image",
    width: 1672,
    height: 464,
    safeArea: {
      width: 440,
      height: 400,
      note: "Keep the subject centred here; listing cards use a wider 800 x 440 portion of the same image.",
    },
    usedFor: [
      "Article page and blog card",
      "Recipe page and recipe card",
      "Discussion page and community card",
    ],
    cropBehavior:
      "Page banners crop for mobile; 16:9 listing cards crop equal amounts from both sides.",
    preferredFormat: "WebP",
    targetFileSize: "250 KB or less",
  },
  {
    id: "product-image",
    group: "Catalogue",
    name: "Product image",
    width: 1200,
    height: 1200,
    safeArea: {
      width: 1080,
      height: 1080,
      note: "Leave at least 60 pixels of breathing room on every edge.",
    },
    usedFor: ["Product cards", "Product detail page", "Related-product grids"],
    cropBehavior: "Always displayed square with object-cover.",
    preferredFormat: "WebP",
    targetFileSize: "300 KB or less",
  },
  {
    id: "brand-mark",
    group: "Brand",
    name: "True Grit brand mark",
    width: 256,
    height: 256,
    safeArea: {
      width: 224,
      height: 224,
      note: "Keep 16 transparent or background pixels around the mark on every edge.",
    },
    usedFor: ["Storefront header", "Banner lockup", "Admin navigation", "Authentication screens"],
    cropBehavior: "Displayed as a 32 or 36 pixel square; never stretch or crop the source.",
    preferredFormat: "WebP",
    targetFileSize: "50 KB or less",
  },
  {
    id: "favicon",
    group: "Brand",
    name: "Browser favicon",
    width: 64,
    height: 64,
    safeArea: {
      width: 48,
      height: 48,
      note: "Keep the recognisable mark inside the centred 48-pixel square.",
    },
    usedFor: ["Browser tabs", "Bookmarks", "Browser shortcuts"],
    cropBehavior: "Browsers scale the square down; fine detail disappears at 16 pixels.",
    preferredFormat: "PNG",
    targetFileSize: "20 KB or less",
  },
] as const;

export function imageDimensions(specification: ImageSpecification): string {
  return `${specification.width} × ${specification.height} px`;
}

export function safeAreaDimensions(specification: ImageSpecification): string {
  return `${specification.safeArea.width} × ${specification.safeArea.height} px`;
}
