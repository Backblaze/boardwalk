"""
This file defines objects that are passed between worker clients and the server,
and contains functions to support clients using the server
"""

import concurrent.futures
import socket
import time
from collections import deque
from datetime import datetime
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, Extra, validator
from tornado.httpclient import (
    AsyncHTTPClient,
    HTTPClient,
    HTTPClientError,
    HTTPError,
    HTTPRequest,
)
from tornado.simple_httpclient import HTTPTimeoutError
from tornado.websocket import websocket_connect


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
        self.async_client = AsyncHTTPClient()
        self.event_queue = deque([])
        self.url = urlparse(url)

    async def api_login(self):
        """Performs an interactive login to the API"""
        url = urljoin(self.url.geturl(), f"/api/auth/login")
        conn = await websocket_connect(url)
        while True:
            msg = await conn.read_message()
            msg = ApiLoginMessage.parse_obj(msg)
            if msg.login_url:
                print(f"Log in at {msg.login_url}")
            elif msg.token:
                print(msg.token)
                break
        conn.close()

    def workspace_delete_mutex(self, workspace_name: str):
        """Deletes a workspace mutex"""
        url = urljoin(
            self.url.geturl(), f"/api/workspace/{workspace_name}/semaphores/has_mutex"
        )
        request = HTTPRequest(
            method="DELETE",
            body=None,
            url=url,
        )
        client = HTTPClient()

        try:
            request = client.fetch(request)
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            else:
                raise e

    def workspace_get_details(self, workspace_name: str) -> WorkspaceDetails:
        """Queries the server for workspace details"""
        url = urljoin(self.url.geturl(), f"/api/workspace/{workspace_name}/details")
        client = HTTPClient()

        try:
            request = client.fetch(url)
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            else:
                raise e

        details = WorkspaceDetails()
        return details.parse_raw(request.body)

    def workspace_post_catch(self, workspace_name: str):
        """Posts a catch to the server"""
        url = urljoin(
            self.url.geturl(), f"/api/workspace/{workspace_name}/semaphores/caught"
        )
        request = HTTPRequest(
            method="POST",
            body="catch",
            url=url,
        )
        client = HTTPClient()

        try:
            client.fetch(request)
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            else:
                raise e

    def workspace_post_details(
        self, workspace_name: str, workspace_details: WorkspaceDetails
    ):
        """Updates the workspace details at the server"""
        url = urljoin(self.url.geturl(), f"/api/workspace/{workspace_name}/details")
        request = HTTPRequest(
            method="POST",
            headers={"Content-Type": "application/json"},
            body=workspace_details.json(),
            url=url,
        )
        client = HTTPClient()

        try:
            client.fetch(request)
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            else:
                raise e

    def workspace_post_heartbeat(self, workspace_name: str):
        """Posts a heartbeat to the server"""
        url = urljoin(self.url.geturl(), f"/api/workspace/{workspace_name}/heartbeat")
        request = HTTPRequest(
            method="POST",
            body="ping",
            url=url,
        )
        client = HTTPClient()

        try:
            client.fetch(request)
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            else:
                raise e

    def workspace_heartbeat_keepalive(self, workspace_name: str) -> None:
        """Tries to post a heartbeat to the server every 5 seconds"""
        while True:
            try:
                self.workspace_post_heartbeat(workspace_name)
            except (
                ConnectionRefusedError,
                HTTPClientError,
                HTTPTimeoutError,
                socket.gaierror,
            ):
                pass
            time.sleep(5)

    def workspace_heartbeat_keepalive_connect(
        self, workspace_name: str
    ) -> concurrent.futures.Future[None]:
        """Starts a background thread to post heartbeats to the server so it
        knows when a client is alive"""
        executor = concurrent.futures.ThreadPoolExecutor()
        future = executor.submit(self.workspace_heartbeat_keepalive, workspace_name)
        return future

    def workspace_post_event(
        self,
        workspace_name: str,
        workspace_event: WorkspaceEvent,
        broadcast: bool = False,
    ):
        """Sends a event to the server to be logged or broadcast"""
        url = urljoin(self.url.geturl(), f"/api/workspace/{workspace_name}/event")
        if broadcast:
            url = url + "?broadcast=1"
        request = HTTPRequest(
            method="POST",
            headers={"Content-Type": "application/json"},
            body=workspace_event.json(),
            url=url,
        )
        client = HTTPClient()

        try:
            client.fetch(request)
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
        Implements self.workspace_post_event(), maintaining a local queue of
        events to send. If an event cannot be sent, it will be sent along with
        the next successful attempt
        """
        self.event_queue.append(
            {
                "workspace_name": workspace_name,
                "workspace_event": workspace_event,
                "broadcast": broadcast,
            }
        )

        try:
            for event in self.event_queue.copy():
                self.workspace_post_event(**event)
                self.event_queue.popleft()
        except ConnectionRefusedError:
            pass

    def workspace_post_mutex(self, workspace_name: str):
        """Posts a mutex to the server"""
        url = urljoin(
            self.url.geturl(), f"/api/workspace/{workspace_name}/semaphores/has_mutex"
        )
        request = HTTPRequest(
            method="POST",
            body="mutex",
            url=url,
        )
        client = HTTPClient()

        try:
            client.fetch(request)
        except HTTPError as e:
            if e.code == 404:
                raise WorkspaceNotFound
            if e.code == 409:
                raise WorkspaceHasMutex
            else:
                raise e

    def workspace_get_semaphores(self, workspace_name: str) -> WorkspaceSemaphores:
        """Queries the server for workspace semaphores"""
        url = urljoin(self.url.geturl(), f"/api/workspace/{workspace_name}/semaphores")
        client = HTTPClient()

        try:
            request = client.fetch(url)
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
