# Contributing

## Bug Reports & Feature Requests

Bug reports and feature requests are really helpful. Head over to
[Issues](https://github.com/Backblaze/boardwalk/issues), and provide
plenty of detail and context.

## Development Guidelines

### Development Dependencies

In addition to the python version specified in the `pyproject.toml`, you will
need:

- `make`
- `pip3`
- `podman`
- `pyenv`

#### Makefile

The [Makefile](./Makefile) has some useful targets for typical development
operations, like formatting, building, and locally installing the module.

To install the module in editable mode run `make develop`. This will also
install extra development dependencies.
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
reliability, user and developer experience. Otherwise there is no specific
enforcement of test coverage.

### Versioning

The boardwalk pip module uses semantic versioning. Please make sure to update
the VERSION file along with any changes to the package.
