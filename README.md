# Vibe Skill

`vibe` is a Codex skill for creating GitHub repositories that deploy Cloudflare Workers through GitHub Actions.

The skill lives in `vibe/` and includes:

- `SKILL.md` - trigger metadata and operating instructions for Codex.
- `scripts/scaffold_worker_repo.py` - the scaffold generator.
- `scripts/test_scaffold_worker_repo.py` - offline tests for the generator and security-sensitive paths.
- `assets/worker-template/` - the generated Worker repository template.
- `references/security.md` - deployment and secret-handling guardrails.

## Generate a Worker Repo

```bash
python vibe/scripts/scaffold_worker_repo.py owner/my-worker --output ../my-worker
```

Preview live GitHub operations without requiring `gh`:

```bash
python vibe/scripts/scaffold_worker_repo.py owner/my-worker --output ../my-worker --create-github-repo --set-secrets --dry-run
```

Create and push the GitHub repo when `gh` is installed and authenticated:

```bash
python vibe/scripts/scaffold_worker_repo.py owner/my-worker --output ../my-worker --create-github-repo
```

Set Cloudflare deployment secrets later without rewriting the scaffold:

```bash
python vibe/scripts/scaffold_worker_repo.py owner/my-worker --output ../my-worker --set-secrets --secrets-only
```

The generator never accepts `CLOUDFLARE_API_TOKEN` as a command-line argument. It reads secrets from environment variables or local prompts and sends them to `gh secret set` through standard input.

## Validate

```bash
python -m unittest vibe/scripts/test_scaffold_worker_repo.py
python C:/Users/dabes/.codex/skills/.system/skill-creator/scripts/quick_validate.py ./vibe
python vibe/scripts/scaffold_worker_repo.py --doctor
```

For an end-to-end generated Worker check:

```bash
python vibe/scripts/scaffold_worker_repo.py owner/test-worker --output ../test-worker
cd ../test-worker
npm ci
npm test
npm run typecheck
npm run deploy:dry-run
```

## Publish Locally

Install the skill where Codex can discover it:

```powershell
Copy-Item -Recurse -Force .\vibe "$env:USERPROFILE\.codex\skills\vibe"
```

`--doctor` is expected to report missing `gh` until GitHub CLI is installed.
That does not block local scaffolding or dry-run validation.

## Publish To GitHub

After installing GitHub CLI:

```powershell
gh auth login
gh auth status --active
gh repo create OWNER/Github-Vibe-Skill --private --source . --remote origin --push
```

For a live throwaway deployment test:

```powershell
python vibe/scripts/scaffold_worker_repo.py OWNER/vibe-worker-test --output ../vibe-worker-test --create-github-repo
python vibe/scripts/scaffold_worker_repo.py OWNER/vibe-worker-test --output ../vibe-worker-test --set-secrets --secrets-only
```
