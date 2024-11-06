# Builds module artifacts
.PHONY: build
build: dist

.PHONY: container
container:
	podman build . --tag boardwalk:$$(poetry version --short)

# Cleans up temporary data that might get created during normal development
.PHONY: clean
clean:
	set -o pipefail

	@echo '[.] Removing built packages ...'
	rm -rf dist/

	@echo '[.] Cleaning __pycache__ directories ...'
	find . -type d -name '__pycache__' | xargs rm -rf

	@echo '[.] Cleaning .boardwalk and .boardwalkd directories ...'
	find . -type d -name '.boardwalk' -or -name '.boardwalkd' | xargs rm -rf

	@echo '[.] Cleaning pytest and ruff caches ...'
	find . -type d -name '.pytest_cache' -or -name '.ruff_cache' | xargs rm -rf

	@echo '[.] Removing podman images for localhost/boardwalk ...'
	podman image rm $$(podman images 'localhost/boardwalk' --quiet) || :

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

# Builds the Sphinx HTML documentation -- Shortcut for `cd docs && make html`
.PHONY: docs
docs: develop
	poetry install --with=docs --sync
	poetry run make --directory=./docs/ html

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

# Render all d2 diagrams in ./diagrams to PNG
.PHONY: render-d2
render-d2:
	for file in $$(find ./diagrams -type f -name '*.d2' -not -name '_*.d2'); \
	do \
		d2 $$file $${file%.*}.png; \
	done

# Runs all available tests
.PHONY: test
test: test-pytest test-ruff test-pyright test-semgrep

# Run pytest verbosely if we're running manually, but normally if we're in a CI environment.
.PHONY: test-pytest
test-pytest: develop
ifndef CI
	poetry run pytest  --verbose
else
	poetry run pytest
endif

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
