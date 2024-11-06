# {py:mod}`boardwalk.ansible`

```{py:module} boardwalk.ansible
```

```{autodoc2-docstring} boardwalk.ansible
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`ansible_runner_cancel_callback <boardwalk.ansible.ansible_runner_cancel_callback>`
  - ```{autodoc2-docstring} boardwalk.ansible.ansible_runner_cancel_callback
    :summary:
    ```
* - {py:obj}`ansible_runner_errors_to_output <boardwalk.ansible.ansible_runner_errors_to_output>`
  - ```{autodoc2-docstring} boardwalk.ansible.ansible_runner_errors_to_output
    :summary:
    ```
* - {py:obj}`ansible_runner_run_tasks <boardwalk.ansible.ansible_runner_run_tasks>`
  - ```{autodoc2-docstring} boardwalk.ansible.ansible_runner_run_tasks
    :summary:
    ```
* - {py:obj}`ansible_inventory <boardwalk.ansible.ansible_inventory>`
  - ```{autodoc2-docstring} boardwalk.ansible.ansible_inventory
    :summary:
    ```
````

### API

````{py:function} ansible_runner_cancel_callback(ws: boardwalk.manifest.Workspace)
:canonical: boardwalk.ansible.ansible_runner_cancel_callback

```{autodoc2-docstring} boardwalk.ansible.ansible_runner_cancel_callback
```
````

````{py:function} ansible_runner_errors_to_output(runner: ansible_runner.Runner, include_msg: bool = True) -> str
:canonical: boardwalk.ansible.ansible_runner_errors_to_output

```{autodoc2-docstring} boardwalk.ansible.ansible_runner_errors_to_output
```
````

````{py:function} ansible_runner_run_tasks(hosts: str, invocation_msg: str, job_type: boardwalk.manifest.JobTypes, tasks: boardwalk.ansible.AnsibleTasksType, become: bool = False, become_password: str | None = None, check: bool = False, gather_facts: bool = True, limit: str | None = None, quiet: bool = True, timeout: int | None = None, verbosity: int = 0, extra_vars: dict = {}) -> ansible_runner.Runner
:canonical: boardwalk.ansible.ansible_runner_run_tasks

```{autodoc2-docstring} boardwalk.ansible.ansible_runner_run_tasks
```
````

````{py:function} ansible_inventory() -> boardwalk.ansible.InventoryData
:canonical: boardwalk.ansible.ansible_inventory

```{autodoc2-docstring} boardwalk.ansible.ansible_inventory
```
````

````{py:exception} AnsibleRunnerBaseException(message: str, runner_msg: str, runner: ansible_runner.Runner)
:canonical: boardwalk.ansible.AnsibleRunnerBaseException

Bases: {py:obj}`Exception`

```{autodoc2-docstring} boardwalk.ansible.AnsibleRunnerBaseException
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.ansible.AnsibleRunnerBaseException.__init__
```

````

````{py:exception} AnsibleRunnerGeneralError(message: str, runner_msg: str, runner: ansible_runner.Runner)
:canonical: boardwalk.ansible.AnsibleRunnerGeneralError

Bases: {py:obj}`boardwalk.ansible.AnsibleRunnerBaseException`

```{autodoc2-docstring} boardwalk.ansible.AnsibleRunnerGeneralError
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.ansible.AnsibleRunnerGeneralError.__init__
```

````

````{py:exception} AnsibleRunError(message: str, runner_msg: str, runner: ansible_runner.Runner)
:canonical: boardwalk.ansible.AnsibleRunError

Bases: {py:obj}`boardwalk.ansible.AnsibleRunnerBaseException`

```{autodoc2-docstring} boardwalk.ansible.AnsibleRunError
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.ansible.AnsibleRunError.__init__
```

````

````{py:exception} AnsibleRunnerUnreachableHost(message: str, runner_msg: str, runner: ansible_runner.Runner)
:canonical: boardwalk.ansible.AnsibleRunnerUnreachableHost

Bases: {py:obj}`boardwalk.ansible.AnsibleRunnerBaseException`

```{autodoc2-docstring} boardwalk.ansible.AnsibleRunnerUnreachableHost
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.ansible.AnsibleRunnerUnreachableHost.__init__
```

````

````{py:exception} AnsibleRunnerFailedHost(message: str, runner_msg: str, runner: ansible_runner.Runner)
:canonical: boardwalk.ansible.AnsibleRunnerFailedHost

Bases: {py:obj}`boardwalk.ansible.AnsibleRunnerBaseException`

```{autodoc2-docstring} boardwalk.ansible.AnsibleRunnerFailedHost
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.ansible.AnsibleRunnerFailedHost.__init__
```

````
