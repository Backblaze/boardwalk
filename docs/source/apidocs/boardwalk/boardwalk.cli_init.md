# {py:mod}`boardwalk.cli_init`

```{py:module} boardwalk.cli_init
```

```{autodoc2-docstring} boardwalk.cli_init
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`init <boardwalk.cli_init.init>`
  - ```{autodoc2-docstring} boardwalk.cli_init.init
    :summary:
    ```
* - {py:obj}`add_gathered_facts_to_state <boardwalk.cli_init.add_gathered_facts_to_state>`
  - ```{autodoc2-docstring} boardwalk.cli_init.add_gathered_facts_to_state
    :summary:
    ```
* - {py:obj}`handle_failed_init_hosts <boardwalk.cli_init.handle_failed_init_hosts>`
  - ```{autodoc2-docstring} boardwalk.cli_init.handle_failed_init_hosts
    :summary:
    ```
````

### API

````{py:function} init(ctx: click.Context, limit: str, retry: bool)
:canonical: boardwalk.cli_init.init

```{autodoc2-docstring} boardwalk.cli_init.init
```
````

````{py:function} add_gathered_facts_to_state(event: ansible_runner.RunnerEvent, ws: boardwalk.manifest.Workspace)
:canonical: boardwalk.cli_init.add_gathered_facts_to_state

```{autodoc2-docstring} boardwalk.cli_init.add_gathered_facts_to_state
```
````

````{py:function} handle_failed_init_hosts(event: ansible_runner.RunnerEvent, retry_file_path: pathlib.Path)
:canonical: boardwalk.cli_init.handle_failed_init_hosts

```{autodoc2-docstring} boardwalk.cli_init.handle_failed_init_hosts
```
````
