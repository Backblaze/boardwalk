# Contributing

Contributions are subject to GitHub’s Terms of Service and You accept and
agree to the following for your present and future Contributions.

1. License Grant: You hereby grant Backblaze, and any recipients or users of
the Backblaze open source software (as may be modified by your Contribution),
a non-exclusive, perpetual, irrevocable, worldwide, royalty-free,
sublicensable license to use, reproduce, distribute, modify, create derivative
works of, publicly display, publicly perform, and otherwise use your
Contributions on any terms Backblaze or such users, deem appropriate.

3. Representations and Warranties: You represent and warrant that you have the
necessary rights to grant the rights described herein and that your
Contribution does not violate any third-party rights or applicable laws.
Except as stated in the previous sentence, the contribution is submitted
“AS IS” and the Contributor disclaims all warranties with regard to the
contribution.

3. Except for the license granted herein to Backblaze and to recipients and
users of the Backblaze open source software, You reserve all right, title, and
interest in and to your Contributions.

## Bug Reports & Feature Requests

Bug reports and feature requests are really helpful. Head over to
[Issues](https://github.com/Backblaze/boardwalk/issues), and provide
plenty of detail and context.

## Development Guidelines

### Fork the Repository

If you are planning to submit a pull request, please begin by [forking this repository in the GitHub UI](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo), then cloning your fork:

```shell
git clone git@github.com:<github-username>/boardwalk.git
cd boardwalk
```

Create a local branch in which to work on your contribution:

```shell
git switch -c my-cool-fix
```

When you're ready to submit, see the section below, [Submitting a Pull Request](#submitting-a-pull-request).

### Development Dependencies

In addition to the python version specified in the `pyproject.toml`, you will
need:

- [Poetry](https://python-poetry.org/docs/)
- `make`
- `pip3`
- `podman`
- `pyenv`

#### Makefile

The [Makefile](./Makefile) has some useful targets for typical development
operations, like formatting, building, and locally installing the module.

To install the module into a Poetry virtual environment in editable mode run
`make develop`. This will also install extra development dependencies.
To run the server in development mode, run `make develop-server`.

See the content of the Makefile for other useful targets.

### Code Style

#### Automated Formatting

- Run `make format` to format to this codebase's standard.

#### Not Automated Styling

- The last sentence in a code comments, logs, or error messages should not end
  in a period (`.`).
- Comments should be used generously.

### Testing

Automated tests are run with `make test`.

Automated tests should be developed for cases that clearly improve Boardwalk's
reliability, user and developer experience. Otherwise, there is no specific
enforcement of test coverage.

#### `ansible-lint`

Both
[Ansible](https://github.com/ansible/ansible/tree/devel?tab=GPL-3.0-1-ov-file#readme)
and
[`ansible-lint`](https://github.com/ansible/ansible-lint?tab=GPL-3.0-1-ov-file#readme)
are licensed under the GNU GPLv3. Consequently, to guard against the GPLv3.0
license attaching to Boardwalk, `ansible-lint` is not included as a development
dependency, even as an optional development dependency. Consequently, to execute
`make test-ansible-lint`, `ansible-lint` will need to be available (e.g., via a
`pipx` install, or similar).

### Versioning

The boardwalk pip module uses semantic versioning. Please make sure to update
the VERSION file along with any changes to the package.

### Logging
Most output should use a logger, with a few exceptions:
- Raw output streamed from Ansible. Playbook runs should look familiar to
  Ansible users. Ansible output that has been processed by Boardwalk should be
  emitted by a logger.
- Cases where the output of a command is intended to be consumed in a specific
  format, and the formatting features of a logger aren't useful. Examples
  include `boardwalk version` and `boardwalk workspace dump`.

### Submitting a Pull Request

When you're ready to submit your pull request, add and commit your files with a relevant message, including the issue number, if the PR fixes a specific issue:

```shell
git add <new and updated files>
git commit -m "Cool update. Fixes #123"
```

Now push your changes to a new branch to your GitHub repository:

```shell
git push --set-upstream origin my-cool-fix
```

The git response will display the pull request URL, or you can go to the branch page in your repo, `https://github.com/<github-username>/boardwalk/tree/my-cool-fix`, and click the 'Compare & pull request' button.

After you submit your pull request, a project maintainer will review it and respond within two weeks, likely much less unless we are flooded with contributions!
