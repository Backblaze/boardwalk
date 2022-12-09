# Builds module artifacts
.PHONY: build
build: dist

.PHONY: container
container:
	podman build . --tag boardwalk:$(shell cat VERSION | tr -d '\n')

# Cleans up temporary data that might get created during normal devlopment
.PHONY: clean
clean:
	rm -r \
		build \
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
	python3 -m pip install --upgrade --editable .[develop]

.PHONY: develop-server
develop-server: develop
ifdef BOARDWALKD_SLACK_WEBHOOK_URL
	boardwalkd serve \
		--develop \
		--host-header-pattern="(localhost|127\.0\.0\.1)" \
		--port=8888 \
		--slack-webhook-url="$(BOARDWALKD_SLACK_WEBHOOK_URL)" \
		--url='http://localhost:8888'
else
	boardwalkd serve \
		--develop \
		--host-header-pattern="(localhost|127\.0\.0\.1)" \
		--port=8888 \
		--url='http://localhost:8888'
endif

dist: clean
	python3 -m pip install --upgrade build pip
	python3 -m build

# Applys project's required code style
.PHONY: format
format:
	black .
	@# This is a workaround for https://github.com/facebook/usort/issues/216
	LIBCST_PARSER_TYPE=native usort format .

# Installs modules to the local system
.PHONY: install
install:
	python3 -m pip install --upgrade .


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
	black . --check

# Perform type analysis
.PHONY: test-pyright
test-pyright: develop
	PYRIGHT_PYTHON_FORCE_VERSION=latest pyright

# Perform security static analysis
.PHONY: test-semgrep
test-semgrep: develop
	semgrep \
		--config test/semgrep-rules.yml \
		--config "p/r2c-security-audit" \
		--config "p/r2c-bug-scan" \
		--config "p/secrets" \
		--config "p/dockerfile"

# Ensure imports are formatted in a uniform way
.PHONY: test-usort
test-usort: develop
	@# This is a workaround for https://github.com/facebook/usort/issues/216
	LIBCST_PARSER_TYPE=native usort check .
