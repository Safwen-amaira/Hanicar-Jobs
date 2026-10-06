#!/usr/bin/env bash
# Some hosts lack buildx/catatonit - fall back to classic builder.
set -euo pipefail
cd "$(dirname "$0")/.."
export DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-0}"
export COMPOSE_DOCKER_CLI_BUILD="${COMPOSE_DOCKER_CLI_BUILD:-0}"
docker compose "$@"
