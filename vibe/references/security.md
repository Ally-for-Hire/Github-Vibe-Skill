# Security Reference

Use this file when changing the deployment workflow, token setup, or runtime-secret setup.

## Source Of Truth

- Cloudflare Workers GitHub Actions: https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/
- Wrangler deploy command and `--dry-run`: https://developers.cloudflare.com/workers/wrangler/commands/workers/#deploy
- Cloudflare Worker secrets: https://developers.cloudflare.com/workers/configuration/secrets/
- Wrangler configuration secrets validation: https://developers.cloudflare.com/workers/wrangler/configuration/#secrets
- GitHub CLI `gh repo create`: https://cli.github.com/manual/gh_repo_create
- GitHub CLI `gh secret set`: https://cli.github.com/manual/gh_secret_set
- GitHub CLI `gh auth status`: https://cli.github.com/manual/gh_auth_status

## Required CI Secrets

Cloudflare documents that non-interactive CI/CD needs both a Cloudflare API token and account ID for Wrangler authentication. Store these as GitHub Actions secrets:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

Use a scoped Cloudflare API token with only the account and Worker permissions needed for deployment. Do not store the token in source files, Wrangler config, `.env`, `.dev.vars`, workflow YAML, shell history, or chat.

## GitHub Actions Guardrails

- Deploy from `push` to `main` and `workflow_dispatch`, not from untrusted pull request events.
- Keep workflow permissions minimal. `contents: read` is enough for checkout and deploy.
- Put deploys behind the `production` environment so repository owners can add reviewers or protection rules.
- Keep the Cloudflare token scoped to the target account and Worker resources where possible.
- Use `npm ci` with a committed lockfile so CI installs the same Wrangler version tested locally.
- Use `npm run deploy:dry-run` before live deployment when modifying generated Worker code or Wrangler configuration.

## Runtime Secrets

Worker runtime secrets are separate from GitHub Actions deployment secrets. Add application secrets with:

```bash
npx wrangler secret put SECRET_NAME
```

Do not place secret values in `wrangler.jsonc`, `.env`, or `.dev.vars` committed to the repo. For local development, set them via `wrangler secret put` (stored on Cloudflare) or via an uncommitted `.dev.vars` file used only by `wrangler dev`.
