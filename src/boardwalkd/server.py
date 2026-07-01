"""
This file contains the main HTTP server code
"""

from __future__ import annotations

import asyncio
import atexit
import hashlib
import json
import os
import re
import secrets
import ssl
import string
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import version as lib_version
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import ParseResult, urljoin, urlparse

import tornado.auth
import tornado.httpclient
import tornado.web
import tornado.websocket
from cryptography.fernet import Fernet
from loguru import logger
from pydantic import ValidationError
from tornado.escape import url_escape, url_unescape
from tornado.log import access_log, app_log
from tornado.routing import HostMatches

from boardwalk.app_exceptions import BoardwalkException
from boardwalk.utils import strtobool
from boardwalkd.auth_prompts import (
    active_auth_prompts,
    clear_auth_prompt,
    orphan_auth_prompts,
    prompts_by_workspace,
    set_auth_prompt,
)
from boardwalkd.broadcast import handle_auth_login_broadcast, handle_slack_broadcast
from boardwalkd.dashboard import (
    DashboardFilters,
    action_url,
    build_dashboard,
    canonical_url,
    partial_url,
    query_url,
    sort_url,
)
from boardwalkd.demo import seed_development_workspaces
from boardwalkd.protocol import AUTH_LOGIN_CONTEXT_FIELDS, ApiLoginMessage, WorkspaceDetails, WorkspaceEvent
from boardwalkd.slack_error_advice import SlackErrorAdviceRule, matching_error_advice
from boardwalkd.snapshot import seed_snapshot_workspaces
from boardwalkd.state import User, WorkspaceState, load_state, valid_user_roles
from boardwalkd.utils import is_workspace_active

if TYPE_CHECKING:
    from tornado.httpserver import HTTPServer

module_dir = Path(__file__).resolve().parent
state = load_state()
SLACK_TOKENS: dict[str, str | None] = {"app": None, "bot": None}
SLACK_SLASH_COMMAND_PREFIX: str = "brdwlk"
SERVER_URL: str | None = None
atexit.register(state.flush)


"""
UI handlers
"""


class UIBaseHandler(tornado.web.RequestHandler):
    """Base request handler for UI paths"""

    def prepare(self):
        # If the request's scheme or host:port differs from the server's
        # configured URL, then the request will be redirected to the configured
        # server URL
        req_url = urlparse(self.request.full_url())
        svr_url: ParseResult = self.settings["url"]
        if req_url.scheme != svr_url.scheme or req_url.netloc != svr_url.netloc:
            redir_url = req_url._replace(scheme=svr_url.scheme, netloc=svr_url.netloc)
            app_log.info(f"Redirecting request {req_url.geturl()} to {redir_url.geturl()}")
            return self.redirect(redir_url.geturl())

        # Gets the logged in user, if any, to determine if their account is
        # disabled. If there is no logged in user, they will automatically be
        # redirected by tornado to the login page. Once there is a logged-in
        # user this logic will return a 403 if either the user is disabled, or
        # somehow they don't exist in the server state
        cur_user = self.current_user
        if isinstance(cur_user, bytes):
            username = cur_user.decode()
            try:
                if not state.users[username].enabled:
                    return self.send_error(403)
            except KeyError:
                return self.send_error(403)

    def get_current_user(self) -> bytes | None:
        """This method is called by @tornado.web.authenticated to get the current
        user, if any. If there is no user, or their cookie is invalid/expired,
        they will be redirected to the login page"""
        return self.get_secure_cookie(
            "boardwalk_user",
            max_age_days=self.settings["auth_expire_days"],
            min_version=2,
        )


def ui_method_secondsdelta(handler: UIBaseHandler, time: datetime) -> float:
    """Custom UI templating method. Accepts a datetime and returns the delta
    between time given and now in number of seconds"""
    delta = datetime.now(UTC) - time.replace(tzinfo=UTC)
    return delta.total_seconds()


def ui_method_server_version(handler: UIBaseHandler) -> str:
    """Returns the version number of the server"""
    return lib_version("boardwalk")


def ui_method_sha256(handler: UIBaseHandler, value: str) -> str:
    """Custom UI templating method. Accepts a string value and returns an sha256
    digest of the string as a string"""
    return hashlib.sha256(value.encode()).hexdigest()


def ui_method_sort_events_by_date(handler: UIBaseHandler, events: deque[WorkspaceEvent]) -> list[WorkspaceEvent]:
    """Custom UI templating method. Accepts a deque of Workspace events and
    sorts them by datetime in ascending order"""
    # While we assume UTC--and the code did/does--this allows for backward compatibility
    # with older `boardwalk` client versions
    key: Callable[[WorkspaceEvent], datetime] = lambda x: x.create_time.replace(tzinfo=UTC)  # type: ignore # noqa: E731
    return sorted(events, key=key, reverse=True)


def dashboard_request_context(handler: UIBaseHandler) -> tuple[DashboardFilters, bool]:
    try:
        edit: str | int | bool = handler.get_argument("edit", default=0)  # type: ignore
        edit = strtobool(edit)  # type: ignore
    except (AttributeError, ValueError):
        edit = 0
    filters = DashboardFilters(
        group=handler.get_query_argument("group", default="All"),
        search=handler.get_query_argument("search", default=""),
        status=handler.get_query_argument("status", default="all"),
        source=handler.get_query_argument("source", default="all"),
        sort=handler.get_query_argument("sort", default="default"),
        direction=handler.get_query_argument("direction", default="asc"),
    )
    return filters, bool(edit)


def render_workspaces_fragment(handler: UIBaseHandler, filters: DashboardFilters, edit: bool):
    dashboard = build_dashboard(
        state.workspaces,
        filters,
        jenkins_job_url=handler.settings.get("jenkins_job_url", ""),
        error_advice_rules=handler.settings.get("slack_error_advice_rules", []),
    )
    return handler.render(
        "index_workspace.html",
        dashboard=dashboard,
        workspaces=state.workspaces,
        edit=edit,
        auth_prompts=list(active_auth_prompts.values()),
        auth_prompts_by_workspace=prompts_by_workspace(),
        action_url=action_url,
        canonical_url=canonical_url,
        partial_url=partial_url,
        query_url=query_url,
        sort_url=sort_url,
        orphan_auth_prompts=orphan_auth_prompts(state.workspaces.keys()),
    )


class AdminUIBaseHandler(UIBaseHandler):
    """Base handler for Admin UI handlers. Requires the current user be a member
    of the 'admin' role"""

    def prepare(self):
        super().prepare()

        cur_user = self.current_user
        if isinstance(cur_user, bytes):
            username = cur_user.decode()
            try:
                if "admin" not in state.users[username].roles:
                    return self.send_error(403)
            except KeyError:
                return self.send_error(403)


class AdminHandler(AdminUIBaseHandler):
    """Handles serving the admin UI"""

    @tornado.web.authenticated
    def get(self):
        return self.render(
            "admin.html",
            title="Admin",
            users=state.users,
            current_user=self.current_user.decode(),
            owner=self.settings["owner"],
            valid_user_roles=valid_user_roles,
        )


class UserEnableHandler(AdminUIBaseHandler):
    """Handles enabling/disabling users in the admin UI"""

    @tornado.web.authenticated
    def post(self, user: str):
        """Enables a given user"""
        try:
            state.users[user].enabled = True
            state.flush()
            return self.render(
                "admin_user_enable.html",
                user=state.users[user],
                current_user=self.current_user.decode(),
                owner=self.settings["owner"],
            )
        except KeyError:
            return self.send_error(404)

    @tornado.web.authenticated
    def delete(self, user: str):
        """Disables a given user"""
        # Don't allow users to disable themselves or the owner
        if user == self.current_user.decode() or user == self.settings["owner"]:
            return self.send_error(406)

        try:
            state.users[user].enabled = False
            state.flush()
            return self.render(
                "admin_user_enable.html",
                user=state.users[user],
                current_user=self.current_user.decode(),
                owner=self.settings["owner"],
            )
        except KeyError:
            return self.send_error(404)


class UserRoleHandler(AdminUIBaseHandler):
    """Handles configuring user roles in the admin UI"""

    @tornado.web.authenticated
    def post(self, user: str):
        """Appends a role to a user"""
        try:
            role: str = self.get_argument("role")
        except tornado.web.MissingArgumentError:
            app_log.warning("role argument missing")
            return self.send_error(422)

        # Don't allow modifying the default role
        if role == "default":
            app_log.warning("The default role cannot be modified")
            return self.send_error(406)

        try:
            User.validate_roles({role})  # type: ignore
        except ValueError:
            app_log.warning(f"Invalid role {role}")
            return self.send_error(422)

        try:
            state.users[user].roles.add(role)
            state.flush()
            return self.render(
                "admin_user_roles.html",
                user=state.users[user],
                current_user=self.current_user.decode(),
                owner=self.settings["owner"],
                valid_user_roles=valid_user_roles,
            )
        except KeyError:
            return self.send_error(404)

    @tornado.web.authenticated
    def delete(self, user: str):
        """Removes a role from a user"""
        try:
            role: str = self.get_argument("role")
        except tornado.web.MissingArgumentError:
            app_log.warning("role argument missing")
            return self.send_error(422)

        # Don't allow modifying the default role
        if role == "default":
            app_log.warning("The default role cannot be modified")
            return self.send_error(406)

        # Don't allow users to remove admin from themselves or the owner
        if (user == self.current_user.decode() or user == self.settings["owner"]) and role == "admin":
            return self.send_error(406)

        try:
            User.validate_roles({role})  # type: ignore
        except ValueError:
            app_log.warning(f"Invalid role {role}")
            return self.send_error(422)

        try:
            state.users[user].roles.remove(role)
            state.flush()
            return self.render(
                "admin_user_roles.html",
                user=state.users[user],
                current_user=self.current_user.decode(),
                owner=self.settings["owner"],
                valid_user_roles=valid_user_roles,
            )
        except KeyError:
            return self.send_error(404)


class AnonymousLoginHandler(UIBaseHandler):
    """Handles "logging in" the UI when no auth is actually configured"""

    # nosemgrep: boardwalk.python.security.handler-method-missing-authentication
    async def get(self):  # pyright: ignore [reportIncompatibleMethodOverride]
        # Save the user to the state if they aren't already in there
        anon_username = "anonymous@example.com"
        if anon_username not in state.users:
            state.users[anon_username] = User(email=anon_username)  # type: ignore
            state.flush()

        self.set_secure_cookie(
            "boardwalk_user",
            anon_username,
            expires_days=self.settings["auth_expire_days"],
            samesite="Lax",  # To allow, for example, Slack to open the dashboard in a new window when the link is clicked from the Slack App
            secure=True,
        )
        return self.redirect(
            self.get_query_argument("next", "/")  # type: ignore
        )  # pyright: ignore [reportGeneralTypeIssues]


class GoogleOAuth2LoginHandler(UIBaseHandler, tornado.auth.GoogleOAuth2Mixin):
    """Handles logging into the UI with Google Oauth2. The username will be
    the Google account email address"""

    url_encryption_key = Fernet.generate_key()

    # nosemgrep: boardwalk.python.security.handler-method-missing-authentication
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

            # If we get this far we know we have a valid google user
            username = user["email"]

            if username not in state.users:
                try:
                    state.users[username] = User(email=username)
                except ValidationError as e:
                    app_log.error(e)
                    return self.send_error(422)
                state.flush()

            self.set_secure_cookie(
                "boardwalk_user",
                username,
                expires_days=self.settings["auth_expire_days"],
                samesite="Strict",
                secure=True,
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
        return url_escape(cipher_text)

    def decrypt_url(self, encoded_url: str) -> str:
        """Reverses self.encode_url()"""
        unescaped_cipher_text = url_unescape(encoded_url)
        return Fernet(self.url_encryption_key).decrypt(unescaped_cipher_text.encode()).decode()


class IndexHandler(UIBaseHandler):
    """Handles serving the index UI"""

    @tornado.web.authenticated
    def get(self):
        filters, edit = dashboard_request_context(self)
        return self.render(
            "index.html",
            title="Index",
            workspaces=state.workspaces,
            workspaces_url=partial_url(filters, edit=edit),
            edit=edit,
        )


class WorkspaceCatchHandler(UIBaseHandler):
    """Handles receiving catch requests for workspaces from the UI"""

    @tornado.web.authenticated
    def post(self, workspace: str):
        filters, edit = dashboard_request_context(self)
        try:
            state.workspaces[workspace].semaphores.caught = True
        except KeyError:
            return self.send_error(404)

        # Record who clicked the catch button
        cur_user = self.current_user.decode()
        event = WorkspaceEvent(severity="info", message=f"Workspace caught by {cur_user}")
        internal_workspace_event(workspace, event)

        return render_workspaces_fragment(self, filters, edit)

    @tornado.web.authenticated
    def delete(self, workspace: str):
        filters, edit = dashboard_request_context(self)
        try:
            state.workspaces[workspace].semaphores.caught = False
        except KeyError:
            return self.send_error(404)

        # Record who clicked the release button
        cur_user = self.current_user.decode()
        event = WorkspaceEvent(severity="info", message=f"Workspace released by {cur_user}")
        internal_workspace_event(workspace, event)

        return render_workspaces_fragment(self, filters, edit)


class WorkspaceRemoteStateClearHandler(UIBaseHandler):
    """Handles UI requests for a worker to clear a host's remote state fact."""

    @tornado.web.authenticated
    def post(self, workspace: str):
        try:
            workspace_state = state.workspaces[workspace]
        except KeyError:
            return self.send_error(404)

        if not workspace_state.semaphores.caught:
            return self.send_error(409)
        if not is_workspace_active(workspace):
            return self.send_error(412)

        workspace_state.semaphores.clear_remote_state_requested = True
        cur_user = self.current_user.decode()
        event = WorkspaceEvent(
            severity="info",
            message=f"Remote Boardwalk state cleanup requested by {cur_user}",
        )
        internal_workspace_event(workspace, event)

        return self.render(
            "index_workspace_remote_state_clear.html",
            workspace_name=workspace,
            workspace=workspace_state,
        )


class WorkspaceRemoteMutexClearHandler(UIBaseHandler):
    """Handles UI requests for a worker to clear a host's remote mutex."""

    @tornado.web.authenticated
    def post(self, workspace: str):
        try:
            workspace_state = state.workspaces[workspace]
        except KeyError:
            return self.send_error(404)

        if not workspace_state.semaphores.caught:
            return self.send_error(409)
        if not is_workspace_active(workspace):
            return self.send_error(412)

        workspace_state.semaphores.clear_remote_mutex_requested = True
        cur_user = self.current_user.decode()
        event = WorkspaceEvent(
            severity="info",
            message=f"Remote Boardwalk mutex cleanup requested by {cur_user}",
        )
        internal_workspace_event(workspace, event)

        return self.render(
            "index_workspace_remote_mutex_clear.html",
            workspace_name=workspace,
            workspace=workspace_state,
        )


class WorkspaceEventsHandler(UIBaseHandler):
    """Handles serving workspace events in the UI"""

    @tornado.web.authenticated
    def get(self, workspace: str):
        try:
            state.workspaces[workspace]
        except KeyError:
            return self.send_error(404)
        return self.render("workspace_events.html", workspace_name=workspace, title="Events")


class WorkspaceEventsTableHandler(UIBaseHandler):
    """Handles serving workspace events tables in the UI"""

    @tornado.web.authenticated
    def get(self, workspace: str):
        try:
            workspace = state.workspaces[workspace]  # type: ignore
        except KeyError:
            return self.send_error(404)
        return self.render("workspace_events_table.html", workspace=workspace)


class WorkspaceMutexHandler(UIBaseHandler):
    """Handles mutex requests for workspaces from the UI"""

    @tornado.web.authenticated
    def delete(self, workspace: str):
        filters, edit = dashboard_request_context(self)
        try:
            # If the host is possibly still connected we will not delete the
            # mutex. Workspaces should send a heartbeat every 5 seconds
            workspace_state = state.workspaces[workspace]
            if is_workspace_active(workspace):
                return self.send_error(412)
            workspace_state.semaphores.has_mutex = False
            state.flush()
            return render_workspaces_fragment(self, filters, edit)
        except KeyError:
            return self.send_error(404)


class WorkspaceDeleteHandler(UIBaseHandler):
    """Handles delete requests for workspaces from the UI"""

    @tornado.web.authenticated
    def post(self, workspace: str):
        filters, edit = dashboard_request_context(self)
        try:
            # If there is a mutex on the workspace we will not delete it
            if state.workspaces[workspace].semaphores.has_mutex:
                return self.send_error(412)
            del state.workspaces[workspace]
            state.flush()
            return render_workspaces_fragment(self, filters, edit)
        except KeyError:
            return self.send_error(404)


class WorkspacesHandler(UIBaseHandler):
    """Handles serving the list of workspaces in the UI"""

    @tornado.web.authenticated
    def get(self):
        filters, edit = dashboard_request_context(self)
        if self.get_query_argument("push_url", default="") == "1":
            self.set_header(name="HX-Push-Url", value=canonical_url(filters, edit=edit))
        return render_workspaces_fragment(self, filters, edit)


"""
API handlers
"""


class APIBaseHandler(tornado.web.RequestHandler):
    """Base request handler for API paths"""

    def prepare(self):
        # If the request's scheme or host:port differs from the server's
        # configured URL, then the request will be rejected
        req_url = urlparse(self.request.full_url())
        svr_url: ParseResult = self.settings["url"]
        if req_url.scheme != svr_url.scheme or req_url.netloc != svr_url.netloc:
            return self.send_error(421)

        # Gets the logged in user, if any, to determine if their account is
        # disabled. If there is no logged in user, they will automatically be
        # redirected by tornado to the login page. Once there is a logged-in
        # user this logic will return a 403 if either the user is disabled, or
        # somehow they don't exist in the server state
        cur_user = self.current_user
        if isinstance(cur_user, bytes):
            username = cur_user.decode()
            try:
                if not state.users[username].enabled:
                    return self.send_error(403)
            except KeyError:
                return self.send_error(403)

    def check_xsrf_cookie(self):
        """We ignore this method on API requests"""
        pass

    def get_current_user(self) -> bytes | None:
        """Decodes the API token to return the current logged in user."""
        return self.get_secure_cookie(
            "boardwalk_api_token",
            value=self.request.headers.get("boardwalk-api-token"),
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


def auth_login_context_from_request(handler: tornado.web.RequestHandler) -> dict[str, str | None]:
    """Gets worker context from the auth login websocket query arguments."""
    auth_context: dict[str, str | None] = {}
    for field in AUTH_LOGIN_CONTEXT_FIELDS:
        value = handler.get_query_argument(field, default="")
        if value:
            auth_context[field] = value
    return auth_context


async def notify_auth_login(login_url: str, auth_context: dict[str, str | None], settings: dict[str, Any]):
    """Posts an auth-login notification without interrupting the websocket flow."""
    try:
        if deployment_user_email := auth_context.get("deployment_user_email", ""):
            slack_user_mention = state.users[deployment_user_email].slack_cache.user_mention
            await handle_auth_login_broadcast(
                login_url=login_url,
                auth_context=auth_context,
                webhook_url=settings.get("slack_webhook_url"),
                error_webhook_url=settings.get("slack_error_webhook_url"),
                server_url=settings["url"].geturl(),
                slack_user_mention=slack_user_mention,
            )
    except Exception as e:
        logger.error(f"Could not send auth login Slack notification: {e}")


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
        token = self.create_signed_value("boardwalk_api_token", current_user)  # type: ignore

        message = ApiLoginMessage(token=token).model_dump()  # type: ignore
        try:
            AuthLoginApiWebsocketHandler.write_to_client_by_id(id, message)
        except AuthLoginApiWebsocketIDNotFound:
            return self.send_error(404)

        return self.write("""
            Authentication to Boardwalk's API was successful. You may close this
            window if it does not automatically close.
            <script>
            setTimeout(function() {
                window.close()
            }, 1000);
            </script>
        """)


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

        this_client_id = id_client()
        app_log.info(f"Login client ID {this_client_id} opened")
        login_url = urljoin(self.settings["url"].geturl(), f"/api/auth/login?id={this_client_id}")
        auth_context = auth_login_context_from_request(self)
        set_auth_prompt(client_id=this_client_id, login_url=login_url, auth_context=auth_context)
        if self.settings.get("auth_login_slack_notify") and (
            self.settings.get("slack_error_webhook_url") or self.settings.get("slack_webhook_url")
        ):
            asyncio.create_task(
                notify_auth_login(
                    login_url=login_url,
                    auth_context=auth_context,
                    settings=self.settings,
                )
            )
        return self.write_message(ApiLoginMessage(login_url=login_url).model_dump())

    def on_close(self):
        client_id = self.clients[self]
        app_log.info(f"Login client ID {client_id} closed")
        clear_auth_prompt(client_id)
        del self.clients[self]

    def on_pong(self, data: bytes):
        app_log.info(f"Login client ID {self.clients[self]} pong received")

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

    # nosemgrep: boardwalk.python.security.handler-method-missing-authentication
    def get(self):
        return self.send_error(403)


class DevelopmentClearAllWorkspaces(APIBaseHandler):
    """When run in development mode, allows clearing all workspaces"""

    # nosemgrep: boardwalk.python.security.handler-method-missing-authentication
    def get(self):
        if self.settings.get("development_features_enabled", False):
            return self.send_error(405)
        else:
            return self.send_error(403)

    # nosemgrep: boardwalk.python.security.handler-method-missing-authentication
    def post(self):
        if self.settings.get("development_features_enabled", False):
            ws_names = [name for name, _ in state.workspaces.items()]
            logger.info(f"Resetting development server workspace state by clearing {len(ws_names)} workspace(s)")
            for name in ws_names:
                # If there is a mutex on the workspace we will not delete it
                if state.workspaces[name].semaphores.has_mutex:
                    continue
                del state.workspaces[name]
            state.flush()
            return
        else:
            return self.send_error(403)


class WorkspacesStatusApiHandler(APIBaseHandler):
    """Returns an unauthenticated, read-only summary of all workspaces for monitoring integrations"""

    # nosemgrep: boardwalk.python.security.handler-method-missing-authentication
    def get(self):
        if not self.settings.get("workspace_status_json"):
            return self.send_error(404)

        payload: dict[str, Any] = {"boardwalkd_version": lib_version("boardwalk")}
        result = []
        for name, ws in state.workspaces.items():
            entry: dict[str, Any] = {
                "name": name,
                "semaphores": ws.semaphores.model_dump(),
            }
            if ws.details:
                entry["details"] = {key: value for key, value in ws.details}
                entry["details"]["worker"] = f"{ws.details.worker_username}@{ws.details.worker_hostname}"
                entry["details"]["worker_connected"] = is_workspace_active(workspace_name=name)
            if ws.last_seen:
                entry["last_seen"] = ws.last_seen.isoformat()
            result.append(entry)
        payload["workspaces"] = result
        self.write(payload)


class WorkspaceCatchApiHandler(APIBaseHandler):
    """Handles setting a catch on a workspace"""

    @tornado.web.authenticated
    def post(self, workspace: str):
        try:
            state.workspaces[workspace].semaphores.caught = True
            state.flush()
        except KeyError:
            return self.send_error(404)


class WorkspaceRemoteStateClearApiHandler(APIBaseHandler):
    """Handles worker/API requests to clear pending remote state cleanup."""

    @tornado.web.authenticated
    def post(self, workspace: str):
        try:
            workspace_state = state.workspaces[workspace]
        except KeyError:
            return self.send_error(404)

        if not workspace_state.semaphores.caught:
            return self.send_error(409)
        if not is_workspace_active(workspace):
            return self.send_error(412)

        workspace_state.semaphores.clear_remote_state_requested = True
        state.flush()
        self.set_status(204)
        return self.finish()

    @tornado.web.authenticated
    def delete(self, workspace: str):
        try:
            state.workspaces[workspace].semaphores.clear_remote_state_requested = False
            state.flush()
            self.set_status(204)
            return self.finish()
        except KeyError:
            return self.send_error(404)


class WorkspaceRemoteMutexClearApiHandler(APIBaseHandler):
    """Handles worker/API requests to clear pending remote mutex cleanup."""

    @tornado.web.authenticated
    def post(self, workspace: str):
        try:
            workspace_state = state.workspaces[workspace]
        except KeyError:
            return self.send_error(404)

        if not workspace_state.semaphores.caught:
            return self.send_error(409)
        if not is_workspace_active(workspace):
            return self.send_error(412)

        workspace_state.semaphores.clear_remote_mutex_requested = True
        state.flush()
        self.set_status(204)
        return self.finish()

    @tornado.web.authenticated
    def delete(self, workspace: str):
        try:
            state.workspaces[workspace].semaphores.clear_remote_mutex_requested = False
            state.flush()
            self.set_status(204)
            return self.finish()
        except KeyError:
            return self.send_error(404)


# These fields decide whether a details POST should create a log event. current_host
# and ui_group intentionally update state silently because workers POST details on
# every host iteration, and logging each update would bury the useful event stream.
WORKSPACE_CLIENT_DETAILS_EVENT_FIELDS = (
    "workflow",
    "worker_username",
    "worker_hostname",
    "host_pattern",
    "worker_limit",
    "worker_command",
)


def workspace_client_details_event_should_log(
    old_details: WorkspaceDetails | None,
    new_details: WorkspaceDetails,
) -> bool:
    if old_details is None:
        return True
    return any(
        getattr(old_details, field) != getattr(new_details, field) for field in WORKSPACE_CLIENT_DETAILS_EVENT_FIELDS
    )


def workspace_client_details_event_message(workspace_details: WorkspaceDetails) -> str:
    return (
        "Workspace client details:"
        f" Workflow: {workspace_details.workflow},"
        f" Worker: {workspace_details.worker_username}@{workspace_details.worker_hostname},"
        f" Host Pattern: {workspace_details.host_pattern},"
        f" Limit Pattern: {workspace_details.worker_limit if workspace_details.worker_limit else '<unknown>'},"
        f" Command: {workspace_details.worker_command}"
    )


class WorkspaceDetailsApiHandler(APIBaseHandler):
    """Handles getting and updating WorkspaceDetails for workspaces"""

    @tornado.web.authenticated
    def get(self, workspace: str):
        try:
            return self.write(state.workspaces[workspace].details.model_dump())  # pyright: ignore [reportUnknownMemberType]
        except KeyError:
            return self.send_error(404)

    @tornado.web.authenticated
    def post(self, workspace: str):
        try:
            payload = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            return self.send_error(415)

        try:
            new_details = WorkspaceDetails().model_validate(payload)
        except ValidationError as e:
            app_log.error(e)
            return self.send_error(422)

        existing_workspace = state.workspaces.get(workspace)
        existing_details = existing_workspace.details if existing_workspace else None
        log_client_details_event = workspace_client_details_event_should_log(existing_details, new_details)

        try:
            state.workspaces[workspace].details = new_details
        except KeyError:
            state.workspaces[workspace] = WorkspaceState()
            state.workspaces[workspace].details = new_details
        state.workspaces[workspace].last_seen = datetime.now(UTC)
        state.flush()

        if log_client_details_event:
            event = WorkspaceEvent(severity="info", message=workspace_client_details_event_message(new_details))
            internal_workspace_event(workspace, event)


class WorkspaceHeartbeatApiHandler(APIBaseHandler):
    """Handles receiving heartbeats from workers"""

    @tornado.web.authenticated
    def post(self, workspace: str):
        try:
            state.workspaces[workspace].last_seen = datetime.now(UTC)
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
            broadcast: str | int | bool = self.get_argument("broadcast", default=0)  # type: ignore
            broadcast = strtobool(broadcast)  # type: ignore
        except (AttributeError, ValueError):
            broadcast = 0

        try:
            payload = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            return self.send_error(415)

        try:
            event = WorkspaceEvent.model_validate(payload)
        except ValidationError as e:
            app_log.error(e)
            return self.send_error(422)

        event.received_time = datetime.now(UTC)

        try:
            state.workspaces[workspace].events.append(event)
        except KeyError:
            return self.send_error(404)

        app_log.info(f"worker_event: {self.request.remote_ip} {workspace} {event.severity} {event.message}")

        if broadcast:
            if self.settings["slack_webhook_url"] or self.settings["slack_error_webhook_url"]:
                workspace_details = state.workspaces[workspace].details
                slack_user_mention = None
                if event.severity == "error":
                    if workspace_details.deployment_user_email:
                        slack_user_mention = state.users[
                            workspace_details.deployment_user_email
                        ].slack_cache.user_mention
                    else:
                        slack_user_mention = None
                await handle_slack_broadcast(
                    event,
                    workspace,
                    self.settings["slack_webhook_url"],
                    self.settings["slack_error_webhook_url"],
                    self.settings["url"].geturl(),
                    error_advice=matching_error_advice(event, self.settings["slack_error_advice_rules"]),
                    slack_user_mention=slack_user_mention,
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
            return self.write(state.workspaces[workspace].semaphores.model_dump())
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


def internal_workspace_event(workspace: str, event: WorkspaceEvent):
    """
    Appends an internally-generated workspace event to the state and logs to the
    application log
    """
    event.received_time = datetime.now(UTC)
    state.workspaces[workspace].events.append(event)
    app_log.info(f"internal_workspace_event: {workspace} {event.severity} {event.message}")
    state.flush()


def make_app(
    auth_expire_days: float,
    auth_login_slack_notify: bool,
    auth_method: str,
    develop: bool,
    host_header_pattern: re.Pattern[str],
    owner: str,
    slack_bot_token: str | None,
    slack_error_advice_rules: list[SlackErrorAdviceRule],
    slack_error_webhook_url: str,
    slack_webhook_url: str,
    url: str,
    workspace_status_json: bool,
    develop_snapshot_path: str | None = None,
    demo: bool = False,
    theme_static_path: str | None = None,
    theme_css_url: str = "",
    theme_logo_url: str = "",
    theme_logo_alt: str = "",
    theme_brand_name: str = "Boardwalk",
    jenkins_job_url: str = "",
) -> tornado.web.Application:
    """Builds the tornado application object"""
    handlers: list[tornado.web.OutputTransform] = []
    settings = {
        "api_access_denied_url": urljoin(url, "/api/auth/denied"),
        "auth_expire_days": auth_expire_days,
        "auth_login_slack_notify": auth_login_slack_notify,
        "development_features_enabled": develop,
        "jenkins_job_url": jenkins_job_url,
        "login_url": urljoin(url, "/auth/login"),
        "log_function": log_request,
        "owner": owner,
        "slack_bot_token": slack_bot_token,
        "slack_error_advice_rules": slack_error_advice_rules,
        "slack_webhook_url": slack_webhook_url,
        "slack_error_webhook_url": slack_error_webhook_url,
        "static_path": module_dir.joinpath("static"),
        "template_path": module_dir.joinpath("templates"),
        "theme_css_url": theme_css_url,
        "theme_logo_url": theme_logo_url,
        "theme_logo_alt": theme_logo_alt,
        "theme_brand_name": theme_brand_name or "Boardwalk",
        "ui_methods": {
            "secondsdelta": ui_method_secondsdelta,
            "server_version": ui_method_server_version,
            "sha256": ui_method_sha256,
            "sort_events_by_date": ui_method_sort_events_by_date,
        },
        "url": urlparse(url),
        "websocket_ping_interval": 10,
        "workspace_status_json": workspace_status_json,
        "xsrf_cookies": True,
        "xsrf_cookie_kwargs": {"samesite": "Strict", "secure": True},
    }
    if develop:
        settings["debug"] = True
    # Snapshot/demo seeding is development-only fixture data. A snapshot wins over
    # demo rows so local replay of real-shaped state is never mixed with synthetic
    # demo workspaces.
    if develop_snapshot_path:
        seeded = seed_snapshot_workspaces(state, develop_snapshot_path)
    elif demo:
        seeded = seed_development_workspaces(state)
    else:
        seeded = False
    if seeded:
        state.flush()

    # Set-up authentication
    if auth_method != "anonymous":
        try:
            settings["cookie_secret"] = os.environ["BOARDWALKD_SECRET"]
        except KeyError:
            raise BoardwalkException(
                "The BOARDWALK_SECRET environment variable is required when any"
                " authentication method is enabled in order to generate secure cookies"
            )

    # Bootstrap the chosen auth_method
    match auth_method:
        case "anonymous":
            handlers.append((r"/auth/login", AnonymousLoginHandler))  # type: ignore
            settings["cookie_secret"] = "ANONYMOUS"
        case "google_oauth":
            try:
                settings["google_oauth"] = {
                    "key": os.environ["BOARDWALKD_GOOGLE_OAUTH_CLIENT_ID"],
                    "secret": os.environ["BOARDWALKD_GOOGLE_OAUTH_SECRET"],
                }
            except KeyError:
                raise BoardwalkException(
                    "BOARDWALKD_GOOGLE_OAUTH_CLIENT_ID and BOARDWALKD_GOOGLE_OAUTH_SECRET env vars"
                    " are required when auth_method is google_oauth"
                )
            handlers.append((r"/auth/login", GoogleOAuth2LoginHandler))  # type: ignore
        case _:
            raise BoardwalkException(f"auth_method {auth_method} is not supported")

    if theme_static_path:
        handlers.append((r"/theme-static/(.*)", tornado.web.StaticFileHandler, {"path": theme_static_path}))  # type: ignore

    # Set-up all the main handlers
    handlers.extend(
        [
            # UI handlers
            (r"/", IndexHandler),
            (r"/admin", AdminHandler),
            (r"/admin/user/([\w%.]+)/enable", UserEnableHandler),
            (r"/admin/user/([\w%.]+)/roles", UserRoleHandler),
            (r"/workspace/(\w+)/delete", WorkspaceDeleteHandler),
            (r"/workspace/(\w+)/events", WorkspaceEventsHandler),
            (r"/workspace/(\w+)/events/table", WorkspaceEventsTableHandler),
            (r"/workspace/(\w+)/remote_mutex/clear", WorkspaceRemoteMutexClearHandler),
            (r"/workspace/(\w+)/remote_state/clear", WorkspaceRemoteStateClearHandler),
            (r"/workspace/(\w+)/semaphores/caught", WorkspaceCatchHandler),
            (r"/workspace/(\w+)/semaphores/has_mutex", WorkspaceMutexHandler),
            (r"/workspaces", WorkspacesHandler),
            # Routes that are gated behind the --develop flag
            (r"/develop/clear_all_workspaces", DevelopmentClearAllWorkspaces),
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
                r"/api/workspaces/status",
                WorkspacesStatusApiHandler,
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
                r"/api/workspace/(\w+)/remote_state/clear",
                WorkspaceRemoteStateClearApiHandler,
            ),
            (
                r"/api/workspace/(\w+)/remote_mutex/clear",
                WorkspaceRemoteMutexClearApiHandler,
            ),
            (
                r"/api/workspace/(\w+)/semaphores/has_mutex",
                WorkspaceMutexApiHandler,
            ),
        ]  # type: ignore
    )

    # Configure rules
    rules = [
        (  # Used to prevent DNS rebinding attacks
            HostMatches(host_header_pattern),
            handlers,
        )
    ]

    return tornado.web.Application(rules, **settings)  # type: ignore


async def run(
    auth_expire_days: float,
    auth_login_slack_notify: bool,
    auth_method: str,
    develop: bool,
    host_header_pattern: re.Pattern[str],
    owner: str,
    port_number: int | None,
    tls_crt_path: str | None,
    tls_key_path: str | None,
    slack_app_token: str | None,
    slack_bot_token: str | None,
    slack_error_advice_rules: list[SlackErrorAdviceRule],
    tls_port_number: int | None,
    slack_error_webhook_url: str,
    slack_webhook_url: str,
    slack_slash_command_prefix: str,
    url: str,
    workspace_status_json: bool,
    develop_snapshot_path: str | None = None,
    demo: bool = False,
    theme_static_path: str | None = None,
    theme_css_url: str = "",
    theme_logo_url: str = "",
    theme_logo_alt: str = "",
    theme_brand_name: str = "Boardwalk",
    jenkins_job_url: str = "",
) -> tuple[tornado.web.Application, list[HTTPServer]]:
    """Starts the tornado server and IO loop"""
    global state
    global SLACK_SLASH_COMMAND_PREFIX

    app = make_app(
        auth_expire_days=auth_expire_days,
        auth_login_slack_notify=auth_login_slack_notify,
        auth_method=auth_method,
        develop=develop,
        host_header_pattern=host_header_pattern,
        owner=owner,
        slack_bot_token=slack_bot_token,
        slack_error_advice_rules=slack_error_advice_rules,
        slack_error_webhook_url=slack_error_webhook_url,
        slack_webhook_url=slack_webhook_url,
        url=url,
        workspace_status_json=workspace_status_json,
        develop_snapshot_path=develop_snapshot_path,
        demo=demo,
        theme_static_path=theme_static_path,
        theme_css_url=theme_css_url,
        theme_logo_url=theme_logo_url,
        theme_logo_alt=theme_logo_alt,
        theme_brand_name=theme_brand_name,
        jenkins_job_url=jenkins_job_url,
    )

    http_servers: list[HTTPServer] = []
    if port_number is not None:
        http_servers.append(app.listen(port_number))
        # If port_number=0 a random open port will be selected and the log message
        # will not be accurate
        app_log.info(f"Server listening on non-TLS port: {port_number}")

    if tls_port_number is not None:
        if urlparse(url).scheme != "https":
            raise BoardwalkException("URL scheme must be HTTPS when TLS is enabled")

        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_ctx.load_cert_chain(certfile=tls_crt_path, keyfile=tls_key_path)  # type: ignore

        http_servers.append(app.listen(tls_port_number, ssl_options=ssl_ctx))
        # If tls_port_number=0 a random open port will be selected and the log
        # message will not be accurate
        app_log.info(f"Server listening on TLS port: {tls_port_number}")

    # Initialize server owner
    if owner not in state.users:
        state.users[owner] = User(email=owner)  # type: ignore
    state.users[owner].roles.add("admin")
    state.users[owner].enabled = True
    state.flush()

    # If configured, intialize Slack integration
    if slack_app_token:
        SLACK_TOKENS["app"] = slack_app_token
        SLACK_TOKENS["bot"] = slack_bot_token
        SLACK_SLASH_COMMAND_PREFIX = slack_slash_command_prefix

        # Store the server URL so that other modules can read from it directly
        global SERVER_URL
        SERVER_URL = url

        from boardwalkd import slack

        await slack.connect()  # pyright: ignore[reportAttributeAccessIssue]

    return (app, http_servers)
