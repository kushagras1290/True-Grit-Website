import { useState } from "react";
import { data, Link } from "react-router";

import type { Route } from "./+types/recipe";
import { Breadcrumbs, Section } from "../components/catalogue";
import { loadProductsBySlugs, loadRecipe } from "../lib/catalogue.server";
import { useCart } from "../lib/cart";
import { seoMeta } from "../lib/seo";

export async function loader({ params }: Route.LoaderArgs) {
  const recipe = await loadRecipe(params.slug);
  if (!recipe) throw data("Recipe not found", { status: 404 });
  const productSlugs = recipe.ingredients.flatMap((entry) => entry.productSlug ?? []);
  return { recipe, ingredientProducts: loadProductsBySlugs(productSlugs) };
}

export function meta({ data: loaderData }: Route.MetaArgs) {
  return seoMeta(loaderData?.recipe.seo);
}

export default function RecipePage({ loaderData }: Route.ComponentProps) {
  const { recipe, ingredientProducts } = loaderData;
  const { add } = useCart();
  const [addedAll, setAddedAll] = useState(false);

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
      <header className="mx-auto max-w-[80rem] px-4 pt-6 sm:px-6">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
            Prep {recipe.prepMinutes} min · cook {recipe.cookMinutes} min · serves {recipe.servings}
          </p>
          <h1 className="mt-2 font-display text-3xl leading-tight text-ink md:text-4xl">
            {recipe.title}
          </h1>
          <p className="mt-3 text-base text-ink-muted">{recipe.excerpt}</p>
        </div>
      </header>

      <Section>
        <div className="grid gap-10 md:grid-cols-[1fr_2fr]">
          <aside>
            <h2 className="text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
              Ingredients
            </h2>
            <ul className="mt-3 space-y-2.5">
              {recipe.ingredients.map((ingredient) => (
                <li key={ingredient.label} className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="text-ink">
                    {ingredient.productSlug ? (
                      <Link to={`/product/${ingredient.productSlug}`} className="text-brand hover:underline">
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
            <h2 className="text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">Method</h2>
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
    </>
  );
}
