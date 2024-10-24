import pytest

from boardwalk import Job


def test_using_not_differentiated_Job_class_warns_about_deprecation():
    with pytest.warns(
        DeprecationWarning,
        match="The job type Job is deprecated, and will be removed in a future release. Use TaskJob or PlaybookJob, as appropriate.",
    ):

        class TestJob(Job):
            def tasks(self):
                return [{"ansible.builtin.debug": {"msg": "Hello, Boardwalk!"}}]

        TestJob()
