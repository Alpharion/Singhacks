.PHONY: doctor-person4 setup-contracts setup-payments setup-all test-contracts test-payments test-e2e-offline test-person4 test-all run-payment-provider run-stack stop-stack test-integration

PNPM ?= corepack pnpm

doctor-person4:
	@command -v node
	@command -v pnpm
	@command -v python3.11
	@command -v uv
	@node --version
	@cd apps/web && $(PNPM) --version
	@python3.11 --version
	@uv --version

setup-contracts:
	cd packages/contracts && $(PNPM) install --frozen-lockfile

setup-payments:
	cd packages/payments && UV_CACHE_DIR=.uv-cache uv sync --locked --all-groups

setup-all: setup-contracts setup-payments
	cd services/marketplace && uv sync --locked --python 3.11 --extra dev
	cd services/providers/sellers && uv sync --locked --python 3.11 --extra dev
	cd services/providers/delivery && uv sync --locked --python 3.11 --extra dev
	cd services/buyer-agent && uv sync --locked --python 3.11 --extra dev
	cd apps/web && $(PNPM) install --frozen-lockfile
	cd apps/web && $(PNPM) exec playwright install chromium

test-contracts:
	cd packages/contracts && $(PNPM) test

test-payments: setup-payments
	cd packages/payments && .venv/bin/pytest

test-e2e-offline: setup-payments
	packages/payments/.venv/bin/pytest -q tests/e2e

test-person4: test-contracts test-payments test-e2e-offline

test-all: test-person4
	cd services/marketplace && .venv/bin/pytest
	cd services/providers/sellers && .venv/bin/pytest
	cd services/providers/delivery && .venv/bin/pytest
	cd services/buyer-agent && .venv/bin/pytest
	cd apps/web && $(PNPM) lint
	cd apps/web && $(PNPM) typecheck
	cd apps/web && $(PNPM) test
	cd apps/web && $(PNPM) build

run-payment-provider:
	cd packages/payments && .venv/bin/uvicorn examples.standalone_provider:app --port 8011

run-stack:
	BUYER_AGENT_PAYMENT_MODE=simulated docker compose up

stop-stack:
	docker compose down

test-integration:
	BUYER_AGENT_PAYMENT_MODE=simulated tests/e2e/run_full_stack.sh
