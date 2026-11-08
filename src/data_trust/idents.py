"""Quote identifiers that the helpers interpolate into SQL."""

from __future__ import annotations

import re

from data_trust.errors import DataTrustError

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TIMEZONE = re.compile(r"^[A-Za-z0-9_+\-/]+$")


def quote_ident(name: str) -> str:
    if not isinstance(name, str) or not _IDENT.match(name):
        raise DataTrustError(f"unsupported identifier: {name!r}")
    return f'"{name}"'


def require_idents(names: list[str], label: str) -> list[str]:
    if not names:
        raise DataTrustError(f"{label} needs at least one column")
    for name in names:
        quote_ident(name)
    return list(names)


def require_timezone(name: str) -> str:
    if not isinstance(name, str) or not _TIMEZONE.match(name):
        raise DataTrustError(f"unsupported timezone name: {name!r}")
    return name
