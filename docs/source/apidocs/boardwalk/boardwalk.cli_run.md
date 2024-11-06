# {py:mod}`boardwalk.cli_run`

```{py:module} boardwalk.cli_run
```

```{autodoc2-docstring} boardwalk.cli_run
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`run <boardwalk.cli_run.run>`
  - ```{autodoc2-docstring} boardwalk.cli_run.run
    :summary:
    ```
* - {py:obj}`check <boardwalk.cli_run.check>`
  - ```{autodoc2-docstring} boardwalk.cli_run.check
    :summary:
    ```
* - {py:obj}`run_workflow <boardwalk.cli_run.run_workflow>`
  - ```{autodoc2-docstring} boardwalk.cli_run.run_workflow
    :summary:
    ```
* - {py:obj}`run_failure_mode_handler <boardwalk.cli_run.run_failure_mode_handler>`
  - ```{autodoc2-docstring} boardwalk.cli_run.run_failure_mode_handler
    :summary:
    ```
* - {py:obj}`filter_hosts_by_limit <boardwalk.cli_run.filter_hosts_by_limit>`
  - ```{autodoc2-docstring} boardwalk.cli_run.filter_hosts_by_limit
    :summary:
    ```
* - {py:obj}`sort_host_list <boardwalk.cli_run.sort_host_list>`
  - ```{autodoc2-docstring} boardwalk.cli_run.sort_host_list
    :summary:
    ```
* - {py:obj}`check_host_preconditions_locally <boardwalk.cli_run.check_host_preconditions_locally>`
  - ```{autodoc2-docstring} boardwalk.cli_run.check_host_preconditions_locally
    :summary:
    ```
* - {py:obj}`handle_workflow_catch <boardwalk.cli_run.handle_workflow_catch>`
  - ```{autodoc2-docstring} boardwalk.cli_run.handle_workflow_catch
    :summary:
    ```
* - {py:obj}`lock_remote_host <boardwalk.cli_run.lock_remote_host>`
  - ```{autodoc2-docstring} boardwalk.cli_run.lock_remote_host
    :summary:
    ```
* - {py:obj}`bootstrap_with_server <boardwalk.cli_run.bootstrap_with_server>`
  - ```{autodoc2-docstring} boardwalk.cli_run.bootstrap_with_server
    :summary:
    ```
* - {py:obj}`update_host_facts_in_local_state <boardwalk.cli_run.update_host_facts_in_local_state>`
  - ```{autodoc2-docstring} boardwalk.cli_run.update_host_facts_in_local_state
    :summary:
    ```
* - {py:obj}`directly_confirm_host_preconditions <boardwalk.cli_run.directly_confirm_host_preconditions>`
  - ```{autodoc2-docstring} boardwalk.cli_run.directly_confirm_host_preconditions
    :summary:
    ```
* - {py:obj}`execute_workflow_jobs <boardwalk.cli_run.execute_workflow_jobs>`
  - ```{autodoc2-docstring} boardwalk.cli_run.execute_workflow_jobs
    :summary:
    ```
* - {py:obj}`execute_host_workflow <boardwalk.cli_run.execute_host_workflow>`
  - ```{autodoc2-docstring} boardwalk.cli_run.execute_host_workflow
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`become_password <boardwalk.cli_run.become_password>`
  - ```{autodoc2-docstring} boardwalk.cli_run.become_password
    :summary:
    ```
* - {py:obj}`boardwalkd_client <boardwalk.cli_run.boardwalkd_client>`
  - ```{autodoc2-docstring} boardwalk.cli_run.boardwalkd_client
    :summary:
    ```
* - {py:obj}`boardwalkd_send_broadcasts <boardwalk.cli_run.boardwalkd_send_broadcasts>`
  - ```{autodoc2-docstring} boardwalk.cli_run.boardwalkd_send_broadcasts
    :summary:
    ```
* - {py:obj}`_check_mode <boardwalk.cli_run._check_mode>`
  - ```{autodoc2-docstring} boardwalk.cli_run._check_mode
    :summary:
    ```
* - {py:obj}`_stomp_locks <boardwalk.cli_run._stomp_locks>`
  - ```{autodoc2-docstring} boardwalk.cli_run._stomp_locks
    :summary:
    ```
````

### API

````{py:data} become_password
:canonical: boardwalk.cli_run.become_password
:type: str | None
:value: >
   None

```{autodoc2-docstring} boardwalk.cli_run.become_password
```

````

````{py:data} boardwalkd_client
:canonical: boardwalk.cli_run.boardwalkd_client
:type: boardwalkd.protocol.WorkspaceClient | None
:value: >
   None

```{autodoc2-docstring} boardwalk.cli_run.boardwalkd_client
```

````

````{py:data} boardwalkd_send_broadcasts
:canonical: boardwalk.cli_run.boardwalkd_send_broadcasts
:type: bool
:value: >
   False

```{autodoc2-docstring} boardwalk.cli_run.boardwalkd_send_broadcasts
```

````

````{py:data} _check_mode
:canonical: boardwalk.cli_run._check_mode
:type: bool
:value: >
   True

```{autodoc2-docstring} boardwalk.cli_run._check_mode
```

````

````{py:data} _stomp_locks
:canonical: boardwalk.cli_run._stomp_locks
:type: bool
:value: >
   False

```{autodoc2-docstring} boardwalk.cli_run._stomp_locks
```

````

````{py:function} run(ctx: click.Context, ask_become_pass: bool, check: bool, limit: str, server_connect: bool, sort_hosts: str, stomp_locks: bool)
:canonical: boardwalk.cli_run.run

```{autodoc2-docstring} boardwalk.cli_run.run
```
````

````{py:function} check(ctx: click.Context, ask_become_pass: bool, limit: str, server_connect: bool, sort_hosts: str)
:canonical: boardwalk.cli_run.check

```{autodoc2-docstring} boardwalk.cli_run.check
```
````

````{py:function} run_workflow(hosts: list[boardwalk.host.Host], inventory_vars: boardwalk.ansible.HostVarsType, workspace: boardwalk.manifest.Workspace, verbosity: int)
:canonical: boardwalk.cli_run.run_workflow

```{autodoc2-docstring} boardwalk.cli_run.run_workflow
```
````

````{py:function} run_failure_mode_handler(exception: Exception, hostname: str, workspace: boardwalk.manifest.Workspace)
:canonical: boardwalk.cli_run.run_failure_mode_handler

```{autodoc2-docstring} boardwalk.cli_run.run_failure_mode_handler
```
````

````{py:function} filter_hosts_by_limit(workspace: boardwalk.manifest.Workspace, hosts: collections.abc.ItemsView[str, boardwalk.host.Host], pattern: str) -> list[boardwalk.host.Host]
:canonical: boardwalk.cli_run.filter_hosts_by_limit

```{autodoc2-docstring} boardwalk.cli_run.filter_hosts_by_limit
```
````

````{py:function} sort_host_list(hosts: list[boardwalk.host.Host], sort_method: str)
:canonical: boardwalk.cli_run.sort_host_list

```{autodoc2-docstring} boardwalk.cli_run.sort_host_list
```
````

````{py:function} check_host_preconditions_locally(hosts: list[boardwalk.host.Host], inventory_vars: boardwalk.ansible.HostVarsType, workspace: boardwalk.manifest.Workspace) -> list[boardwalk.host.Host]
:canonical: boardwalk.cli_run.check_host_preconditions_locally

```{autodoc2-docstring} boardwalk.cli_run.check_host_preconditions_locally
```
````

````{py:function} handle_workflow_catch(workspace: boardwalk.manifest.Workspace, hostname: str)
:canonical: boardwalk.cli_run.handle_workflow_catch

```{autodoc2-docstring} boardwalk.cli_run.handle_workflow_catch
```
````

````{py:function} lock_remote_host(host: boardwalk.host.Host)
:canonical: boardwalk.cli_run.lock_remote_host

```{autodoc2-docstring} boardwalk.cli_run.lock_remote_host
```
````

````{py:function} bootstrap_with_server(workspace: boardwalk.manifest.Workspace, ctx: click.Context)
:canonical: boardwalk.cli_run.bootstrap_with_server

```{autodoc2-docstring} boardwalk.cli_run.bootstrap_with_server
```
````

````{py:function} update_host_facts_in_local_state(host: boardwalk.host.Host, workspace: boardwalk.manifest.Workspace)
:canonical: boardwalk.cli_run.update_host_facts_in_local_state

```{autodoc2-docstring} boardwalk.cli_run.update_host_facts_in_local_state
```
````

````{py:function} directly_confirm_host_preconditions(host: boardwalk.host.Host, inventory_vars: boardwalk.ansible.InventoryHostVars, workspace: boardwalk.manifest.Workspace) -> bool
:canonical: boardwalk.cli_run.directly_confirm_host_preconditions

```{autodoc2-docstring} boardwalk.cli_run.directly_confirm_host_preconditions
```
````

````{py:function} execute_workflow_jobs(host: boardwalk.host.Host, workspace: boardwalk.manifest.Workspace, job_kind: str, verbosity: int)
:canonical: boardwalk.cli_run.execute_workflow_jobs

```{autodoc2-docstring} boardwalk.cli_run.execute_workflow_jobs
```
````

````{py:function} execute_host_workflow(host: boardwalk.host.Host, workspace: boardwalk.manifest.Workspace, verbosity: int)
:canonical: boardwalk.cli_run.execute_host_workflow

```{autodoc2-docstring} boardwalk.cli_run.execute_host_workflow
```
````

````{py:exception} NoHostsMatched()
:canonical: boardwalk.cli_run.NoHostsMatched

Bases: {py:obj}`Exception`

```{autodoc2-docstring} boardwalk.cli_run.NoHostsMatched
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.cli_run.NoHostsMatched.__init__
```

````

````{py:exception} HostPreConditionsUnmet()
:canonical: boardwalk.cli_run.HostPreConditionsUnmet

Bases: {py:obj}`Exception`

```{autodoc2-docstring} boardwalk.cli_run.HostPreConditionsUnmet
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.cli_run.HostPreConditionsUnmet.__init__
```

````
