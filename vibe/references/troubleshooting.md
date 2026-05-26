# Troubleshooting

Use this file when the `vibe` scaffold script, the generated Worker project,
or its GitHub Actions pipeline misbehaves. Each entry lists a symptom, the
likely cause, and the fix. Start with `--doctor` for an environment check.

## First step for any failure

```bash
python vibe/scripts/scaffold_worker_repo.py --doctor
```

`--doctor` reports Python version, required CLIs (`git`, `gh`, `node`, `npm`),
GitHub auth status, Git commit identity, presence of Cloudflare env vars, and
template file integrity. Exit code is 0 only if everything passes; paste the
full output into a bug report when escalating.

## Agent escalation rules

Before asking the user to do anything, an AI should:

1. Run `--doctor` or inspect its output if already provided.
2. Re-run failing live commands with `--dry-run` when possible.
3. Check whether the issue is local and fixable: missing output directory,
   stale lockfile, malformed repo slug, missing placeholder replacement,
   generated project test/typecheck failure.
4. Give the user an action only when the agent cannot complete it safely:
   installing `gh`/Git/Node, authenticating `gh`, entering Cloudflare secrets,
   approving a protected GitHub environment, or choosing a repo owner/name.

User-facing messages should be short and concrete:

- What failed.
- What the agent already checked or fixed.
- The one exact command or UI action the user needs next.

## Scaffold script errors

### `error: required CLI not found on PATH: gh - install from ...`
**Cause:** `--create-github-repo` or `--set-secrets` was used but `gh` is
not installed. **Fix:** install GitHub CLI from <https://cli.github.com/>
and run `gh auth login`. Or re-run without those flags to scaffold files only.

### `error: required CLI not found on PATH: git`
**Cause:** `--create-github-repo` was used but `git` is not installed.
**Fix:** install Git, or generate locally without `--create-github-repo`.

### `error: output directory is not empty: ...`
**Cause:** Target directory has files. **Fix:** pick a fresh path with
`--output`, delete the directory, or pass `--force` if you want to write
template files alongside existing ones (existing files are NOT deleted).

### `error: repository must be NAME or OWNER/NAME`
**Cause:** Bad slug like `owner/`, `/repo`, or `a/b/c`. **Fix:** use either
`my-worker` or `owner/my-worker`.

### `error: CLOUDFLARE_API_TOKEN cannot be empty`
**Cause:** Prompt or env var produced an empty value. **Fix:** set the env
var before invoking, or type the token at the hidden prompt. The token is
never accepted as a CLI argument by design.

### `error: --secrets-only requires --set-secrets`
**Cause:** You asked to skip scaffolding but did not ask to set secrets.
**Fix:** add `--set-secrets`, or drop `--secrets-only` to regenerate files.

### `error: --set-secrets requires OWNER/NAME ...`
**Cause:** GitHub secrets need an explicit remote target. A bare repo name
can be ambiguous before the repo has an origin. **Fix:** use
`OWNER/my-worker --set-secrets`.

### CalledProcessError from `gh auth status --active`
**Cause:** No active GitHub account. **Fix:** `gh auth login`. Verify with
`gh auth status --active` (the script never uses `--show-token`).

### CalledProcessError from `git commit`
**Cause:** Git is installed but `user.name` or `user.email` is not configured.
**Fix:** run `git config --global user.name "Your Name"` and
`git config --global user.email "you@example.com"`, then re-run the scaffold
command. `--doctor` reports both settings.

### CalledProcessError from `gh repo create`
**Cause:** Repo already exists, name collision in your account, insufficient
token scopes, or org policy block. **Fix:** check the gh stderr (printed
live), pick a different name, or grant `repo` scope via `gh auth refresh
-s repo`.

### CalledProcessError from `gh secret set`
**Cause:** Lack of `admin:repo_hook` / repo admin permissions, or wrong
repo slug. **Fix:** confirm you can `gh repo view OWNER/REPO`, and that
your token includes admin access. For environment secrets, the
environment must exist on the repo first.

## Generated project errors

### `npm ci` fails with "lock file out of sync"
**Cause:** `package.json` was edited without regenerating `package-lock.json`.
**Fix:** run `npm install` in the generated project once, commit the new
lockfile. The shipped template is in sync; only edits drift it.

### `npm test` finds no tests
**Cause:** Vitest discovery missed your spec. **Fix:** ensure files end with
`.test.ts` and live under `test/` or co-located with sources.

### `npm run typecheck` fails on `ExecutionContext`
**Cause:** `@cloudflare/workers-types` not installed (skipped `npm ci`).
**Fix:** `npm ci`.

### `npm run deploy:dry-run` fails
**Cause:** Wrangler config error (bad `compatibility_date`, missing `main`).
**Fix:** read the Wrangler error verbatim; common fixes are checking
`wrangler.jsonc` matches the schema linked at the top of the file.

### `npm run deploy` fails in CI with `Authentication error`
**Cause:** Missing or wrong `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN`
secrets. **Fix:** verify with `gh secret list --repo OWNER/REPO`; re-run
`scaffold_worker_repo.py ... --set-secrets --secrets-only` to rotate.

## GitHub Actions

### Deploy job is skipped
**Cause:** Push was not to `main`. **Fix:** merge to `main` or use
"Run workflow" (workflow_dispatch).

### Deploy job is waiting for approval
**Cause:** The `production` environment has required reviewers. **Fix:**
approve in the GitHub UI under the workflow run, or edit environment
protection rules in repo settings.

## Escalation checklist

When opening an issue or asking another agent for help, attach:

1. Output of `python vibe/scripts/scaffold_worker_repo.py --doctor`.
2. The exact failing command, including flags (redact tokens).
3. The last ~20 lines of the failing CLI output.
4. Whether you ran with `--dry-run` (no external state was changed) or
   live (external state may be partially mutated; check `gh repo view`
   and `gh secret list`).
