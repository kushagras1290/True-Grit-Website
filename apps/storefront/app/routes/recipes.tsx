import { Link } from "react-router";

import type { Route } from "./+types/recipes";
import { Section } from "../components/catalogue";
import { catalogueRuntime, loadRecipes } from "../lib/catalogue.server";
import { seoMeta } from "../lib/seo";

export async function loader({ context }: Route.LoaderArgs) {
  return { recipes: await loadRecipes(catalogueRuntime(context)) };
}

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Recipes",
    description: "Seasonal recipes built around the market — add the ingredients in one step.",
    canonicalPath: "/recipes",
    indexing: "index",
  });
}

export default function RecipesPage({ loaderData }: Route.ComponentProps) {
  return (
    <Section eyebrow="From the kitchen" heading="Cook with the season">
      <div className="mb-8 flex items-center justify-between gap-3">
        <p className="max-w-lg text-sm text-ink-muted">
          Got a recipe worth sharing? Pitch it to the community and our editors will review it.
        </p>
        <Link
          to="/recipes/submit"
          className="inline-flex min-h-11 shrink-0 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
        >
          Post a recipe
        </Link>
      </div>
      <div className="grid gap-6 md:grid-cols-3">
        {loaderData.recipes.map((recipe) => (
          <Link
            key={recipe.id}
            to={`/recipes/${recipe.slug}`}
            className="group rounded-md border border-line bg-surface p-6 shadow-card transition-transform duration-200 hover:-translate-y-0.5"
          >
            <p className="text-xs text-ink-muted">
              {recipe.prepMinutes + recipe.cookMinutes} min · serves {recipe.servings}
            </p>
            <h2 className="mt-2 font-display text-xl text-ink group-hover:text-brand">
              {recipe.title}
            </h2>
            <p className="mt-2 text-sm text-ink-muted">{recipe.excerpt}</p>
            <p className="mt-4 flex flex-wrap gap-1.5">
              {recipe.dietaryTags.map((tag) => (
                <span key={tag} className="rounded-full bg-subtle px-2.5 py-0.5 text-xs text-brand">
                  {tag}
                </span>
              ))}
            </p>
          </Link>
        ))}
      </div>
    </Section>
  );
}
