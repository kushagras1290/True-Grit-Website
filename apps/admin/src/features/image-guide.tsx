import { Check, Crop, FileImage, MoveHorizontal } from "lucide-react";

import { PageHeader } from "../components/ui";
import {
  IMAGE_SPECIFICATIONS,
  imageDimensions,
  safeAreaDimensions,
  type ImageSpecification,
  type ImageSpecificationGroup,
} from "../lib/image-specifications";

const GROUPS: readonly ImageSpecificationGroup[] = ["Banners", "Catalogue", "Brand"];

function FrameDiagram({ specification }: { specification: ImageSpecification }) {
  const safeWidth = `${(specification.safeArea.width / specification.width) * 100}%`;
  const safeHeight = `${(specification.safeArea.height / specification.height) * 100}%`;

  return (
    <div
      className="relative flex min-h-36 items-center justify-center overflow-hidden rounded-md border border-line-strong bg-subtle/60"
      style={{ aspectRatio: `${specification.width} / ${specification.height}` }}
      aria-label={`${specification.name}: ${imageDimensions(specification)} with a centred ${safeAreaDimensions(specification)} safe area`}
    >
      <span aria-hidden className="absolute inset-y-0 left-1/2 w-px bg-line" />
      <span aria-hidden className="absolute inset-x-0 top-1/2 h-px bg-line" />
      <div
        className="relative flex min-h-16 items-center justify-center border-2 border-dashed border-brand bg-surface/80 px-2 text-center"
        style={{ width: safeWidth, height: safeHeight }}
      >
        <span className="text-xs font-semibold text-brand">
          Safe area
          <span className="mt-0.5 block whitespace-nowrap font-normal text-ink-muted">
            {safeAreaDimensions(specification)}
          </span>
        </span>
      </div>
      <span className="absolute right-2 bottom-2 rounded-sm bg-ink/80 px-2 py-1 text-[11px] font-medium text-ink-inverse">
        {imageDimensions(specification)}
      </span>
    </div>
  );
}

function SpecificationCard({ specification }: { specification: ImageSpecification }) {
  return (
    <article className="rounded-md border border-line bg-surface p-5 shadow-card">
      <FrameDiagram specification={specification} />
      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-lg text-ink">{specification.name}</h3>
          <p className="mt-1 font-mono text-sm font-semibold text-brand">
            {imageDimensions(specification)}
          </p>
        </div>
        <span className="rounded-full bg-subtle px-2.5 py-1 text-xs font-medium text-brand">
          {specification.preferredFormat}
        </span>
      </div>

      <dl className="mt-4 space-y-3 text-sm">
        <div>
          <dt className="font-medium text-ink">Used for</dt>
          <dd className="mt-1 text-ink-muted">{specification.usedFor.join(" · ")}</dd>
        </div>
        <div>
          <dt className="font-medium text-ink">Centred safe area</dt>
          <dd className="mt-1 text-ink-muted">
            <span className="font-mono text-ink">{safeAreaDimensions(specification)}</span>
            {" — "}
            {specification.safeArea.note}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-ink">Crop behavior</dt>
          <dd className="mt-1 text-ink-muted">{specification.cropBehavior}</dd>
        </div>
        <div>
          <dt className="font-medium text-ink">File target</dt>
          <dd className="mt-1 text-ink-muted">{specification.targetFileSize}</dd>
        </div>
      </dl>
    </article>
  );
}

export function ImageGuidePage() {
  return (
    <div>
      <PageHeader
        title="Image size guide"
        description="Exact upload canvases and crop-safe areas for every image surface on the storefront."
      />

      <section className="grid gap-4 rounded-md border border-brand/25 bg-subtle/40 p-5 md:grid-cols-3">
        <div className="flex gap-3">
          <span className="mt-0.5 text-brand">
            <Crop size={19} aria-hidden />
          </span>
          <div>
            <h2 className="font-medium text-ink">Use the exact canvas</h2>
            <p className="mt-1 text-sm leading-6 text-ink-muted">
              Export at the listed width and height. Do not upload a 16:9 photo for a banner.
            </p>
          </div>
        </div>
        <div className="flex gap-3">
          <span className="mt-0.5 text-brand">
            <MoveHorizontal size={19} aria-hidden />
          </span>
          <div>
            <h2 className="font-medium text-ink">Respect the safe area</h2>
            <p className="mt-1 text-sm leading-6 text-ink-muted">
              Put essential subjects inside the dashed centre. Responsive crops may remove the
              edges.
            </p>
          </div>
        </div>
        <div className="flex gap-3">
          <span className="mt-0.5 text-brand">
            <FileImage size={19} aria-hidden />
          </span>
          <div>
            <h2 className="font-medium text-ink">Keep artwork clean</h2>
            <p className="mt-1 text-sm leading-6 text-ink-muted">
              Use WebP unless PNG is specified. Do not bake text or logos into photographs.
            </p>
          </div>
        </div>
      </section>

      <div className="mt-8 space-y-10">
        {GROUPS.map((group) => (
          <section key={group} aria-labelledby={`image-guide-${group.toLowerCase()}`}>
            <div className="mb-4 flex items-center gap-2">
              <Check size={18} className="text-brand" aria-hidden />
              <h2
                id={`image-guide-${group.toLowerCase()}`}
                className="font-display text-xl text-ink"
              >
                {group}
              </h2>
            </div>
            <div className="grid gap-5 xl:grid-cols-2">
              {IMAGE_SPECIFICATIONS.filter((entry) => entry.group === group).map((entry) => (
                <SpecificationCard key={entry.id} specification={entry} />
              ))}
            </div>
          </section>
        ))}
      </div>

      <section className="mt-10 rounded-md border border-line bg-surface p-5">
        <h2 className="font-display text-lg text-ink">Upload checklist</h2>
        <ul className="mt-3 grid gap-2 text-sm text-ink-muted md:grid-cols-2">
          <li>Canvas matches the exact pixel dimensions above.</li>
          <li>Main subject stays inside the centred safe area.</li>
          <li>No embedded True Grit logo, headline, button, or watermark.</li>
          <li>Image is sRGB and at or below the listed file-size target.</li>
          <li>Alt text describes the image rather than repeating the page title.</li>
          <li>Preview is checked on both a narrow phone and a desktop screen.</li>
        </ul>
        <p className="mt-4 text-xs text-ink-muted">
          The upload API accepts JPG, PNG, WebP, and GIF files up to 5 MB. These stricter targets
          keep storefront pages fast and visually predictable.
        </p>
      </section>
    </div>
  );
}
