import os
import shutil
import tempfile
from getpass import getpass

import pytest
import requests

# The default Boardwalkd url for testing via a pytest harness
boardwalkd_url = "http://localhost:8888"


@pytest.fixture(scope="session", autouse=True)
def clear_workspaces_before_running_tests():
    """Fixture to clear the boardwalkd workspace state before execution of the pytest run."""
    requests.post(url=boardwalkd_url + "/develop/clear_all_workspaces")
    yield


@pytest.fixture(scope="package")
def get_become_password_file_path():
    """Returns a pathlib.Path object with the supplied BECOME/sudo password written to it.

    Required to run the Workspace tests.
    """
    val = getpass(prompt="\nBECOME password: ")
    with tempfile.NamedTemporaryFile(delete_on_close=False, mode="w") as file:
        file.write(val)
        file.close()
        yield file.name


@pytest.fixture
def use_isolated_boardwalk_directory(tmp_path_factory, request):
    dir = tmp_path_factory.mktemp("boardwalk")
    test_dir = os.path.dirname(__file__)
    shutil.copytree(src=os.path.join(test_dir, "server-client"), dst=dir, dirs_exist_ok=True)
    os.chdir(dir)
    return dir


@pytest.fixture
def anyio_backend():
    return "asyncio"
