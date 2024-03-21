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

# Applys project's required code style
.PHONY: format
format:
	poetry run black .
	@# This is a workaround for https://github.com/facebook/usort/issues/216
	LIBCST_PARSER_TYPE=native poetry run usort format .

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
test: test-black test-pyright test-semgrep test-usort

# Test that code is formatted with black
.PHONY: test-black
test-black: develop
	poetry run black . --check

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

# Ensure imports are formatted in a uniform way
.PHONY: test-usort
test-usort: develop
	@# This is a workaround for https://github.com/facebook/usort/issues/216
	LIBCST_PARSER_TYPE=native poetry run usort check .
