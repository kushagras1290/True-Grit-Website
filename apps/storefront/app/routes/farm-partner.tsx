/**
 * `/farms/partner` — where a grower applies to supply the market.
 *
 * Open to everyone: no sign-in, no account. The three-section shape is
 * deliberate — contact first, because that is the only part we truly need;
 * then the farm's facts, which a grower can answer without paperwork; then the
 * long-form questions, which are optional except for the last one. Someone who
 * fills in only the required fields has still sent us something actionable.
 */

import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";

import type { Route } from "./+types/farm-partner";
import { Section } from "../components/catalogue";
import {
  FarmPartnershipError,
  farmPartnershipsEnabled,
  submitFarmPartnership,
} from "../lib/farm-partnerships";
import { useLocaleContext } from "../lib/i18n/context";
import { commerceLive } from "../lib/commerce";
import { seoMeta } from "../lib/seo";

const FIELD =
  "min-h-11 w-full rounded-sm border border-line bg-canvas px-3 text-sm text-ink" +
  " placeholder:text-ink-muted focus:border-brand focus:outline-none";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Partner with True Grit",
    description:
      "Organic growers and farming collectives: apply to supply the True Grit marketplace.",
    canonicalPath: "/farms/partner",
    indexing: "index",
  });
}

function Label({ children }: { children: React.ReactNode }) {
  return <span className="text-xs font-medium text-ink-muted">{children}</span>;
}

function Hint({ children }: { children: React.ReactNode }) {
  return <span className="block text-xs text-ink-muted">{children}</span>;
}

export default function FarmPartnerPage(_props: Route.ComponentProps) {
  const { t } = useLocaleContext();
  const [status, setStatus] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);
  // `null` = not asked yet. Rendering the form optimistically while the answer
  // is in flight beats a spinner: the overwhelming majority of the time intake
  // is open, and a form that appears late reads as a broken page.
  const [open, setOpen] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    farmPartnershipsEnabled().then((enabled) => {
      if (!cancelled) setOpen(enabled);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const text = (name: string): string => String(values.get(name) ?? "").trim();
    const optional = (name: string): string | undefined => text(name) || undefined;
    const year = text("establishedYear");

    setStatus("sending");
    setError(null);
    try {
      await submitFarmPartnership({
        contactName: text("contactName"),
        contactEmail: text("contactEmail"),
        contactPhone: text("contactPhone"),
        farmName: text("farmName"),
        region: text("region"),
        state: optional("state"),
        city: optional("city"),
        pincode: optional("pincode"),
        // Left undefined rather than NaN when blank — the API rejects a
        // non-integer year, and "I did not say" is a valid answer.
        establishedYear: year ? Number(year) : undefined,
        landAreaAcres: optional("landAreaAcres"),
        certification: optional("certification"),
        primaryProduce: optional("primaryProduce"),
        farmingPractices: optional("farmingPractices"),
        websiteUrl: optional("websiteUrl"),
        message: text("message"),
      });
      form.reset();
      setStatus("sent");
    } catch (caught) {
      setStatus("idle");
      // The API writes its validation messages for the applicant, so show them
      // rather than a generic failure that hides which field is wrong.
      setError(caught instanceof FarmPartnershipError ? caught.message : t("partner.failed"));
      if (caught instanceof FarmPartnershipError && caught.status === 403) setOpen(false);
    }
  }

  return (
    <>
      <header className="bg-brand text-ink-inverse">
        <div className="mx-auto max-w-[80rem] px-4 py-16 sm:px-6">
          <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-80">
            {t("partner.eyebrow")}
          </p>
          <h1 className="mt-3 max-w-2xl font-display text-4xl leading-tight">
            {t("partner.title")}
          </h1>
          <p className="mt-4 max-w-2xl text-sm opacity-90">{t("partner.intro")}</p>
        </div>
      </header>

      <Section>
        {open === false ? (
          <div className="max-w-2xl rounded-md border border-line bg-surface p-6">
            <h2 className="font-display text-xl text-ink">{t("partner.closedTitle")}</h2>
            <p className="mt-2 text-sm text-ink-muted">{t("partner.closedBody")}</p>
            <Link
              to="/contact"
              className="mt-5 inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
            >
              {t("contact.send")}
            </Link>
          </div>
        ) : status === "sent" ? (
          <div className="max-w-2xl rounded-md border border-line bg-subtle p-6">
            <h2 className="font-display text-xl text-brand">{t("partner.successTitle")}</h2>
            <p className="mt-2 text-sm text-ink">{t("partner.successBody")}</p>
            <Link
              to="/farms"
              className="mt-5 inline-flex min-h-11 items-center rounded-sm border border-line px-5 text-sm text-ink hover:bg-canvas"
            >
              {t("farms.heading")}
            </Link>
          </div>
        ) : (
          <form className="max-w-2xl space-y-8" onSubmit={handleSubmit}>
            {!commerceLive ? (
              <p className="rounded-sm border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
                {t("common.demoMode")}
              </p>
            ) : null}
            {error ? (
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
            ) : null}

            <fieldset className="space-y-4">
              <legend className="font-display text-lg text-ink">
                {t("partner.sectionContact")}
              </legend>
              <label className="block space-y-1">
                <Label>{t("partner.contactName")}</Label>
                <input
                  name="contactName"
                  required
                  minLength={2}
                  maxLength={160}
                  className={FIELD}
                />
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block space-y-1">
                  <Label>{t("partner.contactEmail")}</Label>
                  <input
                    name="contactEmail"
                    type="email"
                    required
                    maxLength={254}
                    className={FIELD}
                  />
                </label>
                <label className="block space-y-1">
                  <Label>{t("partner.contactPhone")}</Label>
                  <input
                    name="contactPhone"
                    type="tel"
                    required
                    maxLength={24}
                    autoComplete="tel"
                    className={FIELD}
                  />
                  <Hint>{t("partner.contactPhoneHint")}</Hint>
                </label>
              </div>
            </fieldset>

            <fieldset className="space-y-4">
              <legend className="font-display text-lg text-ink">{t("partner.sectionFarm")}</legend>
              <label className="block space-y-1">
                <Label>{t("partner.farmName")}</Label>
                <input name="farmName" required minLength={2} maxLength={200} className={FIELD} />
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block space-y-1">
                  <Label>{t("partner.region")}</Label>
                  <input name="region" required minLength={2} maxLength={160} className={FIELD} />
                </label>
                <label className="block space-y-1">
                  <Label>
                    {t("partner.state")}{" "}
                    <span className="normal-case">({t("common.optional")})</span>
                  </Label>
                  <input name="state" maxLength={120} className={FIELD} />
                </label>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <label className="block space-y-1">
                  <Label>
                    {t("partner.city")}{" "}
                    <span className="normal-case">({t("common.optional")})</span>
                  </Label>
                  <input name="city" maxLength={120} className={FIELD} />
                </label>
                <label className="block space-y-1">
                  <Label>
                    {t("partner.pincode")}{" "}
                    <span className="normal-case">({t("common.optional")})</span>
                  </Label>
                  <input name="pincode" maxLength={16} inputMode="numeric" className={FIELD} />
                </label>
                <label className="block space-y-1">
                  <Label>
                    {t("partner.establishedYear")}{" "}
                    <span className="normal-case">({t("common.optional")})</span>
                  </Label>
                  <input
                    name="establishedYear"
                    type="number"
                    min={1800}
                    max={2200}
                    step={1}
                    className={FIELD}
                  />
                </label>
              </div>
            </fieldset>

            <fieldset className="space-y-4">
              <legend className="font-display text-lg text-ink">{t("partner.sectionStory")}</legend>
              <label className="block space-y-1">
                <Label>
                  {t("partner.landArea")}{" "}
                  <span className="normal-case">({t("common.optional")})</span>
                </Label>
                <input name="landAreaAcres" maxLength={120} className={FIELD} />
                <Hint>{t("partner.landAreaHint")}</Hint>
              </label>
              <label className="block space-y-1">
                <Label>
                  {t("partner.certification")}{" "}
                  <span className="normal-case">({t("common.optional")})</span>
                </Label>
                <input name="certification" maxLength={400} className={FIELD} />
                <Hint>{t("partner.certificationHint")}</Hint>
              </label>
              <label className="block space-y-1">
                <Label>
                  {t("partner.primaryProduce")}{" "}
                  <span className="normal-case">({t("common.optional")})</span>
                </Label>
                <input name="primaryProduce" maxLength={400} className={FIELD} />
              </label>
              <label className="block space-y-1">
                <Label>
                  {t("partner.practices")}{" "}
                  <span className="normal-case">({t("common.optional")})</span>
                </Label>
                <textarea
                  name="farmingPractices"
                  maxLength={4000}
                  rows={4}
                  className={`${FIELD} py-3`}
                />
              </label>
              <label className="block space-y-1">
                <Label>
                  {t("partner.website")}{" "}
                  <span className="normal-case">({t("common.optional")})</span>
                </Label>
                <input
                  name="websiteUrl"
                  type="url"
                  maxLength={500}
                  placeholder="https://"
                  className={FIELD}
                />
              </label>
              <label className="block space-y-1">
                <Label>{t("partner.message")}</Label>
                <textarea
                  name="message"
                  required
                  minLength={20}
                  maxLength={4000}
                  rows={6}
                  className={`${FIELD} py-3`}
                />
                <Hint>{t("partner.messageHint")}</Hint>
              </label>
            </fieldset>

            <button
              type="submit"
              disabled={status === "sending"}
              className="inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:opacity-50"
            >
              {status === "sending" ? t("partner.submitting") : t("partner.submit")}
            </button>
          </form>
        )}
      </Section>
    </>
  );
}
