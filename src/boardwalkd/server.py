"""
This file contains the main HTTP server code
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections import deque
from datetime import datetime, timedelta
from distutils.util import strtobool
from importlib.metadata import version as lib_version
from pathlib import Path
from typing import TYPE_CHECKING

import tornado.auth
import tornado.web
import tornado.websocket
from click import ClickException
from pydantic import ValidationError
from tornado.log import access_log, app_log
from tornado.routing import HostMatches

from boardwalkd.broadcast import handle_slack_broadcast
from boardwalkd.protocol import WorkspaceDetails, WorkspaceEvent
from boardwalkd.state import load_state, WorkspaceState

logging.basicConfig(level=logging.INFO)

module_dir = Path(__file__).resolve().parent
state = load_state()

if TYPE_CHECKING:
    from typing import Any, Callable


class APIBaseHandler(tornado.web.RequestHandler):
    """Base request handler for API paths"""

    def check_xsrf_cookie(self):
        """We ignore this method on API requests"""
        pass


class BaseHandler(tornado.web.RequestHandler):
    """Base request handler for all paths"""


class UIBaseHandler(tornado.web.RequestHandler):
    """Base request handler for UI paths"""

    def get_current_user(self) -> bytes | None:
        """Required method for @tornado.web.authenticated to work"""
        return self.get_secure_cookie(
            "boardwalk_user", max_age_days=self.settings["auth_expire_days"]
        )


"""
UI handlers
"""


def ui_method_secondsdelta(handler: BaseHandler, time: datetime) -> float:
    """Custom UI templating method. Accepts a datetime and returns the delta
    between time given and now in number of seconds"""
    delta = datetime.utcnow() - time
    return delta.total_seconds()


def ui_method_server_version(handler: BaseHandler) -> str:
    """Returns the version number of the server"""
    return lib_version("boardwalk")


def ui_method_sort_events_by_date(
    handler: BaseHandler, events: deque[WorkspaceEvent]
) -> list[WorkspaceEvent]:
    """Custom UI templating method. Accepts a deque of Workspace events and
    sorts them by datetime in ascending order"""
    key: Callable[[WorkspaceEvent], datetime] = lambda x: x.create_time
    return sorted(events, key=key, reverse=True)


class AdminHandler(UIBaseHandler):
    """Handles serving the Admin UI"""

    @tornado.web.authenticated
    def get(self):
        return self.render("admin.html", title="Admin")


class AnonymousLoginHandler(UIBaseHandler):
    """Handles "logging in" the UI when no auth is actually configured"""

    async def get(self):  # pyright: reportIncompatibleMethodOverride=false
        self.set_secure_cookie(
            "boardwalk_user",
            "anonymous@example.com",
            expires_days=self.settings["auth_expire_days"],
        )
        return self.redirect(
            self.get_query_argument("next", "/")
        )  # pyright: reportGeneralTypeIssues=false


class GoogleOAuth2LoginHandler(UIBaseHandler, tornado.auth.GoogleOAuth2Mixin):
    """Handles logging into the UI with Google Oauth2"""

    async def get(self, *args: Any, **kwargs: Any):
        try:
            self.get_argument("code")
            access = await self.get_authenticated_user(
                redirect_uri=self.settings["login_url"],
                code=self.get_argument("code"),
            )
            user = await self.oauth2_request(
                "https://www.googleapis.com/oauth2/v1/userinfo",
                access_token=access["access_token"],
            )
            self.set_secure_cookie(
                "boardwalk_user",
                user["email"],
                expires_days=self.settings["auth_expire_days"],
            )
            return self.redirect("/")
        except tornado.web.MissingArgumentError:
            return self.authorize_redirect(
                redirect_uri=self.settings["login_url"],
                client_id=self.settings["google_oauth"]["key"],
                scope=["email"],
                response_type="code",
                extra_params={"approval_prompt": "auto"},
            )


class IndexHandler(UIBaseHandler):
    """Handles serving the index UI"""

    @tornado.web.authenticated
    def get(self):
        try:
            edit: str | int | bool = self.get_argument("edit", default=0)
            edit = strtobool(edit)
        except (AttributeError, ValueError):
            edit = 0
        return self.render(
            "index.html", title="Index", workspaces=state.workspaces, edit=edit
        )


class WorkspaceCatchHandler(UIBaseHandler):
    """Handles receiving catch requests for workspaces from the UI"""

    @tornado.web.authenticated
    def post(self, workspace: str):
        try:
            state.workspaces[workspace].semaphores.caught = True
            state.flush()
            return self.render("index_workspace_release.html", workspace_name=workspace)
        except KeyError:
            return self.send_error(404)

    @tornado.web.authenticated
    def delete(self, workspace: str):
        try:
            state.workspaces[workspace].semaphores.caught = False
            state.flush()
            return self.render("index_workspace_catch.html", workspace_name=workspace)
        except KeyError:
            return self.send_error(404)


class WorkspaceEventsHandler(UIBaseHandler):
    """Handles serving workspace events in the UI"""

    @tornado.web.authenticated
    def get(self, workspace: str):
        try:
            state.workspaces[workspace]
        except KeyError:
            return self.send_error(404)
        return self.render(
            "workspace_events.html", workspace_name=workspace, title="Events"
        )


class WorkspaceEventsTableHandler(UIBaseHandler):
    """Handles serving workspace events tables in the UI"""

    @tornado.web.authenticated
    def get(self, workspace: str):
        try:
            workspace = state.workspaces[workspace]
        except KeyError:
            return self.send_error(404)
        return self.render("workspace_events_table.html", workspace=workspace)


class WorkspaceMutexHandler(UIBaseHandler):
    """Handles mutex requests for workspaces from the UI"""

    @tornado.web.authenticated
    def delete(self, workspace: str):
        try:
            # If the host is possibly still connected we will not delete the
            # mutex. Workspaces should send a heartbeat every 5 seconds
            delta: timedelta = datetime.utcnow() - state.workspaces[workspace].last_seen
            if delta.total_seconds() < 10:
                return self.send_error(412)
            state.workspaces[workspace].semaphores.has_mutex = False
            state.flush()
            self.set_header(name="HX-Refresh", value="true")
            return
        except KeyError:
            return self.send_error(404)


class WorkspaceDeleteHandler(UIBaseHandler):
    """Handles delete requests for workspaces from the UI"""

    @tornado.web.authenticated
    def post(self, workspace: str):
        try:
            # If there is a mutex on the workspace we will not delete it
            if state.workspaces[workspace].semaphores.has_mutex:
                return self.send_error(412)
            del state.workspaces[workspace]
            state.flush()
            self.set_header(name="HX-Refresh", value="true")
            return
        except KeyError:
            return self.send_error(404)


class WorkspacesHandler(UIBaseHandler):
    """Handles serving the list of workspaces in the UI"""

    @tornado.web.authenticated
    def get(self):
        try:
            edit: str | int | bool = self.get_argument("edit", default=0)
            edit = strtobool(edit)
        except (AttributeError, ValueError):
            edit = 0
        return self.render(
            "index_workspace.html", workspaces=state.workspaces, edit=edit
        )


"""
API handlers
"""


class WorkspaceCatchApiHandler(APIBaseHandler):
    """Handles setting a catch on a workspace"""

    def post(self, workspace: str):
        try:
            state.workspaces[workspace].semaphores.caught = True
            state.flush()
        except KeyError:
            return self.send_error(404)


class WorkspaceDetailsApiHandler(APIBaseHandler):
    """Handles getting and updating WorkspaceDetails for workspaces"""

    def get(self, workspace: str):
        try:
            return self.write(
                state.workspaces[workspace].details.dict()
            )  # pyright: reportUnknownMemberType=false
        except KeyError:
            return self.send_error(404)

    def post(self, workspace: str):
        try:
            payload = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            return self.send_error(415)

        try:
            new_details = WorkspaceDetails().parse_obj(payload)
        except ValidationError as e:
            app_log.error(e)
            return self.send_error(422)

        try:
            state.workspaces[workspace].details = new_details
        except KeyError:
            state.workspaces[workspace] = WorkspaceState()
            state.workspaces[workspace].details = new_details
        state.workspaces[workspace].last_seen = datetime.utcnow()
        state.flush()


class WorkspaceHeartbeatApiHandler(APIBaseHandler):
    """Handles receiving heartbeats from workers"""

    def post(self, workspace: str):
        try:
            state.workspaces[workspace].last_seen = datetime.utcnow()
        except KeyError:
            return self.send_error(404)


class WorkspaceEventApiHandler(APIBaseHandler):
    """
    Handles events sent from clients to the server. Events are always logged to
    the server's stdout and a limited number of events are visible in the UI.
    Optionally the client can request the server "broadcast" an event message,
    and the server will post the broadcasted message to slack as well, if a
    slack webhook is configured
    """

    async def post(self, workspace: str):
        try:
            broadcast: str | int | bool = self.get_argument("broadcast", default=0)
            broadcast = strtobool(broadcast)
        except (AttributeError, ValueError):
            broadcast = 0

        try:
            payload = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            return self.send_error(415)

        try:
            event = WorkspaceEvent.parse_obj(payload)
        except ValidationError as e:
            app_log.error(e)
            return self.send_error(422)

        event.received_time = datetime.utcnow()

        try:
            state.workspaces[workspace].events.append(event)
        except KeyError:
            return self.send_error(404)

        app_log.info(
            f"worker_event: {self.request.remote_ip} {workspace} {event.severity} {event.message}"
        )

        if broadcast:
            if (
                self.settings["slack_webhook_url"]
                or self.settings["slack_error_webhook_url"]
            ):
                await handle_slack_broadcast(
                    event,
                    workspace,
                    self.settings["slack_webhook_url"],
                    self.settings["slack_error_webhook_url"],
                    self.settings["url"],
                )

        state.flush()


class WorkspaceMutexApiHandler(APIBaseHandler):
    """Handles workspace mutex api requests"""

    def post(self, workspace: str):
        try:
            if state.workspaces[workspace].semaphores.has_mutex:
                return self.send_error(409)
            state.workspaces[workspace].semaphores.has_mutex = True
            state.flush()
        except KeyError:
            return self.send_error(404)

    def delete(self, workspace: str):
        try:
            state.workspaces[workspace].semaphores.has_mutex = False
            state.flush()
            return
        except KeyError:
            return self.send_error(404)


class WorkspaceSemaphoresApiHandler(APIBaseHandler):
    """Handles getting server-side WorkspaceSemaphores"""

    def get(self, workspace: str):
        try:
            return self.write(state.workspaces[workspace].semaphores.dict())
        except KeyError:
            return self.send_error(404)


"""
Server functions
"""


def log_request(handler: tornado.web.RequestHandler):
    """Overrides the default request logging function"""
    if handler.get_status() < 400:
        log_method = access_log.info
    elif handler.get_status() < 500:
        log_method = access_log.warning
    else:
        log_method = access_log.error

    # If there is a current user, then include the username
    username = ""
    if u := handler.get_current_user():
        username: str = u.decode("utf8") + " "

    request_time = 1000.0 * handler.request.request_time()

    log_method(
        "%d %s %s (%s) %s%.2fms",
        handler.get_status(),
        handler.request.method,
        handler.request.uri,
        handler.request.remote_ip,
        username,
        request_time,
    )


def make_server(
    auth_expire_days: float,
    auth_method: str,
    develop: bool,
    host_header_pattern: re.Pattern[str],
    slack_error_webhook_url: str,
    slack_webhook_url: str,
    url: str,
):
    """Builds the tornado application server object"""
    handlers: list[tornado.web.OutputTransform] = []
    settings = {
        "auth_expire_days": auth_expire_days,
        "login_url": url + "/auth/login",
        "log_function": log_request,
        "slack_webhook_url": slack_webhook_url,
        "slack_error_webhook_url": slack_error_webhook_url,
        "static_path": module_dir.joinpath("static"),
        "template_path": module_dir.joinpath("templates"),
        "ui_methods": {
            "secondsdelta": ui_method_secondsdelta,
            "server_version": ui_method_server_version,
            "sort_events_by_date": ui_method_sort_events_by_date,
        },
        "url": url,
        "xsrf_cookies": True,
    }
    if develop:
        settings["debug"] = True

    # Set-up authentication
    if auth_method != "anonymous":
        try:
            settings["cookie_secret"] = os.environ["BOARDWALK_SECRET"]
        except KeyError:
            raise ClickException(
                (
                    "The BOARDWALK_SECRET environment variable is required when any"
                    " authentication method is enabled in order to generate secure cookies"
                )
            )

    # Bootstrap the chosen auth_method
    match auth_method:
        case "anonymous":
            handlers.append((r"/auth/login", AnonymousLoginHandler))
            settings["cookie_secret"] = "ANONYMOUS"
        case "google_oauth":
            try:
                settings["google_oauth"] = {
                    "key": os.environ["BOARDWALK_GOOGLE_OAUTH_CLIENT_ID"],
                    "secret": os.environ["BOARDWALK_GOOGLE_OAUTH_SECRET"],
                }
            except KeyError:
                raise ClickException(
                    (
                        "BOARDWALK_GOOGLE_OAUTH_CLIENT_ID and BOARDWALK_GOOGLE_OAUTH_SECRET env vars"
                        " are required when auth_method is google_oauth"
                    )
                )
            handlers.append((r"/auth/login", GoogleOAuth2LoginHandler))
        case _:
            raise ClickException(f"auth_method {auth_method} is not supported")

    # Set-up all the main handlers
    handlers.extend(
        [
            # UI handlers
            (r"/admin", AdminHandler),
            (r"/", IndexHandler),
            (r"/workspaces", WorkspacesHandler),
            (r"/workspace/(\w+)/events", WorkspaceEventsHandler),
            (r"/workspace/(\w+)/events/table", WorkspaceEventsTableHandler),
            (r"/workspace/(\w+)/semaphores/caught", WorkspaceCatchHandler),
            (r"/workspace/(\w+)/semaphores/has_mutex", WorkspaceMutexHandler),
            (r"/workspace/(\w+)/delete", WorkspaceDeleteHandler),
            # API handlers
            (
                r"/api/workspace/(\w+)/details",
                WorkspaceDetailsApiHandler,
            ),
            (
                r"/api/workspace/(\w+)/heartbeat",
                WorkspaceHeartbeatApiHandler,
            ),
            (
                r"/api/workspace/(\w+)/event",
                WorkspaceEventApiHandler,
            ),
            (
                r"/api/workspace/(\w+)/semaphores",
                WorkspaceSemaphoresApiHandler,
            ),
            (
                r"/api/workspace/(\w+)/semaphores/caught",
                WorkspaceCatchApiHandler,
            ),
            (
                r"/api/workspace/(\w+)/semaphores/has_mutex",
                WorkspaceMutexApiHandler,
            ),
        ]
    )

    # Configure rules
    rules = [
        (  # Used to prevent DNS rebinding attacks
            HostMatches(host_header_pattern),
            handlers,
        )
    ]

    return tornado.web.Application(rules, **settings)


async def run(
    auth_expire_days: float,
    auth_method: str,
    develop: bool,
    host_header_pattern: re.Pattern[str],
    port_number: int,
    slack_error_webhook_url: str,
    slack_webhook_url: str,
    url: str,
):
    """Starts the tornado server and IO loop"""
    server = make_server(
        auth_expire_days=auth_expire_days,
        auth_method=auth_method,
        develop=develop,
        host_header_pattern=host_header_pattern,
        slack_error_webhook_url=slack_error_webhook_url,
        slack_webhook_url=slack_webhook_url,
        url=url,
    )
    server.listen(port_number)
    app_log.info(f"Server listening on port: {port_number}")
    await asyncio.Event().wait()
