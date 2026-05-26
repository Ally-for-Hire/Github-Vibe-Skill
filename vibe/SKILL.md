---
name: vibe
description: Create and publish new GitHub repositories configured for secure Cloudflare Workers deployment through GitHub Actions. Use when the user asks for /vibe, vibe scaffolding, GitHub repo creation with the gh CLI, Wrangler or Cloudflare Workers deployment workflows, secure GitHub secret setup for Cloudflare tokens, or testable Workers CI/CD templates.
---

# Vibe

## Overview

Use this skill to scaffold a GitHub repository for a Cloudflare Worker with tests, a lockfile-backed Wrangler toolchain, and a GitHub Actions workflow that deploys only from `main` or manual dispatch.

The bundled generator is the preferred path because it keeps secrets out of command history and makes live operations opt-in.

## Workflow

1. Gather the repository name, visibility, Worker name, and whether the user wants live GitHub operations now. Default to `private` visibility and a Worker name derived from the repository name.
2. Generate files with `scripts/scaffold_worker_repo.py`.
3. Run local validation in the generated project before creating or pushing the remote repo.
4. If requested, create the GitHub repository with `gh`. When secrets are requested in the same run, create the remote first, set secrets, then push so the first workflow can deploy.
5. Configure GitHub Actions secrets through `gh secret set`, reading secret values from environment variables or hidden terminal prompts. Never ask the user to paste the Cloudflare API token into chat.

## Agent Behavior

Do the maximum safe work locally before asking the user for help:

1. Run `python scripts/scaffold_worker_repo.py --doctor` when a command fails or the environment is unknown.
2. Use `--dry-run` before live GitHub operations when `gh` is missing, unauthenticated, or the user has not explicitly approved live repository creation.
3. Read `references/troubleshooting.md` and apply the relevant fix before escalating.
4. Ask the user only for decisions or credentials that cannot be inferred: target repo owner/name, public/private visibility, whether to run live GitHub/Cloudflare operations, and Cloudflare values entered locally through prompts or environment variables.
5. Give concise feedback that states what happened, what was fixed, what still needs user action, and the exact next command if action is needed.

## Generate

From this skill directory:

```bash
python scripts/scaffold_worker_repo.py my-worker --output ../my-worker
```

Useful options:

```bash
python scripts/scaffold_worker_repo.py owner/my-worker --output ../my-worker --worker-name my-worker --visibility private
python scripts/scaffold_worker_repo.py owner/my-worker --output ../my-worker --create-github-repo --set-secrets
python scripts/scaffold_worker_repo.py owner/my-worker --output ../my-worker --create-github-repo --set-secrets --dry-run
python scripts/scaffold_worker_repo.py owner/my-worker --output ../my-worker --set-secrets --secrets-only
```

`--dry-run` still writes the local scaffold but prints external `git`, `gh`, and secret-setting commands instead of executing them.
Use `--secrets-only` with `--set-secrets` when the repo was already scaffolded and only GitHub Actions secrets need to be configured.

## Token Handling

Use the Cloudflare token only as a GitHub Actions secret named `CLOUDFLARE_API_TOKEN`. Use `CLOUDFLARE_ACCOUNT_ID` as a secret too, even though it is less sensitive, to keep workflow configuration uniform.

Prefer the generator's `--set-secrets` path:

```bash
python scripts/scaffold_worker_repo.py owner/my-worker --output ../my-worker --set-secrets
```

The script reads `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` from the terminal environment when present, otherwise prompts locally. The token is never accepted as a CLI argument and is passed to `gh secret set` through standard input.

For app runtime secrets, use Cloudflare Worker secrets, not Wrangler plaintext vars:

```bash
npx wrangler secret put SECRET_NAME
```

Read `references/security.md` when adding custom secrets, changing the workflow trigger model, or deciding between repository and environment secrets.

## GitHub And Wrangler

Before live operations, check:

```bash
gh auth status --active
```

Do not run `gh auth status --show-token` or JSON auth commands that expose tokens.

The generated project installs Wrangler as a dev dependency and deploys with:

```bash
npm run deploy
```

The generated workflow uses `npm ci` and `npm run deploy` with these GitHub Actions secrets:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

## Validate

Validate the skill scaffold:

```bash
python -m unittest scripts/test_scaffold_worker_repo.py
# Optional, when Codex's skill-creator validator is available locally:
python path/to/quick_validate.py .
```

Validate a generated Worker project:

```bash
npm ci
npm test
npm run typecheck
npm run deploy:dry-run
```

## Diagnose

When something fails, start with the built-in self-check:

```bash
python scripts/scaffold_worker_repo.py --doctor
```

It reports Python version, presence of `git`/`gh`/`node`/`npm`, GitHub auth status, Cloudflare env-var presence (values are never displayed), and template file integrity. Exit code is 0 only if everything passes. Paste the full output into a bug report when escalating.

For common error/cause/fix mappings (scaffold script, generated project, GitHub Actions), read `references/troubleshooting.md`.
