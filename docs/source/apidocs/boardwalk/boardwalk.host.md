# {py:mod}`boardwalk.host`

```{py:module} boardwalk.host
```

```{autodoc2-docstring} boardwalk.host
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`Host <boardwalk.host.Host>`
  - ```{autodoc2-docstring} boardwalk.host.Host
    :summary:
    ```
````

### API

`````{py:class} Host(/, **data: typing.Any)
:canonical: boardwalk.host.Host

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} boardwalk.host.Host
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.host.Host.__init__
```

````{py:attribute} ansible_facts
:canonical: boardwalk.host.Host.ansible_facts
:type: dict[str, typing.Any]
:value: >
   None

```{autodoc2-docstring} boardwalk.host.Host.ansible_facts
```

````

````{py:attribute} name
:canonical: boardwalk.host.Host.name
:type: str
:value: >
   None

```{autodoc2-docstring} boardwalk.host.Host.name
```

````

````{py:attribute} meta
:canonical: boardwalk.host.Host.meta
:type: dict[str, str | int | bool]
:value: >
   None

```{autodoc2-docstring} boardwalk.host.Host.meta
```

````

````{py:attribute} remote_mutex_path
:canonical: boardwalk.host.Host.remote_mutex_path
:type: str
:value: >
   '/opt/boardwalk.mutex'

```{autodoc2-docstring} boardwalk.host.Host.remote_mutex_path
```

````

````{py:attribute} remote_alert_msg
:canonical: boardwalk.host.Host.remote_alert_msg
:type: str
:value: >
   'ALERT: Boardwalk is running a workflow against this host. Services may be interrupted'

```{autodoc2-docstring} boardwalk.host.Host.remote_alert_msg
```

````

````{py:attribute} remote_alert_string_formatted
:canonical: boardwalk.host.Host.remote_alert_string_formatted
:type: str
:value: >
   None

```{autodoc2-docstring} boardwalk.host.Host.remote_alert_string_formatted
```

````

````{py:attribute} remote_alert_motd
:canonical: boardwalk.host.Host.remote_alert_motd
:type: str
:value: >
   None

```{autodoc2-docstring} boardwalk.host.Host.remote_alert_motd
```

````

````{py:attribute} remote_alert_motd_path
:canonical: boardwalk.host.Host.remote_alert_motd_path
:type: str
:value: >
   '/etc/update-motd.d/99-boardwalk-alert'

```{autodoc2-docstring} boardwalk.host.Host.remote_alert_motd_path
```

````

````{py:attribute} remote_alert_wall_cmd
:canonical: boardwalk.host.Host.remote_alert_wall_cmd
:type: str
:value: >
   None

```{autodoc2-docstring} boardwalk.host.Host.remote_alert_wall_cmd
```

````

````{py:method} ansible_run(invocation_msg: str, tasks: boardwalk.ansible.AnsibleTasksType, job_type: boardwalk.manifest.JobTypes, verbosity: int = 0, become: bool = False, become_password: str | None = None, check: bool = False, gather_facts: bool = True, quiet: bool = True, extra_vars: dict = {}) -> ansible_runner.Runner
:canonical: boardwalk.host.Host.ansible_run

```{autodoc2-docstring} boardwalk.host.Host.ansible_run
```

````

````{py:method} is_locked() -> str | bool
:canonical: boardwalk.host.Host.is_locked

```{autodoc2-docstring} boardwalk.host.Host.is_locked
```

````

````{py:method} lock(become_password: str | None = None, check: bool = False, stomp_existing_locks: bool = False)
:canonical: boardwalk.host.Host.lock

```{autodoc2-docstring} boardwalk.host.Host.lock
```

````

````{py:method} release(become_password: str | None = None, check: bool = False) -> None
:canonical: boardwalk.host.Host.release

```{autodoc2-docstring} boardwalk.host.Host.release
```

````

````{py:method} gather_facts() -> dict[str, typing.Any]
:canonical: boardwalk.host.Host.gather_facts

```{autodoc2-docstring} boardwalk.host.Host.gather_facts
```

````

````{py:method} get_remote_state() -> boardwalk.state.RemoteStateModel
:canonical: boardwalk.host.Host.get_remote_state

```{autodoc2-docstring} boardwalk.host.Host.get_remote_state
```

````

````{py:method} set_remote_state(remote_state_obj: boardwalk.state.RemoteStateModel, become_password: str | None = None, check: bool = False)
:canonical: boardwalk.host.Host.set_remote_state

```{autodoc2-docstring} boardwalk.host.Host.set_remote_state
```

````

`````

````{py:exception} RemoteHostLocked(message: str)
:canonical: boardwalk.host.RemoteHostLocked

Bases: {py:obj}`boardwalk.app_exceptions.BoardwalkException`

```{autodoc2-docstring} boardwalk.host.RemoteHostLocked
```

```{rubric} Initialization
```

```{autodoc2-docstring} boardwalk.host.RemoteHostLocked.__init__
```

````
