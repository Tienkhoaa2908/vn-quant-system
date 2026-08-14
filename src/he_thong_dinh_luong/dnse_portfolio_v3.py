"""DNSE portfolio sync v3 with official account-field selection."""
from __future__ import annotations

from pathlib import Path

from .dnse_account_contract_v3 import account_options, select_stock_account
from .dnse_portfolio import DnseReadOnlyClient
from .dnse_portfolio_v2 import sync_portfolio as sync_portfolio_v2
from .nguon_dnse import DnseRestSource


def list_masked_accounts(client: DnseReadOnlyClient) -> list[dict[str, object]]:
    return account_options(list(client.accounts()))


def sync_portfolio(
    *,
    data_root: Path,
    output_dir: Path,
    account_no: str | None = None,
    read_client: DnseReadOnlyClient | None = None,
    market_source: DnseRestSource | None = None,
    sync_local_planner: bool = True,
    include_market_context: bool = True,
) -> dict[str, object]:
    reader = read_client or DnseReadOnlyClient.from_env()
    close_reader = read_client is None
    try:
        selected = select_stock_account(list(reader.accounts()), account_no)
        result = sync_portfolio_v2(
            data_root=data_root,
            output_dir=output_dir,
            account_no=str(selected["account_no"]),
            read_client=reader,
            market_source=market_source,
            sync_local_planner=sync_local_planner,
            include_market_context=include_market_context,
        )
        return {
            **result,
            "account_type": selected["account_type"],
            "account_selection_contract": "dnse_official_account_fields_v3",
        }
    finally:
        if close_reader:
            reader.close()


__all__ = ["list_masked_accounts", "sync_portfolio"]
