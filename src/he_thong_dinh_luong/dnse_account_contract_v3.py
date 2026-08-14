"""Normalize DNSE OpenAPI account metadata without exposing account numbers."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "y", "co", "có"}


def _mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(by_alias=True)
        return dumped if isinstance(dumped, Mapping) else None
    as_dict = getattr(value, "dict", None)
    if callable(as_dict):
        dumped = as_dict(by_alias=True)
        return dumped if isinstance(dumped, Mapping) else None
    return None


def account_options(accounts: Sequence[object]) -> list[dict[str, object]]:
    """Return stable account metadata from official DNSE fields.

    Official responses use ``id``, ``accountTypeName`` and
    ``derivativeAccount``. Legacy aliases remain accepted for compatibility.
    """
    output: list[dict[str, object]] = []
    for item in accounts:
        account = _mapping(item)
        if account is None:
            continue
        account_no = ""
        for key in ("id", "accountNo", "account_no", "accountId"):
            value = str(account.get(key) or "").strip()
            if value:
                account_no = value
                break
        if not account_no:
            continue
        account_type = str(
            account.get("accountTypeName")
            or account.get("accountType")
            or account.get("type")
            or "UNKNOWN"
        ).strip()
        derivative = _bool(account.get("derivativeAccount")) or "DERIV" in account_type.upper()
        masked = (
            "*" * len(account_no)
            if len(account_no) <= 4
            else "*" * max(4, len(account_no) - 4) + account_no[-4:]
        )
        output.append({
            "account_no": account_no,
            "masked_account": masked,
            "account_type": account_type,
            "is_derivative": derivative,
            "display_label": f"{masked} · {account_type}",
        })
    return sorted(
        output,
        key=lambda item: (bool(item["is_derivative"]), str(item["account_no"])),
    )


def select_stock_account(
    accounts: Sequence[object],
    requested: str | None = None,
) -> dict[str, object]:
    options = account_options(accounts)
    if not options:
        raise ValueError("DNSE_ACCOUNTS_EMPTY")
    if requested:
        selected = next(
            (item for item in options if item["account_no"] == requested),
            None,
        )
        if selected is None:
            raise ValueError("DNSE_ACCOUNT_NOT_FOUND")
        if bool(selected["is_derivative"]):
            raise ValueError("DNSE_DERIVATIVE_ACCOUNT_NOT_SUPPORTED")
        return selected
    stock = [item for item in options if not bool(item["is_derivative"])]
    if not stock:
        raise ValueError("DNSE_STOCK_ACCOUNT_NOT_FOUND")
    return stock[0]


__all__ = ["account_options", "select_stock_account"]
