# {py:mod}`boardwalkd.protocol`

```{py:module} boardwalkd.protocol
```

```{autodoc2-docstring} boardwalkd.protocol
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`ProtocolBaseModel <boardwalkd.protocol.ProtocolBaseModel>`
  - ```{autodoc2-docstring} boardwalkd.protocol.ProtocolBaseModel
    :summary:
    ```
* - {py:obj}`ApiLoginMessage <boardwalkd.protocol.ApiLoginMessage>`
  - ```{autodoc2-docstring} boardwalkd.protocol.ApiLoginMessage
    :summary:
    ```
* - {py:obj}`WorkspaceDetails <boardwalkd.protocol.WorkspaceDetails>`
  - ```{autodoc2-docstring} boardwalkd.protocol.WorkspaceDetails
    :summary:
    ```
* - {py:obj}`WorkspaceEvent <boardwalkd.protocol.WorkspaceEvent>`
  - ```{autodoc2-docstring} boardwalkd.protocol.WorkspaceEvent
    :summary:
    ```
* - {py:obj}`WorkspaceSemaphores <boardwalkd.protocol.WorkspaceSemaphores>`
  - ```{autodoc2-docstring} boardwalkd.protocol.WorkspaceSemaphores
    :summary:
    ```
* - {py:obj}`Client <boardwalkd.protocol.Client>`
  - ```{autodoc2-docstring} boardwalkd.protocol.Client
    :summary:
    ```
* - {py:obj}`WorkspaceClient <boardwalkd.protocol.WorkspaceClient>`
  - ```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient
    :summary:
    ```
````

### API

````{py:class} ProtocolBaseModel(/, **data: typing.Any)
:canonical: boardwalkd.protocol.ProtocolBaseModel

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} boardwalkd.protocol.ProtocolBaseModel
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.protocol.ProtocolBaseModel.__init__
```

````

`````{py:class} ApiLoginMessage(/, **data: typing.Any)
:canonical: boardwalkd.protocol.ApiLoginMessage

Bases: {py:obj}`boardwalkd.protocol.ProtocolBaseModel`

```{autodoc2-docstring} boardwalkd.protocol.ApiLoginMessage
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.protocol.ApiLoginMessage.__init__
```

````{py:attribute} login_url
:canonical: boardwalkd.protocol.ApiLoginMessage.login_url
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} boardwalkd.protocol.ApiLoginMessage.login_url
```

````

````{py:attribute} token
:canonical: boardwalkd.protocol.ApiLoginMessage.token
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} boardwalkd.protocol.ApiLoginMessage.token
```

````

`````

`````{py:class} WorkspaceDetails(/, **data: typing.Any)
:canonical: boardwalkd.protocol.WorkspaceDetails

Bases: {py:obj}`boardwalkd.protocol.ProtocolBaseModel`

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceDetails
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceDetails.__init__
```

````{py:attribute} host_pattern
:canonical: boardwalkd.protocol.WorkspaceDetails.host_pattern
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceDetails.host_pattern
```

````

````{py:attribute} workflow
:canonical: boardwalkd.protocol.WorkspaceDetails.workflow
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceDetails.workflow
```

````

````{py:attribute} worker_command
:canonical: boardwalkd.protocol.WorkspaceDetails.worker_command
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceDetails.worker_command
```

````

````{py:attribute} worker_hostname
:canonical: boardwalkd.protocol.WorkspaceDetails.worker_hostname
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceDetails.worker_hostname
```

````

````{py:attribute} worker_limit
:canonical: boardwalkd.protocol.WorkspaceDetails.worker_limit
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceDetails.worker_limit
```

````

````{py:attribute} worker_username
:canonical: boardwalkd.protocol.WorkspaceDetails.worker_username
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceDetails.worker_username
```

````

`````

`````{py:class} WorkspaceEvent(**kwargs: str)
:canonical: boardwalkd.protocol.WorkspaceEvent

Bases: {py:obj}`boardwalkd.protocol.ProtocolBaseModel`

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceEvent
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceEvent.__init__
```

````{py:attribute} message
:canonical: boardwalkd.protocol.WorkspaceEvent.message
:type: str
:value: >
   None

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceEvent.message
```

````

````{py:attribute} severity
:canonical: boardwalkd.protocol.WorkspaceEvent.severity
:type: str
:value: >
   None

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceEvent.severity
```

````

````{py:attribute} create_time
:canonical: boardwalkd.protocol.WorkspaceEvent.create_time
:type: datetime.datetime | None
:value: >
   None

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceEvent.create_time
```

````

````{py:attribute} received_time
:canonical: boardwalkd.protocol.WorkspaceEvent.received_time
:type: datetime.datetime | None
:value: >
   None

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceEvent.received_time
```

````

````{py:method} severity_level(v: str)
:canonical: boardwalkd.protocol.WorkspaceEvent.severity_level
:classmethod:

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceEvent.severity_level
```

````

`````

`````{py:class} WorkspaceSemaphores(/, **data: typing.Any)
:canonical: boardwalkd.protocol.WorkspaceSemaphores

Bases: {py:obj}`boardwalkd.protocol.ProtocolBaseModel`

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceSemaphores
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceSemaphores.__init__
```

````{py:attribute} caught
:canonical: boardwalkd.protocol.WorkspaceSemaphores.caught
:type: bool
:value: >
   False

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceSemaphores.caught
```

````

````{py:attribute} has_mutex
:canonical: boardwalkd.protocol.WorkspaceSemaphores.has_mutex
:type: bool
:value: >
   False

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceSemaphores.has_mutex
```

````

`````

````{py:exception} WorkspaceNotFound()
:canonical: boardwalkd.protocol.WorkspaceNotFound

Bases: {py:obj}`Exception`

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceNotFound
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceNotFound.__init__
```

````

````{py:exception} WorkspaceHasMutex()
:canonical: boardwalkd.protocol.WorkspaceHasMutex

Bases: {py:obj}`Exception`

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceHasMutex
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceHasMutex.__init__
```

````

`````{py:class} Client(url: str)
:canonical: boardwalkd.protocol.Client

```{autodoc2-docstring} boardwalkd.protocol.Client
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.protocol.Client.__init__
```

````{py:method} get_api_token() -> str
:canonical: boardwalkd.protocol.Client.get_api_token

```{autodoc2-docstring} boardwalkd.protocol.Client.get_api_token
```

````

````{py:method} api_login()
:canonical: boardwalkd.protocol.Client.api_login
:async:

```{autodoc2-docstring} boardwalkd.protocol.Client.api_login
```

````

````{py:method} authenticated_request(path: str, method: str = 'GET', body: bytes | str | None = None, auto_login_prompt: bool = True) -> tornado.httpclient.HTTPResponse
:canonical: boardwalkd.protocol.Client.authenticated_request

```{autodoc2-docstring} boardwalkd.protocol.Client.authenticated_request
```

````

````{py:method} workspace_delete_mutex(workspace_name: str)
:canonical: boardwalkd.protocol.Client.workspace_delete_mutex

```{autodoc2-docstring} boardwalkd.protocol.Client.workspace_delete_mutex
```

````

````{py:method} workspace_get_details(workspace_name: str) -> boardwalkd.protocol.WorkspaceDetails
:canonical: boardwalkd.protocol.Client.workspace_get_details

```{autodoc2-docstring} boardwalkd.protocol.Client.workspace_get_details
```

````

````{py:method} workspace_post_catch(workspace_name: str)
:canonical: boardwalkd.protocol.Client.workspace_post_catch

```{autodoc2-docstring} boardwalkd.protocol.Client.workspace_post_catch
```

````

````{py:method} workspace_post_details(workspace_name: str, workspace_details: boardwalkd.protocol.WorkspaceDetails)
:canonical: boardwalkd.protocol.Client.workspace_post_details

```{autodoc2-docstring} boardwalkd.protocol.Client.workspace_post_details
```

````

````{py:method} workspace_post_heartbeat(workspace_name: str)
:canonical: boardwalkd.protocol.Client.workspace_post_heartbeat

```{autodoc2-docstring} boardwalkd.protocol.Client.workspace_post_heartbeat
```

````

````{py:method} workspace_heartbeat_keepalive(workspace_name: str, quit: threading.Event) -> None
:canonical: boardwalkd.protocol.Client.workspace_heartbeat_keepalive

```{autodoc2-docstring} boardwalkd.protocol.Client.workspace_heartbeat_keepalive
```

````

````{py:method} workspace_heartbeat_keepalive_connect(workspace_name: str) -> threading.Event
:canonical: boardwalkd.protocol.Client.workspace_heartbeat_keepalive_connect

```{autodoc2-docstring} boardwalkd.protocol.Client.workspace_heartbeat_keepalive_connect
```

````

````{py:method} workspace_post_event(workspace_name: str, workspace_event: boardwalkd.protocol.WorkspaceEvent, broadcast: bool = False)
:canonical: boardwalkd.protocol.Client.workspace_post_event

```{autodoc2-docstring} boardwalkd.protocol.Client.workspace_post_event
```

````

````{py:method} workspace_queue_event(workspace_name: str, workspace_event: boardwalkd.protocol.WorkspaceEvent, broadcast: bool = False)
:canonical: boardwalkd.protocol.Client.workspace_queue_event

```{autodoc2-docstring} boardwalkd.protocol.Client.workspace_queue_event
```

````

````{py:method} flush_event_queue()
:canonical: boardwalkd.protocol.Client.flush_event_queue

```{autodoc2-docstring} boardwalkd.protocol.Client.flush_event_queue
```

````

````{py:method} workspace_post_mutex(workspace_name: str)
:canonical: boardwalkd.protocol.Client.workspace_post_mutex

```{autodoc2-docstring} boardwalkd.protocol.Client.workspace_post_mutex
```

````

````{py:method} workspace_get_semaphores(workspace_name: str) -> boardwalkd.protocol.WorkspaceSemaphores
:canonical: boardwalkd.protocol.Client.workspace_get_semaphores

```{autodoc2-docstring} boardwalkd.protocol.Client.workspace_get_semaphores
```

````

`````

`````{py:class} WorkspaceClient(url: str, workspace_name: str)
:canonical: boardwalkd.protocol.WorkspaceClient

Bases: {py:obj}`boardwalkd.protocol.Client`

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient.__init__
```

````{py:method} get_semaphores() -> boardwalkd.protocol.WorkspaceSemaphores
:canonical: boardwalkd.protocol.WorkspaceClient.get_semaphores

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient.get_semaphores
```

````

````{py:method} has_mutex() -> bool
:canonical: boardwalkd.protocol.WorkspaceClient.has_mutex

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient.has_mutex
```

````

````{py:method} post_catch()
:canonical: boardwalkd.protocol.WorkspaceClient.post_catch

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient.post_catch
```

````

````{py:method} caught() -> bool
:canonical: boardwalkd.protocol.WorkspaceClient.caught

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient.caught
```

````

````{py:method} heartbeat_keepalive_connect()
:canonical: boardwalkd.protocol.WorkspaceClient.heartbeat_keepalive_connect

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient.heartbeat_keepalive_connect
```

````

````{py:method} mutex()
:canonical: boardwalkd.protocol.WorkspaceClient.mutex

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient.mutex
```

````

````{py:method} post_details(workspace_details: boardwalkd.protocol.WorkspaceDetails)
:canonical: boardwalkd.protocol.WorkspaceClient.post_details

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient.post_details
```

````

````{py:method} post_heartbeat()
:canonical: boardwalkd.protocol.WorkspaceClient.post_heartbeat

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient.post_heartbeat
```

````

````{py:method} post_event(workspace_event: boardwalkd.protocol.WorkspaceEvent, broadcast: bool = False)
:canonical: boardwalkd.protocol.WorkspaceClient.post_event

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient.post_event
```

````

````{py:method} queue_event(workspace_event: boardwalkd.protocol.WorkspaceEvent, broadcast: bool = False)
:canonical: boardwalkd.protocol.WorkspaceClient.queue_event

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient.queue_event
```

````

````{py:method} unmutex()
:canonical: boardwalkd.protocol.WorkspaceClient.unmutex

```{autodoc2-docstring} boardwalkd.protocol.WorkspaceClient.unmutex
```

````

`````
