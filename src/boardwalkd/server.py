"""
This file contains the main HTTP server code
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import string
from collections import deque
from datetime import datetime, timedelta
from distutils.util import strtobool
from importlib.metadata import version as lib_version
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

import tornado.auth
import tornado.escape
import tornado.httpclient
import tornado.web
import tornado.websocket
from click import ClickException
from cryptography.fernet import Fernet
from pydantic import ValidationError
from tornado.log import access_log, app_log
from tornado.routing import HostMatches

from boardwalkd.broadcast import handle_slack_broadcast
from boardwalkd.protocol import ApiLoginMessage, WorkspaceDetails, WorkspaceEvent
from boardwalkd.state import load_state, WorkspaceState

logging.basicConfig(level=logging.INFO)

module_dir = Path(__file__).resolve().parent
state = load_state()


"""
UI handlers
"""


class UIBaseHandler(tornado.web.RequestHandler):
    """Base request handler for UI paths"""

    def get_current_user(self) -> bytes | None:
        """Required method for @tornado.web.authenticated to work"""
        return self.get_secure_cookie(
            "boardwalk_user",
            max_age_days=self.settings["auth_expire_days"],
            min_version=2,
        )


def ui_method_secondsdelta(handler: UIBaseHandler, time: datetime) -> float:
    """Custom UI templating method. Accepts a datetime and returns the delta
    between time given and now in number of seconds"""
    delta = datetime.utcnow() - time
    return delta.total_seconds()


def ui_method_server_version(handler: UIBaseHandler) -> str:
    """Returns the version number of the server"""
    return lib_version("boardwalk")


def ui_method_sort_events_by_date(
    handler: UIBaseHandler, events: deque[WorkspaceEvent]
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
    """Handles logging into the UI with Google Oauth2. The username will be
    the Google account email address"""

    url_encryption_key = Fernet.generate_key()

    async def get(self, *args: Any, **kwargs: Any):
        try:
            # If the request is sent along with a code, then we assume the code
            # was sent to us by google and validate it
            try:
                access = await self.get_authenticated_user(
                    redirect_uri=self.settings["login_url"],
                    code=self.get_argument("code"),
                )
                user = await self.oauth2_request(
                    "https://www.googleapis.com/oauth2/v1/userinfo",
                    access_token=access["access_token"],
                )
            except tornado.httpclient.HTTPClientError:
                return self.send_error(400)

            # If we get this far we know we have a valid user
            self.set_secure_cookie(
                "boardwalk_user",
                user["email"],
                expires_days=self.settings["auth_expire_days"],
            )

            # We attempt to redirect back to the original URL the user was browsing
            # This requires decrypting the value we sent to Google in the state arg
            try:
                state_arg = self.get_argument("state")
                orig_url = self.decrypt_url(state_arg)
            except tornado.web.MissingArgumentError:
                orig_url = "/"
            return self.redirect(orig_url)
        except tornado.web.MissingArgumentError:
            # If there was no code arg we need to authorize with google first

            # Tornado will redirect with the next arg containing the URL the user
            # was originally browsing
            orig_url = self.get_argument("next", default="/")

            return self.authorize_redirect(
                redirect_uri=self.settings["login_url"],
                client_id=self.settings["google_oauth"]["key"],
                scope=["email"],
                response_type="code",
                extra_params={
                    "approval_prompt": "auto",
                    # The state param gets returned along with the code and is used
                    # to redirect the user back to their original url
                    "state": self.encode_url(orig_url),
                },
            )

    def encode_url(self, url: str) -> str:
        """For encrypting and encoding a URL to maintain confidentiality. We use
        this because the URL will pass through Google"""
        cipher_text = Fernet(self.url_encryption_key).encrypt(url.encode())
        return tornado.escape.url_escape(cipher_text)

    def decrypt_url(self, encoded_url: str) -> str:
        """Reverses self.encode_url()"""
        unescaped_cipher_text = tornado.escape.url_unescape(encoded_url)
        return (
            Fernet(self.url_encryption_key)
            .decrypt(unescaped_cipher_text.encode())
            .decode()
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


class APIBaseHandler(tornado.web.RequestHandler):
    """Base request handler for API paths"""

    def check_xsrf_cookie(self):
        """We ignore this method on API requests"""
        pass

    def get_current_user(self) -> bytes | None:
        """Decodes the API token to return the current logged in user"""
        return self.get_secure_cookie(
            "boardwalk_api_token",
            value=self.request.headers["boardwalk-api-token"],
            max_age_days=self.settings["auth_expire_days"],
            min_version=2,
        )

    def get_login_url(self) -> str:
        """Overrides the app's configured login url. Normally tornado will
        redirect to the UI's login method, but we don't want that with headless
        API operations. This redirects to a handler that simply outputs a 403"""
        return self.settings["api_access_denied_url"]


class AuthLoginApiWebsocketIDNotFound(Exception):
    """The auth login client socket was not found"""


class AuthLoginApiHandler(UIBaseHandler):
    """Handles authenticating a user to the API and sending back a token to the
    a client with an open login socket. This handler uses the UIBaseHandler
    intentionally because the user must visit the UI to authenticate here"""

    @tornado.web.authenticated
    def get(self):
        try:
            id: str = self.get_argument("id")
        except tornado.web.MissingArgumentError:
            return self.send_error(422)

        current_user = self.get_current_user()
        token = self.create_signed_value("boardwalk_api_token", current_user)

        message = ApiLoginMessage(token=token).dict()
        try:
            AuthLoginApiWebsocketHandler.write_to_client_by_id(id, message)
        except AuthLoginApiWebsocketIDNotFound:
            return self.send_error(404)

        return self.write("Authentication successful. You may close this window")


class AuthLoginApiWebsocketHandler(tornado.websocket.WebSocketHandler):
    """Socket used by CLI clients to login to the API and get an auth token"""

    clients: dict[AuthLoginApiWebsocketHandler, str] = {}

    def open(self):
        def id_client() -> str:
            """Gives clients a unique random id and adds it to the dict of clients.
            This is used to identify this socket so that an auth token can be sent
            back to the correct client after they authenticate themselves at
            AuthLoginApiHandler. The ID is returned and used to message the
            client with a unique login URI"""
            length = 16
            chars = string.ascii_lowercase + string.digits
            id = "".join(secrets.choice(chars) for _ in range(length))
            if id not in self.clients.values():
                self.clients[self] = id
            else:
                id_client()
            return id

        login_url = f"{self.settings['url']}/api/auth/login?id={id_client()}"
        return self.write_message(ApiLoginMessage(login_url=login_url).dict())

    def on_close(self):
        del self.clients[self]

    @classmethod
    def write_to_client_by_id(cls, id: str, msg: bytes | str | dict[str, Any]):
        """Allows writing a message to a client using a connection ID"""
        for k, v in cls.clients.items():
            if v == id:
                k.write_message(msg)
                return
        raise AuthLoginApiWebsocketIDNotFound


class AuthApiDenied(APIBaseHandler):
    """Dedicated handler for redirecting an unauthenticated user to an 'access
    denied' endpoint"""

    def get(self):
        return self.send_error(403)


class WorkspaceCatchApiHandler(APIBaseHandler):
    """Handles setting a catch on a workspace"""

    @tornado.web.authenticated
    def post(self, workspace: str):
        try:
            state.workspaces[workspace].semaphores.caught = True
            state.flush()
        except KeyError:
            return self.send_error(404)


class WorkspaceDetailsApiHandler(APIBaseHandler):
    """Handles getting and updating WorkspaceDetails for workspaces"""

    @tornado.web.authenticated
    def get(self, workspace: str):
        try:
            return self.write(
                state.workspaces[workspace].details.dict()
            )  # pyright: reportUnknownMemberType=false
        except KeyError:
            return self.send_error(404)

    @tornado.web.authenticated
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

    @tornado.web.authenticated
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

    @tornado.web.authenticated
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

    @tornado.web.authenticated
    def post(self, workspace: str):
        try:
            if state.workspaces[workspace].semaphores.has_mutex:
                return self.send_error(409)
            state.workspaces[workspace].semaphores.has_mutex = True
            state.flush()
        except KeyError:
            return self.send_error(404)

    @tornado.web.authenticated
    def delete(self, workspace: str):
        try:
            state.workspaces[workspace].semaphores.has_mutex = False
            state.flush()
            return
        except KeyError:
            return self.send_error(404)


class WorkspaceSemaphoresApiHandler(APIBaseHandler):
    """Handles getting server-side WorkspaceSemaphores"""

    @tornado.web.authenticated
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
        "api_access_denied_url": urljoin(url, "/api/auth/denied"),
        "auth_expire_days": auth_expire_days,
        "login_url": urljoin(url, "/auth/login"),
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
                r"/api/auth/denied",
                AuthApiDenied,
            ),
            (
                r"/api/auth/login",
                AuthLoginApiHandler,
            ),
            (
                r"/api/auth/login/socket",
                AuthLoginApiWebsocketHandler,
            ),
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
