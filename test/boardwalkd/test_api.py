import json
import os
import urllib.request
from importlib.metadata import version as lib_version
from typing import Any

import pytest
from anyio import to_thread


@pytest.mark.anyio
@pytest.mark.skipif(
    condition=os.environ.get("PYTEST_BOARDWALKD_PERSIST_WORKSPACES_BETWEEN_TESTS", "False") == "True",
    reason="Envvar PYTEST_BOARDWALKD_PERSIST_WORKSPACES_BETWEEN_TESTS is set True",
)
@pytest.mark.usefixtures("ensure_workspaces_cleared")
async def test_api_workspaces_status_result_when_no_workspaces_active(
    spawn_boardwalkd_server_and_maybe_clear_workspaces,
):
    def get_workspace_status() -> dict[str, Any]:
        with urllib.request.urlopen(
            url=f"{spawn_boardwalkd_server_and_maybe_clear_workspaces}/api/workspaces/status"
        ) as response:
            return json.loads(response.read().decode())

    expected_payload: dict[str, Any] = {
        "boardwalkd_version": lib_version("boardwalk"),
        "workspaces": [],
    }
    resp = await to_thread.run_sync(get_workspace_status)

    assert resp == expected_payload
