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
