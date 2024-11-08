-------
# Using GitHub flavored Markdown here, as we're including portions of the README.md, which is used on GitHub.
gfm_only: True
-------

```{include} ../../README.md
:end-before: <!-- README.md-Table-of-Contents_Before -->
```

```{toctree}
:includehidden:
:maxdepth: 1
:caption: General

overview.md
installation.md
```

```{toctree}
:includehidden:
:maxdepth: 1
:caption: Command-line applications

cli_helpdocs/index.md
```

```{toctree}
:includehidden:
:maxdepth: 1
:caption: API Reference

apidocs/index.rst
```
