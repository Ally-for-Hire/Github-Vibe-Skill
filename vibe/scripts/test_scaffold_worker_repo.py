import importlib.util
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).with_name("scaffold_worker_repo.py")


def load_module():
    spec = importlib.util.spec_from_file_location("scaffold_worker_repo", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ScaffoldWorkerRepoTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def _config(self, output_dir: Path, **overrides):
        defaults = dict(
            repo_slug="owner/My App",
            repo_name="my-app",
            worker_name="my-worker",
            output_dir=output_dir,
            compatibility_date="2026-05-25",
            node_version="24",
        )
        defaults.update(overrides)
        return self.module.ScaffoldConfig(**defaults)

    def test_scaffold_renders_worker_template(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "app"
            config = self._config(output_dir)

            written = self.module.scaffold_files(config)

            self.assertGreaterEqual(len(written), 8)
            package_json = (output_dir / "package.json").read_text(encoding="utf-8")
            package_lock = (output_dir / "package-lock.json").read_text(encoding="utf-8")
            wrangler_jsonc = (output_dir / "wrangler.jsonc").read_text(encoding="utf-8")
            workflow = (output_dir / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
            response_ts = (output_dir / "src" / "response.ts").read_text(encoding="utf-8")
            readme = (output_dir / "README.md").read_text(encoding="utf-8")

            self.assertIn('"name": "my-app"', package_json)
            self.assertIn('"name": "my-app"', package_lock)
            self.assertIn('"name": "my-worker"', wrangler_jsonc)
            self.assertIn('"compatibility_date": "2026-05-25"', wrangler_jsonc)
            self.assertIn("CLOUDFLARE_API_TOKEN", workflow)
            self.assertIn('node-version: "24"', workflow)
            self.assertIn('service: "my-worker"', response_ts)
            self.assertIn("# my-app", readme)
            self.assertIn("owner/My App", readme)
            self.assertNotIn("vibe-worker-template", package_json)
            self.assertNotIn("vibe-worker-template", package_lock)
            self.assertNotIn("__WORKER_NAME__", response_ts)
            self.assertNotIn("__REPO_NAME__", readme)
            self.assertNotIn("__REPO_SLUG__", readme)

    def test_scaffold_refuses_nonempty_output_without_force(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "app"
            output_dir.mkdir()
            (output_dir / "existing.txt").write_text("keep me", encoding="utf-8")

            config = self._config(output_dir)
            with self.assertRaises(FileExistsError):
                self.module.scaffold_files(config)

            forced = self._config(output_dir, force=True)
            self.module.scaffold_files(forced)
            self.assertTrue((output_dir / "package.json").exists())
            self.assertEqual((output_dir / "existing.txt").read_text(encoding="utf-8"), "keep me")

    def test_split_repo_slug_rejects_bad_input(self):
        self.assertEqual(self.module.split_repo_slug("repo"), (None, "repo"))
        self.assertEqual(self.module.split_repo_slug("owner/repo"), ("owner", "repo"))
        with self.assertRaises(ValueError):
            self.module.split_repo_slug("owner/")
        with self.assertRaises(ValueError):
            self.module.split_repo_slug("/repo")
        with self.assertRaises(ValueError):
            self.module.split_repo_slug("a/b/c")

    def test_normalize_name(self):
        self.assertEqual(self.module.normalize_name("My Worker_API"), "my-worker-api")
        self.assertEqual(self.module.normalize_name("!!!", fallback="fallback"), "fallback")

    def test_parser_does_not_accept_token_argument(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.module.parse_args(["owner/repo", "--cloudflare-api-token", "secret"])

    def test_secrets_only_requires_set_secrets(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.module.parse_args(["owner/repo", "--secrets-only"])

    def test_dry_run_live_operations_do_not_require_clis(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "dry-run"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                result = self.module.main(
                    [
                        "owner/dry-run",
                        "--output",
                        str(output_dir),
                        "--create-github-repo",
                        "--set-secrets",
                        "--dry-run",
                    ]
                )

            self.assertEqual(result, 0)
            self.assertTrue((output_dir / ".github" / "workflows" / "deploy.yml").exists())

            output = buffer.getvalue()
            self.assertIn("gh repo create owner/dry-run", output)
            self.assertIn("gh secret set CLOUDFLARE_ACCOUNT_ID", output)
            self.assertIn("gh secret set CLOUDFLARE_API_TOKEN", output)
            self.assertIn("<redacted-stdin>", output)
            self.assertIn("Next steps:", output)

    def test_next_steps_suggests_repo_create_when_skipped(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "skip-live"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                result = self.module.main(
                    [
                        "owner/skip-live",
                        "--output",
                        str(output_dir),
                    ]
                )

            self.assertEqual(result, 0)
            output = buffer.getvalue()
            self.assertIn("gh repo create owner/skip-live --private", output)
            self.assertIn("--set-secrets", output)
            self.assertIn("--secrets-only", output)
            self.assertIn("scaffold_worker_repo.py", output)

    def test_secrets_only_does_not_rewrite_existing_scaffold(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "existing"
            output_dir.mkdir()
            marker = output_dir / "marker.txt"
            marker.write_text("keep me", encoding="utf-8")
            buffer = io.StringIO()

            with contextlib.redirect_stdout(buffer):
                result = self.module.main(
                    [
                        "owner/existing",
                        "--output",
                        str(output_dir),
                        "--set-secrets",
                        "--secrets-only",
                        "--dry-run",
                    ]
                )

            self.assertEqual(result, 0)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep me")
            self.assertFalse((output_dir / "package.json").exists())
            self.assertIn("skipped file generation", buffer.getvalue())


    def test_render_text_replaces_all_placeholders(self):
        config = self.module.ScaffoldConfig(
            repo_slug="acme/widget",
            repo_name="widget",
            worker_name="widget-worker",
            output_dir=Path("/tmp/unused"),
            compatibility_date="2026-05-25",
            node_version="22",
        )
        source = (
            "name=vibe-worker-template slug=__REPO_SLUG__ name2=__REPO_NAME__ "
            "worker=__WORKER_NAME__ date=__COMPATIBILITY_DATE__ node=__NODE_VERSION__"
        )
        rendered = self.module.render_text(source, config)

        self.assertEqual(
            rendered,
            "name=widget slug=acme/widget name2=widget worker=widget-worker "
            "date=2026-05-25 node=22",
        )
        for token in ("vibe-worker-template", "__REPO_SLUG__", "__REPO_NAME__",
                      "__WORKER_NAME__", "__COMPATIBILITY_DATE__", "__NODE_VERSION__"):
            self.assertNotIn(token, rendered)

    def test_quote_arg_handles_spaces_and_quotes(self):
        quote = self.module.quote_arg
        self.assertEqual(quote("simple"), "simple")
        self.assertEqual(quote("with space"), "'with space'")
        self.assertEqual(quote("with'quote"), "'with'\"'\"'quote'")
        self.assertEqual(quote(""), "''")

    def test_require_tool_includes_install_hint(self):
        with mock.patch.object(self.module.shutil, "which", return_value=None), \
             mock.patch.dict(self.module.WINDOWS_TOOL_PATHS, {"gh": ()}):
            with self.assertRaises(RuntimeError) as ctx:
                self.module.require_tool("gh")
        message = str(ctx.exception)
        self.assertIn("gh", message)
        self.assertIn("https://cli.github.com/", message)

    def test_require_tool_succeeds_when_tool_present(self):
        with mock.patch.object(self.module.shutil, "which", return_value="/usr/bin/git"):
            self.assertEqual(self.module.require_tool("git"), "/usr/bin/git")

    def test_tool_path_falls_back_to_known_windows_location(self):
        fake_path = Path("C:/Program Files/GitHub CLI/gh.exe")
        with mock.patch.object(self.module.shutil, "which", return_value=None), \
             mock.patch.dict(self.module.WINDOWS_TOOL_PATHS, {"gh": (fake_path,)}), \
             mock.patch.object(Path, "exists", return_value=True):
            self.assertEqual(self.module.tool_path("gh"), str(fake_path))

    def test_read_secret_value_prefers_environment(self):
        with mock.patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "from-env"}, clear=False):
            self.assertEqual(self.module.read_secret_value("CLOUDFLARE_ACCOUNT_ID"), "from-env")

    def test_read_secret_value_rejects_empty_prompt(self):
        env = {k: v for k, v in os.environ.items() if k != "CLOUDFLARE_API_TOKEN"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(self.module.getpass, "getpass", return_value=""):
            with self.assertRaises(RuntimeError) as ctx:
                self.module.read_secret_value("CLOUDFLARE_API_TOKEN")
        self.assertIn("cannot be empty", str(ctx.exception))

    def test_environment_secrets_adds_env_flag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "envsec"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                result = self.module.main(
                    [
                        "owner/envsec",
                        "--output",
                        str(output_dir),
                        "--set-secrets",
                        "--environment-secrets",
                        "production",
                        "--dry-run",
                    ]
                )
            self.assertEqual(result, 0)
            output = buffer.getvalue()
            self.assertIn("--env production", output)

    def test_doctor_reports_environment(self):
        buffer = io.StringIO()
        # Force gh to be missing so we get a deterministic ISSUES FOUND path.
        original_which = self.module.shutil.which

        def fake_which(name, *args, **kwargs):
            if name == "gh":
                return None
            return original_which(name, *args, **kwargs)

        with mock.patch.object(self.module.shutil, "which", side_effect=fake_which), \
             mock.patch.dict(self.module.WINDOWS_TOOL_PATHS, {"gh": ()}):
            result = self.module.run_doctor(stream=buffer)

        output = buffer.getvalue()
        self.assertEqual(result, 1)
        self.assertIn("vibe doctor", output)
        self.assertIn("python:", output)
        self.assertIn("Required CLIs:", output)
        self.assertIn("gh", output)
        self.assertIn("MISSING", output)
        self.assertIn("Worker template:", output)
        self.assertIn("ISSUES FOUND", output)
        # Never leak the actual value of a present env var.
        token_val = os.environ.get("CLOUDFLARE_API_TOKEN")
        if token_val:
            self.assertNotIn(token_val, output)

    def test_doctor_exit_zero_when_template_intact_and_clis_present(self):
        buffer = io.StringIO()
        with mock.patch.object(self.module.shutil, "which",
                               return_value="/fake/path"), \
             mock.patch.object(self.module.subprocess, "run",
                               return_value=mock.Mock(returncode=0, stderr="")):
            result = self.module.run_doctor(stream=buffer)
        output = buffer.getvalue()
        self.assertEqual(result, 0, msg=output)
        self.assertIn("status: OK", output)

    def test_doctor_flag_via_argparse_does_not_require_repo(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = self.module.main(["--doctor"])
        # Exit code mirrors run_doctor's return; on this machine gh may or
        # may not exist, so we only assert it ran and printed the report.
        self.assertIn("vibe doctor", buffer.getvalue())
        self.assertIn(result, (0, 1))

    def test_main_without_repo_and_without_doctor_errors(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.module.main([])

    def test_main_failure_points_to_doctor_and_troubleshooting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "busy"
            output_dir.mkdir()
            (output_dir / "existing.txt").write_text("busy", encoding="utf-8")
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                result = self.module.main(["owner/busy", "--output", str(output_dir)])

            output = stderr.getvalue()
            self.assertEqual(result, 1)
            self.assertIn("Self-diagnosis:", output)
            self.assertIn("--doctor", output)
            self.assertIn("troubleshooting.md", output)


if __name__ == "__main__":
    unittest.main()
