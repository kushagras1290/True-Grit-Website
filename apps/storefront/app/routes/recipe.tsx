import { useState } from "react";
import { data, Link } from "react-router";

import type { Route } from "./+types/recipe";
import { Breadcrumbs, Section } from "../components/catalogue";
import { CmsBlock, type BlockData } from "../components/blocks";
import { ContentComments } from "../components/content-comments";
import { PageBanner } from "../components/page-banner";
import {
  catalogueRuntime,
  loadFarms,
  loadProductDetailsBySlugs,
  loadProductsBySlugs,
  loadRecipe,
} from "../lib/catalogue.server";
import { useCart } from "../lib/cart";
import { resolveCountry } from "../lib/geo.server";
import { mediaUrl } from "../lib/media";
import { recipeJsonLd, seoMeta } from "../lib/seo";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const runtime = catalogueRuntime(context);
  const recipe = await loadRecipe(params.slug, runtime);
  if (!recipe) throw data("Recipe not found", { status: 404 });
  const country = resolveCountry(request);
  const ingredientSlugs = recipe.ingredients.flatMap((entry) => entry.productSlug ?? []);
  const blockProductSlugs = recipe.blocks.flatMap((block) =>
    block.type === "product_collection" ? block.props.productSlugs : [],
  );
  const [ingredientProducts, blockProducts, farms] = await Promise.all([
    loadProductDetailsBySlugs(ingredientSlugs, country, runtime),
    loadProductsBySlugs(blockProductSlugs, country, runtime),
    loadFarms(runtime),
  ]);
  return { recipe, ingredientProducts, blockProducts, farms };
}

export function meta({ data: loaderData }: Route.MetaArgs) {
  if (!loaderData) return seoMeta(null);
  return [
    ...seoMeta(loaderData.recipe.seo),
    recipeJsonLd({
      title: loaderData.recipe.title,
      excerpt: loaderData.recipe.excerpt,
      prepMinutes: loaderData.recipe.prepMinutes,
      cookMinutes: loaderData.recipe.cookMinutes,
      servings: loaderData.recipe.servings,
      ingredients: loaderData.recipe.ingredients,
      steps: loaderData.recipe.steps,
      canonicalPath: loaderData.recipe.seo.canonicalPath,
      imageUrl: mediaUrl(loaderData.recipe.heroImageUrl) ?? undefined,
    }),
  ];
}

export default function RecipePage({ loaderData }: Route.ComponentProps) {
  const { recipe, ingredientProducts, blockProducts, farms } = loaderData;
  const { add } = useCart();
  const [addedAll, setAddedAll] = useState(false);
  const blockData: BlockData = {
    productsBySlug: new Map(blockProducts.map((product) => [product.slug, product])),
    categoriesBySlug: new Map(),
    farmsBySlug: new Map(farms.map((farm) => [farm.slug, farm])),
  };

  const availableProducts = ingredientProducts.filter(
    (product) => product.availability !== "out_of_stock" && product.variants.length > 0,
  );

  return (
    <>
      <Breadcrumbs
        items={[
          { label: "Home", path: "/" },
          { label: "Recipes", path: "/recipes" },
          { label: recipe.title, path: `/recipes/${recipe.slug}` },
        ]}
      />
      <PageBanner
        imageUrl={recipe.heroImageUrl || "/banners/content/recipes-cook-with-purpose.webp"}
        imageAlt={recipe.heroImageAlt || recipe.title}
        eyebrow={`Prep ${recipe.prepMinutes} min - cook ${recipe.cookMinutes} min - serves ${recipe.servings}`}
        heading={recipe.title}
        description={recipe.excerpt}
      />

      {recipe.blocks.map((block) => (
        <CmsBlock key={block.id} block={block} data={blockData} />
      ))}

      <Section>
        <div className="grid gap-10 md:grid-cols-[1fr_2fr]">
          <aside>
            <h2 className="text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
              Ingredients
            </h2>
            <ul className="mt-3 space-y-2.5">
              {recipe.ingredients.map((ingredient) => (
                <li
                  key={ingredient.label}
                  className="flex items-baseline justify-between gap-3 text-sm"
                >
                  <span className="text-ink">
                    {ingredient.productSlug ? (
                      <Link
                        to={`/product/${ingredient.productSlug}`}
                        className="text-brand hover:underline"
                      >
                        {ingredient.label}
                      </Link>
                    ) : (
                      ingredient.label
                    )}
                  </span>
                  <span className="text-ink-muted">{ingredient.quantityText}</span>
                </li>
              ))}
            </ul>
            {availableProducts.length > 0 ? (
              <>
                <button
                  type="button"
                  onClick={() => {
                    for (const product of availableProducts) {
                      const variant = product.variants[0]!;
                      add({
                        productSlug: product.slug,
                        productName: product.name,
                        variantId: variant.id,
                        variantName: variant.name,
                        unitMinor: variant.saleMinor ?? variant.listMinor,
                      });
                    }
                    setAddedAll(true);
                    setTimeout(() => setAddedAll(false), 2500);
                  }}
                  className="mt-5 min-h-11 w-full rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-90"
                >
                  Add available ingredients to basket
                </button>
                <p role="status" className="mt-2 min-h-5 text-sm text-success">
                  {addedAll ? `${availableProducts.length} ingredients added.` : ""}
                </p>
              </>
            ) : null}
          </aside>

          <div>
            <h2 className="text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
              Method
            </h2>
            <ol className="mt-3 space-y-5">
              {recipe.steps.map((step, index) => (
                <li key={index} className="flex gap-4">
                  <span aria-hidden className="font-display text-2xl text-accent">
                    {index + 1}
                  </span>
                  <p className="pt-1 text-base text-ink">{step}</p>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </Section>

      <ContentComments contentType="recipe" slug={recipe.slug} />
    </>
  );
}
