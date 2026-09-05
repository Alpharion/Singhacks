.PHONY: doctor-person4 setup-contracts setup-payments test-contracts test-payments test-e2e-offline test-person4 run-payment-provider

doctor-person4:
	@command -v node
	@command -v pnpm
	@command -v python3.11
	@command -v uv
	@node --version
	@pnpm --version
	@python3.11 --version
	@uv --version

setup-contracts:
	pnpm --dir packages/contracts install --frozen-lockfile

setup-payments:
	cd packages/payments && UV_CACHE_DIR=.uv-cache uv sync --locked --all-groups

test-contracts:
	pnpm --dir packages/contracts test

test-payments: setup-payments
	cd packages/payments && .venv/bin/pytest

test-e2e-offline: setup-payments
	packages/payments/.venv/bin/pytest -q tests/e2e

test-person4: test-contracts test-payments test-e2e-offline

run-payment-provider:
	cd packages/payments && .venv/bin/uvicorn examples.standalone_provider:app --port 8011
