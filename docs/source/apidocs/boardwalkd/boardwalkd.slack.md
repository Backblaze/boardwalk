# {py:mod}`boardwalkd.slack`

```{py:module} boardwalkd.slack
```

```{autodoc2-docstring} boardwalkd.slack
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_count_of_workspaces_caught <boardwalkd.slack._count_of_workspaces_caught>`
  - ```{autodoc2-docstring} boardwalkd.slack._count_of_workspaces_caught
    :summary:
    ```
* - {py:obj}`_list_active_workspaces <boardwalkd.slack._list_active_workspaces>`
  - ```{autodoc2-docstring} boardwalkd.slack._list_active_workspaces
    :summary:
    ```
* - {py:obj}`_list_inactive_workspaces <boardwalkd.slack._list_inactive_workspaces>`
  - ```{autodoc2-docstring} boardwalkd.slack._list_inactive_workspaces
    :summary:
    ```
* - {py:obj}`hello_command <boardwalkd.slack.hello_command>`
  - ```{autodoc2-docstring} boardwalkd.slack.hello_command
    :summary:
    ```
* - {py:obj}`catch_release_workspaces <boardwalkd.slack.catch_release_workspaces>`
  - ```{autodoc2-docstring} boardwalkd.slack.catch_release_workspaces
    :summary:
    ```
* - {py:obj}`modal_catch_release_view_submission_event <boardwalkd.slack.modal_catch_release_view_submission_event>`
  - ```{autodoc2-docstring} boardwalkd.slack.modal_catch_release_view_submission_event
    :summary:
    ```
* - {py:obj}`command_list_active_workspaces <boardwalkd.slack.command_list_active_workspaces>`
  - ```{autodoc2-docstring} boardwalkd.slack.command_list_active_workspaces
    :summary:
    ```
* - {py:obj}`app_home_opened <boardwalkd.slack.app_home_opened>`
  - ```{autodoc2-docstring} boardwalkd.slack.app_home_opened
    :summary:
    ```
* - {py:obj}`app_home_workspace_details <boardwalkd.slack.app_home_workspace_details>`
  - ```{autodoc2-docstring} boardwalkd.slack.app_home_workspace_details
    :summary:
    ```
* - {py:obj}`_modal_about_boardwalk <boardwalkd.slack._modal_about_boardwalk>`
  - ```{autodoc2-docstring} boardwalkd.slack._modal_about_boardwalk
    :summary:
    ```
* - {py:obj}`action_app_home_overflow_menu_event_handler <boardwalkd.slack.action_app_home_overflow_menu_event_handler>`
  - ```{autodoc2-docstring} boardwalkd.slack.action_app_home_overflow_menu_event_handler
    :summary:
    ```
* - {py:obj}`dummy_slack_acknowledgement_handler <boardwalkd.slack.dummy_slack_acknowledgement_handler>`
  - ```{autodoc2-docstring} boardwalkd.slack.dummy_slack_acknowledgement_handler
    :summary:
    ```
* - {py:obj}`auth_boardwalk <boardwalkd.slack.auth_boardwalk>`
  - ```{autodoc2-docstring} boardwalkd.slack.auth_boardwalk
    :summary:
    ```
* - {py:obj}`connect <boardwalkd.slack.connect>`
  - ```{autodoc2-docstring} boardwalkd.slack.connect
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`app <boardwalkd.slack.app>`
  - ```{autodoc2-docstring} boardwalkd.slack.app
    :summary:
    ```
````

### API

````{py:data} app
:canonical: boardwalkd.slack.app
:value: >
   'AsyncApp(...)'

```{autodoc2-docstring} boardwalkd.slack.app
```

````

````{py:function} _count_of_workspaces_caught() -> int
:canonical: boardwalkd.slack._count_of_workspaces_caught

```{autodoc2-docstring} boardwalkd.slack._count_of_workspaces_caught
```
````

````{py:function} _list_active_workspaces(last_seen_seconds: int = 10, _sorted: bool = True) -> list[str]
:canonical: boardwalkd.slack._list_active_workspaces

```{autodoc2-docstring} boardwalkd.slack._list_active_workspaces
```
````

````{py:function} _list_inactive_workspaces(last_seen_seconds: int = 10) -> list[str]
:canonical: boardwalkd.slack._list_inactive_workspaces

```{autodoc2-docstring} boardwalkd.slack._list_inactive_workspaces
```
````

````{py:function} hello_command(ack: slack_bolt.async_app.AsyncAck, body: dict[str, typing.Any], client: slack_sdk.web.async_client.AsyncWebClient) -> None
:canonical: boardwalkd.slack.hello_command
:async:

```{autodoc2-docstring} boardwalkd.slack.hello_command
```
````

````{py:function} catch_release_workspaces(ack: slack_bolt.async_app.AsyncAck, body: dict[str, typing.Any], client: slack_sdk.web.async_client.AsyncWebClient)
:canonical: boardwalkd.slack.catch_release_workspaces
:async:

```{autodoc2-docstring} boardwalkd.slack.catch_release_workspaces
```
````

````{py:function} modal_catch_release_view_submission_event(ack: slack_bolt.async_app.AsyncAck, client: slack_sdk.web.async_client.AsyncWebClient, context: slack_bolt.async_app.AsyncBoltContext, logger: logging.Logger, payload: dict[str, typing.Any])
:canonical: boardwalkd.slack.modal_catch_release_view_submission_event
:async:

```{autodoc2-docstring} boardwalkd.slack.modal_catch_release_view_submission_event
```
````

````{py:function} command_list_active_workspaces(ack: slack_bolt.async_app.AsyncAck, body: dict[str, typing.Any], client: slack_sdk.web.async_client.AsyncWebClient) -> None
:canonical: boardwalkd.slack.command_list_active_workspaces
:async:

```{autodoc2-docstring} boardwalkd.slack.command_list_active_workspaces
```
````

````{py:function} app_home_opened(ack: slack_bolt.async_app.AsyncAck, client: slack_sdk.web.async_client.AsyncWebClient, logger: logging.Logger, context: slack_bolt.async_app.AsyncBoltContext)
:canonical: boardwalkd.slack.app_home_opened
:async:

```{autodoc2-docstring} boardwalkd.slack.app_home_opened
```
````

````{py:function} app_home_workspace_details(ack: slack_bolt.async_app.AsyncAck, logger: logging.Logger, client: slack_sdk.web.async_client.AsyncWebClient, context: slack_bolt.async_app.AsyncBoltContext, payload: dict[str, typing.Any]) -> None
:canonical: boardwalkd.slack.app_home_workspace_details
:async:

```{autodoc2-docstring} boardwalkd.slack.app_home_workspace_details
```
````

````{py:function} _modal_about_boardwalk(trigger_id: str, client: slack_sdk.web.async_client.AsyncWebClient)
:canonical: boardwalkd.slack._modal_about_boardwalk
:async:

```{autodoc2-docstring} boardwalkd.slack._modal_about_boardwalk
```
````

````{py:function} action_app_home_overflow_menu_event_handler(ack: slack_bolt.async_app.AsyncAck, body: dict[str, typing.Any], client: slack_sdk.web.async_client.AsyncWebClient, payload) -> None
:canonical: boardwalkd.slack.action_app_home_overflow_menu_event_handler
:async:

```{autodoc2-docstring} boardwalkd.slack.action_app_home_overflow_menu_event_handler
```
````

````{py:function} dummy_slack_acknowledgement_handler(ack: slack_bolt.async_app.AsyncAck)
:canonical: boardwalkd.slack.dummy_slack_acknowledgement_handler
:async:

```{autodoc2-docstring} boardwalkd.slack.dummy_slack_acknowledgement_handler
```
````

````{py:function} auth_boardwalk(client: slack_sdk.web.async_client.AsyncWebClient, context: slack_bolt.async_app.AsyncBoltContext, payload: dict[str, typing.Any], next: collections.abc.Callable[[], collections.abc.Awaitable]) -> None
:canonical: boardwalkd.slack.auth_boardwalk
:async:

```{autodoc2-docstring} boardwalkd.slack.auth_boardwalk
```
````

````{py:function} connect() -> None
:canonical: boardwalkd.slack.connect
:async:

```{autodoc2-docstring} boardwalkd.slack.connect
```
````
