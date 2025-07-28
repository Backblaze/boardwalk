import os
import platform
import re
import signal
from pathlib import Path
from typing import Any

import pytest
from anyio import create_task_group, fail_after, open_process
from anyio.streams.text import TextReceiveStream


async def execute_boardwalk_workspace_test(
    workspace_name: str,
    failure_expected: bool,
    failure_msg: str,
    get_become_password_file_path: Path,
    use_isolated_boardwalk_directory,
):
    WORKSPACE_CAUGHT_REGEX = re.compile(
        rf"The {workspace_name} workspace is remotely caught on .+ Waiting for release before continuing"
    )
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
                        # To allow for reading what was received, if the test ends up failing.
                        print(text)
                        output_stdout.append(text)
                        if re.search(WORKSPACE_CAUGHT_REGEX, text):
                            process.send_signal(signal.SIGINT)
                    async for text in TextReceiveStream(process.stderr):  # type:ignore
                        print(text)
                        output_stderr.append(text)
        assert not scope.cancelled_caught

    if failure_expected:
        assert failure_msg in "".join(output_stdout)
    else:
        assert "Host completed successfully; wrapping up" in "".join(output_stdout)
        assert process.returncode == 0


@pytest.mark.anyio
@pytest.mark.skipif(condition="CI" in os.environ, reason="Not yet able to execute non-interactively.")
@pytest.mark.parametrize(
    ("workspace_name", "failure_expected", "failure_msg"),
    [
        pytest.param("ShouldSucceedTestWorkspace", False, ""),
        pytest.param("ShouldSucceedPlaybookExecutionTestWorkspace", False, ""),
        pytest.param("UITestVeryVeryLongWorkSpaceNameWorkspace", False, ""),
        # Next four are from test/server-client/pylib/regression_bz_svreng_608.py
        pytest.param("TaskJobWithOptionsShouldSucceedWorkspace", False, ""),
        pytest.param("PlaybookJobWithOptionsShouldSucceedWorkspace", False, ""),
        pytest.param(
            "TaskJobWithPreconditionsShouldSucceedIfHostIsMacOSXWorkspace",
            False,
            "",
            marks=pytest.mark.skipif(
                condition="macos" not in platform.platform().lower(),
                reason="Workspace's preconditions depends on the host being MacOS.",
            ),
        ),
        # Technically this one doesn't _fail_, but this lets it fit neatly into the parameterized tests.
        pytest.param(
            "TaskJobWithPreconditionsShouldBeSkippedIfHostIsMacOSXWorkspace",
            True,
            "No hosts meet preconditions",
            marks=pytest.mark.skipif(
                condition="macos" not in platform.platform().lower(),
                reason="Workspace's preconditions depends on the host being MacOS.",
            ),
        ),
        pytest.param(
            "ShouldFailTestWorkspace",
            True,
            "Task failed successfully",
        ),
        pytest.param(
            "ShouldFailPlaybookExecutionTestWorkspace",
            True,
            "Task failed successfully",
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
    await execute_boardwalk_workspace_test(
        workspace_name=workspace_name,
        failure_msg=failure_msg,
        failure_expected=failure_expected,
        get_become_password_file_path=get_become_password_file_path,
        use_isolated_boardwalk_directory=use_isolated_boardwalk_directory,
    )


@pytest.mark.anyio
@pytest.mark.skipif(condition="CI" in os.environ, reason="Not yet able to execute non-interactively.")
async def test_ensure_remote_workflow_success_state_false_during_workflow_execution(
    get_become_password_file_path: Path,
    use_isolated_boardwalk_directory,
    workspace_name: str = "RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionWorkspace",
    failure_expected: bool = False,
    failure_msg: str = "",
):
    # This first execution ensures the Workspace completes at least once (ensuring the state is set)
    await execute_boardwalk_workspace_test(
        workspace_name=workspace_name,
        failure_msg=failure_msg,
        failure_expected=failure_expected,
        get_become_password_file_path=get_become_password_file_path,
        use_isolated_boardwalk_directory=use_isolated_boardwalk_directory,
    )
    # This second execution actually verifies that the succeeded state is False
    await execute_boardwalk_workspace_test(
        workspace_name=workspace_name,
        failure_msg=failure_msg,
        failure_expected=failure_expected,
        get_become_password_file_path=get_become_password_file_path,
        use_isolated_boardwalk_directory=use_isolated_boardwalk_directory,
    )
