# syntax=docker/dockerfile:1

# Full process isolation for the agent: the container filesystem is the only
# thing the harness can touch, and the host is exposed solely through the
# workspace mount. build with `make sandbox-build`, run with `make sandbox`.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYAGENT_WORKSPACE=/workspace

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[web]"

RUN useradd --create-home --uid 1000 agent
WORKDIR /workspace
USER agent

CMD ["pyagent"]
