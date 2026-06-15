from importlib.metadata import version as lib_version
from unittest.mock import AsyncMock, patch

import pytest
from anyio import create_task_group, fail_after, run_process
from click.testing import CliRunner

from boardwalkd import cli


def test_version():
    """Running `boardwalkd version` should return the version of `boardwalk`."""
    runner = CliRunner()
    result = runner.invoke(cli=cli.version)
    assert result.output.strip() == lib_version("boardwalk")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("msg", "options", "expected_rc"),
    [
        ("Missing required parameters to serve boardwalkd: --url, --host-header-pattern, --port/--tls-port", [""], 2),
        (
            "Missing required parameters to serve boardwalkd: --url, --port/--tls-port",
            [r'--host-header-pattern="(localhost|127\.0\.0\.1)"'],
            2,
        ),  # type: ignore
        (
            "Missing required parameters to serve boardwalkd: --port/--tls-port",
            [r'--host-header-pattern="(localhost|127\.0\.0\.1)"', '--url="http://localhost:8888"'],
            2,
        ),  # type: ignore
    ],
)
async def test_incomplete_serve_command(
    msg: str, options: list[str], expected_rc: int, command: list[str] = ["boardwalkd", "serve"]
):
    """Running `boardwalkd serve` without the required parameters shouldn't succeed."""
    command.extend(options)
    async with create_task_group():
        with fail_after(delay=10) as scope:
            result = await run_process(command=command, check=False)
        assert not scope.cancelled_caught
    assert result.returncode == expected_rc, msg


def test_serve_passes_theme_options_to_server_run():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with patch("boardwalkd.cli.run", new_callable=AsyncMock) as run_mock:
            result = runner.invoke(
                cli=cli.serve,
                args=[
                    "--host-header-pattern=(localhost|127\\.0\\.0\\.1)",
                    "--port=8888",
                    "--url=http://localhost:8888",
                    "--theme-static-path=.",
                    "--theme-css-url=/theme-static/boardwalkd-custom.css",
                    "--theme-logo-url=/theme-static/custom-logo.svg",
                    "--theme-logo-alt=Example",
                    "--theme-brand-name=Boardwalk",
                    "--jenkins-job-url=https://ci.example/job/boardwalk/",
                ],
            )

    assert result.exit_code == 0
    kwargs = run_mock.call_args.kwargs
    assert kwargs["theme_static_path"] == "."
    assert kwargs["theme_css_url"] == "/theme-static/boardwalkd-custom.css"
    assert kwargs["theme_logo_url"] == "/theme-static/custom-logo.svg"
    assert kwargs["theme_logo_alt"] == "Example"
    assert kwargs["theme_brand_name"] == "Boardwalk"
    assert kwargs["jenkins_job_url"] == "https://ci.example/job/boardwalk/"


def test_serve_passes_develop_snapshot_to_server_run():
    runner = CliRunner()
    with runner.isolated_filesystem():
        open("snapshot.json", "w").write('{"workspaces": []}')
        with patch("boardwalkd.cli.run", new_callable=AsyncMock) as run_mock:
            result = runner.invoke(
                cli=cli.serve,
                args=[
                    "--develop",
                    "--develop-snapshot=snapshot.json",
                    "--host-header-pattern=(localhost|127\\.0\\.0\\.1)",
                    "--port=8888",
                    "--url=http://localhost:8888",
                ],
            )

    assert result.exit_code == 0
    assert run_mock.call_args.kwargs["develop_snapshot_path"] == "snapshot.json"


def test_serve_rejects_develop_snapshot_without_develop():
    runner = CliRunner()
    with runner.isolated_filesystem():
        open("snapshot.json", "w").write('{"workspaces": []}')
        result = runner.invoke(
            cli=cli.serve,
            args=[
                "--develop-snapshot=snapshot.json",
                "--host-header-pattern=(localhost|127\\.0\\.0\\.1)",
                "--port=8888",
                "--url=http://localhost:8888",
            ],
        )

    assert result.exit_code != 0
    assert "--develop-snapshot requires --develop" in result.output


def test_sanitize_status_snapshot_command_writes_redacted_snapshot():
    runner = CliRunner()
    with runner.isolated_filesystem():
        open("raw.json", "w").write(
            """
            {
              "workspaces": [{
                "name": "real_workspace",
                "semaphores": {"caught": true, "has_mutex": true},
                "details": {
                  "current_host": "node-alpha-a",
                  "ui_group": "alpha",
                  "worker_hostname": "worker-prod-01",
                  "worker_username": "operator-a",
                  "worker_connected": true
                },
                "last_seen": "2026-06-03T00:00:00+00:00"
              }]
            }
            """
        )

        result = runner.invoke(
            cli=cli.sanitize_status_snapshot,
            args=["raw.json", "sanitized.json", "--captured-at=2026-06-03T00:00:03+00:00"],
        )
        text = open("sanitized.json").read()

    assert result.exit_code == 0
    assert "snapshot_alpha_001" in text
    assert "real_workspace" not in text
    assert "snapshot-host-alpha-001" in text
    assert "node-alpha-a" not in text
    assert "worker-prod-01" not in text
    assert "operator-a" not in text


def test_sanitize_status_snapshot_command_can_preserve_identifiers_for_private_replay():
    runner = CliRunner()
    with runner.isolated_filesystem():
        open("raw.json", "w").write(
            """
            {
              "workspaces": [{
                "name": "real_workspace",
                "semaphores": {"caught": true, "has_mutex": true},
                "details": {
                  "current_host": "node-alpha-a",
                  "host_pattern": "nodes_alpha",
                  "worker_hostname": "worker-prod-01",
                  "worker_username": "operator-a",
                  "worker_connected": true
                },
                "last_seen": "2026-06-03T00:00:00+00:00"
              }]
            }
            """
        )

        result = runner.invoke(
            cli=cli.sanitize_status_snapshot,
            args=[
                "raw.json",
                "private-replay.json",
                "--captured-at=2026-06-03T00:00:03+00:00",
                "--preserve-identifiers",
            ],
        )
        text = open("private-replay.json").read()

    assert result.exit_code == 0
    assert "real_workspace" in text
    assert "node-alpha-a" in text
    assert "worker-prod-01" in text
    assert "operator-a" in text
    assert "alpha" in text


def test_sanitize_status_snapshot_command_can_enrich_groups_from_inventory_json():
    runner = CliRunner()
    with runner.isolated_filesystem():
        open("raw.json", "w").write(
            """
            {
              "workspaces": [{
                "name": "storage_workspace",
                "semaphores": {"caught": true, "has_mutex": true},
                "details": {
                  "host_pattern": "storage_001:!storage_nonprod",
                  "worker_connected": true
                },
                "last_seen": "2026-06-03T00:00:00+00:00"
              }]
            }
            """
        )
        open("inventory.json", "w").write(
            """
            {
              "_meta": {"hostvars": {}},
              "storage_001": {"hosts": ["node-alpha-a"]},
              "storage_alpha": {"children": ["storage_001"]}
            }
            """
        )

        result = runner.invoke(
            cli=cli.sanitize_status_snapshot,
            args=[
                "raw.json",
                "private-replay.json",
                "--captured-at=2026-06-03T00:00:03+00:00",
                "--preserve-identifiers",
                "--inventory-json=inventory.json",
            ],
        )
        text = open("private-replay.json").read()

    assert result.exit_code == 0
    assert "storage_workspace" in text
    assert '"ui_group": "alpha"' in text
