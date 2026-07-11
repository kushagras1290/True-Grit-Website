# True Grit design contract

This document is the implementation source of truth for visual decisions. Components request
semantic tokens (`--color-text-primary`), never raw values (`#202820`). Tokens live in
`packages/ui/src/tokens.css`.

## Brand principles

1. **Trust before hype.** No unsupported organic, origin, health, or certification claims.
2. **Editorial, not cluttered.** Typography, photography, whitespace, and hierarchy — not
   endless cards. Sections are separated by background shifts and rhythm, not boxes.
3. **Quietly confident.** Natural, transparent, modern, responsible, warm, premium.
4. **Not a generic green grocery template.** No leaf clip-art, loud discounts, glossy
   gradients, or card overload.

## Colour roles

| Token | Value | Use |
| --- | --- | --- |
| `--color-bg-canvas` | `#F7F4EB` warm organic ivory | Page background |
| `--color-bg-surface` | `#FFFFFF` | Cards, inputs, admin surfaces |
| `--color-bg-subtle` | `#DDE6D8` soft sage | Section shifts, chips |
| `--color-bg-inverse` | `#1A352B` | Footer, inverse sections |
| `--color-text-primary` | `#202820` botanical charcoal | Body text |
| `--color-text-secondary` | `#69736B` muted grey-green | Support text |
| `--color-brand-primary` | `#24483A` deep forest green | Primary actions, links |
| `--color-brand-accent` | `#B96F52` muted terracotta | Accents, seasonal labels |

All text/background pairs must pass WCAG 2.2 AA. Status is never communicated by colour alone.

## Typography

- **Display:** Fraunces (editorial serif) — page titles, section headings, pull quotes.
  Fallback Georgia. Tight leading (`--leading-tight`), no letterspacing.
- **Body/UI:** Inter (humanist sans) — navigation, controls, pricing, forms, admin. Fallback
  system stack. Body ≥ 16px on mobile.
- **Eyebrows:** uppercase sans, `--tracking-eyebrow` (0.14em), `--text-xs`, secondary colour.

Scale: 13 / 15 / 16 / 19 / 24 / 32 / 44 / 60 px (`--text-xs` … `--text-4xl`).

## Spacing, radius, shadow

- 4px base scale: 4, 8, 12, 16, 24, 32, 48, 72, 112 (`--space-1` … `--space-9`).
- Radius vocabulary is limited: `2px` (inputs/chips), `6px` (cards/dialogs), pill (badges).
- Two shadows only: `--shadow-card` (quiet lift) and `--shadow-overlay` (dialogs, drawers).

## Motion

`--duration-fast` 140ms, `--duration-base` 220ms, ease-out curve. All motion collapses to 0ms
under `prefers-reduced-motion`.

## Breakpoints

- Mobile-first. `sm` 640, `md` 768, `lg` 1024, `xl` 1280 (Tailwind defaults).
- Product grid: 2 columns mobile, 3 tablet, 4 desktop.
- Container max `80rem` with generous horizontal padding.

## Accessibility rules

- Visible keyboard focus everywhere (`--focus-ring`).
- 44px minimum touch targets on mobile.
- Semantic landmarks, logical heading order, skip-to-content link.
- Labels on every field; errors associated via `aria-describedby`.
- Empty `alt` for decorative imagery; meaningful `alt` written by editors for content imagery.

## Component states

Every interactive component defines: default, hover, active, focus-visible, disabled, loading.
Every data surface defines: loading, empty, error, and (admin) permission-denied states.
Optional page sections disappear entirely when data is absent — no empty placeholders.

## Photography

Natural light, honest produce, working farms. No stock-photo gloss, no saturated HDR. Images
always ship with intrinsic dimensions to prevent layout shift.
