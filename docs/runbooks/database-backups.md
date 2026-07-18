# Database backup and restore runbook

D1 database: `truegrit-dev` (binding `DB`, see `apps/api/wrangler.jsonc`). `truegrit-staging` /
`truegrit-prod` are named in `infrastructure/cloudflare/README.md`'s resource map but are **not
yet provisioned** — no `env` block exists in `wrangler.jsonc` and `.github/workflows/deploy.yml`
only deploys `dev`. Replace `truegrit-dev` below with the real name once staging/prod exist.

## 1. What D1 already gives you: Time Travel

Time Travel is built in, always on, costs nothing extra, and needs no setup. Every write is
recoverable to the minute for a rolling window:

- **Workers Paid plan: 30 days.** **Workers Free plan: 7 days.**
- **Open question:** this repo does not record which plan the Cloudflare account is on (checked
  `wrangler.jsonc`, `infrastructure/cloudflare/README.md`, `.github/workflows/*` — no mention).
  Confirm with `wrangler d1 info truegrit-dev` / the Cloudflare dashboard billing page. Until
  confirmed, assume the **7-day Free-plan window** (the conservative case) when deciding whether
  an incident is still within Time Travel range.

Check current bookmark / find a bookmark for a past moment:

```bash
npx wrangler d1 time-travel info truegrit-dev
npx wrangler d1 time-travel info truegrit-dev --timestamp="2026-07-18T09:00:00Z"
```

Time Travel is the first thing to reach for after a bad migration or an accidental delete — see
`docs/runbooks/migrations.md` ("Production failure"), which already points here.

## 2. On-demand logical export (for anything outside the Time Travel window)

Use a `wrangler d1 export` for disaster recovery off Cloudflare, migrating providers, or
compliance archival — cases Time Travel doesn't cover because it lives only inside D1 and expires
after the retention window above.

```bash
npx wrangler d1 export truegrit-dev --remote --output="./truegrit-dev-$(date +%Y%m%d-%H%M).sql"
```

Add `--no-data` for a schema-only snapshot or `--table=<name>` to export a single table.

**Store the export in R2, not on a laptop.** `apps/api/wrangler.jsonc` already binds an
exports-oriented bucket — reuse it, do not create a new one:

```jsonc
{ "binding": "EXPORTS_BUCKET", "bucket_name": "truegrit-exports-dev" }
```

```bash
npx wrangler r2 object put \
  truegrit-exports-dev/db-backups/truegrit-dev-$(date +%Y%m%d-%H%M).sql \
  --file="./truegrit-dev-20260719-0900.sql"
```

(`truegrit-exports-prod` is likewise named in the resource map but not yet provisioned.) Delete
the local `.sql` file after upload — it contains full table contents, including customer PII.

Cloudflare also documents a scheduled pattern (D1 REST export API + a cron-triggered Workflow
streaming straight to R2) — see [Export and save D1 database](https://developers.cloudflare.com/workflows/examples/backup-d1/).
Nothing like that is wired up here today; §4 covers whether it's worth adding.

## 3. Restore procedures

### A. Time Travel restore — same database, in place

Use this first for "bad migration" or "accidental delete/update" within the retention window.

```bash
npx wrangler d1 time-travel restore truegrit-dev --timestamp=1721385600
# or: --bookmark=<bookmark-from-`time-travel info`>
```

- **Destructive and in-place.** Cloudflare's own docs call it out explicitly: it overwrites the
  database in place. It does **not** create a new database, and the database ID / `DB` binding in
  `wrangler.jsonc` does not change — no Worker redeploy needed afterwards.
- Any in-flight query/transaction against the database is cancelled with an error returned to the
  caller. Expect a short burst of failed API requests during the restore, not a full outage.
- The restore itself returns a new bookmark, so a bad restore can be undone the same way.
- Wrangler prompts for confirmation before running (skip with `--skip-confirmation` only in
  scripted/CI contexts, never as a habit).

### B. Re-import a logical export — disaster recovery / new environment

Use this if Time Travel's window has passed, you're standing up `truegrit-staging` /
`truegrit-prod` from a dev snapshot, or migrating off Cloudflare entirely.

```bash
npx wrangler d1 execute truegrit-dev --remote --file="./truegrit-dev-20260719-0900.sql"
```

- This replays SQL statements into whatever database you point it at — it does **not**
  auto-create a fresh database for you. If the target already has rows, expect primary-key /
  unique-constraint conflicts.
- To restore into a clean copy instead of the live database (e.g. rebuilding `truegrit-prod` from
  a known-good export, or standing up a scratch DB to inspect data without touching production):

  ```bash
  npx wrangler d1 create truegrit-restore-scratch
  npx wrangler d1 execute truegrit-restore-scratch --remote --file="./truegrit-dev-20260719-0900.sql"
  ```

  Repointing a Worker's `DB` binding at the new database ID is a `wrangler.jsonc` change — plan it
  as a deploy, not a live-restore step.

## 4. Cadence: when to take a manual export

`deploy.yml`'s "Apply D1 migrations" step runs unattended on every push to `Testing`/`master`
(idempotent, no confirmation gate — see `docs/runbooks/deployment.md` and
`docs/runbooks/migrations.md`). It does **not** currently take a backup first. Given the size of
this project (single D1 instance, single operator), adding a CI backup step isn't worth the
complexity yet — an export taken *before you push* is simpler and just as effective:

- **Before pushing any migration that alters or rewrites existing rows** (`ALTER TABLE`,
  backfills, anything beyond an additive `CREATE TABLE` / nullable-column `ADD COLUMN` — see the
  expand-contract steps in `docs/runbooks/migrations.md`). Run the `export` command in §2 locally,
  push the export to `EXPORTS_BUCKET`, *then* push the branch.
- **Monthly otherwise**, as a floor, independent of migration activity — covers the gap once data
  is older than the Time Travel window and gives an off-Cloudflare copy for compliance/portability.

If this cadence becomes a burden, the natural next step is a scheduled Workflow per §2's link, or
a new step in `deploy.yml` that runs `wrangler d1 export` before "Apply D1 migrations" and uploads
to `EXPORTS_BUCKET` — not implemented today; add it deliberately, not as a silent side effect of
this doc.

## 5. Who runs this

No ops team and no scheduled job exist for this today — it's a manual `wrangler` CLI operation run
by whoever holds deploy access, using the same Cloudflare auth (`wrangler login` /
`CLOUDFLARE_API_TOKEN`) already used to deploy. Anyone taking over this project should read this
file top to bottom before running their first production migration.
