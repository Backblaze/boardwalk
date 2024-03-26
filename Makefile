# Builds module artifacts
.PHONY: build
build: dist

.PHONY: container
container:
	podman build . --tag boardwalk:$$(poetry version --short)

# Cleans up temporary data that might get created during normal development
.PHONY: clean
clean:
	rm -r \
		dist \
		src/*.egg-info \
		src/boardwalk/__pycache__ \
		src/boardwalkd/__pycache__ \
		.boardwalk \
		.boardwalkd \
		|| :
	podman image rm localhost/boardwalk || :

# Installs modules in editable mode
.PHONY: develop
develop:
	poetry install

.PHONY: develop-server
develop-server: develop
ifdef BOARDWALKD_SLACK_WEBHOOK_URL
	poetry run boardwalkd serve \
		--develop \
		--host-header-pattern="(localhost|127\.0\.0\.1)" \
		--port=8888 \
		--slack-webhook-url="$(BOARDWALKD_SLACK_WEBHOOK_URL)" \
		--url='http://localhost:8888'
else
	poetry run boardwalkd serve \
		--develop \
		--host-header-pattern="(localhost|127\.0\.0\.1)" \
		--port=8888 \
		--url='http://localhost:8888'
endif

dist: clean
	poetry build

# Applies fixable errors, and formats code
.PHONY: format
format:
	poetry run ruff check --fix
	poetry run ruff format

# Installs modules to the local system (via pipx; will need Ansible injected)
.PHONY: install
install: build
	pipx install --pip-args=--upgrade  ./dist/boardwalk-$(poetry version --short)-py3-none-any.whl
	echo "Boardwalk $(poetry version --short) installed via pipx; execute the following to inject Ansible"
	echo "  pipx inject boardwalk ansible"

# Installs/updates JS/CSS dependencies in boardwalkd
BOOTSTRAP_VERSION := 5.2.2
HTMX_VERSION := 1.8.2
.PHONY: install-web-deps
install-web-deps:
	curl "https://unpkg.com/htmx.org@$(HTMX_VERSION)/dist/htmx.min.js" -o src/boardwalkd/static/htmx.min.js
	curl "https://cdn.jsdelivr.net/npm/bootstrap@$(BOOTSTRAP_VERSION)/dist/css/bootstrap.min.css" -o src/boardwalkd/static/bootstrap.min.css
	curl "https://cdn.jsdelivr.net/npm/bootstrap@$(BOOTSTRAP_VERSION)/dist/js/bootstrap.bundle.min.js" -o src/boardwalkd/static/bootstrap.bundle.min.js

# Runs all available tests
.PHONY: test
test: test-ruff test-pyright test-semgrep

# Run all available Ruff checks
.PHONY: test-ruff
test-ruff: test-ruff-linters test-ruff-formatting

# Run all available Ruff linter checks
.PHONY: test-ruff-linters
test-ruff-linters: develop
	poetry run ruff check

# Run all available Ruff formatting checks
.PHONY: test-ruff-formatting
test-ruff-formatting: develop
	poetry run ruff format --check

# Perform type analysis
.PHONY: test-pyright
test-pyright: develop
	export PYRIGHT_PYTHON_FORCE_VERSION=latest
	poetry run pyright

# Perform security static analysis
.PHONY: test-semgrep
test-semgrep: develop
ifndef GITHUB_ACTIONS
	poetry run semgrep \
		--config test/semgrep-rules.yml \
		--config "p/r2c-security-audit" \
		--config "p/r2c-bug-scan" \
		--config "p/secrets" \
		--config "p/dockerfile"
else
	echo Semgrep will run in its own GitHub Actions job.
endif
