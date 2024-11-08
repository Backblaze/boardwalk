# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import subprocess
from datetime import UTC, datetime
from importlib.metadata import version as lib_version

# -- Helper functions -----------------------------------------------------


def get_git_revision_hash() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("ascii").strip()


def get_git_revision_short_hash() -> str:
    return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode("ascii").strip()


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Boardwalk"
copyright = f"{datetime.now(tz=UTC).year}, Backblaze"
author = "Backblaze"
VERSION: str = lib_version("boardwalk")
release = f"v{VERSION}"
version = VERSION


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.intersphinx",
    "sphinx.ext.doctest",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "autodoc2",
    "myst_parser",
    "sphinx_copybutton",
]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

nitpicky = True
nitpick_ignore = [
    # I think these are just by virtue of the fact we have these behind an `if TYPE_CHECKING:` line? Need to (eventually) figure these out.
    ("py:class", "boardwalk.ansible.AnsibleFacts"),
    ("py:class", "boardwalk.ansible.AnsibleTasksType"),
    ("py:class", "boardwalk.ansible.InventoryData"),
    ("py:class", "boardwalk.ansible.InventoryHostVars"),
    ("py:class", "boardwalk.ansible.HostVarsType"),
]
nitpick_ignore_regex = [
    # slack_sdk and slack_bolt don't use Sphinx
    ("py:class", "slack_bolt.*"),
    ("py:class", "slack_sdk.*"),
    # Neither does pydantic
    ("py:class", "pydantic.*"),
    ("py:obj", "pydantic.*"),
    # TODO: Pretty sure we need to update some type references, here; ignoring these for now
    ("py:class", "ansible_runner.*"),
]

suppress_warnings = [
    # Can Sphinx have a more granular suppression than just ignore _everything_?
    "image.not_readable",
]

templates_path = ["_templates"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "tornado": ("https://www.tornadoweb.org/en/stable/", None),
    "click": ("https://click.palletsprojects.com/en/stable/", None),
    "ansible_runner": ("https://ansible.readthedocs.io/projects/runner/en/latest/", None),
}

# -- sphinx-autodoc2 configuration ---------------------------------------------------
# https://sphinx-autodoc2.readthedocs.io/en/stable/config.html

autodoc2_index_template = """Auto-generated API
==================

This section contains auto-generated API reference documentation [#f1]_.

.. toctree::
   :titlesonly:
{% for package in top_level %}
   {{ package }}
{%- endfor %}

.. [#f1] Created with `sphinx-autodoc2 <https://github.com/chrisjsewell/sphinx-autodoc2>`_

"""  # The blank line above lets us avoid a blank line at the end of the generated file.

autodoc2_packages = [
    {"path": "../../src/boardwalk", "module": "boardwalk"},
    {"path": "../../src/boardwalkd", "module": "boardwalkd"},
]

autodoc2_render_plugin = "myst"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_book_theme"
html_extra_path = [
    "_img/",
]
html_static_path = ["_static"]
html_logo = "_img/src/boardwalkd/static/boardwalk_icon.jpg"
# html_favicon = "_static/logo-square.svg"
html_title = f"Boardwalk v{VERSION} ({get_git_revision_short_hash()})"
html_theme_options = {
    "extra_footer": f"""
    <div>Documentation generated with commit <span onclick="navigator.clipboard.writeText('{get_git_revision_hash()}')" title="{get_git_revision_hash()}">{get_git_revision_short_hash()}</span></div>
    """,
    "home_page_in_toc": True,
    "logo": {
        "alt_text": "Boardwalk documentation - Home",
        "text": f"Boardwalk, a linear Ansible workflow engine <br /><sub>v{VERSION}</sub>",
    },
    "repository_branch": "main",
    "repository_url": "https://github.com/Backblaze/boardwalk/",
    "path_to_docs": "docs",
    "use_edit_page_button": True,
    "use_issues_button": True,
    "use_repository_button": True,
    "use_source_button": True,
}
html_last_updated_fmt = ""

# -- Options for MyST Configuration -------------------------------------------------
# https://myst-parser.readthedocs.io/en/latest/syntax/optional.html
# myst_gfm_only = True
myst_enable_extensions = [
    "amsmath",
    "attrs_inline",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]
