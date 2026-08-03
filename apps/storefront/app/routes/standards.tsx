import type { Route } from "./+types/standards";
import { CmsPage } from "../components/cms-page";
import { Section } from "../components/catalogue";
import { loadCmsRoute } from "../lib/cms-route.server";
import { seoMeta } from "../lib/seo";
import { LocalizedText } from "../lib/i18n/localized-text";

const fallbackSeo = {
  title: "Our standards",
  description:
    "What certified, traceable, responsibly sourced and fairly traded actually mean at True Grit.",
  canonicalPath: "/standards",
  indexing: "index",
} as const;
export async function loader({ request, context }: Route.LoaderArgs) {
  return loadCmsRoute("standards", request, context);
}

export function meta({ data }: Route.MetaArgs) {
  return seoMeta(data?.page?.seo ?? fallbackSeo);
}

const STANDARDS = [
  {
    title: "Certified, then verified",
    body: "Every partner farm holds a current NPOP or PGS-India certificate. We check the paperwork at onboarding, verify it with the issuing body, and re-check annually. Certificates and their validity windows are recorded against every product claim.",
  },
  {
    title: "Traceable to the lot",
    body: "Each lot is tagged at the farm with its harvest or milling date. That tag follows the food through quality checks, packing and dispatch — so the box on your counter can tell you exactly where it began.",
  },
  {
    title: "Responsibly sourced",
    body: "We buy against confirmed orders wherever the crop allows it, so fresh produce is harvested for you, not for a warehouse. Pantry goods are milled and pressed in small batches with their dates printed plainly.",
  },
  {
    title: "Fair partnerships",
    body: "Farms set their prices with us seasonally, before the harvest, and are paid on dispatch — not on our sell-through. Collectives like Anandvan share profits by contributed area.",
  },
];

export default function StandardsPage({ loaderData }: Route.ComponentProps) {
  if (loaderData.page) return <CmsPage page={loaderData.page} data={loaderData.blockData} />;
  return (
    <>
      <header className="bg-brand text-ink-inverse">
        <div className="mx-auto max-w-[80rem] px-4 py-16 sm:px-6">
          <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-80">
            <LocalizedText>Our standards</LocalizedText>
          </p>
          <h1 className="mt-3 max-w-2xl font-display text-4xl leading-tight">
            <LocalizedText>Trust is not a marketing word here. It is a checklist.</LocalizedText>
          </h1>
        </div>
      </header>
      <Section>
        <div className="mx-auto grid max-w-4xl gap-10 md:grid-cols-2">
          {STANDARDS.map((standard, index) => (
            <div key={standard.title}>
              <span className="font-display text-3xl text-accent">{index + 1}</span>
              <h2 className="mt-2 font-display text-xl text-ink">{standard.title}</h2>
              <p className="mt-2 text-base text-ink-muted">{standard.body}</p>
            </div>
          ))}
        </div>
      </Section>
    </>
  );
}
