"""Check public Testnet account state without signing a transaction."""

from __future__ import annotations

import argparse
import json
import os

from surplusflow_payments import PaymentSettings
from surplusflow_payments.config import load_project_environment
from surplusflow_payments.readiness import TestnetReadinessChecker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the buyer wallet and provider accounts on XRPL Testnet. "
            "Only public addresses and balances are printed."
        )
    )
    parser.add_argument(
        "--provider-env",
        action="append",
        required=True,
        help=(
            "Name of an environment variable holding a provider XRPL address; "
            "repeat for each provider"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_project_environment()
    missing = [name for name in args.provider_env if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            "Missing provider address environment variables: " + ", ".join(missing)
        )

    providers = {
        name.lower(): os.environ[name]
        for name in args.provider_env
    }
    report = TestnetReadinessChecker(PaymentSettings()).check(providers)
    print(json.dumps(report.to_public_dict(), indent=2))
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
