import html
import json
import re
from datetime import UTC, datetime
from urllib.parse import urlencode

from tornado.testing import AsyncHTTPTestCase
from tornado.web import create_signed_value

import boardwalkd.server as boardwalkd_server
from boardwalkd.protocol import WorkspaceDetails, WorkspaceSemaphores
from boardwalkd.state import WorkspaceState


class FakeServerState:
    def __init__(self):
        self.workspaces: dict[str, WorkspaceState] = {}
        self.users = {}
        self.flush_calls = 0
        self.flush_error: Exception | None = None

    def flush(self):
        self.flush_calls += 1
        if self.flush_error is not None:
            raise self.flush_error


def workspace(*, active: bool = False, mutexed: bool = False, group: str = "") -> WorkspaceState:
    return WorkspaceState(
        details=WorkspaceDetails(ui_group=group),
        last_seen=datetime.now(UTC) if active else None,
        semaphores=WorkspaceSemaphores(has_mutex=mutexed),
    )


class TestBoardwalkServer(AsyncHTTPTestCase):
    def setUp(self):
        self.original_state = boardwalkd_server.state
        self.fake_state = FakeServerState()
        boardwalkd_server.state = self.fake_state  # type: ignore[assignment]
        super().setUp()
        login = self.fetch("/auth/login", follow_redirects=False)
        assert login.code == 302
        self.cookie = next(
            value.split(";", 1)[0]
            for value in login.headers.get_list("Set-Cookie")
            if value.startswith("boardwalk_user=")
        )
        self.api_token = create_signed_value(
            "ANONYMOUS",
            "boardwalk_api_token",
            "anonymous@example.com",
        ).decode()
        self.fake_state.flush_calls = 0

    def tearDown(self):
        super().tearDown()
        boardwalkd_server.state = self.original_state

    def get_app(self):
        app = boardwalkd_server.make_app(
            auth_expire_days=1,
            auth_login_slack_notify=False,
            auth_method="anonymous",
            develop=False,
            host_header_pattern=re.compile(r".*"),
            owner="anonymous@example.com",
            slack_bot_token=None,
            slack_error_advice_rules=[],
            slack_error_webhook_url="",
            slack_webhook_url="",
            url=self.get_url("/"),
            workspace_status_json=False,
        )
        app.settings["xsrf_cookies"] = False
        return app

    def set_workspaces(self, workspaces: dict[str, WorkspaceState]):
        self.fake_state.workspaces = workspaces
        self.fake_state.flush_calls = 0
        self.fake_state.flush_error = None

    def post_json(self, path: str, payload: dict[str, str]):
        return self.fetch(
            path,
            method="POST",
            headers={"Content-Type": "application/json", "boardwalk-api-token": self.api_token},
            body=json.dumps(payload),
        )

    def post_form(self, path: str, workspace_names: list[str]):
        body = urlencode([("workspace", name) for name in workspace_names])
        return self.fetch(
            path,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded", "Cookie": self.cookie},
            body=body,
        )

    def response_text(self, response) -> str:
        return html.unescape(response.body.decode())

    def assert_deletion_error(self, response, status: int, messages: list[str]):
        assert response.code == status
        assert response.headers["X-Boardwalk-Dashboard-Fragment"] == "deletion-error"
        body = self.response_text(response)
        assert 'role="alert"' in body
        assert 'data-dashboard-error="workspace-deletion"' in body
        positions = [body.index(message) for message in messages]
        assert positions == sorted(positions)

    def test_details_post_preserves_known_group_until_nonblank_replacement(self):
        self.set_workspaces({"known": workspace(group="ams5")})

        blank_response = self.post_json("/api/workspace/known/details", {"ui_group": ""})
        assert blank_response.code == 200
        assert self.fake_state.workspaces["known"].details.ui_group == "ams5"

        replacement_response = self.post_json("/api/workspace/known/details", {"ui_group": "iad1"})
        assert replacement_response.code == 200
        assert self.fake_state.workspaces["known"].details.ui_group == "iad1"

    def test_single_active_and_mutexed_deletions_return_all_server_blockers(self):
        cases = [
            ("active", workspace(active=True), 'Workspace "active" has a connected worker.'),
            ("mutexed", workspace(mutexed=True), 'Workspace "mutexed" has a server-side mutex.'),
        ]
        for name, row, message in cases:
            with self.subTest(name=name):
                self.set_workspaces({name: row})

                response = self.post_form("/workspaces/delete", [name])

                self.assert_deletion_error(response, 412, [message])
                assert tuple(self.fake_state.workspaces) == (name,)
                assert self.fake_state.flush_calls == 0

    def test_single_missing_and_success_responses_are_server_derived_fragments(self):
        self.set_workspaces({"kept": workspace()})

        missing = self.post_form("/workspaces/delete", ["forged"])

        self.assert_deletion_error(missing, 404, ['Workspace "forged" does not exist.'])
        assert tuple(self.fake_state.workspaces) == ("kept",)
        assert self.fake_state.flush_calls == 0

        self.set_workspaces({"delete_me": workspace(), "kept": workspace()})
        deleted = self.post_form("/workspaces/delete", ["delete_me"])

        assert deleted.code == 200
        assert deleted.body.decode().count('class="bw-dashboard"') == 1
        assert tuple(self.fake_state.workspaces) == ("kept",)
        assert self.fake_state.flush_calls == 1

    def test_batch_success_deletes_exact_selection_with_one_flush(self):
        self.set_workspaces(
            {
                "delete_one": workspace(),
                "keep_me": workspace(),
                "delete_two": workspace(),
            }
        )

        response = self.post_form("/workspaces/delete", ["delete_one", "delete_two"])

        assert response.code == 200
        assert response.body.decode().count('class="bw-dashboard"') == 1
        assert tuple(self.fake_state.workspaces) == ("keep_me",)
        assert self.fake_state.flush_calls == 1

    def test_batch_invalid_requests_report_every_blocker_without_mutation(self):
        cases = [
            ([], 400, ["Select at least one workspace to delete."]),
            (
                ["safe", "safe"],
                400,
                ['Workspace "safe" was requested more than once.'],
            ),
            (["forged"], 404, ['Workspace "forged" does not exist.']),
            (["active"], 412, ['Workspace "active" has a connected worker.']),
            (["mutexed"], 412, ['Workspace "mutexed" has a server-side mutex.']),
            (
                ["safe", "safe", "forged", "active", "mutexed", "both"],
                412,
                [
                    'Workspace "safe" was requested more than once.',
                    'Workspace "forged" does not exist.',
                    'Workspace "active" has a connected worker.',
                    'Workspace "mutexed" has a server-side mutex.',
                    'Workspace "both" has a connected worker.',
                    'Workspace "both" has a server-side mutex.',
                ],
            ),
        ]
        for workspace_names, status, messages in cases:
            with self.subTest(workspace_names=workspace_names):
                self.set_workspaces(
                    {
                        "safe": workspace(),
                        "active": workspace(active=True),
                        "mutexed": workspace(mutexed=True),
                        "both": workspace(active=True, mutexed=True),
                    }
                )
                original_items = tuple(self.fake_state.workspaces.items())

                response = self.post_form("/workspaces/delete", workspace_names)

                self.assert_deletion_error(response, status, messages)
                assert tuple(self.fake_state.workspaces.items()) == original_items
                assert self.fake_state.flush_calls == 0

    def test_batch_flush_failure_restores_state_and_reports_truthful_result(self):
        self.set_workspaces(
            {
                "delete_one": workspace(),
                "keep_me": workspace(),
                "delete_two": workspace(),
            }
        )
        original_mapping = self.fake_state.workspaces
        original_items = tuple(original_mapping.items())
        self.fake_state.flush_error = OSError("disk unavailable")

        response = self.post_form("/workspaces/delete", ["delete_one", "delete_two"])

        self.assert_deletion_error(
            response,
            500,
            [
                "No workspace deletions completed in memory.",
                'Workspace "delete_one" was not deleted.',
                'Workspace "delete_two" was not deleted.',
                "Durable state needs inspection because persistence failed.",
            ],
        )
        assert self.fake_state.workspaces is original_mapping
        assert tuple(self.fake_state.workspaces.items()) == original_items
        assert self.fake_state.flush_calls == 1
