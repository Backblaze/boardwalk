import pytest
from click.testing import CliRunner

from boardwalk.cli_workspace import workspace as cli


@pytest.mark.usefixtures("use_isolated_boardwalk_directory")
@pytest.mark.parametrize(
    ["command_arguments", "workspace_subset_to_check"],
    [
        # Testing: `boardwalk workspace list`
        pytest.param(
            ["list"],
            ["ShouldSucceedTestWorkspace", "ShouldFailTestWorkspace", "DumpHostvarsWorkspace"],
            id="boardwalk_workspace_list",
        ),
        # Testing: boardwalk workspace list shouldsucc
        pytest.param(
            ["list"],
            [
                "ShouldSucceedTestWorkspace",
                "ShouldSucceedMixedJobTypesWorkspace",
                "ShouldSucceedPlaybookExecutionTestWorkspace",
            ],
            id="boardwalk_workspace_list_shouldsucc",
        ),
    ],
)
def test_workspace_list(command_arguments: list[str], workspace_subset_to_check: list[str]):
    """Test that `boardwalk workspace list` command returns the expected content"""
    runner = CliRunner()
    result = runner.invoke(cli=cli, args=command_arguments)
    assert result.exit_code == 0
    assert set(workspace_subset_to_check).issubset(result.stdout.splitlines())


@pytest.mark.usefixtures("use_isolated_boardwalk_directory", "propagate_loguru_logs_to_pytest")
@pytest.mark.parametrize(
    ["command_arguments", "warning_on_stderr_expected"],
    [
        # Testing: A dynamic Workspace with the `__module__` defined should return the proper source file
        pytest.param(
            ["list", "--config", "DynamicallyGeneratedWorkspaceBoundToPylibModule"],
            False,
            id="dynamic_ws_with_properly_bound_module",
        ),
        # Testing: A dynamic Workspace without the `__module__` defined should return a notice
        pytest.param(
            ["list", "--config", "DynamicallyGeneratedWorkspaceNotBoundToPylibModule"],
            True,
            id="dynamic_ws_with_improperly_bound_module",
        ),
    ],
)
def test_workspace_list_alerts_if_class_abstract(
    command_arguments: list[str], warning_on_stderr_expected: bool, caplog: pytest.LogCaptureFixture
):
    """Ensure that dynamically generated Workspaces -- see test/server-client/pylib/dynamic_workspace_construction.py -- will
    result in `boardwalk workspace list --config` showing a notice that the exact source module isn't able to be ascertained."""
    runner = CliRunner()
    result = runner.invoke(cli=cli, args=command_arguments)

    assert result.exit_code == 0
    if warning_on_stderr_expected:
        assert any(
            [
                f"Workspace {command_arguments[2]} seems to be sourced from abc.py." in message
                for message in caplog.messages
            ]
        )
        assert any(
            [
                "One or more classes couldn't have their exact source module identified" in message
                for message in caplog.messages
            ]
        )
    else:
        assert len(caplog.messages) == 0


@pytest.mark.usefixtures("use_isolated_boardwalk_directory")
@pytest.mark.parametrize(
    ["command_arguments", "expected_strings_in_stdout"],
    [
        # Testing: `boardwalk workspace list --config ShouldSucceedPlaybookExecutionTestWorkspace`
        pytest.param(
            ["list", "--config", "ShouldSucceedPlaybookExecutionTestWorkspace"],
            ["Workspace Source Module", "Default Sort Order", "Workflow", "ShouldSucceedPlaybookExecutionTestWorkflow"],
            id="boardwalk_workspace_list_--config",
        ),
        # Testing: `boardwalk workspace list --jobs ShouldSucceedPlaybookExecutionTestWorkspace`
        pytest.param(
            ["list", "--jobs", "ShouldSucceedPlaybookExecutionTestWorkspace"],
            [
                "Workflow",
                "ShouldSucceedPlaybookExecutionTestWorkflow",
                "Main Workflow Jobs",
                "ShouldSucceedPlaybookExecutionTestJob",
                "Exit Workflow Jobs",
                "TestJob",
            ],
            id="boardwalk_workspace_list_--jobs",
        ),
        # Testing: `boardwalk workspace list --config --jobs ShouldSucceedPlaybookExecutionTestWorkspace`
        pytest.param(
            ["list", "--config", "--jobs", "ShouldSucceedPlaybookExecutionTestWorkspace"],
            [
                "Workspace Source Module",
                "Default Sort Order",
                "Workflow",
                "ShouldSucceedPlaybookExecutionTestWorkflow",
                "Main Workflow Jobs",
                "ShouldSucceedPlaybookExecutionTestJob",
                "Exit Workflow Jobs",
                "TestJob",
            ],
            id="boardwalk_workspace_list_--config_--jobs",
        ),
    ],
)
def test_workspace_list_config_and_jobs(command_arguments: list[str], expected_strings_in_stdout: list[str]):
    """Test that `boardwalk workspace list` command returns the expected content"""
    runner = CliRunner()
    result = runner.invoke(cli=cli, args=command_arguments)
    assert result.exit_code == 0
    for expected_item in expected_strings_in_stdout:
        assert expected_item in result.stdout
