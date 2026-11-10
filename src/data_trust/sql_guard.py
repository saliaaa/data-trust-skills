"""Allow one read-only SELECT per user statement.

The guard is a keyword filter. It is not a database privilege. Point the
helpers at a warehouse role that can only read.
"""

from __future__ import annotations

import re

from data_trust.errors import DataTrustError

_BANNED = re.compile(
    r"\b(insert|update|delete|drop|alter|attach|detach|copy|export|import|"
    r"truncate|grant|revoke|pragma|call|create|install|load|checkpoint)\b",
    re.IGNORECASE,
)
_SELECT = re.compile(r"^(select|with)\b", re.IGNORECASE)


def strip_comments(sql: str) -> str:
    """Remove SQL comments while leaving string literals intact."""
    out: list[str] = []
    i = 0
    in_string = False
    while i < len(sql):
        if in_string and sql[i] == "'" and i + 1 < len(sql) and sql[i + 1] == "'":
            out.append("''")
            i += 2
            continue
        if sql[i] == "'":
            in_string = not in_string
            out.append(sql[i])
            i += 1
            continue
        if not in_string and sql.startswith("--", i):
            newline = sql.find("\n", i)
            if newline < 0:
                break
            out.append("\n")
            i = newline
            continue
        if not in_string and sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            if end < 0:
                raise DataTrustError("SQL has an unterminated block comment")
            out.append(" ")
            i = end + 2
            continue
        out.append(sql[i])
        i += 1
    return "".join(out)


def _split_statements(sql: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    in_string = False
    i = 0
    while i < len(sql):
        if in_string and sql[i] == "'" and i + 1 < len(sql) and sql[i + 1] == "'":
            buf.append("''")
            i += 2
            continue
        if sql[i] == "'":
            in_string = not in_string
            buf.append(sql[i])
            i += 1
            continue
        if sql[i] == ";" and not in_string:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(sql[i])
        i += 1
    if buf:
        parts.append("".join(buf))
    return [part.strip() for part in parts if part.strip()]


def _mask_strings(sql: str) -> str:
    return re.sub(r"'(?:''|[^'])*'", "''", sql)


def assert_single_select(sql: str) -> str:
    """Return the single SELECT/WITH statement, or raise."""
    statements = _split_statements(strip_comments(sql))
    if len(statements) != 1:
        raise DataTrustError("expected exactly one SQL statement")
    statement = statements[0]
    scanned = _mask_strings(statement)
    if _BANNED.search(scanned):
        raise DataTrustError("statement is not read-only; only a single SELECT is allowed")
    if not _SELECT.match(scanned.lstrip()):
        raise DataTrustError("statement must start with SELECT or WITH")
    return statement
