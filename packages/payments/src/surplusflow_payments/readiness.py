from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo
from xrpl.utils import drops_to_xrp
from xrpl.wallet import Wallet

from .config import PaymentSettings
from .errors import PaymentExecutionError, PolicyViolation
from .models import validate_classic_address
from .wallet import load_buyer_wallet

WalletLoader = Callable[[], Wallet]


@dataclass(frozen=True)
class TestnetAccountReadiness:
    role: str
    address: str
    balance_drops: int

    @property
    def balance_xrp(self) -> str:
        value = format(drops_to_xrp(str(self.balance_drops)), "f")
        return value.rstrip("0").rstrip(".") if "." in value else value

    @property
    def funded(self) -> bool:
        return self.balance_drops > 0


@dataclass(frozen=True)
class TestnetReadinessReport:
    network: str
    rpc_url: str
    accounts: tuple[TestnetAccountReadiness, ...]

    @property
    def ready(self) -> bool:
        return all(account.funded for account in self.accounts)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "network": self.network,
            "ready": self.ready,
            "accounts": [
                {
                    "role": account.role,
                    "address": account.address,
                    "balanceDrops": str(account.balance_drops),
                    "balanceXrp": account.balance_xrp,
                    "funded": account.funded,
                }
                for account in self.accounts
            ],
        }


class TestnetReadinessChecker:
    """Read-only account checks; this class never signs or submits."""

    def __init__(
        self,
        settings: PaymentSettings,
        *,
        client: Any | None = None,
        wallet_loader: WalletLoader = load_buyer_wallet,
    ) -> None:
        self.settings = settings
        self.client = client or JsonRpcClient(settings.rpc_url)
        self.wallet_loader = wallet_loader

    def check(
        self,
        provider_addresses: Mapping[str, str],
    ) -> TestnetReadinessReport:
        if not provider_addresses:
            raise PolicyViolation("at least one provider address is required")
        if "buyer" in provider_addresses:
            raise PolicyViolation("provider roles must not override the buyer role")

        buyer = self.wallet_loader()
        accounts = {"buyer": buyer.classic_address, **provider_addresses}
        normalized: dict[str, str] = {}
        for role, address in accounts.items():
            if not role or not isinstance(address, str):
                raise PolicyViolation("account roles and addresses must be strings")
            try:
                normalized[role] = validate_classic_address(address)
            except ValueError:
                raise PolicyViolation(
                    f"{role} does not contain a valid XRPL classic address"
                ) from None

        if len(set(normalized.values())) != len(normalized):
            raise PolicyViolation(
                "buyer and provider roles must use separate XRPL accounts"
            )

        statuses = tuple(
            self._get_account(role, address)
            for role, address in normalized.items()
        )
        return TestnetReadinessReport(
            network=self.settings.xrpl_network,
            rpc_url=self.settings.rpc_url,
            accounts=statuses,
        )

    def _get_account(
        self,
        role: str,
        address: str,
    ) -> TestnetAccountReadiness:
        try:
            response = self.client.request(
                AccountInfo(account=address, ledger_index="validated")
            )
            account_data = response.result["account_data"]
            balance = int(account_data["Balance"])
        except Exception:
            raise PaymentExecutionError(
                f"could not read validated Testnet account state for {role}"
            ) from None
        return TestnetAccountReadiness(
            role=role,
            address=address,
            balance_drops=balance,
        )
