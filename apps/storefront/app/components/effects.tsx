/**
 * Ambient effects and cursor trails.
 *
 * One canvas particle engine drives both: an ambient effect seeds particles
 * across the viewport and recycles them forever, while a cursor trail seeds
 * them at the pointer and lets them die. Sharing the loop means one rAF
 * callback, one resize listener and one set of shape routines rather than
 * thirty near-identical widgets.
 *
 * Non-negotiables, because decoration must never cost usability:
 *
 * * **`prefers-reduced-motion` wins.** Both layers render nothing at all for a
 *   visitor who asked for less motion — not "slower", nothing. Drifting
 *   particles behind body copy are exactly what that setting is for.
 * * **Never in the way.** Both canvases are `pointer-events: none`, fixed, and
 *   `aria-hidden`, so nothing here can swallow a click or reach a screen
 *   reader.
 * * **Trails need a real pointer.** A trail is skipped entirely on a coarse
 *   pointer (touch), where there is no cursor to trail and the listener would
 *   only burn battery.
 * * **Stops when unwatched.** The loop parks itself while the tab is hidden,
 *   so a backgrounded storefront is not quietly animating.
 *
 * Colour is owner-supplied and validated before it gets here
 * (`lib/theme.isValidThemeColor`); this file re-checks rather than assume,
 * because the value reaches `ctx.fillStyle`.
 */

import type { AmbientEffectKey, CursorTrailKey } from "@truegrit/contracts";
import { useEffect, useRef } from "react";

import { isValidThemeColor } from "../lib/theme";

type ShapeKey =
  | "circle"
  | "ring"
  | "snowflake"
  | "leaf"
  | "petal"
  | "streak"
  | "star"
  | "heart"
  | "confetti"
  | "sparkle"
  | "seed"
  | "blob"
  | "meteor";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  rotation: number;
  spin: number;
  opacity: number;
  /** 1 → 0. Immortal particles (ambient) stay at 1 and wrap instead. */
  life: number;
  decay: number;
  swayPhase: number;
  swayAmplitude: number;
  swaySpeed: number;
}

interface EffectSpec {
  shape: ShapeKey;
  /** Particles on screen at intensity 3, before the viewport-area scale. */
  count: number;
  size: [number, number];
  /** Vertical velocity in px/s. Negative rises. */
  speed: [number, number];
  drift: [number, number];
  spin: number;
  opacity: [number, number];
  swayAmplitude: number;
  swaySpeed: number;
  glow: boolean;
  /** Where a recycled particle re-enters from. */
  from: "top" | "bottom" | "anywhere";
  /** Softens fog and dust without a per-particle blur. */
  blur?: number;
}

const AMBIENT_SPECS: Record<Exclude<AmbientEffectKey, "none">, EffectSpec> = {
  snow: {
    shape: "snowflake",
    count: 70,
    size: [2, 6],
    speed: [18, 55],
    drift: [-12, 12],
    spin: 0.3,
    opacity: [0.45, 0.95],
    swayAmplitude: 22,
    swaySpeed: 0.5,
    glow: false,
    from: "top",
  },
  leaves: {
    shape: "leaf",
    count: 26,
    size: [8, 18],
    speed: [26, 62],
    drift: [-18, 18],
    spin: 1.5,
    opacity: [0.55, 0.95],
    swayAmplitude: 46,
    swaySpeed: 0.7,
    glow: false,
    from: "top",
  },
  petals: {
    shape: "petal",
    count: 45,
    size: [5, 11],
    speed: [20, 48],
    drift: [-14, 14],
    spin: 1.1,
    opacity: [0.5, 0.9],
    swayAmplitude: 38,
    swaySpeed: 0.8,
    glow: false,
    from: "top",
  },
  rain: {
    shape: "streak",
    count: 130,
    size: [7, 17],
    speed: [420, 760],
    drift: [-40, -14],
    spin: 0,
    opacity: [0.2, 0.5],
    swayAmplitude: 0,
    swaySpeed: 0,
    glow: false,
    from: "top",
  },
  fireflies: {
    shape: "circle",
    count: 34,
    size: [1.5, 3.5],
    speed: [-14, 14],
    drift: [-16, 16],
    spin: 0,
    opacity: [0.25, 0.95],
    swayAmplitude: 30,
    swaySpeed: 0.9,
    glow: true,
    from: "anywhere",
  },
  bubbles: {
    shape: "ring",
    count: 34,
    size: [4, 16],
    speed: [-70, -22],
    drift: [-8, 8],
    spin: 0,
    opacity: [0.25, 0.65],
    swayAmplitude: 26,
    swaySpeed: 0.6,
    glow: false,
    from: "bottom",
  },
  confetti: {
    shape: "confetti",
    count: 80,
    size: [4, 10],
    speed: [70, 190],
    drift: [-26, 26],
    spin: 4.5,
    opacity: [0.6, 1],
    swayAmplitude: 34,
    swaySpeed: 1.2,
    glow: false,
    from: "top",
  },
  stars: {
    shape: "star",
    count: 48,
    size: [3, 8],
    speed: [4, 16],
    drift: [-4, 4],
    spin: 0.25,
    opacity: [0.2, 1],
    swayAmplitude: 8,
    swaySpeed: 0.35,
    glow: true,
    from: "anywhere",
  },
  embers: {
    shape: "circle",
    count: 55,
    size: [1, 3.5],
    speed: [-120, -40],
    drift: [-14, 14],
    spin: 0,
    opacity: [0.3, 0.95],
    swayAmplitude: 24,
    swaySpeed: 1.1,
    glow: true,
    from: "bottom",
  },
  dust: {
    shape: "circle",
    count: 90,
    size: [0.8, 2.4],
    speed: [-9, 9],
    drift: [-9, 9],
    spin: 0,
    opacity: [0.15, 0.5],
    swayAmplitude: 16,
    swaySpeed: 0.3,
    glow: false,
    from: "anywhere",
    blur: 0.4,
  },
  seeds: {
    shape: "seed",
    count: 22,
    size: [5, 11],
    speed: [10, 34],
    drift: [-22, 22],
    spin: 0.8,
    opacity: [0.4, 0.85],
    swayAmplitude: 58,
    swaySpeed: 0.45,
    glow: false,
    from: "top",
  },
  hearts: {
    shape: "heart",
    count: 30,
    size: [6, 15],
    speed: [-72, -24],
    drift: [-10, 10],
    spin: 0.5,
    opacity: [0.35, 0.85],
    swayAmplitude: 30,
    swaySpeed: 0.8,
    glow: false,
    from: "bottom",
  },
  sparkles: {
    shape: "sparkle",
    count: 42,
    size: [3, 9],
    speed: [-6, 6],
    drift: [-6, 6],
    spin: 0.6,
    opacity: [0, 1],
    swayAmplitude: 10,
    swaySpeed: 1.6,
    glow: true,
    from: "anywhere",
  },
  fog: {
    shape: "blob",
    count: 9,
    size: [140, 340],
    speed: [-5, 5],
    drift: [-22, 22],
    spin: 0.05,
    opacity: [0.05, 0.16],
    swayAmplitude: 40,
    swaySpeed: 0.15,
    glow: false,
    from: "anywhere",
    blur: 3,
  },
  meteors: {
    shape: "meteor",
    count: 9,
    size: [40, 110],
    speed: [280, 620],
    drift: [-260, -120],
    spin: 0,
    opacity: [0.3, 0.85],
    swayAmplitude: 0,
    swaySpeed: 0,
    glow: true,
    from: "top",
  },
};

/** How a trail spawns: shape, how fast particles die, and where they drift. */
interface TrailSpec {
  shape: ShapeKey;
  /** Particles emitted per pointer sample. */
  perMove: number;
  size: [number, number];
  velocity: [number, number];
  /** Vertical bias: negative rises, positive falls, 0 drifts. */
  gravity: number;
  spin: number;
  opacity: [number, number];
  /** Lifetime in seconds. */
  life: [number, number];
  glow: boolean;
  /** Draws a tapering polyline through recent points instead of particles. */
  ribbon?: { width: number; smooth: boolean };
  /** Grows a particle over its life instead of shrinking it (rings). */
  expand?: number;
}

const TRAIL_SPECS: Record<Exclude<CursorTrailKey, "none">, TrailSpec> = {
  dots: {
    shape: "circle",
    perMove: 1,
    size: [3, 8],
    velocity: [0, 12],
    gravity: 0,
    spin: 0,
    opacity: [0.5, 0.9],
    life: [0.4, 0.8],
    glow: false,
  },
  ribbon: {
    shape: "circle",
    perMove: 0,
    size: [0, 0],
    velocity: [0, 0],
    gravity: 0,
    spin: 0,
    opacity: [0.8, 0.8],
    life: [0.35, 0.35],
    glow: false,
    ribbon: { width: 9, smooth: true },
  },
  comet: {
    shape: "circle",
    perMove: 2,
    size: [2, 7],
    velocity: [10, 45],
    gravity: 26,
    spin: 0,
    opacity: [0.45, 0.95],
    life: [0.35, 0.75],
    glow: true,
  },
  sparkle: {
    shape: "sparkle",
    perMove: 2,
    size: [4, 12],
    velocity: [14, 60],
    gravity: 34,
    spin: 3,
    opacity: [0.6, 1],
    life: [0.4, 0.9],
    glow: true,
  },
  bubbles: {
    shape: "ring",
    perMove: 1,
    size: [4, 13],
    velocity: [8, 34],
    gravity: -46,
    spin: 0,
    opacity: [0.3, 0.7],
    life: [0.7, 1.5],
    glow: false,
  },
  stars: {
    shape: "star",
    perMove: 1,
    size: [5, 13],
    velocity: [12, 55],
    gravity: 40,
    spin: 2.2,
    opacity: [0.5, 1],
    life: [0.5, 1.1],
    glow: true,
  },
  hearts: {
    shape: "heart",
    perMove: 1,
    size: [6, 14],
    velocity: [8, 30],
    gravity: -40,
    spin: 0.9,
    opacity: [0.45, 0.9],
    life: [0.7, 1.4],
    glow: false,
  },
  snow: {
    shape: "snowflake",
    perMove: 1,
    size: [2, 6],
    velocity: [6, 26],
    gravity: 44,
    spin: 1.2,
    opacity: [0.5, 0.95],
    life: [0.8, 1.6],
    glow: false,
  },
  glow: {
    shape: "blob",
    perMove: 1,
    size: [26, 46],
    velocity: [0, 8],
    gravity: 0,
    spin: 0,
    opacity: [0.12, 0.26],
    life: [0.25, 0.5],
    glow: false,
  },
  rings: {
    shape: "ring",
    perMove: 1,
    size: [5, 9],
    velocity: [0, 4],
    gravity: 0,
    spin: 0,
    opacity: [0.5, 0.85],
    life: [0.5, 0.9],
    glow: false,
    expand: 58,
  },
  paint: {
    shape: "circle",
    perMove: 0,
    size: [0, 0],
    velocity: [0, 0],
    gravity: 0,
    spin: 0,
    opacity: [0.85, 0.85],
    life: [1.1, 1.1],
    glow: false,
    ribbon: { width: 20, smooth: true },
  },
  fireflies: {
    shape: "circle",
    perMove: 1,
    size: [1.5, 4],
    velocity: [16, 54],
    gravity: -14,
    spin: 0,
    opacity: [0.4, 1],
    life: [0.8, 1.8],
    glow: true,
  },
  leaves: {
    shape: "leaf",
    perMove: 1,
    size: [7, 16],
    velocity: [10, 40],
    gravity: 52,
    spin: 2.4,
    opacity: [0.5, 0.95],
    life: [0.9, 1.8],
    glow: false,
  },
  petals: {
    shape: "petal",
    perMove: 1,
    size: [5, 11],
    velocity: [10, 38],
    gravity: 40,
    spin: 1.8,
    opacity: [0.45, 0.9],
    life: [0.9, 1.7],
    glow: false,
  },
  embers: {
    shape: "circle",
    perMove: 2,
    size: [1, 3.5],
    velocity: [14, 58],
    gravity: -70,
    spin: 0,
    opacity: [0.4, 1],
    life: [0.5, 1.1],
    glow: true,
  },
};

const FALLBACK_COLOR = "#ffffff";
/** Particle ceiling per layer. Above this the cost is visible and the effect
 *  is not: decoration is never worth a dropped frame on a mid-range phone. */
const MAX_PARTICLES = 320;
const TRAIL_POINTS = 26;

function randomBetween(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

function safeColor(color: string): string {
  return isValidThemeColor(color) ? color.trim() : FALLBACK_COLOR;
}

function drawShape(ctx: CanvasRenderingContext2D, shape: ShapeKey, size: number): void {
  switch (shape) {
    case "circle":
      ctx.beginPath();
      ctx.arc(0, 0, size, 0, Math.PI * 2);
      ctx.fill();
      return;

    case "ring":
      ctx.beginPath();
      ctx.arc(0, 0, size, 0, Math.PI * 2);
      ctx.lineWidth = Math.max(1, size * 0.16);
      ctx.stroke();
      return;

    case "snowflake": {
      ctx.beginPath();
      ctx.arc(0, 0, size * 0.55, 0, Math.PI * 2);
      ctx.fill();
      ctx.lineWidth = Math.max(0.6, size * 0.18);
      for (let arm = 0; arm < 3; arm += 1) {
        const angle = (arm * Math.PI) / 3;
        ctx.beginPath();
        ctx.moveTo(-Math.cos(angle) * size, -Math.sin(angle) * size);
        ctx.lineTo(Math.cos(angle) * size, Math.sin(angle) * size);
        ctx.stroke();
      }
      return;
    }

    case "leaf":
      ctx.beginPath();
      ctx.moveTo(0, -size);
      ctx.bezierCurveTo(size * 0.9, -size * 0.4, size * 0.7, size * 0.6, 0, size);
      ctx.bezierCurveTo(-size * 0.7, size * 0.6, -size * 0.9, -size * 0.4, 0, -size);
      ctx.fill();
      return;

    case "petal":
      ctx.beginPath();
      ctx.ellipse(0, 0, size * 0.55, size, 0, 0, Math.PI * 2);
      ctx.fill();
      return;

    case "streak":
      ctx.lineWidth = Math.max(0.8, size * 0.09);
      ctx.beginPath();
      ctx.moveTo(0, -size);
      ctx.lineTo(size * 0.12, size);
      ctx.stroke();
      return;

    case "star": {
      const points = 5;
      ctx.beginPath();
      for (let index = 0; index < points * 2; index += 1) {
        const radius = index % 2 === 0 ? size : size * 0.42;
        const angle = (index * Math.PI) / points - Math.PI / 2;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.fill();
      return;
    }

    case "heart":
      ctx.beginPath();
      ctx.moveTo(0, size * 0.75);
      ctx.bezierCurveTo(-size * 1.4, -size * 0.25, -size * 0.5, -size, 0, -size * 0.35);
      ctx.bezierCurveTo(size * 0.5, -size, size * 1.4, -size * 0.25, 0, size * 0.75);
      ctx.fill();
      return;

    case "confetti":
      ctx.fillRect(-size * 0.5, -size * 0.28, size, size * 0.56);
      return;

    case "sparkle": {
      // A four-point twinkle: two crossed tapered spikes.
      ctx.beginPath();
      ctx.moveTo(0, -size);
      ctx.quadraticCurveTo(size * 0.15, -size * 0.15, size, 0);
      ctx.quadraticCurveTo(size * 0.15, size * 0.15, 0, size);
      ctx.quadraticCurveTo(-size * 0.15, size * 0.15, -size, 0);
      ctx.quadraticCurveTo(-size * 0.15, -size * 0.15, 0, -size);
      ctx.fill();
      return;
    }

    case "seed": {
      ctx.beginPath();
      ctx.arc(0, size * 0.6, size * 0.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.lineWidth = Math.max(0.5, size * 0.08);
      for (let spoke = 0; spoke < 7; spoke += 1) {
        const angle = -Math.PI / 2 + (spoke - 3) * 0.28;
        ctx.beginPath();
        ctx.moveTo(0, size * 0.5);
        ctx.lineTo(Math.cos(angle) * size, size * 0.5 + Math.sin(angle) * size);
        ctx.stroke();
      }
      return;
    }

    case "blob":
      ctx.beginPath();
      ctx.ellipse(0, 0, size, size * 0.62, 0, 0, Math.PI * 2);
      ctx.fill();
      return;

    case "meteor": {
      ctx.lineWidth = Math.max(1, size * 0.03);
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(size * 0.42, -size);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(0, 0, Math.max(1, size * 0.035), 0, Math.PI * 2);
      ctx.fill();
      return;
    }
  }
}

/** Device pixel ratio, capped: a 3× phone gains nothing visible from a canvas
 *  of drifting dots and pays three times the fill cost for it. */
function pixelRatio(): number {
  return Math.min(window.devicePixelRatio || 1, 2);
}

function fitCanvas(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D): void {
  const ratio = pixelRatio();
  canvas.width = Math.floor(window.innerWidth * ratio);
  canvas.height = Math.floor(window.innerHeight * ratio);
  canvas.style.width = `${window.innerWidth}px`;
  canvas.style.height = `${window.innerHeight}px`;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

const OVERLAY_CLASS = "pointer-events-none fixed inset-0 z-40";

/**
 * Falling, rising and drifting particles behind the whole storefront.
 *
 * Particles are immortal and wrap: an ambient effect should look the same
 * after ten minutes as after ten seconds, and recycling avoids the allocation
 * churn of spawning and collecting thousands of objects.
 */
export function AmbientEffect({
  effect,
  color,
  intensity,
}: {
  effect: AmbientEffectKey;
  color: string;
  intensity: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (effect === "none") return undefined;
    if (prefersReducedMotion()) return undefined;
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    // Bound to a non-null local before the render loop closes over it: an
    // optional-chained context stays `| null` inside a callback and every
    // drawing call would need its own guard.
    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;
    // Re-bound: `draw` below is a hoisted function declaration, which TypeScript
    // treats as callable before the guard above ran, so the narrowing does not
    // survive into it. One alias beats a null check on every drawing call.
    const surface: CanvasRenderingContext2D = ctx;

    const spec = AMBIENT_SPECS[effect];
    const resolvedColor = safeColor(color);
    const scale = Math.min(2, Math.max(0.35, (window.innerWidth * window.innerHeight) / 1_500_000));
    const strength = Math.min(5, Math.max(1, Math.round(intensity))) / 3;
    const count = Math.min(MAX_PARTICLES, Math.round(spec.count * scale * strength));

    function seed(particle: Particle, initial: boolean): Particle {
      const height = window.innerHeight;
      const width = window.innerWidth;
      particle.x = Math.random() * width;
      if (initial || spec.from === "anywhere") particle.y = Math.random() * height;
      else if (spec.from === "top") particle.y = -randomBetween(20, height * 0.4);
      else particle.y = height + randomBetween(20, height * 0.4);
      particle.size = randomBetween(spec.size[0], spec.size[1]);
      particle.vy = randomBetween(spec.speed[0], spec.speed[1]);
      particle.vx = randomBetween(spec.drift[0], spec.drift[1]);
      particle.rotation = Math.random() * Math.PI * 2;
      particle.spin = randomBetween(-spec.spin, spec.spin);
      particle.opacity = randomBetween(spec.opacity[0], spec.opacity[1]);
      particle.life = 1;
      particle.decay = 0;
      particle.swayPhase = Math.random() * Math.PI * 2;
      particle.swayAmplitude = spec.swayAmplitude * randomBetween(0.4, 1);
      particle.swaySpeed = spec.swaySpeed * randomBetween(0.6, 1.4);
      return particle;
    }

    const particles: Particle[] = Array.from({ length: count }, () =>
      seed(
        {
          x: 0,
          y: 0,
          vx: 0,
          vy: 0,
          size: 1,
          rotation: 0,
          spin: 0,
          opacity: 1,
          life: 1,
          decay: 0,
          swayPhase: 0,
          swayAmplitude: 0,
          swaySpeed: 0,
        },
        true,
      ),
    );

    fitCanvas(canvas, ctx);
    const onResize = () => fitCanvas(canvas, ctx);
    window.addEventListener("resize", onResize);

    let frame = 0;
    let last = performance.now();
    // Twinkling effects modulate opacity rather than position, so they need
    // their own clock; reusing `last` would tie the pulse to frame timing.
    let elapsed = 0;

    function draw(now: number) {
      // Clamped: after a tab has been parked, `now - last` can be minutes, and
      // an unclamped step would teleport every particle off-screen at once.
      const delta = Math.min(0.05, (now - last) / 1000);
      last = now;
      elapsed += delta;

      const width = window.innerWidth;
      const height = window.innerHeight;
      surface.clearRect(0, 0, width, height);
      surface.fillStyle = resolvedColor;
      surface.strokeStyle = resolvedColor;
      surface.filter = spec.blur ? `blur(${spec.blur}px)` : "none";
      surface.shadowBlur = 0;

      for (const particle of particles) {
        particle.swayPhase += particle.swaySpeed * delta;
        particle.y += particle.vy * delta;
        particle.x += (particle.vx + Math.cos(particle.swayPhase) * particle.swayAmplitude) * delta;
        particle.rotation += particle.spin * delta;

        if (
          particle.y > height + 120 ||
          particle.y < -120 ||
          particle.x > width + 160 ||
          particle.x < -160
        ) {
          seed(particle, false);
          continue;
        }

        const twinkle =
          spec.shape === "sparkle" || spec.shape === "star" || spec.glow
            ? 0.55 + 0.45 * Math.sin(elapsed * 2 * particle.swaySpeed + particle.swayPhase)
            : 1;

        surface.save();
        surface.globalAlpha = Math.max(0, Math.min(1, particle.opacity * twinkle));
        if (spec.glow) {
          surface.shadowBlur = particle.size * 3;
          surface.shadowColor = resolvedColor;
        }
        surface.translate(particle.x, particle.y);
        if (particle.rotation) surface.rotate(particle.rotation);
        drawShape(surface, spec.shape, particle.size);
        surface.restore();
      }

      surface.filter = "none";
      frame = window.requestAnimationFrame(draw);
    }

    function start() {
      if (frame) return;
      last = performance.now();
      frame = window.requestAnimationFrame(draw);
    }
    function stop() {
      if (!frame) return;
      window.cancelAnimationFrame(frame);
      frame = 0;
    }
    function onVisibility() {
      if (document.hidden) stop();
      else start();
    }

    document.addEventListener("visibilitychange", onVisibility);
    start();

    return () => {
      stop();
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [effect, color, intensity]);

  if (effect === "none") return null;
  return <canvas ref={canvasRef} aria-hidden className={OVERLAY_CLASS} />;
}

interface TrailPoint {
  x: number;
  y: number;
  born: number;
}

/**
 * A particle or ribbon trail following the pointer.
 *
 * Skipped entirely on a coarse pointer: there is no cursor to trail on a
 * touchscreen, and the listener would only cost battery.
 */
export function CursorTrail({
  trail,
  color,
  hideNativeCursor,
}: {
  trail: CursorTrailKey;
  color: string;
  hideNativeCursor: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (trail === "none") return undefined;
    if (prefersReducedMotion()) return undefined;
    if (window.matchMedia?.("(pointer: coarse)").matches) return undefined;
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    // Bound to a non-null local before the render loop closes over it: an
    // optional-chained context stays `| null` inside a callback and every
    // drawing call would need its own guard.
    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;
    // Re-bound: `draw` below is a hoisted function declaration, which TypeScript
    // treats as callable before the guard above ran, so the narrowing does not
    // survive into it. One alias beats a null check on every drawing call.
    const surface: CanvasRenderingContext2D = ctx;

    const spec = TRAIL_SPECS[trail];
    const resolvedColor = safeColor(color);
    const particles: Particle[] = [];
    const points: TrailPoint[] = [];
    let pointerX = 0;
    let pointerY = 0;
    let pointerSeen = false;

    // Hiding the pointer is opt-in and only ever applied here, so switching the
    // trail off can never leave a visitor without a cursor.
    if (hideNativeCursor) document.documentElement.classList.add("cursor-trail-only");

    fitCanvas(canvas, ctx);
    const onResize = () => fitCanvas(canvas, ctx);

    function spawn(x: number, y: number) {
      for (let index = 0; index < spec.perMove; index += 1) {
        if (particles.length >= MAX_PARTICLES) break;
        const angle = Math.random() * Math.PI * 2;
        const speed = randomBetween(spec.velocity[0], spec.velocity[1]);
        const life = randomBetween(spec.life[0], spec.life[1]);
        particles.push({
          x,
          y,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          size: randomBetween(spec.size[0], spec.size[1]),
          rotation: Math.random() * Math.PI * 2,
          spin: randomBetween(-spec.spin, spec.spin),
          opacity: randomBetween(spec.opacity[0], spec.opacity[1]),
          life: 1,
          decay: 1 / life,
          swayPhase: 0,
          swayAmplitude: 0,
          swaySpeed: 0,
        });
      }
    }

    function onPointerMove(event: PointerEvent) {
      pointerX = event.clientX;
      pointerY = event.clientY;
      pointerSeen = true;
      if (spec.ribbon) {
        points.push({ x: pointerX, y: pointerY, born: performance.now() });
        if (points.length > TRAIL_POINTS) points.shift();
      }
      spawn(pointerX, pointerY);
    }

    let frame = 0;
    let last = performance.now();

    function draw(now: number) {
      const delta = Math.min(0.05, (now - last) / 1000);
      last = now;

      surface.clearRect(0, 0, window.innerWidth, window.innerHeight);
      surface.fillStyle = resolvedColor;
      surface.strokeStyle = resolvedColor;

      if (spec.ribbon) {
        const maxAge = spec.life[0] * 1000;
        while (points.length > 0 && now - points[0]!.born > maxAge) points.shift();
        surface.lineCap = "round";
        surface.lineJoin = "round";
        for (let index = 1; index < points.length; index += 1) {
          const from = points[index - 1]!;
          const to = points[index]!;
          const age = (now - to.born) / maxAge;
          const taper = index / points.length;
          surface.globalAlpha = Math.max(0, spec.opacity[1] * (1 - age) * taper);
          surface.lineWidth = Math.max(0.5, spec.ribbon.width * taper);
          surface.beginPath();
          surface.moveTo(from.x, from.y);
          if (spec.ribbon.smooth) {
            surface.quadraticCurveTo(from.x, from.y, (from.x + to.x) / 2, (from.y + to.y) / 2);
          }
          surface.lineTo(to.x, to.y);
          surface.stroke();
        }
        surface.globalAlpha = 1;
      }

      for (let index = particles.length - 1; index >= 0; index -= 1) {
        const particle = particles[index]!;
        particle.life -= particle.decay * delta;
        if (particle.life <= 0) {
          particles.splice(index, 1);
          continue;
        }
        particle.vy += spec.gravity * delta;
        particle.x += particle.vx * delta;
        particle.y += particle.vy * delta;
        particle.rotation += particle.spin * delta;

        const size = spec.expand
          ? particle.size + spec.expand * (1 - particle.life)
          : particle.size * particle.life;

        surface.save();
        surface.globalAlpha = Math.max(0, Math.min(1, particle.opacity * particle.life));
        if (spec.glow) {
          surface.shadowBlur = particle.size * 3;
          surface.shadowColor = resolvedColor;
        }
        surface.translate(particle.x, particle.y);
        if (particle.rotation) surface.rotate(particle.rotation);
        drawShape(surface, spec.shape, Math.max(0.2, size));
        surface.restore();
      }

      // The cursor's own head, so the pointer still reads as a pointer when the
      // native one is hidden. Without it, "hide the cursor" means "lose the
      // cursor" the moment the visitor stops moving.
      if (hideNativeCursor && pointerSeen && !spec.ribbon) {
        surface.save();
        surface.globalAlpha = 0.9;
        surface.translate(pointerX, pointerY);
        drawShape(surface, "circle", 4);
        surface.restore();
      }

      frame = window.requestAnimationFrame(draw);
    }

    function start() {
      if (frame) return;
      last = performance.now();
      frame = window.requestAnimationFrame(draw);
    }
    function stop() {
      if (!frame) return;
      window.cancelAnimationFrame(frame);
      frame = 0;
    }
    function onVisibility() {
      if (document.hidden) {
        stop();
        particles.length = 0;
        points.length = 0;
      } else {
        start();
      }
    }

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", onVisibility);
    start();

    return () => {
      stop();
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
      document.documentElement.classList.remove("cursor-trail-only");
    };
  }, [trail, color, hideNativeCursor]);

  if (trail === "none") return null;
  return <canvas ref={canvasRef} aria-hidden className={`${OVERLAY_CLASS} z-50`} />;
}
