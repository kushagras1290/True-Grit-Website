# True Grit Release Process

Independent release cockpit deployed at `https://process.truegritin.com`.

## Release flow

1. Work lands on `testing`; CI must pass.
2. Codex, Claude, or another authorized agent reviews the exact testing SHA and runs
   `Approve testing commit` in GitHub Actions.
3. The owner or a scoped Release Manager promotes that SHA to `staging` from the cockpit.
4. The staging deployment and CI checks must pass. An authorized release user opens the staging
   domain, tests it, and records verification notes.
5. The cockpit unlocks promotion of that exact staging SHA to `main`.

No action accepts a repository name or arbitrary branch pair from the browser. The API is confined
to `GITHUB_REPOSITORY`, permits only `testing -> staging` and `staging -> main`, and rechecks the
current branch head immediately before every mutation.

## Process users

The owner signs in with the same `ADMIN_LOGIN_EMAIL` / `ADMIN_LOGIN_PASSWORD` account used by the
existing True Grit API. From **Process users**, the owner can add additional staff accounts. New
accounts receive only the system `Release Manager` role: they can view the three lanes, verify
staging, and promote releases, but cannot add more process users or inherit broad admin-panel
permissions. Every status and merge records the signed-in operator's display name.

## Local development

Set `VITE_API_URL=http://localhost:8787`, then run:

```powershell
pnpm --filter @truegrit/process dev
```

The API defaults `PUBLIC_PROCESS_URL` to `http://localhost:5175`, so credentialed CORS works locally.

## Deployment configuration

Set the GitHub credential on each API Worker environment; do not place it in `wrangler.jsonc`:

```powershell
Set-Location apps/api
pnpm exec wrangler secret put GITHUB_TOKEN
pnpm exec wrangler secret put GITHUB_TOKEN --env staging
pnpm exec wrangler secret put GITHUB_TOKEN --env production
```

Use a fine-grained token restricted to this repository with Contents read/write, Commit statuses
read/write, and Checks read. Production is deployed through `Deploy web environment` with the typed
confirmation `DEPLOY production`. That workflow builds this app against `https://api.truegritin.com`,
deploys its custom domain, and verifies the URL.

## Failure handling

Failed and incomplete checks are shown above successful checks and lock promotion. The run link opens
the exact GitHub failure. A branch advancing after review invalidates the screen's action and requires
a refresh and a new approval. GitHub merge conflicts are returned as a safe conflict message; no
force-push or history rewrite is performed.

## Rollback

The cockpit only promotes forward. Rollback remains an explicit reviewed revert commit on `testing`,
which follows the same gates. This preserves an auditable history and avoids hidden branch rewrites.
