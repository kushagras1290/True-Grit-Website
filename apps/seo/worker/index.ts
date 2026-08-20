/**
 * The SEO agent Worker.
 *
 * Two cron expressions, doing different jobs:
 *
 *   `0 3 * * *`      check whether a scheduled audit is due, once a day.
 *   every 5 minutes  advance whatever is queued or half-finished.
 *
 * (The five-minute expression is not written out here because a cron step
 * contains the sequence that would close this comment block.)
 *
 * Splitting them is what makes the crawl resumable. The daily trigger only
 * writes a row; all the actual work happens on the five-minute tick, which
 * crawls one batch and returns. A run of five hundred pages therefore spreads
 * across a handful of ticks and survives anything that kills a single
 * invocation, and a run queued by hand from the dashboard is picked up by the
 * same path within five minutes without the API needing a queue binding.
 *
 * The daily trigger firing does not mean a run gets queued every day --
 * `isScheduleDue` compares the dashboard's `seo.schedule_days` setting
 * against the last cron-queued run, so "every 3 days" or "weekly" is a
 * setting change, not a redeploy. See `crawl.ts` for that check.
 *
 * There is no `fetch` handler. The dashboard is served from this Worker's
 * static assets, and its data comes from the main API (`/v1/admin/seo/*`),
 * which already has the staff session and permission checks. Adding a second
 * authenticated API surface here would mean re-implementing session validation
 * against the same D1, which is exactly the kind of duplication that ends up
 * subtly wrong.
 */

import { enqueueRun, isEnabled, isScheduleDue, tick } from "./crawl";
import type { Env } from "./types";

const DAILY_CRON = "0 3 * * *";

export default {
  async scheduled(event: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    if (event.cron === DAILY_CRON) {
      // Queue only, and only when due. The tick that follows does the
      // crawling, so the daily trigger stays fast and cannot be the thing
      // that times out.
      ctx.waitUntil(
        (async () => {
          if (!(await isEnabled(env))) return;
          if (!(await isScheduleDue(env))) return;
          const runId = await enqueueRun(env, "cron");
          console.log(`seo.run_queued run=${runId} trigger=cron`);
        })(),
      );
      return;
    }

    ctx.waitUntil(
      tick(env).catch((error) => {
        // Rethrowing here would only mark the cron failed; the run itself has
        // already been recorded as failed by `tick`, which is what the
        // dashboard reads.
        console.error(`seo.tick_failed error=${String(error)}`);
      }),
    );
  },
} satisfies ExportedHandler<Env>;
