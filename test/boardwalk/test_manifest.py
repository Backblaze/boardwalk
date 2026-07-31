import pytest

from boardwalk import Job, PlaybookJob, TaskJob, Workflow, WorkspaceConfig
from boardwalk.manifest import JobTypes


@pytest.fixture
def empty_workflow_class_fixture() -> type[Workflow]:
    """Having the EmptyWorkflow directly instantiated seems to be breaking things in strange ways;
    it works if its defined in a fixture to return the class, so we'll use that"""

    class EmptyWorkflow(Workflow):
        def jobs(self):
            return ()

    return EmptyWorkflow


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


@pytest.mark.filterwarnings("ignore:The job type Job is deprecated")
@pytest.mark.parametrize(
    ("job_class"),
    [
        pytest.param(TaskJob),
        pytest.param(PlaybookJob),
        pytest.param(Job),
    ],
)
def test_jobs_definining_options_have_options_existing_in_instantiated_class(job_class) -> None:
    test_options = {"option_one": 123, "option_omega": "xyz"}

    class TestJobClass(job_class):
        pass

    obj = TestJobClass(options=test_options)
    assert obj.options == test_options


@pytest.mark.filterwarnings("ignore:The job type Job is deprecated")
@pytest.mark.parametrize(
    ("job_class"),
    [
        pytest.param(TaskJob),
        pytest.param(PlaybookJob),
        pytest.param(Job),
    ],
)
@pytest.mark.parametrize(
    ("required_options_tuple", "options_provided", "expected_missing_options"),
    [
        pytest.param(("required_one",), ("some_different_option",), ("required_one",)),
        pytest.param(("required_one", "required_two"), ("required_one",), ("required_two",)),
        pytest.param(
            ("required_one", "required_two", "required_three"), ("required_one", "required_two"), ("required_three",)
        ),
    ],
)
def test_jobs_definining_required_options_raise_when_options_not_provided(
    job_class, required_options_tuple: tuple[str], options_provided: tuple[str], expected_missing_options: tuple[str]
) -> None:
    test_options = {k: "some_value" for k in options_provided}

    class TestJobClass(job_class):
        def required_options(self) -> tuple[str, ...]:
            return required_options_tuple

    with pytest.raises(ValueError) as err:
        _obj = TestJobClass(options=test_options)

    for missing_option in expected_missing_options:
        assert missing_option in str(err)


@pytest.mark.filterwarnings("ignore:The job type Job is deprecated")
@pytest.mark.parametrize(
    ("job_class"),
    [
        pytest.param(TaskJob),
        pytest.param(PlaybookJob),
        pytest.param(Job),
    ],
)
def test_jobs_definining_required_options_instantiates_correctly_when_provided(job_class) -> None:
    test_options = {"required_option": "value", "optional_option": "some_other_value"}

    class TestJobClass(job_class):
        def required_options(self) -> tuple[str, ...]:
            return ("required_option",)

    obj = TestJobClass(options=test_options)
    assert obj.options == test_options


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
    class TestJob(Job):
        def tasks(self):
            return [{"ansible.builtin.debug": {"msg": "Hello, Boardwalk!"}}]

    with pytest.warns(
        DeprecationWarning,
        match="The job type Job is deprecated, and will be removed in a future release. Use TaskJob or PlaybookJob, as appropriate.",
    ):
        TestJob()


def test_workspace_config_accepts_explicit_ui_group(empty_workflow_class_fixture):
    cfg = WorkspaceConfig(
        host_pattern="localhost",
        workflow=empty_workflow_class_fixture(),
        ui_group="alpha",
    )

    assert cfg.ui_group == "alpha"
    assert cfg.ui_group_inventory_var == ""


def test_workspace_config_accepts_generic_inventory_var_grouping(empty_workflow_class_fixture):
    cfg = WorkspaceConfig(
        host_pattern="localhost",
        workflow=empty_workflow_class_fixture(),
        ui_group_inventory_var="site_group",
    )

    assert cfg.ui_group == ""
    assert cfg.ui_group_inventory_var == "site_group"
