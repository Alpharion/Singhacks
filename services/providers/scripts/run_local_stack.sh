#!/usr/bin/env bash
# Runs the marketplace plus all five provider simulators locally for manual
# testing or a demo, without Docker Compose (owned by Person 4, not yet
# built as of this script). Each service is `uv run uvicorn`, backgrounded,
# sharing one SQLite file at $SURPLUSFLOW_DB_PATH (default: repo_root/data).
#
# Usage: services/providers/scripts/run_local_stack.sh
# Stop:  Ctrl+C (the trap below kills every child process)

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../.." && pwd)"

if [ -f "$repo_root/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$repo_root/.env"
  set +a
fi

pids=()
cleanup() {
  echo "Stopping local stack..."
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

run_service() {
  local dir="$1"
  local port="$2"
  shift 2
  (
    cd "$repo_root/$dir"
    uv sync --extra dev --quiet
    env "$@" uv run uvicorn app.main:app --port "$port"
  ) &
  pids+=("$!")
}

run_service "services/marketplace" 8002
run_service "services/providers/sellers" 8011 SELLER_ID=seller_bakery_001 PORT=8011
run_service "services/providers/sellers" 8012 SELLER_ID=seller_hotel_001 PORT=8012
run_service "services/providers/sellers" 8013 SELLER_ID=seller_grill_001 PORT=8013
run_service "services/providers/delivery" 8021 PROVIDER_ID=courier_fast_001 PORT=8021
run_service "services/providers/delivery" 8022 PROVIDER_ID=courier_economy_001 PORT=8022

echo "Marketplace + 3 sellers + 2 couriers running. Press Ctrl+C to stop."
wait
