# {py:mod}`boardwalk.manifest`

```{py:module} boardwalk.manifest
```

```{autodoc2-docstring} boardwalk.manifest
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`JobTypes <boardwalk.manifest.JobTypes>`
  -
* - {py:obj}`BaseJob <boardwalk.manifest.BaseJob>`
  - ```{autodoc2-docstring} boardwalk.manifest.BaseJob
    :summary:
    ```
* - {py:obj}`TaskJob <boardwalk.manifest.TaskJob>`
  - ```{autodoc2-docstring} boardwalk.manifest.TaskJob
    :summary:
    ```
* - {py:obj}`Job <boardwalk.manifest.Job>`
  - ```{autodoc2-docstring} boardwalk.manifest.Job
    :summary:
    ```
* - {py:obj}`PlaybookJob <boardwalk.manifest.PlaybookJob>`
  - ```{autodoc2-docstring} boardwalk.manifest.PlaybookJob
    :summary:
    ```
* - {py:obj}`WorkflowConfig <boardwalk.manifest.WorkflowConfig>`
  - ```{autodoc2-docstring} boardwalk.manifest.WorkflowConfig
    :summary:
    ```
* - {py:obj}`Workflow <boardwalk.manifest.Workflow>`
  - ```{autodoc2-docstring} boardwalk.manifest.Workflow
    :summary:
    ```
* - {py:obj}`WorkspaceConfig <boardwalk.manifest.WorkspaceConfig>`
  - ```{autodoc2-docstring} boardwalk.manifest.WorkspaceConfig
    :summary:
    ```
* - {py:obj}`Workspace <boardwalk.manifest.Workspace>`
  - ```{autodoc2-docstring} boardwalk.manifest.Workspace
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`get_ws <boardwalk.manifest.get_ws>`
  - ```{autodoc2-docstring} boardwalk.manifest.get_ws
    :summary:
    ```
* - {py:obj}`get_boardwalkd_url <boardwalk.manifest.get_boardwalkd_url>`
  - ```{autodoc2-docstring} boardwalk.manifest.get_boardwalkd_url
    :summary:
    ```
* - {py:obj}`path <boardwalk.manifest.path>`
  - ```{autodoc2-docstring} boardwalk.manifest.path
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`workspaces_dir <boardwalk.manifest.workspaces_dir>`
  - ```{autodoc2-docstring} boardwalk.manifest.workspaces_dir
    :summary:
    ```
* - {py:obj}`active_workspace_file <boardwalk.manifest.active_workspace_file>`
  - ```{autodoc2-docstring} boardwalk.manifest.active_workspace_file
    :summary:
    ```
````

### API

````{py:data} workspaces_dir
:canonical: boardwalk.manifest.workspaces_dir
:value: >
   'joinpath(...)'

```{autodoc2-docstring} boardwalk.manifest.workspaces_dir
```

````

````{py:data} active_workspace_file
:canonical: boardwalk.manifest.active_workspace_file
:value: >
   'joinpath(...)'

```{autodoc2-docstring} boardwalk.manifest.active_workspace_file
```

````

````{py:exception} DuplicateManifestClass()
:canonical: boardwalk.manifest.DuplicateManifestClass

Bases: {py:obj}`Exception`

```{autodoc2-docstring} boardwalk.manifest.DuplicateManifestClass
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.manifest.DuplicateManifestClass.__init__
```

````

````{py:exception} ManifestNotFound()
:canonical: boardwalk.manifest.ManifestNotFound

Bases: {py:obj}`Exception`

```{autodoc2-docstring} boardwalk.manifest.ManifestNotFound
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.manifest.ManifestNotFound.__init__
```

````

`````{py:exception} NoActiveWorkspace()
:canonical: boardwalk.manifest.NoActiveWorkspace

Bases: {py:obj}`Exception`

```{autodoc2-docstring} boardwalk.manifest.NoActiveWorkspace
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.manifest.NoActiveWorkspace.__init__
```

````{py:attribute} message
:canonical: boardwalk.manifest.NoActiveWorkspace.message
:value: >
   'No workspace selected. Use `boardwalk workspace list` to list workspaces and `boardwalk workspace us...'

```{autodoc2-docstring} boardwalk.manifest.NoActiveWorkspace.message
```

````

`````

````{py:exception} WorkspaceNotFound()
:canonical: boardwalk.manifest.WorkspaceNotFound

Bases: {py:obj}`Exception`

```{autodoc2-docstring} boardwalk.manifest.WorkspaceNotFound
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.manifest.WorkspaceNotFound.__init__
```

````

````{py:function} get_ws() -> Workspace
:canonical: boardwalk.manifest.get_ws

```{autodoc2-docstring} boardwalk.manifest.get_ws
```
````

````{py:function} get_boardwalkd_url() -> str
:canonical: boardwalk.manifest.get_boardwalkd_url

```{autodoc2-docstring} boardwalk.manifest.get_boardwalkd_url
```
````

`````{py:class} JobTypes(*args, **kwds)
:canonical: boardwalk.manifest.JobTypes

Bases: {py:obj}`enum.Enum`

````{py:attribute} TASK
:canonical: boardwalk.manifest.JobTypes.TASK
:value: >
   1

```{autodoc2-docstring} boardwalk.manifest.JobTypes.TASK
```

````

````{py:attribute} PLAYBOOK
:canonical: boardwalk.manifest.JobTypes.PLAYBOOK
:value: >
   2

```{autodoc2-docstring} boardwalk.manifest.JobTypes.PLAYBOOK
```

````

`````

`````{py:class} BaseJob(options: dict[str, typing.Any] = dict())
:canonical: boardwalk.manifest.BaseJob

```{autodoc2-docstring} boardwalk.manifest.BaseJob
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.manifest.BaseJob.__init__
```

````{py:attribute} options
:canonical: boardwalk.manifest.BaseJob.options
:value: >
   None

```{autodoc2-docstring} boardwalk.manifest.BaseJob.options
```

````

````{py:method} required_options() -> tuple[str]
:canonical: boardwalk.manifest.BaseJob.required_options

```{autodoc2-docstring} boardwalk.manifest.BaseJob.required_options
```

````

````{py:method} preconditions(facts: boardwalk.ansible.AnsibleFacts, inventory_vars: boardwalk.ansible.InventoryHostVars) -> bool
:canonical: boardwalk.manifest.BaseJob.preconditions

```{autodoc2-docstring} boardwalk.manifest.BaseJob.preconditions
```

````

````{py:method} _required_options() -> tuple[str]
:canonical: boardwalk.manifest.BaseJob._required_options

```{autodoc2-docstring} boardwalk.manifest.BaseJob._required_options
```

````

````{py:method} _check_options(options: dict[str, typing.Any])
:canonical: boardwalk.manifest.BaseJob._check_options

```{autodoc2-docstring} boardwalk.manifest.BaseJob._check_options
```

````

`````

`````{py:class} TaskJob(options: dict[str, typing.Any] = dict())
:canonical: boardwalk.manifest.TaskJob

Bases: {py:obj}`boardwalk.manifest.BaseJob`

```{autodoc2-docstring} boardwalk.manifest.TaskJob
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.manifest.TaskJob.__init__
```

````{py:method} tasks() -> boardwalk.ansible.AnsibleTasksType
:canonical: boardwalk.manifest.TaskJob.tasks

```{autodoc2-docstring} boardwalk.manifest.TaskJob.tasks
```

````

`````

````{py:class} Job(options: dict[str, typing.Any] = dict())
:canonical: boardwalk.manifest.Job

Bases: {py:obj}`boardwalk.manifest.TaskJob`

```{autodoc2-docstring} boardwalk.manifest.Job
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.manifest.Job.__init__
```

````

`````{py:class} PlaybookJob(options: dict[str, typing.Any] = dict())
:canonical: boardwalk.manifest.PlaybookJob

Bases: {py:obj}`boardwalk.manifest.BaseJob`

```{autodoc2-docstring} boardwalk.manifest.PlaybookJob
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.manifest.PlaybookJob.__init__
```

````{py:method} tasks() -> boardwalk.ansible.AnsibleTasksType
:canonical: boardwalk.manifest.PlaybookJob.tasks

```{autodoc2-docstring} boardwalk.manifest.PlaybookJob.tasks
```

````

````{py:method} playbooks() -> boardwalk.ansible.AnsibleTasksType
:canonical: boardwalk.manifest.PlaybookJob.playbooks

```{autodoc2-docstring} boardwalk.manifest.PlaybookJob.playbooks
```

````

`````

````{py:class} WorkflowConfig(always_retry_failed_hosts: bool = True)
:canonical: boardwalk.manifest.WorkflowConfig

```{autodoc2-docstring} boardwalk.manifest.WorkflowConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.manifest.WorkflowConfig.__init__
```

````

`````{py:class} Workflow()
:canonical: boardwalk.manifest.Workflow

Bases: {py:obj}`abc.ABC`

```{autodoc2-docstring} boardwalk.manifest.Workflow
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.manifest.Workflow.__init__
```

````{py:method} config() -> boardwalk.manifest.WorkflowConfig
:canonical: boardwalk.manifest.Workflow.config

```{autodoc2-docstring} boardwalk.manifest.Workflow.config
```

````

````{py:method} jobs()
:canonical: boardwalk.manifest.Workflow.jobs
:abstractmethod:

```{autodoc2-docstring} boardwalk.manifest.Workflow.jobs
```

````

````{py:method} exit_jobs() -> boardwalk.manifest.TaskJob | boardwalk.manifest.PlaybookJob | tuple[boardwalk.manifest.TaskJob | boardwalk.manifest.PlaybookJob, ...]
:canonical: boardwalk.manifest.Workflow.exit_jobs

```{autodoc2-docstring} boardwalk.manifest.Workflow.exit_jobs
```

````

`````

`````{py:class} WorkspaceConfig(host_pattern: str, workflow: boardwalk.manifest.Workflow, default_sort_order: str = 'shuffle', require_limit: bool = False)
:canonical: boardwalk.manifest.WorkspaceConfig

```{autodoc2-docstring} boardwalk.manifest.WorkspaceConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.manifest.WorkspaceConfig.__init__
```

````{py:attribute} valid_sort_orders
:canonical: boardwalk.manifest.WorkspaceConfig.valid_sort_orders
:value: >
   ['ascending', 'descending', 'shuffle']

```{autodoc2-docstring} boardwalk.manifest.WorkspaceConfig.valid_sort_orders
```

````

````{py:property} default_sort_order
:canonical: boardwalk.manifest.WorkspaceConfig.default_sort_order
:type: str

```{autodoc2-docstring} boardwalk.manifest.WorkspaceConfig.default_sort_order
```

````

````{py:method} _is_valid_sort_order(value: str)
:canonical: boardwalk.manifest.WorkspaceConfig._is_valid_sort_order

```{autodoc2-docstring} boardwalk.manifest.WorkspaceConfig._is_valid_sort_order
```

````

`````

`````{py:class} Workspace()
:canonical: boardwalk.manifest.Workspace

Bases: {py:obj}`abc.ABC`

```{autodoc2-docstring} boardwalk.manifest.Workspace
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.manifest.Workspace.__init__
```

````{py:attribute} _initialized
:canonical: boardwalk.manifest.Workspace._initialized
:type: bool
:value: >
   False

```{autodoc2-docstring} boardwalk.manifest.Workspace._initialized
```

````

````{py:attribute} _instance
:canonical: boardwalk.manifest.Workspace._instance
:type: boardwalk.manifest.Workspace | None
:value: >
   None

```{autodoc2-docstring} boardwalk.manifest.Workspace._instance
```

````

````{py:method} __new__()
:canonical: boardwalk.manifest.Workspace.__new__

```{autodoc2-docstring} boardwalk.manifest.Workspace.__new__
```

````

````{py:method} assert_host_pattern_unchanged() -> None
:canonical: boardwalk.manifest.Workspace.assert_host_pattern_unchanged

```{autodoc2-docstring} boardwalk.manifest.Workspace.assert_host_pattern_unchanged
```

````

````{py:method} config() -> boardwalk.manifest.WorkspaceConfig
:canonical: boardwalk.manifest.Workspace.config
:abstractmethod:

```{autodoc2-docstring} boardwalk.manifest.Workspace.config
```

````

````{py:method} flush()
:canonical: boardwalk.manifest.Workspace.flush

```{autodoc2-docstring} boardwalk.manifest.Workspace.flush
```

````

````{py:method} reset()
:canonical: boardwalk.manifest.Workspace.reset

```{autodoc2-docstring} boardwalk.manifest.Workspace.reset
```

````

````{py:method} mutex()
:canonical: boardwalk.manifest.Workspace.mutex

```{autodoc2-docstring} boardwalk.manifest.Workspace.mutex
```

````

````{py:method} has_mutex()
:canonical: boardwalk.manifest.Workspace.has_mutex

```{autodoc2-docstring} boardwalk.manifest.Workspace.has_mutex
```

````

````{py:method} unmutex()
:canonical: boardwalk.manifest.Workspace.unmutex

```{autodoc2-docstring} boardwalk.manifest.Workspace.unmutex
```

````

````{py:method} catch()
:canonical: boardwalk.manifest.Workspace.catch

```{autodoc2-docstring} boardwalk.manifest.Workspace.catch
```

````

````{py:method} caught()
:canonical: boardwalk.manifest.Workspace.caught

```{autodoc2-docstring} boardwalk.manifest.Workspace.caught
```

````

````{py:method} release()
:canonical: boardwalk.manifest.Workspace.release

```{autodoc2-docstring} boardwalk.manifest.Workspace.release
```

````

````{py:method} use(name: str)
:canonical: boardwalk.manifest.Workspace.use
:staticmethod:

```{autodoc2-docstring} boardwalk.manifest.Workspace.use
```

````

````{py:method} exists(name: str) -> bool
:canonical: boardwalk.manifest.Workspace.exists
:staticmethod:

```{autodoc2-docstring} boardwalk.manifest.Workspace.exists
```

````

````{py:method} fetch_subclass(name: str) -> collections.abc.Callable[..., boardwalk.manifest.Workspace]
:canonical: boardwalk.manifest.Workspace.fetch_subclass
:staticmethod:

```{autodoc2-docstring} boardwalk.manifest.Workspace.fetch_subclass
```

````

`````

````{py:function} path(file_path: str) -> str
:canonical: boardwalk.manifest.path

```{autodoc2-docstring} boardwalk.manifest.path
```
````
