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
	python3 -m pip install --editable .

.PHONY: develop-server
develop-server:
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
	python3 -m pip install -U build pip
	python3 -m build

# Applys project's required code style
.PHONY: format
format:
	black .
	usort format .


# Installs modules to the local system
.PHONY: install
install:
	python3 -m pip install --upgrade .

# Runs all available tests
.PHONY: test
test: test-black test-pyright test-usort

# Test that code is formatted with black
.PHONY: test-black
test-black:
	black . --check

# Perform type analysis
.PHONY: test-pyright
test-pyright: develop
	pyright

# Ensure imports are formatted in a uniform way
.PHONY: test-usort
test-usort:
	usort check .
