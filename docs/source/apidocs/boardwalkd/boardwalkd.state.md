# {py:mod}`boardwalkd.state`

```{py:module} boardwalkd.state
```

```{autodoc2-docstring} boardwalkd.state
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`StateBaseModel <boardwalkd.state.StateBaseModel>`
  - ```{autodoc2-docstring} boardwalkd.state.StateBaseModel
    :summary:
    ```
* - {py:obj}`User <boardwalkd.state.User>`
  - ```{autodoc2-docstring} boardwalkd.state.User
    :summary:
    ```
* - {py:obj}`WorkspaceState <boardwalkd.state.WorkspaceState>`
  - ```{autodoc2-docstring} boardwalkd.state.WorkspaceState
    :summary:
    ```
* - {py:obj}`State <boardwalkd.state.State>`
  - ```{autodoc2-docstring} boardwalkd.state.State
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`load_state <boardwalkd.state.load_state>`
  - ```{autodoc2-docstring} boardwalkd.state.load_state
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`statefile_dir_path <boardwalkd.state.statefile_dir_path>`
  - ```{autodoc2-docstring} boardwalkd.state.statefile_dir_path
    :summary:
    ```
* - {py:obj}`statefile_path <boardwalkd.state.statefile_path>`
  - ```{autodoc2-docstring} boardwalkd.state.statefile_path
    :summary:
    ```
* - {py:obj}`valid_user_roles <boardwalkd.state.valid_user_roles>`
  - ```{autodoc2-docstring} boardwalkd.state.valid_user_roles
    :summary:
    ```
````

### API

````{py:data} statefile_dir_path
:canonical: boardwalkd.state.statefile_dir_path
:value: >
   'joinpath(...)'

```{autodoc2-docstring} boardwalkd.state.statefile_dir_path
```

````

````{py:data} statefile_path
:canonical: boardwalkd.state.statefile_path
:value: >
   'joinpath(...)'

```{autodoc2-docstring} boardwalkd.state.statefile_path
```

````

````{py:data} valid_user_roles
:canonical: boardwalkd.state.valid_user_roles
:value: >
   None

```{autodoc2-docstring} boardwalkd.state.valid_user_roles
```

````

````{py:class} StateBaseModel(/, **data: typing.Any)
:canonical: boardwalkd.state.StateBaseModel

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} boardwalkd.state.StateBaseModel
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.state.StateBaseModel.__init__
```

````

`````{py:class} User(/, **data: typing.Any)
:canonical: boardwalkd.state.User

Bases: {py:obj}`boardwalkd.state.StateBaseModel`

```{autodoc2-docstring} boardwalkd.state.User
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.state.User.__init__
```

````{py:attribute} enabled
:canonical: boardwalkd.state.User.enabled
:type: bool
:value: >
   True

```{autodoc2-docstring} boardwalkd.state.User.enabled
```

````

````{py:attribute} email
:canonical: boardwalkd.state.User.email
:type: pydantic.EmailStr
:value: >
   None

```{autodoc2-docstring} boardwalkd.state.User.email
```

````

````{py:attribute} roles
:canonical: boardwalkd.state.User.roles
:type: set[str]
:value: >
   None

```{autodoc2-docstring} boardwalkd.state.User.roles
```

````

````{py:method} validate_roles(input_roles: set[str])
:canonical: boardwalkd.state.User.validate_roles
:classmethod:

```{autodoc2-docstring} boardwalkd.state.User.validate_roles
```

````

`````

`````{py:class} WorkspaceState(/, **data: typing.Any)
:canonical: boardwalkd.state.WorkspaceState

Bases: {py:obj}`boardwalkd.state.StateBaseModel`

```{autodoc2-docstring} boardwalkd.state.WorkspaceState
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.state.WorkspaceState.__init__
```

````{py:attribute} details
:canonical: boardwalkd.state.WorkspaceState.details
:type: boardwalkd.protocol.WorkspaceDetails
:value: >
   'WorkspaceDetails(...)'

```{autodoc2-docstring} boardwalkd.state.WorkspaceState.details
```

````

````{py:attribute} last_seen
:canonical: boardwalkd.state.WorkspaceState.last_seen
:type: datetime.datetime | None
:value: >
   None

```{autodoc2-docstring} boardwalkd.state.WorkspaceState.last_seen
```

````

````{py:attribute} _max_workspace_events
:canonical: boardwalkd.state.WorkspaceState._max_workspace_events
:type: int
:value: >
   64

```{autodoc2-docstring} boardwalkd.state.WorkspaceState._max_workspace_events
```

````

````{py:attribute} events
:canonical: boardwalkd.state.WorkspaceState.events
:type: collections.deque[boardwalkd.protocol.WorkspaceEvent]
:value: >
   'deque(...)'

```{autodoc2-docstring} boardwalkd.state.WorkspaceState.events
```

````

````{py:attribute} semaphores
:canonical: boardwalkd.state.WorkspaceState.semaphores
:type: boardwalkd.protocol.WorkspaceSemaphores
:value: >
   'WorkspaceSemaphores(...)'

```{autodoc2-docstring} boardwalkd.state.WorkspaceState.semaphores
```

````

````{py:method} validate_events(input_events: collections.deque[boardwalkd.protocol.WorkspaceEvent]) -> collections.deque[boardwalkd.protocol.WorkspaceEvent]
:canonical: boardwalkd.state.WorkspaceState.validate_events
:classmethod:

```{autodoc2-docstring} boardwalkd.state.WorkspaceState.validate_events
```

````

`````

`````{py:class} State(/, **data: typing.Any)
:canonical: boardwalkd.state.State

Bases: {py:obj}`boardwalkd.state.StateBaseModel`

```{autodoc2-docstring} boardwalkd.state.State
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalkd.state.State.__init__
```

````{py:attribute} workspaces
:canonical: boardwalkd.state.State.workspaces
:type: dict[str, boardwalkd.state.WorkspaceState]
:value: >
   None

```{autodoc2-docstring} boardwalkd.state.State.workspaces
```

````

````{py:attribute} users
:canonical: boardwalkd.state.State.users
:type: dict[str, boardwalkd.state.User]
:value: >
   None

```{autodoc2-docstring} boardwalkd.state.State.users
```

````

````{py:method} flush()
:canonical: boardwalkd.state.State.flush

```{autodoc2-docstring} boardwalkd.state.State.flush
```

````

`````

````{py:function} load_state() -> boardwalkd.state.State
:canonical: boardwalkd.state.load_state

```{autodoc2-docstring} boardwalkd.state.load_state
```
````
