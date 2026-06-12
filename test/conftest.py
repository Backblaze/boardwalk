import asyncio
import os
import re
import shutil
import tempfile
from getpass import getpass

import pytest
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

# The default Boardwalkd url for testing via a pytest harness
boardwalkd_standard_dev_port = 8888
boardwalkd_url = "http://localhost:{port}"


@pytest.fixture(scope="function")
async def spawn_boardwalkd_server(anyio_backend, free_tcp_port: int):
    """Spawns a `boardwalkd` server if one is not currently running.

    If one is spawned, a free port is selected and the Boardwalkfile.py
    will use the selected port."""
    try:
        http_client = AsyncHTTPClient()
        url = boardwalkd_url.format(port=boardwalkd_standard_dev_port)
        await http_client.fetch(url, raise_error=False)
        print(f"Using existing boardwalkd instance @ {url}")
        yield url
        return
    except ConnectionRefusedError:
        # If we hit a connection error, no server is up; so let's launch our own below
        from boardwalkd.server import run as boardwalkd_run

        os.environ["BOARDWALK_PYTEST_PORT"] = str(free_tcp_port)
        url = boardwalkd_url.format(port=free_tcp_port)
        run_kwargs = {
            "auth_expire_days": 3,
            "auth_login_slack_notify": False,
            "auth_method": "anonymous",
            "develop": True,
            "host_header_pattern": re.compile(r"(localhost|127\.0\.0\.1)"),
            "owner": "anonymous@example.com",
            "port_number": free_tcp_port,
            "tls_crt_path": None,
            "tls_key_path": None,
            "slack_app_token": None,
            "slack_bot_token": None,
            "slack_error_advice_rules": [],
            "tls_port_number": None,
            "slack_error_webhook_url": "",
            "slack_webhook_url": "",
            "slack_slash_command_prefix": "brdwlk",
            "url": url,
            "workspace_status_json": True,
        }
        app, http_servers = await boardwalkd_run(**run_kwargs)

        await asyncio.sleep(0.5)

        # Yield to the next text and/or fixture, and return the url
        yield url

        # Close out all the server connections
        for server in http_servers:
            server.stop()
            await server.close_all_connections()


@pytest.fixture(scope="function")
async def ensure_workspaces_cleared(spawn_boardwalkd_server):
    """Ensures an instance of `boardwalkd` is running, and clears all workspaces in the state."""
    http_client = AsyncHTTPClient()
    await http_client.fetch(
        HTTPRequest(url=spawn_boardwalkd_server + "/develop/clear_all_workspaces", method="POST", body="{}")
    )


@pytest.fixture(scope="function")
async def spawn_boardwalkd_server_and_maybe_clear_workspaces(spawn_boardwalkd_server):
    """Ensures an instance of `boardwalkd` is running, and conditionally clears all workspaces in the state,
    if the envvar `PYTEST_BOARDWALKD_PERSIST_WORKSPACES_BETWEEN_TESTS` is set."""
    if os.environ.get("PYTEST_BOARDWALKD_PERSIST_WORKSPACES_BETWEEN_TESTS", "False") != "True":
        http_client = AsyncHTTPClient()
        await http_client.fetch(
            HTTPRequest(
                url=spawn_boardwalkd_server + "/develop/clear_all_workspaces",
                method="POST",
                allow_nonstandard_methods=True,
            )
        )
    yield spawn_boardwalkd_server


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
