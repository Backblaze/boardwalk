import pytest

from boardwalk import Job, PlaybookJob, TaskJob, Workflow, WorkspaceConfig
from boardwalk.manifest import JobTypes, get_boardwalkd_url


class EmptyWorkflow(Workflow):
    def jobs(self):
        return ()


@pytest.mark.parametrize(
    ("job_class", "job_type"),
    [
        pytest.param(TaskJob, JobTypes.TASK),
        pytest.param(
            Job,
            JobTypes.TASK,
            marks=pytest.mark.filterwarnings("ignore:The job type Job is deprecated:DeprecationWarning"),
        ),
        pytest.param(PlaybookJob, JobTypes.PLAYBOOK),
    ],
)
def test_verify_job_types_match_expected_types(job_class, job_type):
    job = job_class()
    assert job_type == job.job_type


@pytest.mark.parametrize(
    ("job_class", "function_name"),
    [
        pytest.param(TaskJob, "tasks"),
        pytest.param(Job, "tasks"),
        pytest.param(PlaybookJob, "playbooks"),
        pytest.param(PlaybookJob, "tasks"),
    ],
)
def test_verify_job_classes_have_expected_task_functions(job_class, function_name):
    # The Job type needs to have the expected function name, and also be a callable function
    assert hasattr(job_class, function_name)
    assert callable(eval(f"{job_class.__name__}.{function_name}"))


def test_using_not_differentiated_Job_class_warns_about_deprecation():
    with pytest.warns(
        DeprecationWarning,
        match="The job type Job is deprecated, and will be removed in a future release. Use TaskJob or PlaybookJob, as appropriate.",
    ):

        class TestJob(Job):
            def tasks(self):
                return [{"ansible.builtin.debug": {"msg": "Hello, Boardwalk!"}}]

        TestJob()


def test_workspace_config_accepts_explicit_ui_group():
    cfg = WorkspaceConfig(
        host_pattern="localhost",
        workflow=EmptyWorkflow(),
        ui_group="alpha",
    )

    assert cfg.ui_group == "alpha"
    assert cfg.ui_group_inventory_var == ""


def test_workspace_config_accepts_generic_inventory_var_grouping():
    cfg = WorkspaceConfig(
        host_pattern="localhost",
        workflow=EmptyWorkflow(),
        ui_group_inventory_var="site_group",
    )

    assert cfg.ui_group == ""
    assert cfg.ui_group_inventory_var == "site_group"


def test_get_boardwalkd_url_prefers_environment_override(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BOARDWALKD_URL", "http://localhost:8888/")

    assert get_boardwalkd_url() == "http://localhost:8888/"
