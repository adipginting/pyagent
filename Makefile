PYTHON ?= .venv/bin/python
NPM ?= npm
IMAGE ?= pyagent
HOST_UID := $(shell id -u)
HOST_GID := $(shell id -g)
PASS_KEYS = -e OPENROUTER_API_KEY -e KIMI_API_KEY -e DEEPSEEK_API_KEY

.PHONY: install install-api install-web api web dev build test \
        sandbox-build sandbox sandbox-web

install: install-api install-web

install-api:
	$(PYTHON) -m pip install -e ".[dev,web]"

install-web:
	$(NPM) --prefix web install

## Backend only: http://127.0.0.1:8000
api:
	$(PYTHON) -m uvicorn pyagent.server:app --reload --host 127.0.0.1 --port 8000

## Frontend only: http://127.0.0.1:5173 (proxies /api to the backend)
web:
	$(NPM) --prefix web run dev

## Both at once (Ctrl+C stops both). Open http://127.0.0.1:5173
dev:
	@echo "FastAPI on :8000, Vite on :5173 — open http://127.0.0.1:5173"
	@trap 'kill 0' EXIT INT TERM; \
	$(PYTHON) -m uvicorn pyagent.server:app --host 127.0.0.1 --port 8000 & \
	$(NPM) --prefix web run dev & \
	wait

## Build the frontend into web/dist, then `make api` serves it at :8000
build:
	$(NPM) --prefix web run build

test:
	$(PYTHON) -m pytest

## Build the container image used for full process isolation
sandbox-build:
	docker build -t $(IMAGE) .

## Run one prompt inside the container. The host is exposed only via ./workspace.
##   make sandbox PROMPT="explain this repo"
sandbox: sandbox-build
	docker run --rm -it --user $(HOST_UID):$(HOST_GID) -e HOME=/tmp \
	  -v "$(CURDIR):/workspace" $(PASS_KEYS) \
	  $(IMAGE) pyagent "$(PROMPT)"

## Run the web API inside the container, published on :8000
sandbox-web: sandbox-build
	docker run --rm -it --user $(HOST_UID):$(HOST_GID) -e HOME=/tmp \
	  -p 8000:8000 -v "$(CURDIR):/workspace" $(PASS_KEYS) \
	  $(IMAGE) uvicorn pyagent.server:app --host 0.0.0.0 --port 8000
