"""
This file defines objects that are passed between worker clients and the server,
and contains functions to support clients using the server
"""
import asyncio
import concurrent.futures
import json
import logging
import socket
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, Extra, validator
from tornado.httpclient import (
    HTTPClient,
    HTTPClientError,
    HTTPError,
    HTTPRequest,
    HTTPResponse,
)
from tornado.simple_httpclient import HTTPTimeoutError
from tornado.websocket import websocket_connect

logger = logging.getLogger(__name__)


class ProtocolBaseModel(BaseModel, extra=Extra.forbid):
    """BaseModel for protocol usage"""


class ApiLoginMessage(ProtocolBaseModel):
    """Model for websocket messages passed during authentication of CLI
    users to the API"""

    login_url: str = ""
    token: str = ""


class WorkspaceDetails(ProtocolBaseModel):
    """Model for basic workspace details from workers"""

    host_pattern: str = ""
    workflow: str = ""
    worker_command: str = ""
    worker_hostname: str = ""
    worker_username: str = ""


class WorkspaceEvent(ProtocolBaseModel):
    """Model for workspace events sent from boardwalk workers"""

    message: str
    severity: str
    create_time: datetime | None = None
    received_time: datetime | None = None

    def __init__(self, **kwargs: str):
        super().__init__(**kwargs)
        if not self.create_time:
            self.create_time: datetime | None = datetime.utcnow()

    @validator("severity")
    def severity_level(cls, v: str):
        if v not in ["info", "success", "error"]:
            raise ValueError(f"invalid severity level")
        return v


class WorkspaceSemaphores(ProtocolBaseModel):
    """Model for server-side workspace semaphores"""

    caught: bool = False
    has_mutex: bool = False


class WorkspaceNotFound(Exception):
    """The API doesn't have this workspace"""


class WorkspaceHasMutex(Exception):
    """The workspace is locked"""


class Client:
    """Boardwalkd protocol client"""

    def __init__(self, url: str):
        self.api_token_file = Path.cwd().joinpath(".boardwalk/api_token.txt")
        self.event_queue = deque([])
        self.url = urlparse(url)

    def get_api_token(self) -> str:
        """Retrieves the API token from disk"""
        return self.api_token_file.read_text().rstrip()

    async def api_login(self):
        """Performs an interactive login to the API and writes the session token
        to disk"""
        match self.url.scheme:
            case "http":
                websocket_url = self.url._replace(scheme="ws")
            case "https":
                websocket_url = self.url._replace(scheme="wss")
            case _:
                raise ValueError(f"{self.url.scheme} is not a valid url scheme")

        websocket_url = urljoin(websocket_url.geturl(), f"/api/auth/login/socket")
        conn = await websocket_connect(websocket_url)
        while True:
            msg = await conn.read_message()
            if not msg:
                # The msg is None if the connection closes
                raise ConnectionAbortedError("Server closed login websocket")

            msg = json.loads(str(msg))
            msg = ApiLoginMessage.parse_obj(msg)

            if msg.login_url:
                print(f"---\nPlease visit to login:\n{msg.login_url}")
                if webbrowser.open_new_tab(msg.login_url):
                    print("---\nOpened browser to login URL")
            elif msg.token:
                conn.close()
                self.api_token_file.write_text(msg.token)
                print("---\nAuthentication successful")
                return

    def authenticated_request(
        self,
        path: str,
        method: str = "GET",
        body: bytes | str | None = None,
        auto_login_prompt: bool = True,
    ) -> HTTPResponse:
        """Performs an API request with authentication. By default, auto-prompts
        for authentication if auth fails"""
        url = urljoin(self.url.geturl(), path)

        try:
            api_token = self.get_api_token()
        except FileNotFoundError:
            # If there is no token, automatically try to log in
            asyncio.run(self.api_login())
            # Always flush the event queue in case any messages were pending on auth
            self.flush_event_queue()

            api_token = self.get_api_token()

        request = HTTPRequest(
            method=method,
            body=body,
            headers={
                "Content-Type": "application/json",
                "boardwalk-api-token": api_token,
            },
            url=url,
        )
        client = HTTPClient()

        try:
            logger.debug(f"Fetching request {request.method} {request.url}")
            return client.fetch(request)
        except HTTPError as e:
            if e.code == 403 and auto_login_prompt:
                # If auth is denied, automatically try to login
                asyncio.run(self.api_login())
                # Always flush the event queue in case any messages were pending on auth
                self.flush_event_queue()
                # Attempt the request again
                return self.authenticated_request(
                    path=path,
                    method=method,
                    body=body,
                    auto_login_prompt=auto_login_prompt,
                )
            if e.code == 421:
                # The server URL is probably incorrect
                raise ConnectionRefusedError
            else:
                raise e

    def workspace_delete_mutex(self, workspace_name: str):
        """Deletes a workspace mutex"""
        try:
            self.authenticated_request(
                path=f"/api/workspace/{workspace_name}/semaphores/has_mutex",
                method="DELETE",
            )
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            else:
                raise e

    def workspace_get_details(self, workspace_name: str) -> WorkspaceDetails:
        """Queries the server for workspace details"""
        try:
            request = self.authenticated_request(
                path=f"/api/workspace/{workspace_name}/details",
            )
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            else:
                raise e

        details = WorkspaceDetails()
        return details.parse_raw(request.body)

    def workspace_post_catch(self, workspace_name: str):
        """Posts a catch to the server"""
        try:
            self.authenticated_request(
                path=f"/api/workspace/{workspace_name}/semaphores/caught",
                method="POST",
                body="catch",
            )
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            else:
                raise e

    def workspace_post_details(
        self, workspace_name: str, workspace_details: WorkspaceDetails
    ):
        """Updates the workspace details at the server"""
        try:
            self.authenticated_request(
                path=f"/api/workspace/{workspace_name}/details",
                method="POST",
                body=workspace_details.json(),
            )
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            else:
                raise e

    def workspace_post_heartbeat(self, workspace_name: str):
        """Posts a heartbeat to the server. This method will not automatically
        prompt to re-login if there is an auth failure"""
        try:
            self.authenticated_request(
                path=f"/api/workspace/{workspace_name}/heartbeat",
                method="POST",
                body="ping",
                auto_login_prompt=False,
            )
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            else:
                raise e

    def workspace_heartbeat_keepalive(
        self, workspace_name: str, quit: threading.Event
    ) -> None:
        """Tries to post a heartbeat to the server every 5 seconds"""
        while True:
            if quit.is_set():
                logging.debug("Heartbeat keepalive thread closing")
                return
            try:
                self.workspace_post_heartbeat(workspace_name)
            except (
                ConnectionRefusedError,
                HTTPClientError,
                HTTPError,
                HTTPTimeoutError,
                socket.gaierror,
            ) as e:
                logger.debug(f"Heartbeat keepalive error {e.__class__.__qualname__}")
                pass
            time.sleep(5)  # nosemgrep: python.lang.best-practice.sleep.arbitrary-sleep

    def workspace_heartbeat_keepalive_connect(
        self, workspace_name: str
    ) -> threading.Event:
        """Starts a background thread to post heartbeats to the server so it
        knows when a client is alive"""
        executor = concurrent.futures.ThreadPoolExecutor()
        quit = threading.Event()
        executor.submit(self.workspace_heartbeat_keepalive, workspace_name, quit)
        return quit

    def workspace_post_event(
        self,
        workspace_name: str,
        workspace_event: WorkspaceEvent,
        broadcast: bool = False,
    ):
        """Sends a event to the server to be logged or broadcast"""
        path = f"/api/workspace/{workspace_name}/event"
        if broadcast:
            path += "?broadcast=1"

        try:
            self.authenticated_request(
                path=path,
                method="POST",
                body=workspace_event.json(),
                auto_login_prompt=False,
            )
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            else:
                raise e

    def workspace_queue_event(
        self,
        workspace_name: str,
        workspace_event: WorkspaceEvent,
        broadcast: bool = False,
    ):
        """
        Appends an event to the event queue and attempts to flush messages to
        the server
        """
        self.event_queue.append(
            {
                "workspace_name": workspace_name,
                "workspace_event": workspace_event,
                "broadcast": broadcast,
            }
        )

        self.flush_event_queue()

    def flush_event_queue(self):
        """
        Attempts to flush events to the server
        """
        try:
            for event in self.event_queue.copy():
                self.workspace_post_event(**event)
                self.event_queue.popleft()
        except (ConnectionRefusedError, HTTPError):
            pass

    def workspace_post_mutex(self, workspace_name: str):
        """Posts a mutex to the server"""
        try:
            self.authenticated_request(
                path=f"/api/workspace/{workspace_name}/semaphores/has_mutex",
                method="POST",
                body="mutex",
            )
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            if e.code == 409:
                raise WorkspaceHasMutex
            else:
                raise e

    def workspace_get_semaphores(self, workspace_name: str) -> WorkspaceSemaphores:
        """Queries the server for workspace semaphores"""
        try:
            request = self.authenticated_request(
                path=f"/api/workspace/{workspace_name}/semaphores"
            )
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            else:
                raise e

        semaphores = WorkspaceSemaphores()
        return semaphores.parse_raw(request.body)


class WorkspaceClient(Client):
    """Subclass of the Boardwalkd protocol client with the Workspace name
    pre-initialized"""

    def __init__(self, url: str, workspace_name: str):
        super().__init__(url)
        self.workspace_name = workspace_name

    def get_semaphores(self) -> WorkspaceSemaphores:
        return self.workspace_get_semaphores(self.workspace_name)

    def has_mutex(self) -> bool:
        try:
            return self.get_semaphores().has_mutex
        except WorkspaceNotFound:
            return False

    def post_catch(self):
        self.workspace_post_catch(self.workspace_name)

    def caught(self) -> bool:
        return self.workspace_get_semaphores(self.workspace_name).caught

    def heartbeat_keepalive_connect(self):
        return self.workspace_heartbeat_keepalive_connect(self.workspace_name)

    def mutex(self):
        self.workspace_post_mutex(self.workspace_name)

    def post_details(self, workspace_details: WorkspaceDetails):
        self.workspace_post_details(self.workspace_name, workspace_details)

    def post_heartbeat(self):
        self.workspace_post_heartbeat(self.workspace_name)

    def post_event(self, workspace_event: WorkspaceEvent, broadcast: bool = False):
        self.workspace_post_event(self.workspace_name, workspace_event, broadcast)

    def queue_event(self, workspace_event: WorkspaceEvent, broadcast: bool = False):
        self.workspace_queue_event(self.workspace_name, workspace_event, broadcast)

    def unmutex(self):
        self.workspace_delete_mutex(self.workspace_name)
