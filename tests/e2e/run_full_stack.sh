#!/usr/bin/env bash
# Boot every real service in simulated-payment mode and prove the user-visible
# commercial loop. No XRPL transaction is signed or submitted by this gate.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
export COMPOSE_ANSI=never
export COMPOSE_PROGRESS=plain

cleanup() {
  docker compose --project-directory "$repo_root" down
}
trap cleanup EXIT INT TERM

docker compose --project-directory "$repo_root" up --detach --wait
(
  cd "$repo_root/apps/web"
  corepack pnpm run verify:live -- "$@"
)
