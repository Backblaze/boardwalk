# {py:mod}`boardwalk.state`

```{py:module} boardwalk.state
```

```{autodoc2-docstring} boardwalk.state
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`StateBaseModel <boardwalk.state.StateBaseModel>`
  - ```{autodoc2-docstring} boardwalk.state.StateBaseModel
    :summary:
    ```
* - {py:obj}`LocalState <boardwalk.state.LocalState>`
  - ```{autodoc2-docstring} boardwalk.state.LocalState
    :summary:
    ```
* - {py:obj}`RemoteStateWorkflow <boardwalk.state.RemoteStateWorkflow>`
  - ```{autodoc2-docstring} boardwalk.state.RemoteStateWorkflow
    :summary:
    ```
* - {py:obj}`RemoteStateWorkspace <boardwalk.state.RemoteStateWorkspace>`
  - ```{autodoc2-docstring} boardwalk.state.RemoteStateWorkspace
    :summary:
    ```
* - {py:obj}`RemoteStateModel <boardwalk.state.RemoteStateModel>`
  - ```{autodoc2-docstring} boardwalk.state.RemoteStateModel
    :summary:
    ```
````

### API

````{py:class} StateBaseModel(/, **data: typing.Any)
:canonical: boardwalk.state.StateBaseModel

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} boardwalk.state.StateBaseModel
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.state.StateBaseModel.__init__
```

````

`````{py:class} LocalState(/, **data: typing.Any)
:canonical: boardwalk.state.LocalState

Bases: {py:obj}`boardwalk.state.StateBaseModel`

```{autodoc2-docstring} boardwalk.state.LocalState
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.state.LocalState.__init__
```

````{py:attribute} host_pattern
:canonical: boardwalk.state.LocalState.host_pattern
:type: str
:value: >
   None

```{autodoc2-docstring} boardwalk.state.LocalState.host_pattern
```

````

````{py:attribute} hosts
:canonical: boardwalk.state.LocalState.hosts
:type: dict[str, boardwalk.host.Host]
:value: >
   None

```{autodoc2-docstring} boardwalk.state.LocalState.hosts
```

````

`````

`````{py:class} RemoteStateWorkflow(/, **data: typing.Any)
:canonical: boardwalk.state.RemoteStateWorkflow

Bases: {py:obj}`boardwalk.state.StateBaseModel`

```{autodoc2-docstring} boardwalk.state.RemoteStateWorkflow
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.state.RemoteStateWorkflow.__init__
```

````{py:attribute} started
:canonical: boardwalk.state.RemoteStateWorkflow.started
:type: bool
:value: >
   False

```{autodoc2-docstring} boardwalk.state.RemoteStateWorkflow.started
```

````

````{py:attribute} succeeded
:canonical: boardwalk.state.RemoteStateWorkflow.succeeded
:type: bool
:value: >
   False

```{autodoc2-docstring} boardwalk.state.RemoteStateWorkflow.succeeded
```

````

`````

`````{py:class} RemoteStateWorkspace(/, **data: typing.Any)
:canonical: boardwalk.state.RemoteStateWorkspace

Bases: {py:obj}`boardwalk.state.StateBaseModel`

```{autodoc2-docstring} boardwalk.state.RemoteStateWorkspace
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.state.RemoteStateWorkspace.__init__
```

````{py:attribute} workflow
:canonical: boardwalk.state.RemoteStateWorkspace.workflow
:type: boardwalk.state.RemoteStateWorkflow
:value: >
   None

```{autodoc2-docstring} boardwalk.state.RemoteStateWorkspace.workflow
```

````

`````

`````{py:class} RemoteStateModel(/, **data: typing.Any)
:canonical: boardwalk.state.RemoteStateModel

Bases: {py:obj}`boardwalk.state.StateBaseModel`

```{autodoc2-docstring} boardwalk.state.RemoteStateModel
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.state.RemoteStateModel.__init__
```

````{py:attribute} workspaces
:canonical: boardwalk.state.RemoteStateModel.workspaces
:type: dict[str, boardwalk.state.RemoteStateWorkspace]
:value: >
   None

```{autodoc2-docstring} boardwalk.state.RemoteStateModel.workspaces
```

````

`````
