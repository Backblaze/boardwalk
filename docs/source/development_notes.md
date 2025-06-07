# Notes for Development

This page contains some notes, tips, tricks, etc., for aiding in the development
of Boardwalk. This is intended mostly as a place to record and document things
that assist in development, so other individuals don't need to rediscover the
same tricks. Readers are free to use -- or not -- any of the topics discussed
herein to make their development experience easier.

## GitHub Actions

It is possible, using the [`act`](https://github.com/nektos/act) application, to
run GitHub Actions workflows locally in a reasonable approximation of how the
workflows would execute were they run via the GitHub hosted runners. For
example, to do this on _macOS_, and without installing Docker Desktop[^1], the
following commands may be used to set up your environment using Colima[^2].
```bash
# Retrieve the latest brew update
brew update
# Install Colima, and optionally set it to run at user login
brew install colima
brew services start colima
# Installl the Docker CLI, which is Apache License, v2.0.
brew install docker
# Install act
brew install act
```

Reference [`act`'s documentation](https://nektosact.com/) for full information
on how to use it, though a quick example for how to use it with Colima and
emulating a push, the following command may be used if executing _just_ the CI
suite is desired:
```bash
# Runs `act` against the ci_suite workflow, limited to the run_all_tests job,
# and sets the DOCKER_HOST environment variable to use Colima's sock file.
DOCKER_HOST="unix://$(realpath ~/.colima/default/docker.sock)" act --container-architecture linux/aarch64 -W '.github/workflows/ci_suite.yml' --job run_all_tests
```

Linux systems would be similar, however as the Docker Engine is natively
available for those systems, the steps for Colima can be omitted.


[^1]: Which _would_ provide Docker Engine.
[^2]: It may be reasonable to make the assumption that Boardwalk -- as an
    MIT-licensed non-commercial open source project -- falls under the clause
    within the [Docker Subscription Service
    Agreement](https://www.docker.com/legal/docker-subscription-service-agreement/#:~:text=4.2%20Specific%20License%20Limitations%20for%20Standalone%20use%20of%20Docker%20Desktop.%C2%A0)
    which [permits free
    use](https://docs.docker.com/subscription/desktop-license/) of Docker
    Desktop for such projects. However, in order to completely avoid such
    questions, this document is electing to use Colima and completely bypass
    Docker Desktop all together.
