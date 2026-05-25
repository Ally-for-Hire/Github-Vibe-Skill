#!/usr/bin/env python3
"""Scaffold a testable GitHub + Cloudflare Workers repository.

Pipeline (per CLI invocation):

    parse_args -> build_config -> scaffold_files
                              \\-> [create_github_repo]   (--create-github-repo)
                              \\-> [set_github_secrets]   (--set-secrets)
                              -> print_next_steps

Design contracts other contributors/AIs should preserve:

* The Cloudflare API token is NEVER a CLI argument. It is read from the
  environment variable CLOUDFLARE_API_TOKEN, or prompted with getpass, and
  is passed to `gh secret set` via stdin so it never appears in argv or
  shell history. See `set_github_secrets` / `read_secret_value`.
* `--dry-run` MUST still write the local scaffold (so users can inspect it)
  but must only PRINT external `git`/`gh` commands rather than execute them.
  All external commands therefore route through `run_command(..., dry_run=)`.
* `scaffold_files` refuses to write into a non-empty directory unless
  `force=True`. `--secrets-only` short-circuits scaffolding entirely so the
  script can be re-run later to rotate secrets without disturbing files.
* Error messages should be self-diagnosable: `require_tool` includes an
  install hint, and `--doctor` prints a full environment report.

Run `python scaffold_worker_repo.py --doctor` for an environment check.
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = SKILL_DIR / "assets" / "worker-template"
DEFAULT_NODE_VERSION = "24"
SECRET_NAMES = ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN")

TOOL_INSTALL_HINTS: dict[str, str] = {
    "git": "install from https://git-scm.com/downloads",
    "gh": "install from https://cli.github.com/ then run: gh auth login",
    "node": "install from https://nodejs.org/ (includes npm)",
    "npm": "install Node.js from https://nodejs.org/ (includes npm)",
}

WINDOWS_TOOL_PATHS: dict[str, tuple[Path, ...]] = {
    "gh": (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "GitHub CLI" / "gh.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "GitHub CLI" / "gh.exe",
    ),
}


@dataclass(frozen=True)
class ScaffoldConfig:
    repo_slug: str
    repo_name: str
    worker_name: str
    output_dir: Path
    compatibility_date: str
    node_version: str
    force: bool = False


def normalize_name(value: str, fallback: str = "worker") -> str:
    """Lowercase, kebab-case slug suitable for GitHub repo + Worker names."""
    normalized = re.sub(r"[^a-z0-9-]+", "-", value.lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or fallback


def split_repo_slug(slug: str) -> tuple[str | None, str]:
    """Split "OWNER/NAME" or bare "NAME" into (owner_or_None, name).

    Raises ValueError for malformed slugs ("owner/", "/repo", "a/b/c") so
    callers fail loudly instead of silently producing bad gh commands.
    """
    if "/" not in slug:
        return None, slug
    owner, repo = slug.split("/", 1)
    if not owner or not repo or "/" in repo:
        raise ValueError("repository must be NAME or OWNER/NAME")
    return owner, repo


def build_config(args: argparse.Namespace) -> ScaffoldConfig:
    _, raw_repo_name = split_repo_slug(args.repo)
    repo_name = normalize_name(raw_repo_name)
    worker_name = normalize_name(args.worker_name or repo_name)
    return ScaffoldConfig(
        repo_slug=args.repo,
        repo_name=repo_name,
        worker_name=worker_name,
        output_dir=Path(args.output).expanduser().resolve(),
        compatibility_date=args.compatibility_date,
        node_version=args.node_version,
        force=args.force,
    )


def render_text(text: str, config: ScaffoldConfig) -> str:
    """Substitute scaffold placeholders in `text`.

    Template files in `assets/worker-template/` use two placeholder styles:

    * The literal string ``vibe-worker-template`` for fields where a real
      identifier is required for the file to be valid (e.g. package.json's
      "name", which npm parses even in unrendered form).
    * ``__UPPER_SNAKE__`` tokens for everything else - chosen because they
      survive most syntax checkers (JSON, YAML, TypeScript) so the template
      stays parseable, and they're distinctive enough to grep for.

    When you add a new placeholder, also add it to the replacement dict and
    to `test_scaffold_renders_worker_template` so unrendered tokens can't
    leak into generated projects.
    """
    replacements = {
        "vibe-worker-template": config.repo_name,
        "__REPO_SLUG__": config.repo_slug,
        "__REPO_NAME__": config.repo_name,
        "__WORKER_NAME__": config.worker_name,
        "__COMPATIBILITY_DATE__": config.compatibility_date,
        "__NODE_VERSION__": config.node_version,
    }
    for needle, value in replacements.items():
        text = text.replace(needle, value)
    return text


def scaffold_files(config: ScaffoldConfig) -> list[Path]:
    """Copy and render every template file into `config.output_dir`.

    Refuses to write into a non-empty directory unless `config.force=True`,
    to avoid silently overwriting in-progress user work.
    """
    if not TEMPLATE_DIR.exists():
        raise FileNotFoundError(f"template directory not found: {TEMPLATE_DIR}")

    if config.output_dir.exists() and any(config.output_dir.iterdir()) and not config.force:
        raise FileExistsError(f"output directory is not empty: {config.output_dir}")

    written: list[Path] = []
    for source in TEMPLATE_DIR.rglob("*"):
        relative = source.relative_to(TEMPLATE_DIR)
        target = config.output_dir / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8")
        target.write_text(render_text(text, config), encoding="utf-8", newline="\n")
        written.append(target)
    return written


def command_display(command: list[str]) -> str:
    return " ".join(quote_arg(part) for part in command)


def quote_arg(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:=@%+-]+", value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def tool_path(name: str) -> str | None:
    """Return an executable path, including common Windows install locations."""
    found = shutil.which(name)
    if found:
        return found

    for candidate in WINDOWS_TOOL_PATHS.get(name, ()):
        if candidate and candidate.exists():
            return str(candidate)
    return None


def require_tool(name: str) -> str:
    """Return a CLI executable path, or raise with an install hint."""
    found = tool_path(name)
    if found:
        return found

    hint = TOOL_INSTALL_HINTS.get(name)
    suffix = f" - {hint}" if hint else ""
    raise RuntimeError(f"required CLI not found on PATH or known install paths: {name}{suffix}")


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    input_text: str | None = None,
    dry_run: bool = False,
) -> subprocess.CompletedProcess[str] | None:
    """Execute an external command, or print it in dry-run mode.

    Routing every `git`/`gh` invocation through this function is what makes
    `--dry-run` safe: callers never need to branch on dry_run themselves,
    and stdin that may contain secrets is shown as ``<redacted-stdin>``
    instead of being printed.
    """
    if dry_run:
        suffix = " <redacted-stdin>" if input_text is not None else ""
        print(f"$ {command_display(command)}{suffix}")
        return None

    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        input=input_text,
        text=True,
        check=True,
    )


def ensure_git_repo(output_dir: Path, dry_run: bool) -> None:
    git = "git" if dry_run else require_tool("git")
    if (output_dir / ".git").exists():
        return
    run_command([git, "init", "-b", "main"], cwd=output_dir, dry_run=dry_run)
    run_command([git, "add", "."], cwd=output_dir, dry_run=dry_run)
    run_command(
        [git, "commit", "-m", "Initial Cloudflare Worker scaffold"],
        cwd=output_dir,
        dry_run=dry_run,
    )


def create_github_repo(config: ScaffoldConfig, visibility: str, dry_run: bool) -> None:
    gh = "gh" if dry_run else require_tool("gh")
    ensure_git_repo(config.output_dir, dry_run)
    run_command([gh, "auth", "status", "--active"], dry_run=dry_run)
    run_command(
        [
            gh,
            "repo",
            "create",
            config.repo_slug,
            f"--{visibility}",
            "--source",
            str(config.output_dir),
            "--remote",
            "origin",
            "--push",
        ],
        dry_run=dry_run,
    )


def resolve_secret_repo(config: ScaffoldConfig, output_dir: Path, dry_run: bool) -> str:
    owner, _ = split_repo_slug(config.repo_slug)
    if owner:
        return config.repo_slug
    if dry_run:
        return f"OWNER/{config.repo_name}"

    gh = require_tool("gh")
    completed = subprocess.run(
        [gh, "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        cwd=str(output_dir),
        text=True,
        check=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def read_secret_value(name: str) -> str:
    """Resolve a secret from env, or prompt the user interactively.

    Tokens (CLOUDFLARE_API_TOKEN) are read via getpass so they don't echo
    to the terminal; non-secret IDs use plain input. Empty values are
    rejected so we never push an empty secret to GitHub.
    """
    value = os.environ.get(name)
    if value:
        return value

    if name == "CLOUDFLARE_API_TOKEN":
        value = getpass.getpass(f"{name}: ")
    else:
        value = input(f"{name}: ")

    if not value:
        raise RuntimeError(f"{name} cannot be empty")
    return value


def set_github_secrets(config: ScaffoldConfig, environment: str | None, dry_run: bool) -> None:
    """Push CLOUDFLARE_* secrets to GitHub via stdin.

    The secret value is passed to `gh secret set` through stdin (the
    `input_text` arg on `run_command`) so it never appears in argv,
    shell history, or `ps` output.
    """
    gh = "gh" if dry_run else require_tool("gh")
    repo = resolve_secret_repo(config, config.output_dir, dry_run)
    for name in SECRET_NAMES:
        value = "redacted" if dry_run else read_secret_value(name)
        command = [gh, "secret", "set", name, "--app", "actions", "--repo", repo]
        if environment:
            command.extend(["--env", environment])
        run_command(command, input_text=value, dry_run=dry_run)


def script_command(*parts: str) -> str:
    """Render a copy-pasteable invocation of THIS script with extra args."""
    return command_display(["python", str(Path(__file__).resolve()), *parts])


def run_doctor(stream=None) -> int:
    """Print an environment diagnostic and return 0 if everything looks OK.

    Run as `python scaffold_worker_repo.py --doctor`. Designed so a future
    AI or user can paste the output into a bug report and self-diagnose the
    most common failures (missing CLIs, unauthenticated gh, missing Cloudflare
    env vars, deleted template files).

    `stream` is the file-like to write to; defaults to stdout. Tests inject
    a StringIO buffer here so they can assert on the report.
    """
    out = stream if stream is not None else sys.stdout
    issues: list[str] = []

    def line(text: str = "") -> None:
        print(text, file=out)

    line("vibe doctor")
    line("=" * 40)
    line(f"python:   {sys.version.split()[0]} ({sys.platform})")
    line(f"skill dir: {SKILL_DIR}")

    line("")
    line("Required CLIs:")
    for tool in ("git", "gh", "node", "npm"):
        path = tool_path(tool)
        if path:
            line(f"  {tool:6s} OK    {path}")
        else:
            line(f"  {tool:6s} MISSING")
            hint = TOOL_INSTALL_HINTS.get(tool)
            if hint:
                line(f"         hint: {hint}")
            issues.append(f"missing CLI: {tool}")

    line("")
    line("GitHub auth:")
    gh = tool_path("gh")
    if gh is None:
        line("  skipped (gh not installed)")
    else:
        try:
            subprocess.run(
                [gh, "auth", "status", "--active"],
                check=True,
                capture_output=True,
                text=True,
            )
            line("  active")
        except subprocess.CalledProcessError as exc:
            line("  NOT AUTHENTICATED")
            line("  hint: run `gh auth login`")
            stderr_tail = (exc.stderr or "").strip().splitlines()[-1:] or [""]
            if stderr_tail[0]:
                line(f"  gh said: {stderr_tail[0]}")
            issues.append("gh not authenticated")
        except FileNotFoundError:
            line("  gh not on PATH (race?)")
            issues.append("gh not on PATH")

    line("")
    line("Cloudflare env vars (presence only, values not displayed):")
    for name in SECRET_NAMES:
        present = bool(os.environ.get(name))
        line(f"  {name:25s} {'set' if present else 'not set'}")

    line("")
    line("Worker template:")
    if not TEMPLATE_DIR.exists():
        line(f"  MISSING: {TEMPLATE_DIR}")
        issues.append("template directory missing")
    else:
        files = [p for p in TEMPLATE_DIR.rglob("*") if p.is_file()]
        line(f"  {len(files)} files at {TEMPLATE_DIR}")
        for required in ("package.json", "wrangler.jsonc", "src/index.ts",
                         ".github/workflows/deploy.yml"):
            present = (TEMPLATE_DIR / required).exists()
            mark = "OK     " if present else "MISSING"
            line(f"    {mark} {required}")
            if not present:
                issues.append(f"template file missing: {required}")

    line("")
    if issues:
        line("status: ISSUES FOUND")
        for issue in issues:
            line(f"  - {issue}")
        return 1
    line("status: OK")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scaffold a GitHub repository that deploys to Cloudflare Workers.",
    )
    parser.add_argument(
        "repo",
        nargs="?",
        help="Repository name or OWNER/NAME slug. Required unless --doctor is used.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Print environment diagnostics (tools, gh auth, env vars, template) and exit.",
    )
    parser.add_argument("--output", "-o", default=None, help="Output directory. Defaults to ./REPO.")
    parser.add_argument("--worker-name", help="Cloudflare Worker name. Defaults to the repo name.")
    parser.add_argument(
        "--visibility",
        choices=("private", "public", "internal"),
        default="private",
        help="GitHub repository visibility when --create-github-repo is used.",
    )
    parser.add_argument(
        "--compatibility-date",
        default=dt.date.today().isoformat(),
        help="Wrangler compatibility_date value.",
    )
    parser.add_argument("--node-version", default=DEFAULT_NODE_VERSION, help="Node.js version for GitHub Actions.")
    parser.add_argument("--force", action="store_true", help="Allow writing into a non-empty output directory.")
    parser.add_argument("--create-github-repo", action="store_true", help="Create and push the repo with gh.")
    parser.add_argument("--set-secrets", action="store_true", help="Set Cloudflare GitHub Actions secrets with gh.")
    parser.add_argument(
        "--secrets-only",
        action="store_true",
        help="Skip file generation and only set GitHub Actions secrets. Use with --set-secrets.",
    )
    parser.add_argument(
        "--environment-secrets",
        metavar="ENVIRONMENT",
        help="Store secrets on a GitHub Actions environment instead of the repository.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write scaffold files, then print external git/gh operations instead of executing them.",
    )

    args = parser.parse_args(argv)
    if args.doctor:
        return args
    if not args.repo:
        parser.error("repo is required unless --doctor is used")
    if args.secrets_only and not args.set_secrets:
        parser.error("--secrets-only requires --set-secrets")
    if args.output is None:
        _, repo_name = split_repo_slug(args.repo)
        args.output = normalize_name(repo_name)
    return args


def print_next_steps(config: ScaffoldConfig, args: argparse.Namespace) -> None:
    print("")
    print("Next steps:")
    print(f"  cd {config.output_dir}")
    print("  npm ci")
    print("  npm test && npm run typecheck && npm run deploy:dry-run")
    if not args.create_github_repo:
        print("  # then, when ready:")
        print(f"  gh repo create {config.repo_slug} --{args.visibility} --source . --remote origin --push")
    if not args.set_secrets:
        print("  # set deploy secrets without exposing them in shell history:")
        print(
            "  "
            + script_command(
                config.repo_slug,
                "--output",
                str(config.output_dir),
                "--set-secrets",
                "--secrets-only",
            )
        )


def print_failure_help(exc: Exception) -> None:
    print(f"error: {exc}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Self-diagnosis:", file=sys.stderr)
    print(f"  {script_command('--doctor')}", file=sys.stderr)
    print("Troubleshooting guide:", file=sys.stderr)
    print(f"  {SKILL_DIR / 'references' / 'troubleshooting.md'}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.doctor:
        return run_doctor()
    config = build_config(args)

    try:
        if args.secrets_only:
            print(f"skipped file generation for {config.output_dir}")
        else:
            written = scaffold_files(config)
            print(f"wrote {len(written)} files to {config.output_dir}")

        if args.create_github_repo:
            create_github_repo(config, args.visibility, args.dry_run)

        if args.set_secrets:
            set_github_secrets(config, args.environment_secrets, args.dry_run)

        print_next_steps(config, args)

    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print_failure_help(exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
