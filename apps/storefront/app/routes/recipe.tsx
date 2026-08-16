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
  loadProductsBySlugs,
  loadRecipe,
} from "../lib/catalogue.server";
import { useCart } from "../lib/cart";
import { resolveCountry } from "../lib/geo.server";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { mediaUrl } from "../lib/media";
import { productEffectivePrice } from "../lib/pricing";
import { breadcrumbJsonLd, recipeJsonLd, recipeStepAnchor, seoMeta } from "../lib/seo";
import { LocalizedText, useLocalizeFormat } from "../lib/i18n/localized-text";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const runtime = catalogueRuntime(context);
  const { locale } = resolveLocale(request);
  const recipe = await loadRecipe(params.slug, runtime, locale.code);
  if (!recipe) throw data("Recipe not found", { status: 404 });
  const country = resolveCountry(request);
  const ingredientSlugs = recipe.ingredients.flatMap((entry) => entry.productSlug ?? []);
  const blockProductSlugs = recipe.blocks.flatMap((block) =>
    block.type === "product_collection" ? block.props.productSlugs : [],
  );
  const [ingredientProducts, blockProducts, farms] = await Promise.all([
    // A batched summary fetch, not one product-detail request per ingredient
    // -- `leadVariantId` on the summary is enough to add a single-variant
    // ingredient straight to the cart (see `lib/pricing.ts`).
    loadProductsBySlugs(ingredientSlugs, country, runtime, locale.code),
    loadProductsBySlugs(blockProductSlugs, country, runtime, locale.code),
    loadFarms(runtime),
  ]);
  return { recipe, ingredientProducts, blockProducts, farms };
}

export function meta({ data: loaderData, matches }: Route.MetaArgs) {
  if (!loaderData) return seoMeta(null, matches);
  return [
    ...seoMeta(loaderData.recipe.seo, matches),
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
      dietaryTags: loaderData.recipe.dietaryTags,
      keywords: loaderData.recipe.seo.keywords,
      cuisine: loaderData.recipe.cuisine,
    }),
    breadcrumbJsonLd([
      { name: "Home", path: "/" },
      { name: "Recipes", path: "/recipes" },
      {
        name: loaderData.recipe.title,
        path: loaderData.recipe.seo.canonicalPath,
      },
    ]),
  ];
}

export default function RecipePage({ loaderData }: Route.ComponentProps) {
  const format = useLocalizeFormat();
  const { recipe, ingredientProducts, blockProducts, farms } = loaderData;
  const { add } = useCart();
  const [addedAll, setAddedAll] = useState(false);
  const blockData: BlockData = {
    productsBySlug: new Map(blockProducts.map((product) => [product.slug, product])),
    categoriesBySlug: new Map(),
    farmsBySlug: new Map(farms.map((farm) => [farm.slug, farm])),
    // Recipe body content is limited to `ContentBlock` -- `reviews_showcase`,
    // `promotion_banner` and `recommendations` never appear here.
    reviewsByBlockId: new Map(),
    promotionsByBlockId: new Map(),
    recommendationsByBlockId: new Map(),
  };

  const availableProducts = ingredientProducts.filter(
    (product) => product.availability !== "out_of_stock" && product.leadVariantId !== null,
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
        eyebrow={format("Prep {prep} min - cook {cook} min - serves {servings}", {
          prep: recipe.prepMinutes,
          cook: recipe.cookMinutes,
          servings: recipe.servings,
        })}
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
              <LocalizedText>Ingredients</LocalizedText>
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
                      add({
                        productSlug: product.slug,
                        productName: product.name,
                        variantId: product.leadVariantId!,
                        variantName: product.unitLabel,
                        unitMinor: productEffectivePrice(product).amountMinor,
                      });
                    }
                    setAddedAll(true);
                    setTimeout(() => setAddedAll(false), 2500);
                  }}
                  className="mt-5 min-h-11 w-full rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-90"
                >
                  <LocalizedText>Add available ingredients to basket</LocalizedText>
                </button>
                <p role="status" className="mt-2 min-h-5 text-sm text-success">
                  {addedAll
                    ? format("{count} ingredients added.", { count: availableProducts.length })
                    : ""}
                </p>
              </>
            ) : null}
          </aside>

          <div>
            <h2 className="text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
              <LocalizedText>Method</LocalizedText>
            </h2>
            <ol className="mt-3 space-y-5">
              {recipe.steps.map((step, index) => (
                // `id` is the target of the `HowToStep.url` emitted in the
                // recipe JSON-LD, so a step deep link from search results
                // scrolls to the instruction it names.
                <li key={index} id={recipeStepAnchor(index)} className="flex gap-4">
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
