import os
import signal
from pathlib import Path
from typing import Any

import pytest
from anyio import create_task_group, fail_after, open_process
from anyio.streams.text import TextReceiveStream


@pytest.mark.anyio
@pytest.mark.skipif(condition="CI" in os.environ, reason="Not yet able to execute non-interactively.")
@pytest.mark.parametrize(
    ("workspace_name", "failure_expected", "failure_msg"),
    [
        pytest.param("ShouldSucceedTestWorkspace", False, ""),
        pytest.param("ShouldSucceedPlaybookExecutionTestWorkspace", False, ""),
        pytest.param("UITestVeryVeryLongWorkSpaceNameWorkspace", False, ""),
        pytest.param(
            "ShouldFailTestWorkspace",
            True,
            "runner_on_failed: ansible.builtin.fail: ansible.builtin.fail: 127.0.0.1: Task failed successfully.: fatal: [127.0.0.1]: FAILED! => changed=false",
        ),
        pytest.param(
            "ShouldFailPlaybookExecutionTestWorkspace",
            True,
            "runner_on_failed: Fail: ansible.builtin.fail: 127.0.0.1: Task failed successfully!: fatal: [127.0.0.1]: FAILED! => changed=false",
        ),
    ],
)
async def test_development_workspaces(
    workspace_name: str,
    failure_expected: bool,
    failure_msg: str,
    get_become_password_file_path: Path,
    use_isolated_boardwalk_directory,
):
    envvars: dict[str, Any] = {
        "ANSIBLE_BECOME_PASSWORD_FILE": get_become_password_file_path,
        "BOARDWALK_VERBOSITY": "2",
    }
    new_environ = os.environ | envvars
    new_environ.pop("ANSIBLE_BECOME_ASK_PASS", None)
    commands: tuple[str, ...] = (
        f"boardwalk -vv workspace use {workspace_name}",
        "boardwalk init",
        "boardwalk run",
    )
    output_stdout = []
    output_stderr = []
    os.chdir(use_isolated_boardwalk_directory)
    async with create_task_group():
        for command in commands:
            with fail_after(delay=90) as scope:
                async with await open_process(command=command, env=new_environ) as process:
                    async for text in TextReceiveStream(process.stdout):  # type:ignore
                        output_stdout.append(text)
                        if failure_expected and "Waiting for release before continuing" in text:
                            process.send_signal(signal.SIGINT)
                    async for text in TextReceiveStream(process.stderr):  # type:ignore
                        output_stderr.append(text)

        assert not scope.cancelled_caught

    if failure_expected:
        assert failure_msg in "".join(output_stdout)
    else:
        assert process.returncode == 0
