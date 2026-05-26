# __REPO_NAME__

Cloudflare Worker scaffolded from the `vibe` skill. Deploys from GitHub Actions on push to `main` or manual dispatch.

## Local development

One command does the full local path: install dependencies, run tests,
typecheck, compile with Wrangler dry-run, then start the dev server.

```bash
npm run vibe
```

Open <http://127.0.0.1:8787/> after Wrangler starts.

Useful individual commands:

```bash
npm run check       # install + test + typecheck + wrangler dry-run
npm ci
npm test            # vitest
npm run typecheck   # tsc --noEmit
npm run dev         # wrangler dev (local Worker runtime)
npm run deploy:dry-run  # compile + validate without uploading
```

`npm run deploy:dry-run` writes the compiled Worker to `dist/` and needs no Cloudflare credentials.

## Deploy

`npm run deploy` calls `wrangler deploy` and requires:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN` (scoped Workers token)

In CI those are read from GitHub Actions secrets. Locally, export them in your shell; never commit them or paste into chat.

`wrangler.jsonc` has `workers_dev` enabled so the Worker gets a public `workers.dev` URL after deployment. Set it to `false` and configure Cloudflare routes if this Worker should not be reachable on that default subdomain.

## GitHub Actions

`.github/workflows/deploy.yml` runs `npm run check` on every push. The `deploy` job runs only on `main` and uses the `production` environment. GitHub creates that environment without reviewers by default; add reviewers or branch protection in repo settings when you want manual approval.

If Cloudflare secrets are not set, the deploy job skips deployment cleanly. If secrets are set, the workflow runs `npx wrangler whoami` before deploy so bad account IDs or tokens fail with a clear preflight error.

Third-party GitHub Actions are pinned to commit SHAs, with the source tag shown in comments. Refresh those SHAs deliberately when updating Actions versions.

## Runtime secrets

App-level secrets (API keys the Worker reads at runtime) belong in Cloudflare, not in `wrangler.jsonc`:

```bash
npx wrangler secret put SECRET_NAME
```

## Source layout

- `src/index.ts` - Worker entrypoint (`fetch` handler)
- `src/response.ts` - pure helpers, easy to unit test
- `test/response.test.ts` - vitest specs
- `wrangler.jsonc` - Worker name, compatibility date, observability
- `.github/workflows/deploy.yml` - CI + deploy pipeline

Repo: `__REPO_SLUG__`
