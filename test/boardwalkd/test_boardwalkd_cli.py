from importlib.metadata import version as lib_version

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
