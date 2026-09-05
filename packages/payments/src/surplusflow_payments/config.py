from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_project_env_file() -> Path:
    candidates = [Path.cwd(), *Path.cwd().parents]
    candidates.extend(Path(__file__).resolve().parents)
    seen: set[Path] = set()
    for directory in candidates:
        if directory in seen:
            continue
        seen.add(directory)
        if (directory / ".env.example").is_file():
            return directory / ".env"
    return Path.cwd() / ".env"


PROJECT_ENV_FILE = find_project_env_file()


def load_project_environment() -> None:
    load_dotenv(PROJECT_ENV_FILE)


class PaymentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    xrpl_network: Literal["xrpl:1"] = "xrpl:1"
    xrpl_testnet_rpc_url: HttpUrl = HttpUrl(
        "https://s.altnet.rippletest.net:51234/"
    )
    xrpl_facilitator_url: HttpUrl = HttpUrl(
        "https://xrpl-facilitator-testnet.t54.ai"
    )
    payment_journal_path: Path = Path(".data/payments.sqlite3")
    max_order_spend_drops: int = Field(default=120_000_000, gt=0)
    max_transaction_spend_drops: int = Field(default=70_000_000, gt=0)
    xrpl_source_tag: int = Field(default=20_260_530, ge=0, le=4_294_967_295)

    @property
    def rpc_url(self) -> str:
        return str(self.xrpl_testnet_rpc_url)

    @property
    def facilitator_url(self) -> str:
        return str(self.xrpl_facilitator_url)
