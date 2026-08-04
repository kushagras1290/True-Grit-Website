import { Link } from "react-router";

import type { Route } from "./+types/recipes";
import { Section } from "../components/catalogue";
import { PageBanner } from "../components/page-banner";
import { PageLinkPagination } from "../components/pagination";
import { catalogueRuntime, loadRecipes } from "../lib/catalogue.server";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { mediaUrl } from "../lib/media";
import { seoMeta } from "../lib/seo";
import { LocalizedText, useLocalizePlural } from "../lib/i18n/localized-text";

const RECIPE_PAGE_SIZE = 12;

export async function loader({ context, request }: Route.LoaderArgs) {
  const page = Math.max(1, Number(new URL(request.url).searchParams.get("page")) || 1);
  const { locale } = resolveLocale(request);
  return {
    page,
    pageSize: RECIPE_PAGE_SIZE,
    recipes: await loadRecipes(page, RECIPE_PAGE_SIZE, catalogueRuntime(context), locale.code),
  };
}

export function meta({ matches }: Route.MetaArgs) {
  return seoMeta(
    {
      title: "Recipes",
      description: "Seasonal recipes built around the market — add the ingredients in one step.",
      canonicalPath: "/recipes",
      indexing: "index",
    },
    matches,
  );
}

export default function RecipesPage({ loaderData }: Route.ComponentProps) {
  const plural = useLocalizePlural();
  return (
    <>
      <PageBanner
        imageUrl="/banners/content/recipes-cook-with-purpose.webp"
        imageAlt="Seasonal ingredients arranged in cooking order beside a ragi dosa"
        eyebrow="From the kitchen"
        heading="Recipes that earn a place in the weekly rotation"
        description="Clear methods, realistic timings and flexible ways to cook what is in season."
      />
      <Section eyebrow="Browse recipes" heading="Cook with the season">
        <div className="mb-8 flex items-center justify-between gap-3">
          <p className="max-w-lg text-sm text-ink-muted">
            <LocalizedText>
              Got a recipe worth sharing? Pitch it to the community and our editors will review it.
            </LocalizedText>
          </p>
          <Link
            to="/recipes/submit"
            className="inline-flex min-h-11 shrink-0 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
          >
            <LocalizedText>Post a recipe</LocalizedText>
          </Link>
        </div>
        <p className="mb-5 text-sm text-ink-muted" role="status">
          {plural("{count} recipe", "{count} recipes", loaderData.recipes.total)}
        </p>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {loaderData.recipes.items.map((recipe) => (
            <Link
              key={recipe.id}
              to={`/recipes/${recipe.slug}`}
              className="group overflow-hidden rounded-md border border-line bg-surface p-6 shadow-card transition-transform duration-200 hover:-translate-y-0.5"
            >
              {recipe.heroImageUrl ? (
                <img
                  src={mediaUrl(recipe.heroImageUrl)}
                  alt={recipe.heroImageAlt || ""}
                  loading="lazy"
                  className="-mx-6 -mt-6 mb-5 aspect-[16/9] w-[calc(100%+3rem)] max-w-none bg-subtle object-contain"
                />
              ) : null}
              <p className="text-xs text-ink-muted">
                {recipe.prepMinutes + recipe.cookMinutes}{" "}
                <LocalizedText>min · serves</LocalizedText> {recipe.servings}
              </p>
              <h2 className="mt-2 font-display text-xl text-ink group-hover:text-brand">
                {recipe.title}
              </h2>
              <p className="mt-2 text-sm text-ink-muted">{recipe.excerpt}</p>
              <p className="mt-4 flex flex-wrap gap-1.5">
                {recipe.dietaryTags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-subtle px-2.5 py-0.5 text-xs text-brand"
                  >
                    {tag}
                  </span>
                ))}
              </p>
            </Link>
          ))}
        </div>
        <PageLinkPagination
          page={loaderData.page}
          pageSize={loaderData.pageSize}
          total={loaderData.recipes.total}
        />
      </Section>
    </>
  );
}
