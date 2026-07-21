import os
import platform
import re
import signal
import subprocess
from pathlib import Path
from typing import Any

import pytest
from anyio import create_task_group, fail_after, open_process
from anyio.streams.text import TextReceiveStream


async def execute_boardwalk_workspace_test(
    workspace_name: str,
    failure_expected: bool,
    failure_msg: str,
    get_become_password_file_path: Path | None,
    use_isolated_boardwalk_directory,
):
    # API_LOGIN_URI_REGEX = re.compile(r"http://localhost:\d{1,5}/api/auth/login\?id=[a-z0-9]{16}")
    WORKSPACE_CAUGHT_REGEX = re.compile(
        rf"The {workspace_name} workspace is remotely caught on .+ Waiting for release before continuing"
    )
    envvars: dict[str, Any] = {
        # "ANSIBLE_BECOME_PASSWORD_FILE": get_become_password_file_path,
        # "BOARDWALK_RUN_OPEN_BROWSER_FOR_API_LOGIN": "False",
        "BOARDWALK_VERBOSITY": "2",
    }
    if "CI" not in os.environ:
        envvars["ANSIBLE_BECOME_PASSWORD_FILE"] = get_become_password_file_path
    new_environ = os.environ | envvars
    new_environ.pop("ANSIBLE_BECOME_ASK_PASS", None)
    commands: tuple[str, ...] = (
        f"boardwalk -vv workspace use {workspace_name}",
        "boardwalk init",
        "boardwalk run",
    )
    output_stdout = []
    os.chdir(use_isolated_boardwalk_directory)
    async with create_task_group():
        for command in commands:
            with fail_after(delay=90) as scope:
                async with await open_process(command=command, env=new_environ, stderr=subprocess.STDOUT) as process:
                    async for text in TextReceiveStream(process.stdout):  # type:ignore
                        # To allow for reading what was received, if the test ends up failing.
                        print(text, end="")
                        output_stdout.append(text)
                        # TODO: Figure out how to get async API login working?
                        # Or should we just have a flag to optionally disable
                        # API authentication if (and only if) in development
                        # mode altogether?
                        # if match := re.search(API_LOGIN_URI_REGEX, text):
                        if re.search(WORKSPACE_CAUGHT_REGEX, text):
                            process.send_signal(signal.SIGINT)
        assert not scope.cancelled_caught

    if failure_expected:
        assert failure_msg in "".join(output_stdout)
    else:
        assert "Host completed successfully; wrapping up" in "".join(output_stdout)
        assert process.returncode == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("workspace_name", "failure_expected", "failure_msg"),
    [
        pytest.param("ShouldSucceedTestWorkspace", False, "", id="ShouldSucceedTestWorkspace"),
        pytest.param(
            "ShouldSucceedPlaybookExecutionTestWorkspace", False, "", id="ShouldSucceedPlaybookExecutionTestWorkspace"
        ),
        pytest.param(
            "UITestVeryVeryLongWorkSpaceNameWorkspace", False, "", id="UITestVeryVeryLongWorkSpaceNameWorkspace"
        ),
        # Next four are from test/server-client/pylib/regression_bz_svreng_608.py
        pytest.param(
            "TaskJobWithOptionsShouldSucceedWorkspace", False, "", id="TaskJobWithOptionsShouldSucceedWorkspace"
        ),
        pytest.param(
            "PlaybookJobWithOptionsShouldSucceedWorkspace", False, "", id="PlaybookJobWithOptionsShouldSucceedWorkspace"
        ),
        pytest.param(
            "TaskJobWithPreconditionsShouldSucceedIfHostIsMacOSXWorkspace",
            False,
            "",
            marks=pytest.mark.skipif(
                condition="macos" not in platform.platform().lower(),
                reason="Workspace's preconditions depends on the host being MacOS.",
            ),
            id="TaskJobWithPreconditionsShouldSucceedIfHostIsMacOSXWorkspace",
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
            id="TaskJobWithPreconditionsShouldBeSkippedIfHostIsMacOSXWorkspace",
        ),
        pytest.param(
            "ShouldFailTestWorkspace",
            True,
            "Task failed successfully",
            id="ShouldFailTestWorkspace",
        ),
        pytest.param(
            "ShouldFailPlaybookExecutionTestWorkspace",
            True,
            "Task failed successfully",
            id="ShouldFailPlaybookExecutionTestWorkspace",
        ),
    ],
)
@pytest.mark.usefixtures("spawn_boardwalkd_server_and_maybe_clear_workspaces")
@pytest.mark.integration
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
@pytest.mark.usefixtures("spawn_boardwalkd_server_and_maybe_clear_workspaces")
@pytest.mark.integration
async def test_ensure_remote_workflow_success_state_false_during_workflow_execution(
    get_become_password_file_path: Path,
    use_isolated_boardwalk_directory,
    workspace_name: str = "RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionWorkspace",
    failure_expected: bool = False,
    failure_msg: str = "",
):
    # TODO: We really should try to see if we can get the tests running properly
    # in the context of pytest; right now this test is twice as long as it needs
    # to be -- given that we need to ensure the remote state is correctly set up
    # -- since if we could override boardwalk.host.Host.remote_state_path to a
    # temp file, we could give it a minified state already pre-configured, like:
    # {"workspaces":{"RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionWorkspace":{"workflow":{"started":true,"succeeded":true}}}}
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
